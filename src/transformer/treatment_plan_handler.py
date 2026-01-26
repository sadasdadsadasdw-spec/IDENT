"""
Модуль для обработки планов лечения из IDENT

Функции:
- Преобразование сырых данных из БД в структурированный JSON
- Вычисление хеша для отслеживания изменений
- Компактное представление для хранения в Bitrix24
"""

import json
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional
from collections import defaultdict
from decimal import Decimal

from src.logger.custom_logger_v2 import get_logger

logger = get_logger(__name__)


class TreatmentPlanTransformer:
    """
    Трансформер для планов лечения

    Преобразует плоские данные из SQL запроса в иерархическую структуру JSON
    """

    # Маппинг статусов для компактности
    STATUS_MAP = {
        'Выполнено и оплачено': 'done_paid',
        'Выполнено': 'done',
        'Не выполнено': 'pending'
    }

    @staticmethod
    def transform_plan(raw_data: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Преобразует сырые данные плана лечения в структурированный JSON

        Args:
            raw_data: Список строк из SQL запроса (одна строка = одна услуга)

        Returns:
            Словарь с иерархической структурой плана или None если данных нет
        """
        if not raw_data:
            logger.warning("Нет данных для преобразования плана лечения")
            return None

        # Берем метаданные из первой строки (они одинаковые для всех строк)
        first_row = raw_data[0]

        plan_id = first_row.get('PlanID')
        if not plan_id:
            logger.error("Отсутствует PlanID в данных")
            return None

        # Метаданные плана
        plan = {
            'plan_id': plan_id,
            'name': first_row.get('PlanName', ''),
            'created': TreatmentPlanTransformer._format_datetime(first_row.get('CreatedAt')),
            'active': bool(first_row.get('IsActive', False)),
            'patient': first_row.get('PatientFullName', ''),
            'card_number': first_row.get('CardNumber', ''),
            'doctor': first_row.get('DoctorFullName', ''),
            'speciality': first_row.get('DoctorSpeciality', ''),
            'stages': []
        }

        # Группируем услуги по этапам и элементам
        stages_dict = defaultdict(lambda: {
            'id': None,
            'name': '',
            'order': 0,
            'elements': defaultdict(lambda: {
                'id': None,
                'name': '',
                'order': 0,
                'services': []
            })
        })

        total_amount = Decimal('0')
        status_counts = {'done_paid': 0, 'done': 0, 'pending': 0}

        for row in raw_data:
            # КРИТИЧНО: Пропускаем строки из других планов (если SQL вернул несколько планов)
            if row.get('PlanID') != plan_id:
                logger.warning(
                    f"Обнаружена строка из другого плана (PlanID={row.get('PlanID')}) "
                    f"при обработке плана {plan_id}, пропускаем"
                )
                continue

            stage_id = row.get('StageID')
            element_id = row.get('ElementID')
            service_id = row.get('ServiceID')

            # Пропускаем строки без услуги (могут быть пустые этапы)
            if not service_id:
                continue

            # Пропускаем строки без этапа
            if not stage_id:
                logger.warning(f"Услуга {service_id} без этапа (StageID=NULL) в плане {plan_id}")
                continue

            # Заполняем информацию об этапе
            if stage_id not in stages_dict:
                stages_dict[stage_id]['id'] = stage_id
                stages_dict[stage_id]['name'] = row.get('StageName', '')
                stages_dict[stage_id]['order'] = row.get('StageOrder', 0)

            # ✅ ИСПРАВЛЕНИЕ: Если элемента нет, создаем виртуальный элемент = этапу
            if not element_id:
                # Используем stage_id как element_id для виртуального элемента
                element_id = f"stage_{stage_id}"

            # Заполняем информацию об элементе
            if element_id not in stages_dict[stage_id]['elements']:
                stages_dict[stage_id]['elements'][element_id]['id'] = element_id if isinstance(element_id, int) else None
                stages_dict[stage_id]['elements'][element_id]['name'] = row.get('ElementName') or row.get('StageName', '')
                stages_dict[stage_id]['elements'][element_id]['order'] = row.get('ElementOrder', 0)

            # Добавляем услугу
            status_raw = row.get('Status', 'Не выполнено')
            status = TreatmentPlanTransformer.STATUS_MAP.get(status_raw, 'pending')

            price = TreatmentPlanTransformer._to_decimal(row.get('Price', 0))
            discount = TreatmentPlanTransformer._to_decimal(row.get('DiscountAmount', 0))
            total = TreatmentPlanTransformer._to_decimal(row.get('TotalAmount', 0))

            service = {
                'id': service_id,
                'name': row.get('ServiceName', ''),
                'category': row.get('ServiceCategory', ''),
                'folder': row.get('ServiceFolder', ''),
                'price': float(price),
                'discount': float(discount),
                'total': float(total),
                'status': status,
                'teeth': row.get('TeethMask', ''),
                'exec_date': TreatmentPlanTransformer._format_datetime(row.get('ExecutionDate')),
                'order_id': row.get('OrderID'),
                'reception_id': row.get('ReceptionID')
            }

            stages_dict[stage_id]['elements'][element_id]['services'].append(service)

            # Считаем статистику
            total_amount += total
            status_counts[status] = status_counts.get(status, 0) + 1

        # Преобразуем словари в списки и сортируем
        for stage_id, stage_data in sorted(stages_dict.items(), key=lambda x: x[1]['order']):
            elements_list = []
            for element_id, element_data in sorted(stage_data['elements'].items(),
                                                   key=lambda x: x[1]['order']):
                elements_list.append({
                    'id': element_data['id'],
                    'name': element_data['name'],
                    'order': element_data['order'],
                    'services': element_data['services']
                })

            plan['stages'].append({
                'id': stage_data['id'],
                'name': stage_data['name'],
                'order': stage_data['order'],
                'elements': elements_list
            })

        # Добавляем суммарную информацию
        total_services = sum(status_counts.values())
        plan['summary'] = {
            'total_services': total_services,
            'done_paid': status_counts['done_paid'],
            'done': status_counts['done'],
            'pending': status_counts['pending'],
            'total_amount': float(total_amount),
            'completion_percent': round((status_counts['done_paid'] + status_counts['done']) / total_services * 100, 1) if total_services > 0 else 0
        }

        # Логирование для пустых планов
        if total_services == 0:
            logger.info(
                f"⚠️ План лечения ID={plan_id} пустой (нет услуг). "
                f"Пациент: {first_row.get('PatientFullName')}, IsActive={plan['active']}"
            )

        return plan

    @staticmethod
    def _format_datetime(dt: Optional[datetime]) -> str:
        """Форматирует datetime в строку ISO формата"""
        if not dt:
            return ''
        if isinstance(dt, datetime):
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        return str(dt)

    @staticmethod
    def _to_decimal(value: Any) -> Decimal:
        """Безопасное преобразование в Decimal"""
        if value is None:
            return Decimal('0')
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except:
            return Decimal('0')

    @staticmethod
    def to_json_string(plan: Dict[str, Any], minify: bool = True) -> str:
        """
        Преобразует план в JSON строку

        Args:
            plan: Структура плана
            minify: Если True - компактный JSON без отступов

        Returns:
            JSON строка
        """
        if minify:
            return json.dumps(plan, ensure_ascii=False, separators=(',', ':'))
        else:
            return json.dumps(plan, ensure_ascii=False, indent=2)

    @staticmethod
    def from_json_string(json_str: str) -> Optional[Dict[str, Any]]:
        """
        Парсит JSON строку в структуру плана

        Args:
            json_str: JSON строка

        Returns:
            Словарь с планом или None при ошибке
        """
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON плана: {e}")
            return None

    @staticmethod
    def calculate_hash(plan: Dict[str, Any]) -> str:
        """
        Вычисляет MD5 хеш плана для отслеживания изменений

        Args:
            plan: Структура плана

        Returns:
            MD5 хеш в hex формате
        """
        # Используем minified JSON для хеша
        json_str = TreatmentPlanTransformer.to_json_string(plan, minify=True)
        return hashlib.md5(json_str.encode('utf-8')).hexdigest()

    @staticmethod
    def has_changed(plan1_hash: str, plan2_hash: str) -> bool:
        """
        Проверяет изменился ли план

        Args:
            plan1_hash: Хеш первого плана
            plan2_hash: Хеш второго плана

        Returns:
            True если планы отличаются
        """
        return plan1_hash != plan2_hash

    @staticmethod
    def get_plan_size(plan: Dict[str, Any]) -> int:
        """
        Вычисляет размер плана в байтах

        Args:
            plan: Структура плана

        Returns:
            Размер в байтах
        """
        json_str = TreatmentPlanTransformer.to_json_string(plan, minify=True)
        return len(json_str.encode('utf-8'))

    @staticmethod
    def validate_size(plan: Dict[str, Any], max_size_kb: int = 60) -> tuple[bool, int]:
        """
        Проверяет не превышает ли план допустимый размер

        Args:
            plan: Структура плана
            max_size_kb: Максимальный размер в KB

        Returns:
            Tuple (is_valid, size_kb)
        """
        size_bytes = TreatmentPlanTransformer.get_plan_size(plan)
        size_kb = size_bytes / 1024
        is_valid = size_kb <= max_size_kb

        return is_valid, round(size_kb, 2)


def get_treatment_plan_for_patient(
    db_connector,
    patient_full_name: str
) -> Optional[Dict[str, Any]]:
    """
    Получает активный план лечения пациента

    Args:
        db_connector: Экземпляр IdentConnector
        patient_full_name: ФИО пациента

    Returns:
        Структурированный план лечения или None
    """
    try:
        # Получаем сырые данные из БД
        raw_data = db_connector.get_treatment_plans_by_patient_name(patient_full_name)

        if not raw_data:
            logger.debug(f"План лечения не найден для пациента: {patient_full_name}")
            return None

        # Фильтруем только активные планы
        active_plans = {}
        for row in raw_data:
            plan_id = row.get('PlanID')
            is_active = row.get('IsActive')

            if plan_id not in active_plans:
                active_plans[plan_id] = {
                    'is_active': is_active,
                    'rows': []
                }

            active_plans[plan_id]['rows'].append(row)

        # Берем первый активный план (или последний созданный если нет активных)
        target_plan_rows = None
        for plan_id in sorted(active_plans.keys(), reverse=True):  # Сортируем по ID (новые первыми)
            if active_plans[plan_id]['is_active']:
                target_plan_rows = active_plans[plan_id]['rows']
                break

        # Если нет активных - берем последний созданный
        if not target_plan_rows and active_plans:
            latest_plan_id = max(active_plans.keys())
            target_plan_rows = active_plans[latest_plan_id]['rows']
            logger.warning(f"Нет активного плана для {patient_full_name}, используем план ID={latest_plan_id}")

        if not target_plan_rows:
            return None

        # Преобразуем в структурированный формат
        plan = TreatmentPlanTransformer.transform_plan(target_plan_rows)

        if plan:
            # Проверяем размер
            is_valid, size_kb = TreatmentPlanTransformer.validate_size(plan)
            logger.info(
                f"План лечения для {patient_full_name}: "
                f"ID={plan['plan_id']}, услуг={plan['summary']['total_services']}, "
                f"размер={size_kb}KB, valid={is_valid}"
            )

            if not is_valid:
                logger.warning(f"⚠️ План лечения превышает 60KB: {size_kb}KB")

        return plan

    except Exception as e:
        logger.error(f"Ошибка получения плана лечения для {patient_full_name}: {e}", exc_info=True)
        return None

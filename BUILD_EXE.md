# Building Standalone EXE

This guide explains how to build a standalone executable file for the IDENT → Bitrix24 integration.

## Why EXE?

**Advantages:**
- No Python required on target server
- All dependencies packaged inside
- Simpler deployment
- No encoding/console issues with Task Scheduler
- Works perfectly with SYSTEM user

**Disadvantages:**
- Larger file size (~80-150 MB)
- Slightly more RAM usage (+30-50 MB)
- Slower startup (+1-2 seconds)
- Need to rebuild after code changes

## Requirements

- Python 3.8+ installed (for building only)
- PyInstaller package

## Step 1: Install PyInstaller

```powershell
pip install pyinstaller
```

## Step 2: Build EXE

Run the automated build script:

```powershell
.\build_exe.ps1
```

This will:
1. Clean previous builds
2. Package all code and dependencies
3. Create `dist\ident_sync.exe`

**Build time:** 2-3 minutes

**Output:** `dist\ident_sync.exe` (~80-150 MB)

## Step 3: Test EXE

Before installing as service, test the EXE:

```powershell
.\dist\ident_sync.exe
```

Should see:
- Connection tests
- Synchronization starting
- No encoding errors

Press Ctrl+C to stop.

## Step 4: Install as Windows Task

```powershell
.\install_task.ps1
```

This will:
- Register task in Task Scheduler
- Set auto-start on boot
- Configure auto-restart on failure
- Start the task

## Step 5: Verify

```powershell
.\check_task.ps1
```

Should show:
- Task state: Running
- Python process: Found
- Logs: Active

## Manual Build (Advanced)

If you want to customize the build:

```powershell
pyinstaller `
    --name="ident_sync" `
    --onefile `
    --windowed `
    --add-data="config.ini;." `
    --hidden-import=pyodbc `
    --hidden-import=requests `
    --collect-all=pyodbc `
    --noconfirm `
    run_service.py
```

### PyInstaller Options Explained

- `--name="ident_sync"` - Output filename
- `--onefile` - Single EXE file (not folder)
- `--windowed` - No console window (runs in background)
- `--add-data="config.ini;."` - Include config.ini
- `--hidden-import=pyodbc` - Explicitly include pyodbc
- `--collect-all=pyodbc` - Include all pyodbc files
- `--noconfirm` - Overwrite without asking

## Updating the EXE

When you change code:

```powershell
# 1. Stop the task
Stop-ScheduledTask -TaskName "IdentBitrix24Integration" -TaskPath "\IDENT\"

# 2. Rebuild EXE
.\build_exe.ps1

# 3. Start the task
Start-ScheduledTask -TaskName "IdentBitrix24Integration" -TaskPath "\IDENT\"
```

## Deployment to Another Server

Copy these files to the target server:

```
ident_sync.exe          (from dist/)
config.ini              (configured for target environment)
install_task.ps1
uninstall_task.ps1
check_task.ps1
```

Then on target server:

```powershell
# No Python installation needed!
.\install_task.ps1
```

## Troubleshooting

### Build fails with "module not found"

Add the missing module to build_exe.ps1:

```powershell
--hidden-import=<module_name>
```

### EXE doesn't start

Check logs in `logs\service_runner.log`

Common issues:
- Missing config.ini
- Database connection issues
- Bitrix24 API issues

### Antivirus blocks EXE

This is a false positive. Packed Python EXEs often trigger antivirus.

Solutions:
1. Add to antivirus exceptions
2. Sign the EXE with code signing certificate (advanced)

### EXE is too large

This is normal. PyInstaller includes:
- Python interpreter (~15 MB)
- All libraries (~40 MB)
- Your code (~5 MB)
- pyodbc drivers (~20 MB)

Total: ~80-150 MB (acceptable for production)

## Performance

The EXE runs with identical performance to Python script:
- Same CPU usage
- Same network speed
- Only +30-50 MB extra RAM (for bundled Python)
- +1-2 sec startup time (one-time, not important)

All optimizations preserved:
- Stream processing
- Batch API
- Connection pooling
- LRU caching

## File Structure

After building:

```
Project/
├── dist/
│   └── ident_sync.exe          # Final executable
├── build/                       # Temporary build files (can delete)
├── ident_sync.spec             # PyInstaller spec file
├── run_service.py              # Source (not needed on target server)
├── main.py                     # Source (not needed on target server)
├── config.ini                  # Required on target server
├── build_exe.ps1               # Build script
├── install_task.ps1            # Install script
└── logs/                       # Created at runtime
```

## Next Steps

After successful build and installation:

1. Close RDP - task continues running
2. Monitor logs: `logs\integration_log_YYYY-MM-DD.txt`
3. Check status: `.\check_task.ps1`
4. View metrics in logs

The integration is now running 24/7 automatically!

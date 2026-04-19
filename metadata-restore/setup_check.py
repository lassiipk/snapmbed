"""
setup_check.py — Pre-flight environment checker.
Run this to verify your setup is correct before processing your photos.
Usage: python setup_check.py
"""

import sys
import subprocess
import shutil
from pathlib import Path


def _ok(msg):    print(f"  ✓  {msg}")
def _warn(msg):  print(f"  ⚠  {msg}")
def _fail(msg):  print(f"  ✗  {msg}")
def _info(msg):  print(f"     {msg}")


def check_python_version():
    print("\n[1] Python version")
    v = sys.version_info
    if v >= (3, 9):
        _ok(f"Python {v.major}.{v.minor}.{v.micro} — OK")
        return True
    else:
        _fail(f"Python {v.major}.{v.minor}.{v.micro} — too old. Need 3.9+")
        _info("Download: https://www.python.org/downloads/")
        return False


def check_exiftool():
    print("\n[2] exiftool")
    try:
        result = subprocess.run(
            ["exiftool", "-ver"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            _ok(f"exiftool {result.stdout.strip()} — found on PATH")
            return True
        else:
            _fail("exiftool found but returned an error")
            return False
    except FileNotFoundError:
        _fail("exiftool NOT found on PATH")
        _info("Download: https://exiftool.org")
        _info("Windows: rename exiftool(-k).exe → exiftool.exe, place in C:\\Windows\\")
        return False
    except subprocess.TimeoutExpired:
        _warn("exiftool check timed out — it may still work")
        return True


def check_tqdm():
    print("\n[3] tqdm (optional — CLI progress bar)")
    try:
        import tqdm
        _ok(f"tqdm {tqdm.__version__} installed")
    except ImportError:
        _warn("tqdm not installed — CLI will work but without a progress bar")
        _info("Install with: pip install tqdm")


def check_tkinter():
    print("\n[4] tkinter (GUI)")
    try:
        import tkinter
        _ok("tkinter available — GUI mode supported")
    except ImportError:
        _fail("tkinter not available — GUI mode won't work")
        _info("On Windows this should always be available with a standard Python install.")
        _info("Try reinstalling Python and ensuring tkinter is checked during install.")


def check_zoneinfo():
    print("\n[5] zoneinfo / tzdata (timezone support)")
    try:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    except ImportError:
        _warn("zoneinfo not available — named timezone support limited")
        _info("UTC and 'local' timezone will still work.")
        return
    try:
        ZoneInfo("UTC")
        _ok("zoneinfo + tzdata available — all timezones supported")
    except Exception:
        _warn("zoneinfo is present but tzdata is not installed")
        _info("Named timezones like Asia/Karachi will not work until you run:")
        _info("  pip install tzdata")
        _info("UTC and 'local' timezone will still work fine.")


def check_project_files():
    print("\n[6] Project files")
    base = Path(__file__).parent
    required = [
        "main.py",
        "core/scanner.py",
        "core/matcher.py",
        "core/metadata.py",
        "core/progress.py",
        "core/reporter.py",
        "core/engine.py",
        "interfaces/cli.py",
        "interfaces/gui.py",
        "config/defaults.json",
    ]
    all_ok = True
    for rel in required:
        p = base / rel
        if p.exists():
            _ok(f"{rel}")
        else:
            _fail(f"{rel} — MISSING")
            all_ok = False
    return all_ok


def check_write_test():
    """Quick sanity: create and delete a temp file to confirm write access."""
    print("\n[7] Write permission (temp file test)")
    import tempfile, os
    try:
        with tempfile.NamedTemporaryFile(dir=Path(__file__).parent,
                                         delete=False, suffix=".tmp") as f:
            f.write(b"test")
            tmp = f.name
        os.unlink(tmp)
        _ok("Write access confirmed")
        return True
    except OSError as e:
        _fail(f"Cannot write to tool folder: {e}")
        return False


def main():
    print()
    print("╔══════════════════════════════════════════════╗")
    print("║  Metadata Restore Tool — Pre-flight Check   ║")
    print("╚══════════════════════════════════════════════╝")

    results = {
        "python":    check_python_version(),
        "exiftool":  check_exiftool(),
        "files":     check_project_files(),
        "write":     check_write_test(),
    }
    check_tqdm()
    check_tkinter()
    check_zoneinfo()

    print()
    print("─" * 50)
    critical_ok = all(results.values())
    if critical_ok:
        print("  ✓  All critical checks passed. You're good to go!")
        print()
        print("  Run:  python main.py")
    else:
        print("  ✗  Some critical checks failed (see above).")
        print("     Fix the issues marked with ✗ before running the tool.")
    print("─" * 50)
    print()


if __name__ == "__main__":
    main()

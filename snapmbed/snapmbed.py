"""
SnapMbed — Entry Point
Run this file to launch the application.
  python snapmbed.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_dependencies():
    missing = []
    try:
        import customtkinter
    except ImportError:
        missing.append("customtkinter")
    try:
        import PIL
    except ImportError:
        missing.append("Pillow")
    try:
        import piexif
    except ImportError:
        missing.append("piexif")
    try:
        import mutagen
    except ImportError:
        missing.append("mutagen")

    if missing:
        print("=" * 55)
        print("  SnapMbed — Missing dependencies")
        print("=" * 55)
        print(f"\n  Install them with:\n")
        print(f"    pip install {' '.join(missing)}")
        print(f"\n  For HEIC support also run:")
        print(f"    pip install pillow-heif")
        print()
        sys.exit(1)

if __name__ == "__main__":
    check_dependencies()
    from gui.app import SnapMbedApp
    app = SnapMbedApp()
    app.mainloop()

"""
main.py — Entry point for the Google Takeout Metadata Restore Tool.

Usage:
  python main.py              → asks: CLI or GUI?
  python main.py --gui        → launches GUI directly
  python main.py --cli [...]  → launches CLI directly
  python main.py --help       → shows help
"""

import sys
import os

# Make sure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    args = sys.argv[1:]

    # ── Direct launch modes ──
    if "--gui" in args:
        _launch_gui()
        return

    if "--cli" in args:
        # Strip the --gui/--cli flag and pass the rest to CLI
        remaining = [a for a in args if a not in ("--gui", "--cli")]
        _launch_cli(remaining)
        return

    # ── Interactive mode selector ──
    _mode_selector()


def _mode_selector():
    """Ask user which interface to launch."""
    print()
    print("╔══════════════════════════════════════════════╗")
    print("║   Google Takeout — Metadata Restore Tool     ║")
    print("╠══════════════════════════════════════════════╣")
    print("║                                              ║")
    print("║   How would you like to run this tool?       ║")
    print("║                                              ║")
    print("║   [1]  Graphical Interface (GUI)             ║")
    print("║   [2]  Command Line Interface (CLI)          ║")
    print("║   [Q]  Quit                                  ║")
    print("║                                              ║")
    print("╚══════════════════════════════════════════════╝")
    print()

    while True:
        try:
            choice = input("  Your choice [1/2/Q]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nBye.")
            sys.exit(0)

        if choice in ("1", "gui", "g"):
            _launch_gui()
            return
        elif choice in ("2", "cli", "c"):
            _launch_cli([])
            return
        elif choice in ("q", "quit", "exit"):
            print("Bye.")
            sys.exit(0)
        else:
            print("  Please enter 1, 2, or Q.")


def _launch_gui():
    try:
        from interfaces.gui import run_gui
        run_gui()
    except ImportError as e:
        print(f"[ERROR] Could not launch GUI: {e}")
        print("Make sure tkinter is available (it ships with Python on Windows).")
        sys.exit(1)


def _launch_cli(argv):
    from interfaces.cli import run_cli
    run_cli(argv if argv else None)


if __name__ == "__main__":
    main()

"""
============================================================
  FORGE MASTER UI — Entry point
  Run : python main.py
============================================================
"""

import sys
import os

# Ensure the root folder is in the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    try:
        import customtkinter
    except ImportError:
        print("=" * 55)
        print("  ERROR : CustomTkinter is not installed.")
        print("  Install it with the following command :")
        print("    pip install customtkinter")
        print("=" * 55)
        sys.exit(1)

    from ui.app import run
    run()


if __name__ == "__main__":
    main()
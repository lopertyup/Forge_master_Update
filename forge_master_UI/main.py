"""
============================================================
  FORGE MASTER UI — Point d'entrée
  Lancer : python main.py
============================================================
"""

import sys
import os

# S'assurer que le dossier racine est dans le path Python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    try:
        import customtkinter
    except ImportError:
        print("=" * 55)
        print("  ERREUR : CustomTkinter n'est pas installé.")
        print("  Installez-le avec la commande :")
        print("    pip install customtkinter")
        print("=" * 55)
        sys.exit(1)

    from ui.app import run
    run()


if __name__ == "__main__":
    main()

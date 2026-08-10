"""Punto de entrada para PyInstaller.

Analysis no puede apuntar directo a gui/app.py: ese fichero usa imports
relativos (`from ..config import ...`) porque vive dentro del paquete
bib_expres.gui, y esos imports fallan si el fichero se ejecuta como script
__main__ en vez de importarse como submodulo del paquete. Este script sí es
un modulo top-level normal, así que `from bib_expres.gui.app import main` es
un import absoluto de verdad -- y dentro de app.py sus imports relativos
vuelven a tener sentido porque se importa como submodulo, no se ejecuta solo.
"""

from bib_expres.gui.app import main

if __name__ == "__main__":
    main()

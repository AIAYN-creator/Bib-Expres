"""Avisos del sistema para cuando una busqueda termina con la app en segundo plano.

- Windows: una notificacion nativa ("toast") con el nombre y el logo de bib_exprés,
  y el icono de la barra de tareas parpadeando hasta que vuelves a la ventana.
- macOS: `osascript` (display notification). Linux: `notify-send`.

Nada de esto es imprescindible: si el sistema no lo permite, falla en silencio y
la app sigue igual.

Seguridad: los textos (que incluyen titulos de papers venidos de una API externa)
NUNCA se interpolan en un script. En Windows el XML de la notificacion, ya escapado,
viaja en una variable de entorno que el script de PowerShell solo lee; en macOS y
Linux van como argumentos (argv), sin shell.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape

APP_ID = "BibExpres.Desktop"
APP_NAME = "bib_exprés"
WINDOW_TITLE = "bib-exprés"
MAX_TEXT = 180

# Lee el XML ya escapado de una variable de entorno: el script es fijo, los datos no
# se mezclan nunca con el codigo.
_PS_SCRIPT = (
    "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null;"
    "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] > $null;"
    "$x = New-Object Windows.Data.Xml.Dom.XmlDocument;"
    "$x.LoadXml($env:BIBEXPRES_TOAST_XML);"
    "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($env:BIBEXPRES_TOAST_APPID)"
    ".Show([Windows.UI.Notifications.ToastNotification]::new($x))"
)


def _clip(text: str) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= MAX_TEXT else text[: MAX_TEXT - 1] + "…"


def toast_xml(title: str, body: str, logo: Path | None = None) -> str:
    """XML de la notificacion de Windows, con todo el texto escapado. El logo va
    DENTRO del aviso (appLogoOverride): fiarse solo del icono registrado no basta,
    porque Windows lo guarda en cache o lo ignora y el aviso salia sin logo."""
    image = ""
    if logo is not None:
        image = f'<image placement="appLogoOverride" src="{escape(logo.as_uri(), {chr(34): "&quot;"})}"/>'
    return (
        '<toast><visual><binding template="ToastGeneric">'
        f"<text>{escape(_clip(title))}</text>"
        f"<text>{escape(_clip(body))}</text>"
        f"{image}"
        "</binding></visual></toast>"
    )


def logo_path() -> Path:
    return Path(__file__).parent / "static" / "logo.png"


def _register_windows_app_id() -> None:
    """Registra bib_exprés como origen de notificaciones para el usuario actual
    (HKCU, sin permisos de administrador), para que el aviso salga con su nombre y
    su logo en vez de como "Windows PowerShell". Es el registro estandar de una app
    de escritorio sin instalador; solo toca la clave de bib_exprés."""
    import winreg

    key_path = rf"Software\Classes\AppUserModelId\{APP_ID}"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
        logo = ensure_stable_logo()
        if logo is not None:
            winreg.SetValueEx(key, "IconUri", 0, winreg.REG_SZ, str(logo))


def ensure_stable_logo() -> Path | None:
    """Copia el logo a una ruta que no desaparece. En el .exe, static/ vive en una
    carpeta temporal que se borra al cerrar, y el aviso puede mostrarse despues."""
    import shutil

    logo = stable_logo_path()
    try:
        source = logo_path()
        if source.exists() and (not logo.exists() or logo.stat().st_size != source.stat().st_size):
            logo.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, logo)
    except OSError:
        pass
    return logo if logo.exists() else None


def stable_logo_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "bib_expres" / "logo.png"


def windows_command(title: str, body: str, logo: Path | None = None) -> tuple[list[str], dict[str, str]]:
    env = dict(os.environ, BIBEXPRES_TOAST_XML=toast_xml(title, body, logo), BIBEXPRES_TOAST_APPID=APP_ID)
    cmd = ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", _PS_SCRIPT]
    return cmd, env


def mac_command(title: str, body: str) -> list[str]:
    return [
        "osascript",
        "-e", "on run argv",
        "-e", "display notification (item 2 of argv) with title (item 1 of argv)",
        "-e", "end run",
        _clip(title), _clip(body),
    ]


def linux_command(title: str, body: str) -> list[str]:
    return ["notify-send", "--app-name", APP_NAME, _clip(title), _clip(body)]


def flash_taskbar(window_title: str = WINDOW_TITLE) -> bool:
    """Hace parpadear el icono de la ventana en la barra de tareas hasta que el
    usuario vuelve a ella (Windows)."""
    if sys.platform != "win32":
        return False

    class FLASHWINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("hwnd", ctypes.c_void_p), ("dwFlags", ctypes.c_uint),
                    ("uCount", ctypes.c_uint), ("dwTimeout", ctypes.c_uint)]

    user32 = ctypes.windll.user32
    user32.FindWindowW.restype = ctypes.c_void_p
    hwnd = user32.FindWindowW(None, window_title)
    if not hwnd:
        return False
    FLASHW_ALL, FLASHW_TIMERNOFG = 0x3, 0xC
    info = FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd, FLASHW_ALL | FLASHW_TIMERNOFG, 0, 0)
    return bool(user32.FlashWindowEx(ctypes.byref(info)))


def notify(title: str, body: str) -> bool:
    """Lanza el aviso sin esperar a que termine. Devuelve False si no se pudo."""
    try:
        if sys.platform == "win32":
            try:
                _register_windows_app_id()
            except OSError:
                pass  # sin registro sale igual, solo que sin nombre ni logo propios
            cmd, env = windows_command(title, body, ensure_stable_logo())
            subprocess.Popen(cmd, env=env, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            flash_taskbar()
        elif sys.platform == "darwin":
            subprocess.Popen(mac_command(title, body), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(linux_command(title, body), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except (OSError, ValueError):
        return False

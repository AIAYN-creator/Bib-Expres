# Instalación

> [English version](en/installation.md)

## Descargar el `.exe` (recomendado si no vas a usar la CLI)

**[Descarga `bib-expres-gui.exe` desde Releases](https://github.com/AIAYN-creator/Bib-Expres/releases/latest)** (~17 MB) y ejecútalo — no hace falta instalar Python ni nada más. Ese enlace apunta siempre a la última versión publicada.

Windows puede avisar la primera vez porque el `.exe` no está firmado ("Windows protegió tu PC" → "Más información" → "Ejecutar de todas formas") — es un aviso conocido, no significa que algo vaya mal.

El resto de esta página es para quien quiera la CLI, tocar el código, o construir el `.exe` en su propia máquina en vez de descargarlo.

## Requisitos

- Python 3.10 o superior.
- Un email de contacto para el `mailto` de OpenAlex/CrossRef (no hace falta registro, solo un email).
- Conexión a internet: las búsquedas consultan OpenAlex, CrossRef y, opcionalmente, Semantic Scholar.
- Opcional: una [API key gratuita de Semantic Scholar](https://www.semanticscholar.org/product/api) si vas a usar el modo de expansión "similares".

## Clonar e instalar en modo desarrollo

```bash
git clone https://github.com/AIAYN-creator/Bib-Expres.git
cd Bib-Expres
pip install -e ".[dev]"
```

Esto instala el paquete en modo editable (los cambios en `src/` se reflejan sin reinstalar) junto con las dependencias de desarrollo (`pytest`).

## Configurar variables de entorno

```bash
cp .env.example .env
```

Y rellena:

- `CONTACT_EMAIL` — tu email, usado como identificación de buena fe ante OpenAlex/CrossRef (mejora los límites de peticiones, no se publica en ningún sitio).
- `SEMANTIC_SCHOLAR_API_KEY` — opcional, solo si vas a usar el modo "similares".
- `LIBRARY_LINK_TEMPLATE` y `SUBSCRIBED_PUBLISHERS` — opcionales: el enlace de acceso remoto de tu biblioteca y las editoriales que cubre tu institución ([guía](acceso-institucional.md)). Lo normal es rellenarlos desde la GUI.
- `UI_LANGUAGE` (`es` / `en`) y `UI_THEME` (`system` / `light` / `dark`) — los guarda la GUI al cambiarlos; no hace falta tocarlos a mano.

Desde la GUI los valores se guardan entre comillas, así que un `#` dentro de un valor (p.ej. en el nombre de una editorial) no se pierde como si fuera un comentario.

**El `.env` real nunca se commitea** — ya está excluido en `.gitignore`.

### Cuota diaria de OpenAlex

OpenAlex da gratis unas **1.000 peticiones al día** (lo dice en las cabeceras de sus respuestas), y una búsqueda por defecto gasta unas 75: salen unas **13 búsquedas nuevas al día**. Las búsquedas repetidas salen de la caché local y no gastan. La GUI enseña en la cabecera cuántas quedan hoy y cuándo se reinicia la cuota (medianoche UTC); la CLI lo imprime al terminar. Si se agota, bib_exprés avisa al momento y dice cuánto esperar.

Ojo: la API key se guarda **en texto plano** en ese `.env` (también cuando la configuras desde los Ajustes de la GUI, que escribe el `.env` en la carpeta desde la que abres la app). Es lo normal en una app de escritorio local, pero no compartas esa carpeta tal cual (un zip, una carpeta sincronizada con otra gente…) sin quitar antes el `.env`.

## Verificar la instalación

```bash
bib-expres --version
```

## Interfaz gráfica

Alternativa a la CLI para quien prefiera no usar terminal. Con el paquete instalado (paso anterior), se lanza igual que la CLI:

```bash
bib-expres-gui
```

Abre una ventana de escritorio (usa el motor web del propio sistema: WebView2 en Windows, que ya viene con Windows 10/11), en **español o inglés** (por defecto, el idioma del sistema; se cambia con ES/EN en la cabecera) y con **tema claro u oscuro** (por defecto, el del sistema). Los pasos se ven en la cabecera:

1. **Paper**: escribe un DOI, un enlace de arXiv o un título, o **suelta un PDF en la ventana** (o elígelo con el botón).
2. **Parámetros**: hasta dónde buscar (generaciones, número de artículos, referencias/citas/similares) y filtros del resultado (idioma, acceso abierto, *solo lo que puedo leer*, tipo de documento). Lo técnico (pesos del score, fanout, presupuesto de exploración) está en *Avanzado*.
3. **Búsqueda**: barra de progreso con papers explorados, candidatos vistos y el paper en curso; "última actividad hace X s" (a partir de 30 s avisa de que las APIs van lentas, pero la búsqueda sigue) y **Cancelar** quedándote con lo encontrado.
4. **Resultados**: cada artículo con su score, su estado de acceso, **Abrir** (versión libre o a través de tu biblioteca) y **"¿Por qué?"**, con el desglose del score. Se pueden ordenar por relevancia, autor o año, buscar dentro y ocultar lo que no puedes leer. El panel **Mi institución** sirve para marcar las editoriales que cubre la tuya ([guía](acceso-institucional.md)).
5. **Curación** (opcional): revisar cada candidato con su abstract y guardar o descartar con botones, flechas ← →, arrastrando la tarjeta, y **Z para deshacer**.
6. **Exportar**: BibTeX, RIS, CSL-JSON o Excel, con un resumen de cuántos van al fichero, y **Abrir carpeta** al terminar.

En la cabecera, **≈ búsquedas que quedan hoy** según la cuota de OpenAlex (ver arriba). En **Ajustes**: idioma, tema, el enlace de tu biblioteca (con un botón para probarlo), el email de contacto y la API key de Semantic Scholar, sin tocar el `.env` a mano.

Probada en la ventana nativa real, con el backend real y en los dos idiomas ([ejemplo-v3.md](ejemplo-v3.md)).

## Construir el `.exe` standalone tú mismo

Alternativa a descargarlo de Releases (arriba) — para verificar el build, modificar el código, o generarlo en una plataforma sin release publicado. Requiere haber clonado el repo:

```bash
pip install -r packaging/requirements-build.txt
pip install --no-deps -e .
pyinstaller packaging/bib-expres-gui.spec
```

`packaging/requirements-build.txt` fija las versiones exactas que van dentro del `.exe` (el `pyproject.toml` solo pone mínimos). Así el binario no depende de lo que tengas instalado ese día, y el CI pasa `pip-audit` sobre ese fichero cada semana para avisar si sale una vulnerabilidad nueva en algo que ya está publicado. Con `pip install -e ".[packaging]"` también funciona, pero empaqueta las versiones que haya en tu entorno.

Cada release publica el **SHA-256** del `.exe`. Para comprobar que lo que has descargado es exactamente lo que se subió, en PowerShell:

```powershell
Get-FileHash .\bib-expres-gui.exe -Algorithm SHA256
```

El resultado queda en `dist/bib-expres-gui.exe` (~17 MB) — un único fichero, sin dependencias externas salvo el WebView2 que Windows 10/11 ya trae de fábrica. Como no está firmado, Windows puede mostrar un aviso de SmartScreen la primera vez ("Más información" > "Ejecutar de todas formas"), y el antivirus puede bloquearlo brevemente justo al terminar de construirlo (pasa de verdad, no es solo teórico).

## Ejecutar los tests

```bash
pytest
```

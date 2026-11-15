# Installation

> [Versión en español](../instalacion.md)

## Download the `.exe` (recommended if you won't use the CLI)

**[Download `bib-expres-gui.exe` from Releases](https://github.com/AIAYN-creator/Bib-Expres/releases/latest)** (~17 MB) and run it. No Python or anything else to install. That link always points to the latest release.

Windows may warn you the first time because the `.exe` is not signed ("Windows protected your PC" → "More info" → "Run anyway"). It is a known warning and does not mean anything is wrong.

The rest of this page is for those who want the CLI, want to change the code, or want to build the `.exe` on their own machine instead of downloading it.

## Requirements

- Python 3.10 or later.
- A contact email for the OpenAlex/CrossRef `mailto` (no sign-up, just an email).
- An internet connection: searches query OpenAlex, CrossRef and, optionally, Semantic Scholar.
- Optional: a [free Semantic Scholar API key](https://www.semanticscholar.org/product/api) if you'll use the "similar" expansion mode.

## Clone and install in development mode

```bash
git clone https://github.com/AIAYN-creator/Bib-Expres.git
cd Bib-Expres
pip install -e ".[dev]"
```

This installs the package in editable mode (changes in `src/` apply without reinstalling), together with the development dependencies (`pytest`).

## Environment variables

```bash
cp .env.example .env
```

Then fill in:

- `CONTACT_EMAIL` — your email, used as a good-faith identification towards OpenAlex/CrossRef (it raises the request limits and is never published).
- `SEMANTIC_SCHOLAR_API_KEY` — optional, only for "similar" mode.
- `LIBRARY_LINK_TEMPLATE` and `SUBSCRIBED_PUBLISHERS` — optional: your library's remote-access link and the publishers your institution covers ([guide](institutional-access.md)). Usually filled in from the GUI.
- `UI_LANGUAGE` (`es` / `en`) and `UI_THEME` (`system` / `light` / `dark`) — saved by the GUI when you change them; no need to touch them by hand.

Values saved from the GUI are quoted, so a `#` inside a value (e.g. in a publisher's name) is not lost as if it were a comment.

**The real `.env` is never committed** — it is already in `.gitignore`.

### OpenAlex's daily quota

OpenAlex gives about **1,000 free requests a day** (it says so in its response headers), and a default search uses about 75: that is roughly **13 new searches a day**. Repeated searches come from the local cache and cost nothing. The GUI shows how many are left today and when the quota resets (midnight UTC) in its header; the CLI prints it when it finishes. If the quota runs out, bib_exprés says so right away and tells you how long to wait.

Note: the API key is stored **in plain text** in that `.env` (also when you set it from the GUI's Settings, which writes the `.env` in the folder you open the app from). That is normal for a local desktop app, but don't share that folder as is (a zip, a folder synced with other people…) without removing the `.env` first.

## Check the installation

```bash
bib-expres --version
```

## Desktop app

An alternative to the CLI for those who prefer not to use a terminal. With the package installed (previous step), launch it like the CLI:

```bash
bib-expres-gui
```

It opens a desktop window (using the system's own web engine: WebView2 on Windows, which ships with Windows 10/11), in **English or Spanish** (your system's language by default; switch with ES/EN in the header) and with a **light or dark theme** (your system's by default). The steps are shown in the header:

1. **Paper**: type a DOI, an arXiv link or a title, or **drop a PDF on the window** (or choose one with the button).
2. **Settings**: how far to search (generations, number of articles, references/citations/similar) and result filters (language, open access, *only what I can read*, document type). The technical part (score weights, fanout, exploration budget) is under *Advanced*.
3. **Search**: a progress bar with papers explored, candidates seen and the paper being explored; "last activity X s ago" (after 30 s it warns that the APIs are slow, but the search keeps going) and **Cancel**, keeping what was found so far.
4. **Results**: each article with its score, its access status, **Open** (free version or through your library) and **"Why?"**, with the score breakdown. Sort by relevance, author or year, search within the results and hide what you can't read. The **My institution** panel is where you tick the publishers your institution covers ([guide](institutional-access.md)).
5. **Curation** (optional): review each candidate with its abstract and keep or discard it with buttons, ← → arrow keys or by dragging the card, and **Z to undo**.
6. **Export**: BibTeX, RIS, CSL-JSON or Excel, with a summary of how many go to the file, and **Open folder** when done.

In the header: **≈ searches left today** according to OpenAlex's quota (see above). In **Settings**: language, theme, your library link (with a button to test it), the contact email and the Semantic Scholar API key, without editing the `.env` by hand.

Tested in the real native window, with the real backend and in both languages ([v3 example](../ejemplo-v3.md), in Spanish).

## Build the standalone `.exe` yourself

An alternative to downloading it from Releases (above) — to verify the build, change the code, or build it for a platform without a published release. It needs a clone of the repo:

```bash
pip install -r packaging/requirements-build.txt
pip install --no-deps -e .
pyinstaller packaging/bib-expres-gui.spec
```

`packaging/requirements-build.txt` pins the exact versions that go inside the `.exe` (`pyproject.toml` only sets minimums). That way the binary doesn't depend on whatever you have installed that day, and CI runs `pip-audit` on that file every week to warn if a new vulnerability appears in something already published. `pip install -e ".[packaging]"` also works, but it bundles whatever versions are in your environment.

Every release publishes the `.exe`'s **SHA-256**. To check that what you downloaded is exactly what was uploaded, in PowerShell:

```powershell
Get-FileHash .\bib-expres-gui.exe -Algorithm SHA256
```

The result goes to `dist/bib-expres-gui.exe` (~17 MB) — a single file, with no external dependencies other than the WebView2 that Windows 10/11 already ships with. Since it is not signed, Windows may show a SmartScreen warning the first time ("More info" > "Run anyway"), and antivirus software may briefly block it right after building (it really happens, not just in theory).

## Run the tests

```bash
pytest
```

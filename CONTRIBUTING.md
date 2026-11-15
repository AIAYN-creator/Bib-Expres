# Contributing to bib_exprés

Thanks for wanting to help! Issues, ideas, benchmark cases and pull requests are all welcome, in **English or Spanish** (*se aceptan contribuciones en español*).

Not sure where to start? The [roadmap](ROADMAP.md) lists ideas that nobody has picked up yet.

## Set up

```bash
git clone https://github.com/AIAYN-creator/Bib-Expres.git
cd Bib-Expres
pip install -e ".[dev]"
cp .env.example .env   # add your contact email; see docs/en/installation.md
pytest
```

Run the desktop app with `bib-expres-gui` and the CLI with `bib-expres --help`. Full guides: [installation](docs/en/installation.md) · [usage](docs/en/usage.md).

## Before you open a pull request

- **Tests pass**: `pytest`. CI runs them on Linux, macOS and Windows with Python 3.10 and 3.12.
- **New behaviour has a test**, especially anything that touches data coming from an API.
- **No new vulnerabilities**: `pip-audit`. CI also audits weekly.
- **One topic per PR**, with a short description of what changes for the user and how you checked it.

## How the project is built

- `src/bib_expres/` — the library and CLI: `expansion.py` (the algorithm), `relevance.py` (the score and its explanation), `sources/` (OpenAlex, CrossRef, Semantic Scholar, with caching, retries and rate-limit handling), `export.py`, `access.py`.
- `src/bib_expres/gui/` — the desktop app: `app.py` is the bridge that the page can call; `static/` holds plain HTML, CSS and JavaScript, with no framework and no build step.
- `benchmarks/` — the recall benchmark (below).
- `packaging/` — the `.exe` build, with pinned versions in `requirements-build.txt`.

## House rules

These come from real bugs and audits; please keep them:

- **The algorithm stays explainable.** A new signal is welcome if it can be explained to a user in one line and shown in the score breakdown. No language models or embeddings in the score.
- **Change the algorithm only with numbers.** Run the benchmark before and after, and put both tables in the PR.
- **Data from APIs is untrusted.** Escape it before putting it in a URL path (`urllib.parse.quote`). Paint it in the GUI with `textContent`, never `innerHTML`. Store it in Excel as text, never as a formula. Only open `http(s)` links.
- **The page can only call what it needs.** Every public method of `gui/app.Api` is callable from the page; internal helpers start with `_`. A test pins the exact list, so a new public method is a conscious decision.
- **Every GUI text exists in both languages.** Add it to `static/i18n.js` under `es` and `en`. A test fails if a key is missing in either.
- **Never hang in silence.** A slow or failing API must end in a clear message, not a frozen window.

## The benchmark

`benchmarks/run_benchmark.py` measures how much of a published review's bibliography bib_exprés finds from one paper the review cites (recall@N). To add a case from your field, add an entry with two DOIs (the starting paper and the review) to `benchmarks/cases.json`, then:

```bash
python benchmarks/run_benchmark.py --label my-change
```

Mind OpenAlex's free quota (about 1,000 requests a day): a full run with an empty cache uses about 250. Repeated runs mostly come from the local cache.

## Versions and release notes

- [Semantic versioning](https://semver.org/): **patch** (3.1.1) for fixes only, **minor** (3.2.0) for new features that don't change existing results, **major** (4.0.0) when the same input can give different results. Security fixes get at least a minor bump.
- There is no separate changelog: release notes live in the **version history** of `README.md` and `README.es.md`, written for users, not for developers. The [roadmap](ROADMAP.md) gives the overview.

## Reporting a security issue

Please don't describe a vulnerability in a public issue. Report it privately through GitHub instead: **[Report a vulnerability](https://github.com/AIAYN-creator/Bib-Expres/security/advisories/new)** (also under the repository's *Security* tab). Only the maintainer sees it.

## Licence

By contributing, you agree that your contribution is licensed under the [MIT licence](LICENSE).

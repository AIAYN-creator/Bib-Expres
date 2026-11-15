# Roadmap

**English** · [Español](ROADMAP.es.md)

Where bib_exprés has been, and where it might go. Each released version's full notes are in the [README's version history](README.md#version-history).

## Released

| Version | Theme | Highlights |
|---|---|---|
| **v1** | It works | DOI → snowballing (references + citations) → BibTeX, from the command line. 200 articles in ~22 s. |
| **v2.0.0** | No terminal needed | Desktop app and standalone `.exe`, Tinder-style curation, arXiv/title/PDF input, RIS and CSL-JSON, document-type and open-access filters. |
| v2.1.0 · v2.1.1 | Hardening | Escaped DOIs in API requests (security) · the app's own icon. |
| v2.2.0 | Hardening | Outdated libraries inside the `.exe` updated, pinned build, weekly vulnerability audit. |
| **v2.3.0** | Feels alive | Live progress bar with cancel, Excel export for literature reviews, bilingual README, no more silent hangs when OpenAlex rate-limits. |
| **v3.0.0** | Finds more, explains why | New algorithm (explore wide, pick at the end): recall@200 from 9.9 % to 24 % on real reviews, with every score explained. Institutional access, language filter, a redesigned app in English and Spanish, OpenAlex daily quota at a glance. |
| **v3.1.0** | Lets you walk away | A system notification when a search finishes while you're in another window, and moving freely between screens ("New search" after exporting, clickable steps and logo). |

## Next: ideas, not yet planned

- **Library holdings files (KBART)**: an exact "what my library covers" list per journal and year, if libraries make it available. Today institutional access is approximate (open access + the publishers you tick).
- **Re-check OpenAlex topics** as a replacement for the older concepts once their coverage improves. Today they lower recall in one of the three benchmark cases.
- **More benchmark cases** from other fields, to tune the defaults with more than three reviews. Adding one is two DOIs in `benchmarks/cases.json` ([how](CONTRIBUTING.md#the-benchmark)).
- **A gentler use of OpenAlex's free quota** (~13 new searches a day), e.g. reusing more of what earlier searches already fetched.

## Open questions

- Whether signing the `.exe` (code-signing certificate) is worth it so Windows stops warning.
- Whether the library/CLI part ships on PyPI or only from GitHub.
- Whether the CLI's own messages (still in Spanish) should follow the app and become bilingual.

Ideas and votes are welcome: open an issue, or see [CONTRIBUTING.md](CONTRIBUTING.md).

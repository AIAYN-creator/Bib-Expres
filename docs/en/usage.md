# Usage

> [Versión en español](../uso.md) · Validated with real cases (in Spanish): [v1](../ejemplo.md), [v2](../ejemplo-v2.md), [v3](../ejemplo-v3.md).

## Basic usage

```bash
bib-expres --doi 10.1000/example --output bibliography.bib
```

Given a starting paper, it writes a file with the bibliography built from it. There is also a [desktop app](installation.md#desktop-app) (`bib-expres-gui`), in English or Spanish, for those who prefer not to use a terminal.

> The CLI's own messages and `--help` are in Spanish; the parameters and file formats are the same in any language.

## The starting paper: `--doi` or `--input`

`--doi` is a direct shortcut when you already know it is a DOI. `--input` accepts the same plus an arXiv ID or URL, a path to a PDF or a free-text title, and detects which one it is. If a title is ambiguous (several similar candidates), the CLI asks which one is right; it never picks one on its own.

```bash
bib-expres --input "2301.12345" --output bibliography.bib                 # arXiv
bib-expres --input "./paper.pdf" --output bibliography.bib                # PDF
bib-expres --input "Attention Is All You Need" --output bibliography.bib  # title, with confirmation
```

**Known limit of arXiv IDs** (see [ejemplo-v2.md](../ejemplo-v2.md)): it works by resolving the DOI that arXiv assigns automatically. But if the paper was later published in a journal or conference under its own DOI (common for well-known ML papers; "Attention Is All You Need" is a real example), OpenAlex indexes that other DOI as the main one and the arXiv lookup fails with a message suggesting a title search. Searching by title doesn't have this problem.

## How it picks the articles (v3)

1. It **explores** the citation graph: from each expanded paper, the `--max-fanout` most relevant candidates are explored next. At most `--explore-budget` papers are expanded.
2. It **keeps everything it sees** and counts how many of the explored papers each candidate appears in (its **connections**).
3. It **picks at the end** the best ones by a score made of three signals, each one explainable:
   - **topical relevance**: topic, citations and recency, the classic formula;
   - **connections**: "linked to 5 papers in your search";
   - OpenAlex **keywords** shared with the starting paper.

Filters (type, open access, language) are applied when picking, not while exploring: a paper you don't want in the result can still lead to others you do want. `--explain` shows the breakdown of the top 20 (in Spanish):

```
- A Survey on Vision Transformer
    0.67 = relevancia 0.64 (tema 0.56, citas 0.93, recencia 0.87) · conectado con 8 papers de la búsqueda · comparte: transformer models
```

Measured against the bibliographies of three published reviews, this method finds on average **24 %** of what each review cites within its top 200 results (v2: 9.9 %). Details in [ejemplo-v3.md](../ejemplo-v3.md) and in `benchmarks/`.

## Parameters

| Parameter | What it controls | Default |
|---|---|---|
| `--doi` / `--input` | The starting paper (one of the two is required) | — |
| `--generations` | How many "hops" from the starting paper (1-5) | 2 |
| `--max-articles` | Articles in the result | 200 |
| `--max-fanout` | Candidates explored per paper | 20 |
| `--explore-budget` | Maximum papers to expand (bounds the time) | 30 |
| `--modes` | `references`, `citations`, `similar` (comma-separated) | `references,citations` |
| `--relevance-threshold` | Minimum final score (0-1) to enter the result | 0.15 |
| `--weight-topic` / `--weight-citations` / `--weight-recency` | Weights inside topical relevance | 1.0 / 0.2 / 0.1 |
| `--weight-coupling` | Weight of connections in the final score | 1.0 |
| `--weight-keywords` | Weight of shared keywords | 0.5 |
| `--explain` | Print the score breakdown of the top 20 (on `stderr`) | off |
| `--doc-types` | Allowed document types, comma-separated (e.g. `article,preprint`; OpenAlex vocabulary) | all |
| `--open-access-only` | Only open-access articles | off |
| `--language` | `any`, `same` (the starting paper's) or ISO codes such as `en,es` | `any` |
| `--library-link` | Your library's remote-access link ([guide](institutional-access.md)) | `LIBRARY_LINK_TEMPLATE` in `.env` |
| `--publishers` | Publishers your institution covers, separated by `;` | `SUBSCRIBED_PUBLISHERS` in `.env` |
| `--accessible-only` | Remove what you can't read (neither open nor from a ticked publisher) | off |
| `--strict-access` | With `--accessible-only`, also remove what can't be checked | off |
| `--output` | Output file | `bibliografia.bib` |
| `--format` | `bibtex`, `ris`, `csljson` or `xlsx` | from the `--output` extension, or `bibtex` |
| `--quiet` | No progress line and no quota summary | off |

The starting paper is never dropped, by relevance or by any filter: it always appears in the result. Articles with no known language are never dropped by the language filter.

`similar` mode works best with `SEMANTIC_SCHOLAR_API_KEY` set (see [installation](installation.md)). Without it, it runs under a much lower request limit, and the CLI warns you.

## Examples

A wider search:

```bash
bib-expres --doi 10.1000/example --generations 3 --max-articles 500 \
  --modes references,citations,similar --output wide-bibliography.bib
```

Only in Spanish, starting from a paper in Spanish:

```bash
bib-expres --doi 10.6018/analesps.30.3.199361 --language same --output review.xlsx
```

Only what you can read, with links through your library:

```bash
bib-expres --doi 10.1000/example --publishers "Elsevier BV;Springer Nature" \
  --accessible-only --library-link "https://proxy.your-uni.edu/login?url=" --output review.xlsx
```

## Output

BibTeX (`.bib`), RIS (`.ris`), CSL-JSON (`.json`) or Excel (`.xlsx`), from `--format` or the `--output` extension. The first three import directly into Zotero, Mendeley, JabRef or LaTeX.

### Excel, for literature reviews

One row per article, built for the first round of a review:

| Column | Content |
|---|---|
| Title | the article's title |
| Authors | all of them, separated by `; `, in the article's order |
| DOI | the DOI as a link to `doi.org` (or to its OpenAlex page if it has no DOI) |
| Topic | main topic according to OpenAlex |
| Keywords | keywords according to OpenAlex |
| Relevance | the final score (0–1), as a number you can sort |
| Why | the score breakdown in one line |
| Access | open, open (bronze), institution, no known access or unchecked ([guide](institutional-access.md)) |
| Access link | the free version, or the link through your library |
| Other notes | empty, for your notes |

Frozen header and filters: sorting by author or relevance, or filtering by topic, is one click. From the CLI the headers are in Spanish; from the GUI they follow the interface language.

The file goes to the `--output` path (or `bibliografia.bib` in the folder you ran the command from). The program doesn't open or move it.

## Progress and quota

While searching, the CLI writes one line on `stderr` that keeps rewriting itself:

```
explorados 5/21 -- 480 candidatos -- generacion 2 -- Effective Approaches to Attention-based Neu
```

When it finishes, it prints how much **OpenAlex quota** is left today:

```
Cuota de OpenAlex hoy: 482/1000 peticiones (~6 busquedas) -- se reinicia en 23 h 28 min
```

OpenAlex gives about **1,000 free requests a day** and a default search uses about 75, so roughly **13 new searches a day**. Repeating a search you already ran costs nothing, because it comes from the local cache (one week). If the quota runs out, bib_exprés says so clearly and tells you how long to wait, instead of hanging. `--quiet` hides both the progress line and the quota line; `stdout` only carries the result.

In the GUI the same shows as a progress bar with Cancel and, in the header, *"≈ 6 of 13 searches left today"* ([details](installation.md#desktop-app)).

## Performance

A default search from *Attention Is All You Need* takes **~55 s with an empty cache** (74 requests to OpenAlex) and a couple of seconds if it is already cached. v3 is slower than v2 (~36 s) because it explores everything before picking; in exchange it finds about 2.4 times more relevant literature. The time depends mostly on how fast OpenAlex answers that day and on the size of the starting paper's citation graph. The first validation, of v1, is in [ejemplo.md](../ejemplo.md).

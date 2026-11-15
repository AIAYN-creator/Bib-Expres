# Access to papers: open, through your library, and "only what I can read"

> [Versión en español](../acceso-institucional.md)

bib_exprés can't know for sure what your institution has access to: that information lives in each library's systems, behind its login. What it does is combine three things that can be known:

1. **Whether the paper is open access**, according to OpenAlex, and the link to that free version.
2. **A link through your library**, so the paper opens as if you were on campus (you log in in your browser, as usual).
3. **Which publishers your institution covers**, ticked by you, to filter approximately.

bib_exprés **never sends any request through your library's proxy and never stores credentials**: it only builds links that open in your browser.

## Access status of each article

| Status | Meaning |
|---|---|
| **open** | There is a free version ("Open free version" link) |
| **open (bronze)** | Free on the publisher's site but without an open licence: it may stop being free |
| **institution** | Not open, but its publisher (or the parent publisher: *Cell Press* counts as *Elsevier*) is on your list |
| **no known access** | Not open, and its publisher is not on your list |
| **unchecked** | No data to tell (unknown publisher, or you haven't ticked any publishers yet) |

It shows in the results screen and in the **Access** and **Access link** columns of the Excel file.

## 1. Your library's link

In the GUI: **Settings → My library → Remote access link**. In the CLI: `--library-link`, or `LIBRARY_LINK_TEMPLATE` in the `.env`.

### How to find it

1. From home (outside your university's network), go to your library's website and open any article from a subscribed journal through its search or catalogue.
2. When you reach the article, look at the browser's URL:
   - **If it contains `login?url=`** (EZproxy, the most common one): copy everything up to and including `login?url=`. Example: `https://proxy.your-uni.edu/login?url=`
   - **If it contains `go.openathens.net/redirector/`** (OpenAthens): copy up to and including `?url=`. Example: `https://go.openathens.net/redirector/your-uni.edu?url=`
   - **If the article's URL has an odd domain** like `www-sciencedirect-com.proxy.your-uni.edu`, that is also EZproxy, in its domain-rewriting flavour. Look for "remote access" or "EZproxy" on your library's website: they almost always document the `login?url=` link.
3. If you find nothing, ask your library for **"the proxy prefix for remote access"**. It is a common question and they know the answer.

### Supported formats

- **Prefix** (EZproxy, OpenAthens): bib_exprés appends the paper's `https://doi.org/...` link.
- **With `{doi}` or `{url}`** (OpenURL resolvers, e.g. Alma/Primo or SFX): they are replaced by the DOI or by the doi.org link. Example: `https://resolver.your-uni.edu/openurl?rft_id=info:doi/{doi}`

Only `https://` links are accepted. The **"Test"** button opens a *Nature* article through your link: if you see the full article after logging in, it is set up correctly.

## 2. Your institution's publishers

In the results screen, the **"My institution"** panel (on the right, or above the list when the window is narrow) lists the publishers in your search, with how many articles each has. Tick the ones your institution covers and press **"Save"**: they are remembered for later searches (`SUBSCRIBED_PUBLISHERS` in the `.env`). In the CLI: `--publishers "Elsevier BV;Springer Nature"`.

If you don't know which ones your university covers, the library's website usually lists "subscribed resources", "databases" or "e-journals" by publisher.

**It is approximate**: a contract with a publisher doesn't always cover every journal or every year.

## 3. "Hide what I can't read"

- The **"Hide what I can't read"** toggle in the results bar (or *"Only what I can read"* already in the search settings), or `--accessible-only` in the CLI. It hides articles with **no known access**.
- **Unchecked** ones stay, because missing data is no reason to exclude something. To hide them too: the *"…and what can't be checked"* toggle, or `--strict-access`.
- The filter applies **to the results**, not during the search: not being able to read a paper doesn't make it less relevant, nor does it stop the search from reaching others you can read.
- The starting paper is never hidden.
- Hidden articles are not exported and don't show up in curation.

## Privacy

Your library link and your publisher list are stored in plain text in the `.env`. They are not secrets, but they reveal which institution you belong to. Be careful when sharing that folder.

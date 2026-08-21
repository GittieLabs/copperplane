# Documentation site

The user-facing docs for Hardware Agent Studio, built with
[Astro Starlight](https://starlight.astro.build/) and published to GitHub Pages
from `develop`.

```bash
cd docs/site
npm install
npm run dev      # http://localhost:4321/hardware-agent-studio
npm run build    # writes dist/
```

Search is [Pagefind](https://pagefind.app/), which Starlight builds into the
static output. There is no third-party search service, no account, and no
request leaves the reader's browser — which is the same promise the app itself
makes, and worth keeping that way.

Editing docs does **not** require a `CTX-*.md` context file: `docs` is in the
validator's `EXCLUDE_DIR_NAMES` as of `CTX-902.3`. A documentation fix is
genuinely the lowest-friction way to make a first contribution here.

Screenshots live in `public/images/` and are referenced as
`/hardware-agent-studio/images/<name>.png`. Files listed in
`public/images/NEEDED.md` are still outstanding.

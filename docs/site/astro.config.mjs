// @ts-check
import { defineConfig } from 'astro/config'
import starlight from '@astrojs/starlight'

// Published to GitHub Pages as a *project* site, so `base` must be the repo
// name. If this ever moves to a custom domain, set `site` to that domain and
// remove `base` entirely -- leaving a stale `base` in place silently breaks
// every internal link.
export default defineConfig({
  site: 'https://gittielabs.github.io',
  base: '/copperplane',
  integrations: [
    starlight({
      title: 'Copperplane',
      // SPEC-338 put the mark in the app; this is the same mark on the site,
      // from the same generated files. Starlight swaps the two variants by
      // theme itself, which is the one place a light/dark pair is worth
      // carrying -- unlike the screenshots, where mixing themes just looks
      // careless. `replacesTitle: false` keeps the wordmark as text, so the
      // site title stays selectable and searchable.
      logo: {
        light: './src/assets/copperplane-mark.svg',
        dark: './src/assets/copperplane-mark-on-dark.svg',
        replacesTitle: false,
      },
      description:
        'A co-pilot for your first real circuit board. It reads your KiCad project, explains what the checks are telling you, and sizes a case that fits.',
      // The card a shared link previews with: the lockup and the cold open's
      // finished PCB, drawn by docs/video/studio/card.html so it matches the video.
      head: [
        { tag: 'meta', attrs: { property: 'og:image', content: 'https://gittielabs.github.io/copperplane/og-card.png' } },
        { tag: 'meta', attrs: { property: 'og:image:width', content: '1200' } },
        { tag: 'meta', attrs: { property: 'og:image:height', content: '630' } },
        { tag: 'meta', attrs: { property: 'og:image:alt', content: 'Copperplane: a co-pilot for your first real circuit board' } },
        { tag: 'meta', attrs: { name: 'twitter:card', content: 'summary_large_image' } },
        { tag: 'meta', attrs: { name: 'twitter:image', content: 'https://gittielabs.github.io/copperplane/og-card.png' } },
      ],
      social: [
        {
          icon: 'github',
          label: 'GitHub',
          href: 'https://github.com/GittieLabs/copperplane',
        },
      ],
      editLink: {
        baseUrl:
          'https://github.com/GittieLabs/copperplane/edit/develop/docs/site/',
      },
      lastUpdated: true,
      customCss: ['./src/styles/custom.css'],
      sidebar: [
        {
          label: 'Start here',
          items: [
            { label: 'Watch it', slug: 'watch' },
            { label: 'Why this exists', slug: 'why' },
            { label: 'What it is, and what it is not', slug: 'what-it-is' },
            { label: 'Install', slug: 'install' },
            { label: 'First run', slug: 'first-run' },
          ],
        },
        {
          label: 'Tutorials',
          items: [{ autogenerate: { directory: 'tutorials' } }],
        },
        {
          label: 'Guides',
          items: [{ autogenerate: { directory: 'guides' } }],
        },
        {
          label: 'Reference',
          items: [
            { label: 'Privacy and your data', slug: 'privacy' },
            { label: 'Built on KiCad and FreeCAD', slug: 'built-on' },
            { label: 'Attribution and licences', slug: 'attribution' },
          ],
        },
        {
          label: 'Contributing',
          items: [
            { label: 'Contribute', slug: 'contribute' },
            { label: 'How this codebase is written', slug: 'how-this-is-built' },
          ],
        },
      ],
    }),
  ],
})

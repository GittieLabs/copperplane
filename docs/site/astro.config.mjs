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
      description:
        'A local-first desktop assistant that bridges KiCad and FreeCAD. It reads the datasheet and shows you the page it got that from.',
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
            { label: 'Why this exists', slug: 'why' },
            { label: 'What it is, and what it is not', slug: 'what-it-is' },
            { label: 'Install', slug: 'install' },
            { label: 'First run', slug: 'first-run' },
          ],
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

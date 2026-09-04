/** SPEC-338: the Copperplane mark, correct in every theme.
 *
 *  Two files rather than one inlined SVG on purpose. `brand/svg/mark.svg`
 *  and `mark-on-dark.svg` are byte-identical except for the stroke colour
 *  (`#10743F` and `#4FC17E`, the same pair as `--color-brand`), so inlining
 *  the path and colouring it with `currentColor` would work — and would copy
 *  the mark's geometry into a `.tsx` file, where regenerating the brand kit
 *  could not reach it. `brand/README.md` is explicit that these assets are
 *  generated, never hand-drawn. Copies in `public/` stay verbatim, and
 *  `tests/brandAssets.test.ts` fails if they drift from the kit.
 *
 *  Theme selection is CSS, not JavaScript: the app's theme can change from
 *  the OS without a re-render, and a `useState` mirror of
 *  `prefers-color-scheme` would be a second source of truth for something
 *  `index.css` already tracks in three blocks.
 *
 *  `aria-hidden` because on both screens that use it the mark sits directly
 *  beside an `<h1>` reading "Copperplane". A screen reader announcing the
 *  product name twice is worse than not announcing the logo at all. */
export function BrandMark({ size = 44 }: { size?: number }) {
  return (
    <span className="brand-mark" style={{ width: size, height: size }} aria-hidden="true">
      <img
        src="/brand-mark.svg"
        alt=""
        width={size}
        height={size}
        className="brand-mark-light"
      />
      <img
        src="/brand-mark-on-dark.svg"
        alt=""
        width={size}
        height={size}
        className="brand-mark-dark"
      />
    </span>
  )
}

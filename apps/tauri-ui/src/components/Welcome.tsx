import { BrandMark } from './BrandMark'

/** SPEC-336 step 1-3: the first screen, and the two paths off it.
 *
 *  Managed is *shown and disabled*. `SPEC-320` and `SPEC-404` are both still
 *  Draft and the backing service does not exist. `SPEC-305`'s
 *  "visible-but-empty beats hidden" argues for showing it; §3 adds the
 *  condition that it "must say *why* it is disabled and roughly when, or it
 *  reads as broken rather than forthcoming."
 *
 *  Skipping is available from here, not only from inside the guided steps —
 *  the maintainer's reason is worth keeping in view: *"A user may also be
 *  unsure about providing an api key and really want to see more before
 *  deciding."* */
export function Welcome({
  onChooseGuided,
  onChooseManual,
  onSkip,
}: {
  onChooseGuided: () => void
  onChooseManual: () => void
  onSkip: () => void
}) {
  return (
    <div className="flex h-full flex-col items-start justify-center gap-6 p-10">
      <div className="flex flex-col gap-2">
        <BrandMark />
        <h1 className="text-2xl font-medium text-fg-bright">Welcome to Copperplane</h1>
        <p className="max-w-xl text-sm text-fg-secondary">
          Copperplane reads your KiCad schematic and board, checks them, explains what the checks
          mean, and sizes an enclosure to fit. It needs an AI provider for the explaining, and
          KiCad and FreeCAD for everything else.
        </p>
      </div>

      <div className="flex flex-col gap-3">
        <div className="flex max-w-xl flex-col gap-1 rounded border border-line p-3">
          <p className="text-sm font-medium text-fg-bright">Use your own provider</p>
          <p className="text-xs text-fg-secondary">
            You bring an API key from Anthropic, OpenAI, Google or Perplexity. You pay them
            directly, and the key stays in your machine&rsquo;s keychain.
          </p>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <button
              type="button"
              className="rounded bg-accent px-3 py-1.5 text-xs font-medium text-accent-fg hover:opacity-90"
              onClick={onChooseGuided}
            >
              Guide me through it
            </button>
            <button
              type="button"
              className="rounded border border-line px-3 py-1.5 text-xs text-fg-secondary hover:bg-surface-alt"
              onClick={onChooseManual}
            >
              I&rsquo;ll set it up myself
            </button>
          </div>
        </div>

        {/* Present, deliberately inert, and explicit about why. */}
        <div className="flex max-w-xl flex-col gap-1 rounded border border-line-subtle bg-surface-alt/40 p-3 opacity-80">
          <p className="flex items-center gap-2 text-sm font-medium text-fg-secondary">
            Managed by Copperplane
            <span className="rounded bg-surface px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-fg-muted">
              Coming soon
            </span>
          </p>
          <p className="text-xs text-fg-muted">
            No API key to manage — keys and model choices maintained for you. The hosted service
            is still being built, so this cannot be chosen yet.
          </p>
          <button
            type="button"
            disabled
            aria-disabled="true"
            className="mt-1 cursor-not-allowed self-start rounded border border-line-subtle px-3 py-1.5 text-xs text-fg-faint"
          >
            Sign in
          </button>
        </div>
      </div>

      {/* A quiet link, not a peer of the two real choices -- but always
          present. The manual path never gated anyone, and gating only the
          guided one would punish the user who asked for help. */}
      <button
        type="button"
        className="text-xs text-fg-muted underline decoration-dotted underline-offset-2 hover:text-fg-secondary"
        onClick={onSkip}
      >
        Skip for now and look around
      </button>
    </div>
  )
}

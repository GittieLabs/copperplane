/** SPEC-305 §2: "visible-but-empty beats hidden" -- an area tab a user
 * can click that isn't built yet still names what's coming and which
 * spec owns it, rather than being omitted from the tab row or showing a
 * bare, uninformative "Not built" with no context. */
export function NotBuiltPlaceholder({ specId, title, description }: {
  specId: string
  title: string
  description: string
}) {
  return (
    <div className="flex w-full max-w-md flex-col items-center gap-2 rounded border border-dashed border-neutral-700 p-8 text-center">
      <p className="text-sm font-medium text-neutral-300">{title} — not built yet</p>
      <p className="text-xs text-neutral-500">{description}</p>
      <p className="text-xs text-neutral-600">Coming in {specId}</p>
    </div>
  )
}

import { useEffect, useState } from 'react'

import { describeFootprint, type FootprintDetail as Detail } from '../lib/kicadProject'

/** SPEC-334: the detail view behind a row in the board components table.
 *
 *  "there are often many options to choose from that have very similar names
 *  and it's hard to know what P2.54mm_Vertical means when to use over
 *  P2.00mm_Horizontal. If I am a user, that's what I am trying to get
 *  clarification on."
 *
 *  Every fact here is read from the footprint's own file, so it is instant and
 *  cannot be wrong about the library. Nothing is generated. */
export function FootprintDetailView({
  footprintId,
  reference,
  onClose,
}: {
  footprintId: string
  reference?: string
  onClose: () => void
}) {
  const [detail, setDetail] = useState<Detail | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setDetail(null)
    setError(null)
    void (async () => {
      try {
        const result = await describeFootprint(footprintId)
        if (!cancelled) setDetail(result)
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err))
      }
    })()
    return () => { cancelled = true }
  }, [footprintId])

  return (
    <div className="flex flex-col gap-3 rounded border border-line p-3 text-xs">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-0.5">
          <p className="text-sm font-medium text-fg-bright">
            {reference ? `${reference} — ` : ''}{detail?.name ?? footprintId.split(':').pop()}
          </p>
          {detail?.library && (
            <p className="text-fg-muted">
              from the <span className="text-fg-secondary">{detail.library}</span> library
            </p>
          )}
        </div>
        <button
          type="button"
          className="shrink-0 rounded border border-line px-2 py-1 text-fg-secondary hover:bg-surface-alt"
          onClick={onClose}
        >
          Close
        </button>
      </div>

      {error && <p className="text-danger">Could not read this footprint: {error}</p>}
      {!detail && !error && <p className="text-fg-muted">Reading the footprint…</p>}

      {detail && (
        <>
          {detail.description ? (
            <p className="text-fg-secondary">{detail.description}</p>
          ) : (
            /* A personal or community library may carry no description. Saying
               so beats an empty panel, and the naming notes below still work. */
            <p className="text-fg-muted">
              This library gives no description for the footprint, so what follows is read from its
              name and its pads.
            </p>
          )}

          <dl className="flex flex-wrap gap-x-6 gap-y-1">
            {detail.pad_count != null && (
              <div>
                <dt className="inline text-fg-muted">Pads: </dt>
                <dd className="inline text-fg-secondary">{detail.pad_count}</dd>
              </div>
            )}
            {detail.mounting && (
              <div>
                <dt className="inline text-fg-muted">Mounting: </dt>
                <dd className="inline text-fg-secondary">{detail.mounting}</dd>
              </div>
            )}
            {detail.courtyard && (
              <div>
                <dt className="inline text-fg-muted">Keep-clear area: </dt>
                <dd className="inline text-fg-secondary">
                  {detail.courtyard.x_mm} × {detail.courtyard.y_mm} mm
                </dd>
              </div>
            )}
          </dl>

          {detail.name_notes.length > 0 && (
            <div className="flex flex-col gap-1 rounded bg-surface-alt/60 p-2">
              <p className="font-medium text-fg-secondary">What the name is telling you</p>
              <ul className="flex list-disc flex-col gap-1 pl-4">
                {detail.name_notes.map((note) => (
                  <li key={note} className="text-fg-secondary">{note}</li>
                ))}
              </ul>
            </div>
          )}

          {/* The 3D model decides whether this part can be measured for the
              enclosure at all -- SPEC-326's whole subject, and the reason a
              user ends up looking at a footprint in the first place. */}
          <p className={detail.has_model ? 'text-fg-muted' : 'text-warning'}>
            {detail.has_model
              ? 'Has a 3D model, so its height is measured automatically.'
              : 'No 3D model is installed for this footprint, so its height has to be supplied by hand before an enclosure can account for it.'}
          </p>

          {detail.datasheet_url && (
            <p className="break-all text-fg-muted">
              Datasheet named by the library:{' '}
              <span className="text-fg-tertiary">{detail.datasheet_url}</span>
            </p>
          )}

          {detail.tags.length > 0 && (
            <p className="text-fg-faint">Tags: {detail.tags.join(', ')}</p>
          )}
        </>
      )}
    </div>
  )
}

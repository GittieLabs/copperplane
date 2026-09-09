import { useCallback, useEffect, useState } from 'react'

import type { CapabilityProfile } from '../lib/fabricationReview'
import {
  cloneHouse,
  deleteHouse,
  exportHouses,
  genericProfile,
  importHouses,
  listHouses,
  resetHouse,
  saveHouse,
} from '../lib/fabricationReview'

/**
 * SPEC-342 §5: the library of board houses, and choosing one for a project.
 *
 * The library is global; the choice is per project. Two things this surface has
 * to keep true, both of them measured or decided rather than preferences:
 *
 * *   **A house that came with the app is read-only** (§2.6). It offers Clone
 *     and not Edit, because a mistake in a bundled house would otherwise be
 *     unrecoverable — there would be nothing left to revert to. An *imported*
 *     house is not bundled: the user brought it in and owns it, so it edits
 *     like any other.
 * *   **Nothing here is attributed to a vendor who did not publish it**
 *     (`CTX-114.1` Deviation 6). The bundled starting point is a template, so
 *     it is offered as something to start from and never as a house.
 */

const FIELDS: { key: keyof CapabilityProfile; label: string }[] = [
  { key: 'min_track_width', label: 'Minimum track width' },
  { key: 'min_clearance', label: 'Minimum clearance' },
  { key: 'min_annular_ring', label: 'Minimum annular ring' },
  { key: 'min_drill', label: 'Minimum drill' },
  { key: 'min_hole_to_hole', label: 'Minimum hole to hole' },
  { key: 'min_edge_clearance', label: 'Copper to board edge' },
  { key: 'min_silk_clearance', label: 'Minimum silkscreen clearance' },
  { key: 'min_text_height', label: 'Minimum text height' },
  { key: 'min_text_thickness', label: 'Minimum text thickness' },
]

function slug(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'house'
}

function today(): string {
  return new Date().toISOString().slice(0, 10)
}

export function HouseLibrary({
  chosenId,
  onChoose,
  onClose,
}: {
  /** The house this project currently checks against, if any. */
  chosenId: string | null
  onChoose: (house: CapabilityProfile) => void | Promise<void>
  onClose: () => void
}) {
  const [houses, setHouses] = useState<CapabilityProfile[] | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [editing, setEditing] = useState<string | null>(null)
  const [draft, setDraft] = useState<Record<string, string>>({})

  const refresh = useCallback(async () => {
    setHouses(await listHouses())
  }, [])

  useEffect(() => {
    refresh().catch((err) => setError(err instanceof Error ? err.message : String(err)))
  }, [refresh])

  async function run(label: string, fn: () => Promise<string | null>) {
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      const message = await fn()
      if (message) setNotice(message)
      await refresh()
    } catch (err) {
      setError(`${label}: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setBusy(false)
    }
  }

  function onStartFromTemplate() {
    void run('Could not create a house', async () => {
      const template = await genericProfile()
      const name = 'My board house'
      const created = await cloneHouse(template, name, slug(name), today())
      await saveHouse(created)
      return `Created “${name}” from the standard numbers. Edit it to match your fab.`
    })
  }

  function onClone(house: CapabilityProfile) {
    void run('Could not clone', async () => {
      const name = `${house.house_name} (copy)`
      const created = await cloneHouse(house, name, slug(name), today())
      await saveHouse(created)
      return `Cloned as “${name}”. Every number is marked unconfirmed until you check it.`
    })
  }

  function onRemove(house: CapabilityProfile) {
    void run('Could not remove', async () => {
      const result = await deleteHouse(house.house_id as string)
      const used = result.still_referenced_by ?? []
      return used.length
        ? `Removed. ${used.join(', ')} still shows the numbers it was checked against.`
        : 'Removed.'
    })
  }

  function onReset(house: CapabilityProfile) {
    void run('Could not reset', async () => {
      const original = await resetHouse(house.house_id as string)
      return `Reset to “${original.house_name}” as it shipped. Your copy is gone.`
    })
  }

  function onSaveEdits(house: CapabilityProfile) {
    void run('Could not save', async () => {
      const next: Record<string, unknown> = { ...house }
      for (const { key } of FIELDS) {
        const raw = draft[key as string]
        if (raw === undefined) continue
        const value = raw.trim() === '' ? null : Number(raw)
        if (value !== null && (Number.isNaN(value) || value <= 0)) {
          throw new Error(`${key} must be a positive measurement in millimetres`)
        }
        next[key as string] = value
      }
      await saveHouse(next as unknown as CapabilityProfile, true)
      setEditing(null)
      setDraft({})
      return 'Saved.'
    })
  }

  async function onExport() {
    void run('Could not export', async () => {
      const payload = await exportHouses()
      // Rendered for the user to copy: writing a file the user picked is a
      // separate permission question and not one this panel needs to answer.
      setNotice(null)
      await navigator.clipboard?.writeText(JSON.stringify(payload, null, 2))
      return `Copied ${payload.houses.length} house(s) to the clipboard as JSON.`
    })
  }

  function onImport() {
    void run('Could not import', async () => {
      const text = await navigator.clipboard?.readText()
      if (!text) throw new Error('There was nothing on the clipboard to import.')
      const report = await importHouses(JSON.parse(text))
      const parts = [`${report.imported.length} imported`]
      if (report.skipped_existing.length) {
        parts.push(`${report.skipped_existing.length} already in your library and left alone`)
      }
      if (report.rejected.length) parts.push(`${report.rejected.length} rejected`)
      return parts.join(', ') + '.'
    })
  }

  return (
    <div className="flex flex-col gap-3 rounded border border-line-subtle p-3">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-medium text-fg-bright">Board houses</h3>
        <button type="button" className="text-xs text-fg-muted underline" onClick={onClose}>
          Done
        </button>
      </div>

      <p className="text-xs text-fg-tertiary">
        These are shared across your projects. Each project picks one, and keeps the numbers it was
        actually checked against — so editing a house never rewrites what an old check reported.
      </p>

      {error && <p className="text-xs text-danger">{error}</p>}
      {notice && <p className="text-xs text-fg-secondary">{notice}</p>}

      {houses === null ? (
        <p className="text-xs text-fg-muted">Loading…</p>
      ) : houses.length === 0 ? (
        <div className="flex flex-col gap-2">
          <p className="text-xs text-fg-tertiary">
            You have no board houses yet. Start from a standard 2-layer process and edit it to match
            what your fab publishes — nothing here is attributed to a company that did not publish
            it.
          </p>
          <button
            type="button"
            className="self-start rounded border border-line-strong px-3 py-1 text-xs text-fg-bright"
            onClick={onStartFromTemplate}
            disabled={busy}
          >
            Start from standard 2-layer numbers
          </button>
        </div>
      ) : (
        <ul className="flex flex-col gap-2">
          {houses.map((house) => {
            const id = house.house_id as string
            const isChosen = id === chosenId
            const isEditing = editing === id
            return (
              <li
                key={id}
                className={`rounded border p-2 text-xs ${
                  isChosen ? 'border-fg bg-surface-alt' : 'border-line-subtle'
                }`}
              >
                <div className="flex items-baseline justify-between gap-2">
                  <span className="font-medium text-fg-bright">
                    {house.house_name}
                    {house.is_bundled && (
                      <span className="text-fg-muted"> · came with the app, read-only</span>
                    )}
                    {house.cloned_from && <span className="text-fg-muted"> · your copy</span>}
                    {isChosen && <span className="text-fg-muted"> · in use here</span>}
                  </span>
                </div>

                {isEditing ? (
                  <div className="mt-2 flex flex-col gap-1">
                    {FIELDS.map(({ key, label }) => (
                      <label key={key as string} className="flex items-baseline justify-between gap-2">
                        <span className="text-fg-secondary">{label}</span>
                        <input
                          className="w-24 rounded border border-line px-1 text-right text-fg-bright"
                          value={
                            draft[key as string] ??
                            String((house[key] as number | null | undefined) ?? '')
                          }
                          onChange={(e) =>
                            setDraft((d) => ({ ...d, [key as string]: e.target.value }))
                          }
                          aria-label={label}
                        />
                      </label>
                    ))}
                    <p className="text-fg-muted">
                      Leave a field empty if your fab does not publish it — an empty field is not
                      checked, rather than checked against a guess.
                    </p>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        className="rounded border border-line-strong px-2 py-0.5 text-fg-bright"
                        onClick={() => onSaveEdits(house)}
                        disabled={busy}
                      >
                        Save
                      </button>
                      <button
                        type="button"
                        className="text-fg-muted underline"
                        onClick={() => {
                          setEditing(null)
                          setDraft({})
                        }}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="mt-1 flex flex-wrap items-baseline gap-3">
                    {!isChosen && (
                      <button
                        type="button"
                        className="rounded border border-line-strong px-2 py-0.5 text-fg-bright"
                        onClick={() => void onChoose(house)}
                        disabled={busy}
                      >
                        Use for this project
                      </button>
                    )}
                    {/* No Edit on a bundled house. Clone it and edit the
                        clone -- keeping the bundled copy pristine is the only
                        way back if a change turns out to be wrong. */}
                    {!house.is_bundled && (
                      <button
                        type="button"
                        className="text-fg-muted underline"
                        onClick={() => {
                          setEditing(id)
                          setDraft({})
                        }}
                      >
                        Edit
                      </button>
                    )}
                    <button
                      type="button"
                      className="text-fg-muted underline"
                      onClick={() => onClone(house)}
                      disabled={busy}
                    >
                      Clone
                    </button>
                    {house.cloned_from && (
                      <button
                        type="button"
                        className="text-fg-muted underline"
                        onClick={() => onReset(house)}
                        disabled={busy}
                      >
                        Reset to shipped
                      </button>
                    )}
                    {!house.is_bundled && (
                      <button
                        type="button"
                        className="text-fg-muted underline"
                        onClick={() => onRemove(house)}
                        disabled={busy}
                      >
                        Remove
                      </button>
                    )}
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      )}

      <div className="flex flex-wrap items-baseline gap-3 border-t border-line-subtle pt-2">
        <button
          type="button"
          className="text-xs text-fg-muted underline"
          onClick={onStartFromTemplate}
          disabled={busy}
        >
          Add from standard numbers
        </button>
        <button
          type="button"
          className="text-xs text-fg-muted underline"
          onClick={() => void onExport()}
          disabled={busy}
        >
          Copy library as JSON
        </button>
        <button
          type="button"
          className="text-xs text-fg-muted underline"
          onClick={onImport}
          disabled={busy}
        >
          Import from clipboard
        </button>
      </div>
    </div>
  )
}

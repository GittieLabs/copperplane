import { useCallback, useEffect, useState } from 'react'

import {
  componentEnvelopes,
  listSchematicComponents,
  pickKicadProject,
  resolveKicadProject,
  type EnvelopeResult,
  type KicadProjectFiles,
  type SchematicComponent,
  type SchematicRead,
} from '../lib/kicadProject'
import { loadProject, saveProject } from '../lib/projects'

/** SPEC-325 §5: what is actually in the user's schematic, read from the
 * file with KiCad closed.
 *
 * Deliberately a table, not a canvas. KiCad already draws the schematic,
 * better, and is usually open next to this app -- the question this
 * answers is "what is in my design and what is missing from it", which a
 * drawing does not answer well. */
export function SchematicComponents({ projectName }: { projectName: string }) {
  const [proPath, setProPath] = useState<string | null>(null)
  const [files, setFiles] = useState<KicadProjectFiles | null>(null)
  const [read, setRead] = useState<SchematicRead | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  /* SPEC-326 §2.5: heights the user supplied, keyed by FOOTPRINT -- ten
     identical resistors are one decision, and it survives a schematic edit
     that renumbers references. */
  const [heights, setHeights] = useState<Record<string, number>>({})
  const [envelopes, setEnvelopes] = useState<EnvelopeResult | null>(null)
  const [draftHeight, setDraftHeight] = useState<Record<string, string>>({})

  const readSchematic = useCallback(
    async (resolved: KicadProjectFiles, supplied: Record<string, number>) => {
      setFiles(resolved)
      if (!resolved.schematic_path) {
        setRead(null)
        setEnvelopes(null)
        return
      }
      setRead(await listSchematicComponents(resolved.schematic_path))
      // SPEC-326: a recommendation, never an override -- the enclosure's own
      // height stays user-entered. This says what the parts need, and where
      // each number came from.
      try {
        setEnvelopes(await componentEnvelopes(resolved.schematic_path, supplied))
      } catch {
        setEnvelopes(null)
      }
    },
    [],
  )

  const load = useCallback(async (path: string, supplied: Record<string, number> = {}) => {
    setBusy(true)
    setError(null)
    try {
      await readSchematic(await resolveKicadProject(path), supplied)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setRead(null)
    } finally {
      setBusy(false)
    }
  }, [readSchematic])

  // A previously linked project reloads on mount. Nothing is cached: the
  // file is read fresh, because a stored copy of a schematic's contents
  // goes stale the moment the user edits in KiCad (SPEC-325 §2.3).
  useEffect(() => {
    let cancelled = false
    void (async () => {
      try {
        const project = await loadProject(projectName)
        if (cancelled || !project.kicad_project_path) return
        setProPath(project.kicad_project_path)
        const supplied = project.component_heights ?? {}
        setHeights(supplied)
        await load(project.kicad_project_path, supplied)
      } catch {
        // A project with no KiCad link yet is the ordinary first state.
      }
    })()
    return () => { cancelled = true }
  }, [projectName, load])

  async function handlePick() {
    setError(null)
    try {
      const picked = await pickKicadProject()
      if (!picked) return
      setProPath(picked)
      const project = await loadProject(projectName)
      await saveProject({ ...project, kicad_project_path: picked })
      await load(picked, heights)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  /** SPEC-326: a height for a footprint KiCad ships no model for. Keyed by
   *  footprint and remembered on the project, so it is entered once. */
  async function handleSetHeight(footprint: string) {
    const raw = draftHeight[footprint]
    const value = Number(raw)
    if (!raw || !Number.isFinite(value) || value <= 0) return
    const next = { ...heights, [footprint]: value }
    setHeights(next)
    setDraftHeight((prev) => ({ ...prev, [footprint]: '' }))
    try {
      const project = await loadProject(projectName)
      await saveProject({ ...project, component_heights: next })
      if (proPath) await load(proPath, next)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  function statusOf(component: SchematicComponent): { label: string; tone: string } {
    if (!component.footprint) return { label: 'no footprint', tone: 'text-warning' }
    if (!component.footprint_found) return { label: 'footprint not installed', tone: 'text-warning' }
    if (!component.has_model) return { label: 'no 3D model', tone: 'text-warning' }
    return { label: 'ready', tone: 'text-success' }
  }

  const missingModels = (read?.components ?? []).filter((c) => c.footprint && !c.has_model).length

  return (
    <div className="flex flex-col gap-2 rounded border border-line p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-medium uppercase text-fg-muted">Schematic components</p>
        <button
          type="button"
          className="rounded border border-line px-2 py-1 text-xs hover:bg-surface-alt disabled:opacity-50"
          onClick={() => void handlePick()}
          disabled={busy}
        >
          {proPath ? 'Change KiCad project…' : 'Link KiCad project…'}
        </button>
      </div>

      {!proPath && (
        <p className="text-xs text-fg-tertiary">
          Pick your <code>.kicad_pro</code> to see every component in the schematic — its footprint,
          and whether that footprint has a 3D model your enclosure can use. KiCad does not need to
          be running.
        </p>
      )}

      {proPath && <p className="break-all text-xs text-fg-muted">{proPath}</p>}
      {busy && <p className="text-sm text-fg-tertiary">Reading the schematic…</p>}
      {error && <p className="text-xs text-danger">{error}</p>}

      {files && !files.schematic_path && !busy && (
        <p className="text-xs text-warning">
          This project has no <code>.kicad_sch</code> next to its project file yet.
        </p>
      )}

      {/* SPEC-325 §3: whether `kicad-cli sch export bom` walks a hierarchy
          from the root sheet is UNVERIFIED -- no multi-sheet project was
          available to test against. Saying so is the honest option; showing
          a possibly-partial list as complete is not. */}
      {files?.sheet_count != null && files.sheet_count > 1 && (
        <p className="text-xs text-warning">
          This project has {files.sheet_count} sheets. This list is read from the root sheet and may
          not include components on the others — that has not been verified.
        </p>
      )}

      {read && (
        <>
          <p className="text-xs text-fg-muted">
            {read.components.length} component{read.components.length === 1 ? '' : 's'}
            {missingModels > 0 && `, ${missingModels} with no 3D model`} · read{' '}
            {new Date(read.read_at).toLocaleTimeString()}
          </p>

          {/* SPEC-326: a recommendation, never an override. The enclosure's
              own height stays user-entered; this says what the parts need and
              names where the number came from, so a partly-stated result is
              never mistaken for a measured one. */}
          {envelopes?.min_interior_height_mm != null && envelopes.tallest && (
            <p className="text-xs text-fg-secondary">
              Enclosure needs at least{' '}
              <strong className="text-fg-bright">{envelopes.min_interior_height_mm}mm</strong> of
              interior height — set by {envelopes.tallest.reference} (
              {envelopes.tallest.source === 'model' ? 'measured from its 3D model' : 'height you supplied'}).{' '}
              {envelopes.measured} measured, {envelopes.stated} stated
              {envelopes.unknown > 0 && `, ${envelopes.unknown} still unknown`}.
            </p>
          )}
          {envelopes && envelopes.unknown > 0 && (
            <p className="text-xs text-warning">
              A component with no height is not counted above, so the real minimum may be taller.
            </p>
          )}
          {/* The file is what was read, so this can lag an editor holding
              unsaved changes. Never presented as live sync. */}
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="text-fg-muted">
                <tr>
                  <th className="py-1 pr-3 font-medium">Ref</th>
                  <th className="py-1 pr-3 font-medium">Value</th>
                  <th className="py-1 pr-3 font-medium">Footprint</th>
                  <th className="py-1 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {read.components.map((component) => {
                  const status = statusOf(component)
                  return (
                    <tr key={component.reference} className="border-t border-line-subtle">
                      <td className="py-1 pr-3 text-fg-bright">{component.reference}</td>
                      <td className="py-1 pr-3 text-fg-secondary">{component.value ?? '—'}</td>
                      <td className="py-1 pr-3 break-all text-fg-tertiary">
                        {component.footprint ?? '—'}
                      </td>
                      <td className={`py-1 ${status.tone}`}>
                        {status.label}
                        {component.dnp && <span className="text-fg-muted"> · DNP</span>}
                        {/* SPEC-326 §2.3: a height is SOURCED, never guessed.
                            For a footprint KiCad ships no model for, the user
                            is the only remaining source -- so ask, once, and
                            remember it against the footprint. */}
                        {component.footprint && !component.has_model && (
                          heights[component.footprint] != null ? (
                            <span className="text-fg-muted">
                              {' '}· {heights[component.footprint]}mm (you)
                            </span>
                          ) : (
                            <span className="ml-2 inline-flex items-center gap-1">
                              <input
                                aria-label={`Height for ${component.footprint}`}
                                className="w-16 rounded border border-line bg-surface px-1 py-0.5 text-xs text-fg"
                                placeholder="mm"
                                value={draftHeight[component.footprint] ?? ''}
                                onChange={(e) =>
                                  setDraftHeight((prev) => ({
                                    ...prev,
                                    [component.footprint as string]: e.target.value,
                                  }))
                                }
                              />
                              <button
                                type="button"
                                className="rounded border border-line px-1 py-0.5 text-xs"
                                onClick={() => void handleSetHeight(component.footprint as string)}
                              >
                                set
                              </button>
                            </span>
                          )
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}

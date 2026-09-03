import { useCallback, useEffect, useState } from 'react'

import {
  checkSchematicParity,
  componentEnvelopes,
  listSchematicComponents,
  pickKicadProject,
  resolveKicadProject,
  type EnvelopeResult,
  type KicadProjectFiles,
  type ParityResult,
  type SchematicComponent,
  type SchematicRead,
} from '../lib/kicadProject'
import { loadProject, saveProject } from '../lib/projects'

/** KiCad repeats an identical parity description once per offending item --
 *  a real board of the maintainer's reports "Duplicate footprints" three
 *  times. Three identical lines tell a user nothing a count does not, and
 *  the description is the natural React key only once it is unique. */
function distinctIssues(parity: ParityResult): { description: string; count: number }[] {
  const counts = new Map<string, number>()
  for (const issue of parity.issues) {
    counts.set(issue.description, (counts.get(issue.description) ?? 0) + 1)
  }
  return [...counts].map(([description, count]) => ({ description, count }))
}

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
  /* SPEC-326 §2.7: whether the board still agrees with the schematic every
     number above was read from. */
  const [parity, setParity] = useState<ParityResult | null>(null)
  /* Why the numbers are missing, when they are. Never swallowed. */
  const [measureError, setMeasureError] = useState<string | null>(null)

  const readSchematic = useCallback(
    async (resolved: KicadProjectFiles, supplied: Record<string, number>) => {
      setFiles(resolved)
      setMeasureError(null)
      if (!resolved.schematic_path) {
        setRead(null)
        setEnvelopes(null)
        setParity(null)
        return
      }
      // SPEC-326 §2.7: ONE read decides both the table and the summary above
      // it. Listing the schematic's components under a summary counting the
      // board's is what CTX-326.3 first shipped, and it is not a discipline
      // problem -- two reads of two files will drift.
      //
      // A recommendation, never an override: the enclosure's own height stays
      // user-entered. This says what the parts need and where each number
      // came from.
      try {
        const measured = await componentEnvelopes(
          resolved.schematic_path, resolved.pcb_path, supplied,
        )
        setEnvelopes(measured)
        setRead({
          source_path: measured.source_path,
          read_at: measured.read_at,
          components: measured.components,
        })
      } catch (err) {
        // Falling back to the schematic list keeps the table alive when
        // envelope measurement fails (no FreeCAD, say).
        //
        // The fallback used to be SILENT, and that cost three rounds of
        // debugging a live defect: the panel showed the schematic's
        // components under a "Board components" heading with no indication
        // that measurement had failed at all, which is indistinguishable
        // from the measurement simply being wrong. A fallback the user
        // cannot see is a fallback nobody can diagnose.
        setEnvelopes(null)
        setMeasureError(err instanceof Error ? err.message : String(err))
        setRead(
          resolved.schematic_path
            ? await listSchematicComponents(resolved.schematic_path)
            : null,
        )
      }
      // SPEC-326 §2.7: everything above was read from the SCHEMATIC, but the
      // enclosure is built around the BOARD. If the user has edited the
      // schematic and not yet run KiCad's "Update PCB from Schematic", those
      // are different designs and the height above may describe a part that
      // is not on the board. Neither KiCad view shows this; both files open
      // and render correctly on their own.
      try {
        setParity(resolved.pcb_path ? await checkSchematicParity(resolved.pcb_path) : null)
      } catch {
        // Parity needs a readable board beside the schematic. Not having one
        // is an ordinary state, and must not blank the component list.
        setParity(null)
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
  const parityIssues = parity && !parity.in_sync ? distinctIssues(parity) : []

  return (
    <div className="flex flex-col gap-2 rounded border border-line p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-medium uppercase text-fg-muted">
          {envelopes?.measured_from === 'board' ? 'Board components' : 'Schematic components'}
        </p>
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

          {measureError && (
            <div className="flex flex-col gap-1 rounded border border-danger/40 bg-danger/5 p-2">
              <p className="text-xs font-medium text-danger">
                Could not measure this project&rsquo;s components, so the list below is read from the
                schematic and no height is recommended.
              </p>
              <p className="break-all text-xs text-fg-tertiary">{measureError}</p>
            </div>
          )}

          {/* SPEC-326 §2.7. Placed ABOVE the height recommendation on
              purpose: when the board and schematic disagree, the number
              below was read from footprints that are not on the board, so
              the caveat has to arrive before the claim it qualifies. */}
          {parity && !parity.in_sync && (
            <div className="flex flex-col gap-1 rounded border border-warning/40 bg-warning/5 p-2">
              <p className="text-xs font-medium text-warning">
                Your board does not match your schematic
                {parity.issue_count > 1 && ` (${parity.issue_count} differences)`}.
              </p>
              <ul className="flex flex-col gap-0.5">
                {parityIssues.slice(0, 5).map(({ description, count }) => (
                  <li key={description} className="text-xs text-fg-secondary">
                    {description}
                    {count > 1 && ` (×${count})`}
                  </li>
                ))}
              </ul>
              {parityIssues.length > 5 && (
                <p className="text-xs text-fg-tertiary">
                  …and {parityIssues.length - 5} more.
                </p>
              )}
              <p className="text-xs text-fg-tertiary">
                {envelopes?.measured_from === 'board' ? (
                  <>
                    Heights and clearances below are measured from the <strong>board</strong>, since
                    the board is what goes in the enclosure.{' '}
                  </>
                ) : (
                  <>
                    The list below is read from the <strong>schematic</strong>, not the board — so it
                    describes a different design from the one above.{' '}
                  </>
                )}
                If the schematic is the version you want, open the PCB in KiCad and run{' '}
                <strong>Tools → Update PCB from Schematic</strong> to bring the board up to date,
                then re-read the project here. This app does not change your files.
              </p>
            </div>
          )}

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
          {/* SPEC-326 §2.7: the board is the source of truth, so a number
              that came from the schematic instead has to say so. This is not
              an error state — a project whose board is not laid out yet has
              no footprints to measure — but it is a different claim. */}
          {envelopes?.measured_from === 'schematic' && (
            <p className="text-xs text-warning">
              Measured from the schematic: this project&rsquo;s board has no footprints on it yet.
              Lay the board out in KiCad and re-read the project to size the enclosure from what is
              actually on it.
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

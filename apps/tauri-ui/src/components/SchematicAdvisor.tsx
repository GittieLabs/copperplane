import { useCallback, useEffect, useState } from 'react'

import { SchematicComponents } from './SchematicComponents'
import type { MenuCommand } from '../lib/areas'
import {
  checkResultForProject,
  checkSchematic,
  listProjectSchematics,
  openKicad,
  pickSchematicFile,
  type CheckResult,
  type ListProjectSchematicsResult,
  type SchematicCandidate,
} from '../lib/boardAdvisor'
import { AgentChat } from './AgentChat'
import { ReviewPanel } from './ReviewPanel'
import { ViolationsList } from './ViolationsList'
import { linkedProjectSchematic } from '../lib/kicadProject'
import { setProjectCheckResult } from '../lib/projects'

/** SPEC-309: real ERC via kicad-cli (CTX-309.1), explained in plain
 * language. Lives in the Schematic area -- moved here from the PCB
 * area (real user feedback: both checks briefly lived together under
 * "PCB", which SPEC-300's own original stage-machine design never
 * intended -- ERC belongs to the "Schematic Advisor" stage).
 *
 * KiCad's IPC server has no handler for listing open schematics at
 * all, confirmed live -- unlike the PCB case, this isn't a transient
 * "nothing open yet" state, it's a permanent gap in KiCad's own API
 * surface. Instead of a blind file dialog (the only real option
 * before this), this derives each currently open board's own root
 * schematic path from KiCad's real project-naming convention and
 * verifies it actually exists on disk before ever offering it --
 * mirroring BoardAdvisor's own list-first UX as closely as the real
 * technical constraint allows. A manual file picker remains as a real
 * fallback for a schematic that isn't tied to any board currently open
 * in KiCad.
 *
 * Stays mounted across every area tab (App.tsx hides it with CSS
 * instead of unmounting it), same as BoardAdvisor and for the same
 * reason: a finished check shouldn't disappear just because the user
 * glanced at another tab. `projectName` only resets state on a genuine
 * project switch. */
export function SchematicAdvisor({
  projectName,
  menuCommand,
}: {
  projectName: string
  /** SPEC-316: a Design > Schematic menu click -- only 'open_kicad' and
   * 'pick_manually' are real commands here, `handleCheck` needs a
   * specific candidate a menu click can't supply. */
  menuCommand?: MenuCommand | null
}) {
  const [loadingList, setLoadingList] = useState(false)
  const [listResult, setListResult] = useState<ListProjectSchematicsResult | null>(null)
  const [listError, setListError] = useState<string | null>(null)
  const [openingKicad, setOpeningKicad] = useState(false)
  const [openKicadError, setOpenKicadError] = useState<string | null>(null)

  const [checking, setChecking] = useState(false)
  const [selected, setSelected] = useState<SchematicCandidate | null>(null)
  const [result, setResult] = useState<CheckResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setSelected(null)
    setResult(null)
    setError(null)
  }, [projectName])

  const refreshList = useCallback(async () => {
    setLoadingList(true)
    setListError(null)
    try {
      // The linked project first: it names the schematic outright. Asking
      // KiCad meant opening the PCB Editor to find a *schematic*, because
      // KiCad's IPC cannot list schematics at all -- a real limitation this
      // tab no longer has to inherit now that SPEC-325 reads the .kicad_pro.
      const linked = await linkedProjectSchematic(projectName)
      setListResult(
        linked
          ? { status: 'schematics_found', candidates: [linked] }
          : await listProjectSchematics(),
      )
    } catch (err) {
      setListError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoadingList(false)
    }
  }, [projectName])

  useEffect(() => {
    void refreshList()
  }, [refreshList])

  async function handleOpenKicad() {
    setOpeningKicad(true)
    setOpenKicadError(null)
    try {
      await openKicad()
    } catch (err) {
      setOpenKicadError(err instanceof Error ? err.message : String(err))
    } finally {
      setOpeningKicad(false)
    }
  }

  async function handleCheck(candidate: SchematicCandidate) {
    setSelected(candidate)
    setChecking(true)
    setError(null)
    setResult(null)
    try {
      const checked = await checkSchematic(candidate.path)
      setResult(checked)
      // SPEC-319 §2.1's prerequisite -- see BoardAdvisor for why. An ERC
      // result kept only in React state is invisible to the review agent.
      try {
        await setProjectCheckResult(
          projectName, 'schematic', checkResultForProject(checked, 'schematic'),
        )
      } catch (persistErr) {
        setError(
          `Checked, but could not save the result for review: ${
            persistErr instanceof Error ? persistErr.message : String(persistErr)
          }`,
        )
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setChecking(false)
    }
  }

  async function handlePickManually() {
    // pickSchematicFile returning null (the user closed the dialog) is
    // a normal, silent no-op -- not an error state.
    const path = await pickSchematicFile()
    if (!path) return
    await handleCheck({ path, label: path.split('/').pop() ?? path })
  }

  // SPEC-316: Design > Schematic menu clicks dispatch to these same two
  // handlers -- no new business logic, just a second entry point.
  useEffect(() => {
    if (menuCommand?.area !== 'schematic') return
    if (menuCommand.command === 'open_kicad') void handleOpenKicad()
    if (menuCommand.command === 'pick_manually') void handlePickManually()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [menuCommand?.nonce])

  const showGuidance = !loadingList && (listError !== null || listResult?.status === 'no_schematic_found')
  const selectedIsListed =
    selected !== null &&
    listResult?.status === 'schematics_found' &&
    listResult.candidates.some((c) => c.path === selected.path)

  return (
    <div className="flex w-full max-w-4xl flex-col gap-6">
      {/* SPEC-325: what is actually in the schematic, read from the file.
          Above ERC deliberately -- "what is in my design" is the question a
          user arrives with; "does it pass ERC" is the one they ask second. */}
      <SchematicComponents projectName={projectName} />

      <div className="flex flex-col gap-2 rounded border border-line p-3">
        <p className="text-xs font-medium uppercase text-fg-muted">Schematic (ERC)</p>

        {loadingList && (
          <p className="text-sm text-fg-tertiary">Looking for schematics near the boards open in KiCad…</p>
        )}

        {showGuidance && (
          <div className="flex flex-col gap-2 rounded border border-line-subtle bg-surface p-3 text-sm">
            {/* This used to tell the user to launch KiCad and open the PCB
                Editor -- to find a SCHEMATIC -- because discovery went through
                KiCad's IPC, which cannot list schematics at all. A linked
                .kicad_pro names the schematic outright and needs nothing
                running, so the instructions are now about linking a project,
                and KiCad is the fallback rather than the first step. */}
            <p className="text-fg-bright">No schematic is linked yet.</p>
            <ol className="list-decimal space-y-1 pl-4 text-xs text-fg-tertiary">
              <li>
                Link your KiCad project on the <strong className="text-fg-secondary">Schematic
                components</strong> panel above — its <code>.kicad_pro</code> names the schematic,
                and KiCad does not need to be running.
              </li>
              <li>Or pick the <code>.kicad_sch</code> file directly with the button below.</li>
            </ol>
            <p className="text-xs text-fg-muted">
              {listError
                ? 'Asking KiCad directly also failed, which only matters if you have no project linked.'
                : 'Opening KiCad is still an option if you would rather work there first.'}
            </p>
            {openKicadError && <p className="text-xs text-danger">{openKicadError}</p>}
            <div className="flex gap-2">
              <button
                type="button"
                className="rounded bg-accent px-3 py-1 text-xs font-medium text-accent-fg disabled:opacity-50"
                onClick={() => void handleOpenKicad()}
                disabled={openingKicad}
              >
                {openingKicad ? 'Opening…' : 'Open KiCad'}
              </button>
              <button
                type="button"
                className="rounded border border-line-strong px-3 py-1 text-xs text-fg-bright"
                onClick={() => void refreshList()}
              >
                Refresh
              </button>
              <button
                type="button"
                className="rounded border border-line-strong px-3 py-1 text-xs text-fg-bright"
                onClick={() => void handlePickManually()}
              >
                Pick file manually…
              </button>
            </div>
          </div>
        )}

        {!loadingList && !showGuidance && listResult?.status === 'schematics_found' && (
          <div className="flex flex-col gap-2 rounded border border-line-subtle bg-surface p-3 text-sm">
            <p className="text-fg-bright">
              {listResult.candidates.length === 1
                ? 'Schematic found for the board open in KiCad:'
                : 'Schematics found for the boards open in KiCad — pick one to check:'}
            </p>
            <ul className="flex flex-col gap-1">
              {listResult.candidates.map((candidate) => {
                const isSelected = selected?.path === candidate.path
                return (
                  <li key={candidate.path}>
                    <button
                      type="button"
                      aria-pressed={isSelected}
                      className={`w-full rounded border px-3 py-2 text-left text-xs disabled:opacity-50 ${
                        isSelected
                          ? 'border-fg bg-surface-alt text-fg'
                          : 'border-line text-fg-bright hover:bg-surface-alt'
                      }`}
                      onClick={() => void handleCheck(candidate)}
                      disabled={checking}
                    >
                      <span className="block font-medium">{candidate.label}</span>
                      <span className="block break-all text-fg-muted">{candidate.path}</span>
                    </button>
                  </li>
                )
              })}
            </ul>
            <p className="text-xs text-fg-muted">
              Don't see the schematic you want? Switch to KiCad and open its board there, then click Refresh --
              or pick a file directly below.
            </p>
            {openKicadError && <p className="text-xs text-danger">{openKicadError}</p>}
            <div className="flex gap-2">
              <button
                type="button"
                className="rounded border border-line-strong px-3 py-1 text-xs text-fg-bright"
                onClick={() => void handleOpenKicad()}
                disabled={openingKicad}
              >
                {openingKicad ? 'Switching…' : 'Switch to KiCad'}
              </button>
              <button
                type="button"
                className="rounded border border-line-strong px-3 py-1 text-xs text-fg-bright"
                onClick={() => void refreshList()}
              >
                Refresh
              </button>
              <button
                type="button"
                className="rounded border border-line-strong px-3 py-1 text-xs text-fg-bright"
                onClick={() => void handlePickManually()}
              >
                Pick file manually…
              </button>
            </div>
          </div>
        )}

        {checking && (
          <p className="text-sm text-fg-tertiary">
            Running ERC checks on {selected?.label ?? 'the selected schematic'}… this can take a few seconds.
          </p>
        )}
        {error && <p className="text-sm text-danger">{error}</p>}
        {result && <ViolationsList result={result} hideSourcePath={selectedIsListed} />}
      </div>
      {/* SPEC-319 §2.4: a sibling action, not inside AgentChat -- a review
          is a flow step with a typed result, not a conversational turn. */}
      <ReviewPanel
        area="schematic"
        scope="project"
        scopeId={`${projectName}:schematic`}
        title="Review the schematic"
        projectName={projectName}
        menuCommand={menuCommand}
      />
      {/* SPEC-318 §5: "a collapsible chat panel at the foot of each area."
          A project-scoped chat has no single Part to offer as a promotion
          target -- "this project" is the only real target here. */}
      <AgentChat
        area="schematic"
        scope="project"
        scopeId={`${projectName}:schematic`}
        title="Ask about the schematic"
        projectName={projectName}
        promotionTargets={[{ label: 'this project', scope: 'project', id: projectName }]}
      />
    </div>
  )
}

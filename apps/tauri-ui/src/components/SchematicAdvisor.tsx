import { useCallback, useEffect, useState } from 'react'
import {
  checkSchematic,
  listProjectSchematics,
  openKicad,
  pickSchematicFile,
  type CheckResult,
  type ListProjectSchematicsResult,
  type SchematicCandidate,
} from '../lib/boardAdvisor'
import { ViolationsList } from './ViolationsList'

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
export function SchematicAdvisor({ projectName }: { projectName: string }) {
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
      setListResult(await listProjectSchematics())
    } catch (err) {
      setListError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoadingList(false)
    }
  }, [])

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
      setResult(await checkSchematic(candidate.path))
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

  const showGuidance = !loadingList && (listError !== null || listResult?.status === 'no_schematic_found')
  const selectedIsListed =
    selected !== null &&
    listResult?.status === 'schematics_found' &&
    listResult.candidates.some((c) => c.path === selected.path)

  return (
    <div className="flex w-full max-w-md flex-col gap-6">
      <div className="flex flex-col gap-2 rounded border border-neutral-700 p-3">
        <p className="text-xs font-medium uppercase text-neutral-500">Schematic (ERC)</p>

        {loadingList && (
          <p className="text-sm text-neutral-400">Looking for schematics near the boards open in KiCad…</p>
        )}

        {showGuidance && (
          <div className="flex flex-col gap-2 rounded border border-neutral-800 bg-neutral-900 p-3 text-sm">
            <p className="text-neutral-200">
              {listError
                ? "KiCad doesn't appear to be running yet."
                : 'No schematic could be found automatically.'}
            </p>
            <ol className="list-decimal space-y-1 pl-4 text-xs text-neutral-400">
              <li>Click <strong className="text-neutral-300">Open KiCad</strong> below (or open it yourself).</li>
              <li>
                Open your project, then open its <strong className="text-neutral-300">PCB Editor</strong> window --
                the schematic itself can't be listed directly (a real KiCad limitation, not this app's), so it's
                found via whichever board you have open.
              </li>
              <li>Click <strong className="text-neutral-300">Refresh</strong> below.</li>
            </ol>
            <p className="text-xs text-neutral-500">
              Or, if the schematic you want isn't tied to any board currently open in KiCad, pick it directly.
            </p>
            {openKicadError && <p className="text-xs text-red-400">{openKicadError}</p>}
            <div className="flex gap-2">
              <button
                type="button"
                className="rounded bg-neutral-100 px-3 py-1 text-xs font-medium text-neutral-950 disabled:opacity-50"
                onClick={() => void handleOpenKicad()}
                disabled={openingKicad}
              >
                {openingKicad ? 'Opening…' : 'Open KiCad'}
              </button>
              <button
                type="button"
                className="rounded border border-neutral-600 px-3 py-1 text-xs text-neutral-200"
                onClick={() => void refreshList()}
              >
                Refresh
              </button>
              <button
                type="button"
                className="rounded border border-neutral-600 px-3 py-1 text-xs text-neutral-200"
                onClick={() => void handlePickManually()}
              >
                Pick file manually…
              </button>
            </div>
          </div>
        )}

        {!loadingList && !showGuidance && listResult?.status === 'schematics_found' && (
          <div className="flex flex-col gap-2 rounded border border-neutral-800 bg-neutral-900 p-3 text-sm">
            <p className="text-neutral-200">
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
                          ? 'border-neutral-100 bg-neutral-800 text-neutral-100'
                          : 'border-neutral-700 text-neutral-200 hover:bg-neutral-800'
                      }`}
                      onClick={() => void handleCheck(candidate)}
                      disabled={checking}
                    >
                      <span className="block font-medium">{candidate.label}</span>
                      <span className="block break-all text-neutral-500">{candidate.path}</span>
                    </button>
                  </li>
                )
              })}
            </ul>
            <p className="text-xs text-neutral-500">
              Don't see the schematic you want? Switch to KiCad and open its board there, then click Refresh --
              or pick a file directly below.
            </p>
            {openKicadError && <p className="text-xs text-red-400">{openKicadError}</p>}
            <div className="flex gap-2">
              <button
                type="button"
                className="rounded border border-neutral-600 px-3 py-1 text-xs text-neutral-200"
                onClick={() => void handleOpenKicad()}
                disabled={openingKicad}
              >
                {openingKicad ? 'Switching…' : 'Switch to KiCad'}
              </button>
              <button
                type="button"
                className="rounded border border-neutral-600 px-3 py-1 text-xs text-neutral-200"
                onClick={() => void refreshList()}
              >
                Refresh
              </button>
              <button
                type="button"
                className="rounded border border-neutral-600 px-3 py-1 text-xs text-neutral-200"
                onClick={() => void handlePickManually()}
              >
                Pick file manually…
              </button>
            </div>
          </div>
        )}

        {checking && (
          <p className="text-sm text-neutral-400">
            Running ERC checks on {selected?.label ?? 'the selected schematic'}… this can take a few seconds.
          </p>
        )}
        {error && <p className="text-sm text-red-400">{error}</p>}
        {result && <ViolationsList result={result} hideSourcePath={selectedIsListed} />}
      </div>
    </div>
  )
}

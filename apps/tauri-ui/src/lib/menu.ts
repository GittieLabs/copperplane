import { invoke } from '@tauri-apps/api/core'
import type { LibrarySummary } from './library'

/** CTX-316.2: keeps the native Library menu (`core/tauri-rust/src/
 * menu.rs`) in sync with the real library registry -- called after
 * every real `listLibraries()` fetch (`App.tsx` on mount, `LibraryArea`'s
 * own `refreshLibraries()`), not pushed proactively by the daemon. A
 * plain, direct `invoke()` call like `openKicad`/`saveSecret` -- this is
 * a native command, not a `library.*` JSON-RPC route. Best-effort: a
 * failure here never blocks the real UI list from rendering correctly,
 * only leaves the native menu momentarily stale until the next real
 * sync point. */
export async function syncLibraryMenu(libraries: LibrarySummary[]): Promise<void> {
  try {
    await invoke('update_library_menu', {
      libraries: libraries.map((library) => ({ id: library.id, name: library.name })),
    })
  } catch {
    // Best-effort, see doc comment above.
  }
}

/** CTX-316.2: keeps the native Design menu's enabled state in sync with
 * whether a project is currently open. Best-effort, same reasoning as
 * `syncLibraryMenu`. */
export async function setDesignMenuEnabled(enabled: boolean): Promise<void> {
  try {
    await invoke('set_design_menu_enabled', { enabled })
  } catch {
    // Best-effort, see doc comment above.
  }
}

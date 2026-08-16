import { relaunch } from '@tauri-apps/plugin-process'
import { check, type Update } from '@tauri-apps/plugin-updater'

export type { Update }

/** SPEC-402 (CTX-402.2): checks the real update manifest
 * (`tauri.conf.json`'s `plugins.updater.endpoints`, a real GitHub Release
 * asset) and verifies its signature against the embedded public key --
 * `@tauri-apps/plugin-updater` does both as one real, native call. Returns
 * `null` when no update is available, not an error -- that's the normal,
 * expected state most of the time. Returns the real `Update` object
 * (not just a summary) so the caller can pass it straight to
 * `installUpdateAndRelaunch` without a second round trip. */
export async function checkForUpdates(): Promise<Update | null> {
  const update = await check()
  return update?.available ? update : null
}

/** Downloads and installs a real, already-checked update, then relaunches
 * into it -- only ever called from an explicit user action (never on a
 * timer or automatically after check), matching this product's existing
 * "every AI/external step confirmable, never silent" principle already
 * established for Board Advisor and Connection Guidance. */
export async function installUpdateAndRelaunch(update: Update): Promise<void> {
  await update.downloadAndInstall()
  await relaunch()
}

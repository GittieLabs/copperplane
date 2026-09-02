import { open } from '@tauri-apps/plugin-shell'
import type { SourceRef } from './chat'
import { cacheDatasheet } from './components'
import { loadPart } from './partDetail'

/** SPEC-319 §2.5: extracted out of `AgentChat.tsx` (CTX-318.1) so
 * `ReviewPanel` can reuse the identical source-chip rendering and
 * open-source flow rather than a second implementation -- both a chat
 * answer and a review finding carry the same `SourceRef[]` union
 * (SPEC-206 §2.3) and need to resolve/open one the same way. */

export function sourceChipLabel(ref: SourceRef): string {
  switch (ref.kind) {
    case 'datasheet_page':
      return `Datasheet page ${ref.page}`
    case 'guidance_item':
      return `Design guidance: ${ref.category}`
    case 'connection_guidance':
      return `Pin ${ref.pin_number} guidance`
    case 'part_field':
      return `Part: ${ref.field}`
    case 'project_intent':
      return 'Project intent'
    case 'chat_turn':
      return 'Earlier answer'
    case 'note':
      return 'Saved note'
    case 'check_finding':
      // Naming the check is the point: "DRC finding" tells a user this came
      // from KiCad's own run on their board, which is exactly what the
      // general-practice note used to deny.
      return ref.source_path?.endsWith('.kicad_sch') ? 'ERC finding' : 'DRC finding'
    default:
      return 'Source'
  }
}

/** Only these two kinds carry (or can resolve) a real, direct
 * open-the-document target -- `connection_guidance`/`part_field`/
 * `project_intent`/`chat_turn`/`note` all cite pre-assembled context or
 * a conversational fact with no document location to jump to, and
 * `check_finding` never actually resolves today (its own backend
 * resolver is still the deliberate `_resolve_deferred` stub). */
export function isOpenableSource(ref: SourceRef): boolean {
  return ref.kind === 'datasheet_page' || ref.kind === 'guidance_item'
}

/** Generalizes `PartDetail.tsx`'s own original `handleOpenCitation` --
 * that one is hardcoded to the single Part already open in that view.
 * `datasheet_page` already carries its own real `page`; `guidance_item`
 * doesn't (the chunk index's own SourceRef for it deliberately omits
 * one -- see CTX-206.7), so this resolves it by loading the real Part
 * and matching `category`+`quote` against its stored `design_guidance`
 * before falling through to the same cache-then-open flow. Throws on
 * failure -- callers own their own loading/error UI state, matching
 * every other async lib function in this codebase (none of them carry
 * their own React state). */
export async function openSource(ref: SourceRef): Promise<void> {
  if (!ref.part_id) {
    throw new Error('This source has no real part to open.')
  }
  const part = await loadPart(ref.part_id)
  let page = ref.page
  if (ref.kind === 'guidance_item' && page === undefined) {
    const items = part.design_guidance?.categories[ref.category ?? ''] ?? []
    page = items.find((item) => item.quote === ref.quote)?.page
  }
  if (page === undefined) {
    throw new Error('Could not resolve a real page for this source.')
  }
  const path = await cacheDatasheet(part.part_id, part.datasheet_url)
  await open(`${path}#page=${page}`)
}

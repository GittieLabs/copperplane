/** SPEC-305 §2: the five per-project area tabs, in the shell's own
 * order. Shared between `App.tsx` and the area components themselves
 * (SPEC-316's `menuCommand` prop needs both sides to agree on the same
 * type without a circular import back into `App.tsx`). */
export type Area = 'overview' | 'components' | 'schematic' | 'pcb' | 'enclosure'

/** SPEC-316: a Design-menu click's real target -- `nonce` so the exact
 * same command fired twice in a row still re-triggers the consuming
 * area component's effect (a plain `{area, command}` object wouldn't
 * change identity or value between two identical clicks). */
export type MenuCommand = { area: Area; command: string; nonce: number }

import type { ReactNode } from 'react'

/** The agents answer in Markdown -- the prompts ask them to -- and it was
 *  rendered into a single `<p>`, so a user saw literal `###` and `**bold**`
 *  runs and every newline collapsed into one wall of text. Reported directly
 *  from the PCB chat.
 *
 *  Deliberately NOT `react-markdown`: that is ~20 transitive packages for the
 *  small, known subset our own prompts produce, in an app whose runtime
 *  dependency list is eleven entries of substance. The subset is fixed here
 *  and covered by tests.
 *
 *  **Builds React elements, never HTML strings.** Nothing here touches
 *  `dangerouslySetInnerHTML`, so model output -- or anything a datasheet or
 *  a web result dragged into it -- cannot inject markup. That is the whole
 *  reason to hand-roll rather than to sanitize.
 *
 *  Unsupported syntax degrades to plain text rather than being swallowed:
 *  a table or a link renders as the characters the model wrote, which is
 *  worse-looking than a real renderer and strictly better than nothing. */

const _BOLD = /\*\*(.+?)\*\*/
const _CODE = /`([^`]+)`/
const _ITALIC = /(?<![*\w])\*(?!\s)([^*]+?)(?<!\s)\*(?!\*)/

/** Inline spans, innermost-first so `**bold `code`**` nests correctly. */
export function renderInline(text: string, keyPrefix = ''): ReactNode[] {
  const out: ReactNode[] = []
  let rest = text
  let n = 0

  while (rest.length > 0) {
    const code = _CODE.exec(rest)
    const bold = _BOLD.exec(rest)
    const italic = _ITALIC.exec(rest)
    const candidates = [
      { m: code, kind: 'code' as const },
      { m: bold, kind: 'bold' as const },
      { m: italic, kind: 'italic' as const },
    ].filter((c): c is { m: RegExpExecArray; kind: 'code' | 'bold' | 'italic' } => c.m !== null)

    if (candidates.length === 0) {
      out.push(rest)
      break
    }

    // Earliest match wins, so `a **b** c` is not reordered by rule priority.
    const first = candidates.reduce((a, b) => (a.m.index <= b.m.index ? a : b))
    const { m, kind } = first
    if (m.index > 0) out.push(rest.slice(0, m.index))

    const key = `${keyPrefix}i${n++}`
    if (kind === 'code') {
      out.push(
        <code key={key} className="rounded bg-surface-alt px-1 py-0.5 font-mono text-[0.9em]">
          {m[1]}
        </code>,
      )
    } else if (kind === 'bold') {
      out.push(<strong key={key} className="font-semibold text-fg">{renderInline(m[1], key)}</strong>)
    } else {
      out.push(<em key={key}>{renderInline(m[1], key)}</em>)
    }
    rest = rest.slice(m.index + m[0].length)
  }
  return out
}

type Block =
  | { kind: 'heading'; level: number; text: string }
  | { kind: 'ul'; items: string[] }
  | { kind: 'ol'; items: string[] }
  | { kind: 'hr' }
  | { kind: 'p'; lines: string[] }

/** Groups lines into blocks. Kept separate from rendering so the parsing is
 *  testable on its own, without reaching through rendered DOM. */
export function parseBlocks(text: string): Block[] {
  const blocks: Block[] = []
  const lines = text.replace(/\r\n/g, '\n').split('\n')

  for (const raw of lines) {
    const line = raw.trimEnd()
    const trimmed = line.trim()
    const last = blocks[blocks.length - 1]

    if (trimmed === '') { blocks.push({ kind: 'p', lines: [] }); continue }

    const heading = /^(#{1,6})\s+(.*)$/.exec(trimmed)
    if (heading) { blocks.push({ kind: 'heading', level: heading[1].length, text: heading[2] }); continue }

    if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) { blocks.push({ kind: 'hr' }); continue }

    const ul = /^[*-]\s+(.*)$/.exec(trimmed)
    if (ul) {
      if (last?.kind === 'ul') last.items.push(ul[1])
      else blocks.push({ kind: 'ul', items: [ul[1]] })
      continue
    }

    const ol = /^\d+[.)]\s+(.*)$/.exec(trimmed)
    if (ol) {
      if (last?.kind === 'ol') last.items.push(ol[1])
      else blocks.push({ kind: 'ol', items: [ol[1]] })
      continue
    }

    if (last?.kind === 'p' && last.lines.length > 0) last.lines.push(trimmed)
    else blocks.push({ kind: 'p', lines: [trimmed] })
  }

  return blocks.filter((b) => b.kind !== 'p' || b.lines.length > 0)
}

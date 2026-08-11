/**
 * SPEC-302's own deliberately narrow command recognizer -- not real NLP,
 * not agentic tool-calling (SPEC-204's eventual job). A message either
 * matches one of exactly two real commands, or it's a plain chat turn.
 * A pure function on purpose: testable in isolation, no side effects,
 * no knowledge of conversation state (e.g. whether anything has been
 * generated yet -- that check belongs to the caller, which actually
 * holds that state).
 */
export type Command =
  | { type: 'generate'; partNumber: string }
  | { type: 'inject' }
  | { type: 'chat'; message: string }

const GENERATE_PATTERN = /^generate\s+(.+)$/i
const INJECT_PATTERN = /^inject$/i

export function parseCommand(input: string): Command {
  const trimmed = input.trim()

  const generateMatch = trimmed.match(GENERATE_PATTERN)
  if (generateMatch) {
    return { type: 'generate', partNumber: generateMatch[1].trim() }
  }

  if (INJECT_PATTERN.test(trimmed)) {
    return { type: 'inject' }
  }

  return { type: 'chat', message: trimmed }
}

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Markdown } from './Markdown'
import { parseBlocks } from '../lib/markdown'

/** Reported from the PCB chat: the agent's Markdown rendered as literal `###`
 *  and `**` runs in one collapsed wall of text. */
describe('parseBlocks', () => {
  it('recognises headings, and does not treat them as prose', () => {
    expect(parseBlocks('### What is a "Net"?')).toEqual([
      { kind: 'heading', level: 3, text: 'What is a "Net"?' },
    ])
  })

  it('groups consecutive bullets into one list', () => {
    const blocks = parseBlocks('* one\n* two\n* three')
    expect(blocks).toHaveLength(1)
    expect(blocks[0]).toEqual({ kind: 'ul', items: ['one', 'two', 'three'] })
  })

  it('keeps numbered steps ordered and separate from bullets', () => {
    const blocks = parseBlocks('1. first\n2. second\n* aside')
    expect(blocks.map((b) => b.kind)).toEqual(['ol', 'ul'])
  })

  it('treats --- as a rule, not as a bullet or as text', () => {
    expect(parseBlocks('a\n\n---\n\nb').map((b) => b.kind)).toEqual(['p', 'hr', 'p'])
  })

  it('joins wrapped lines into one paragraph but keeps blank-line breaks', () => {
    const blocks = parseBlocks('one line\nstill same para\n\nnew para')
    expect(blocks).toEqual([
      { kind: 'p', lines: ['one line', 'still same para'] },
      { kind: 'p', lines: ['new para'] },
    ])
  })

  it('does not emit empty paragraphs for runs of blank lines', () => {
    expect(parseBlocks('\n\n\na\n\n\n')).toEqual([{ kind: 'p', lines: ['a'] }])
  })
})

describe('Markdown rendering', () => {
  it('renders bold as emphasis rather than showing asterisks', () => {
    render(<Markdown text="a **net** is a group of pins" />)
    expect(screen.getByText('net').tagName).toBe('STRONG')
    expect(screen.queryByText(/\*\*/)).toBeNull()
  })

  it('renders inline code as code, not backticks', () => {
    render(<Markdown text="press `B` to refill" />)
    expect(screen.getByText('B').tagName).toBe('CODE')
  })

  it('renders bold containing code, innermost first', () => {
    render(<Markdown text="the **`VCC` net**" />)
    expect(screen.getByText('VCC').tagName).toBe('CODE')
    expect(screen.getByText('VCC').closest('strong')).not.toBeNull()
  })

  it('takes the earliest span when several kinds are present', () => {
    render(<Markdown text="**bold** then `code`" />)
    expect(screen.getByText('bold').tagName).toBe('STRONG')
    expect(screen.getByText('code').tagName).toBe('CODE')
  })

  it('renders a real list, so steps are readable as steps', () => {
    // Braces, not a plain string attribute: JSX does not process escape
    // sequences in `attr="..."`, so `text="a\nb"` passes a literal backslash-n
    // and the list silently parses as one line.
    const { container } = render(<Markdown text={'1. route it\n2. save it'} />)
    expect(container.querySelectorAll('ol li')).toHaveLength(2)
  })

  it('never injects markup -- model output is text, not HTML', () => {
    const { container } = render(<Markdown text={'<img src=x onerror="alert(1)"> **b**'} />)
    // The tag is shown as characters. Nothing here uses dangerouslySetInnerHTML,
    // so there is no path for model output to become an element.
    expect(container.querySelector('img')).toBeNull()
    expect(container.textContent).toContain('<img src=x')
  })

  it('shows unsupported syntax as written rather than swallowing it', () => {
    const { container } = render(<Markdown text="| a | b |" />)
    expect(container.textContent).toContain('| a | b |')
  })

  it('handles the real answer shape from the reported screenshot', () => {
    const { container } = render(
      <Markdown text={'### What is a "Net"?\n\nA **net** is a group of pins.\n\n* the `VCC` net\n* the `GND` net\n\n---\n\n1. Open the DRC dialog\n2. Route the trace'} />,
    )
    expect(container.querySelectorAll('ul li')).toHaveLength(2)
    expect(container.querySelectorAll('ol li')).toHaveLength(2)
    expect(container.querySelector('hr')).not.toBeNull()
    expect(container.textContent).not.toContain('###')
    expect(container.textContent).not.toContain('**')
  })
})

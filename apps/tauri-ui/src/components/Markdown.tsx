import { parseBlocks, renderInline } from '../lib/markdown'

export function Markdown({ text, className }: { text: string; className?: string }) {
  const blocks = parseBlocks(text)

  return (
    <div className={`flex flex-col gap-2 ${className ?? ''}`}>
      {blocks.map((block, i) => {
        const key = `b${i}`
        if (block.kind === 'hr') return <hr key={key} className="border-line-subtle" />
        if (block.kind === 'heading') {
          // One visual weight for every level: these are short answer
          // sections, not a document outline, and h1-through-h6 scaling
          // inside a chat bubble reads as noise.
          return (
            <p key={key} className="text-sm font-semibold text-fg-bright">
              {renderInline(block.text, key)}
            </p>
          )
        }
        if (block.kind === 'ul' || block.kind === 'ol') {
          const List = block.kind === 'ul' ? 'ul' : 'ol'
          return (
            <List
              key={key}
              className={`flex flex-col gap-1 pl-5 ${
                block.kind === 'ul' ? 'list-disc' : 'list-decimal'
              }`}
            >
              {block.items.map((item, j) => (
                <li key={`${key}l${j}`}>{renderInline(item, `${key}l${j}`)}</li>
              ))}
            </List>
          )
        }
        return <p key={key}>{renderInline(block.lines.join(' '), key)}</p>
      })}
    </div>
  )
}

import { useState } from 'react'
import { dispatch, type JsonRpcResponse } from './lib/ipc'

function App() {
  const [query, setQuery] = useState('')
  const [pending, setPending] = useState(false)
  const [response, setResponse] = useState<JsonRpcResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function handleGenerate() {
    setPending(true)
    setError(null)
    try {
      const result = await dispatch('kicad.generate_component', { query })
      setResponse(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setPending(false)
    }
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-neutral-950 p-8 text-neutral-100">
      <h1 className="text-2xl font-medium">Hardware Agent Studio</h1>
      <div className="flex w-full max-w-md gap-2">
        <input
          className="flex-1 rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
          placeholder="e.g. BME280"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          disabled={pending}
        />
        <button
          type="button"
          className="rounded bg-neutral-100 px-4 py-2 text-sm font-medium text-neutral-950 disabled:opacity-50"
          onClick={handleGenerate}
          disabled={pending || query.trim().length === 0}
        >
          {pending ? 'Generating…' : 'Generate'}
        </button>
      </div>
      {error && <p className="text-sm text-red-400">{error}</p>}
      {response && (
        <pre className="w-full max-w-md overflow-auto rounded bg-neutral-900 p-3 text-xs">
          {JSON.stringify(response, null, 2)}
        </pre>
      )}
    </main>
  )
}

export default App

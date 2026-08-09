import { useState } from 'react'
import { dispatch, submitJob, type JobHandle, type JsonRpcResponse } from './lib/ipc'
import { EnclosureViewer } from './components/EnclosureViewer'

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
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 bg-neutral-950 p-8 text-neutral-100">
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
      <EnclosurePanel />
    </main>
  )
}

/** Proves out CTX-105.2's job client against the one real async route
 * CTX-105.1 wired up (freecad.generate_enclosure): submit, watch progress,
 * cancel mid-flight, or land on a completed/failed result. */
function EnclosurePanel() {
  const [dims, setDims] = useState({ width: 50, depth: 30, height: 20 })
  const [job, setJob] = useState<JobHandle<string> | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [glbPath, setGlbPath] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const running = status === 'running'

  async function handleGenerate() {
    setError(null)
    setGlbPath(null)
    setStatus('running')

    try {
      const handle = await submitJob<string>('freecad.generate_enclosure', dims)
      setJob(handle)
      handle.onUpdate((update) => setStatus(update.status))

      const path = await handle.result
      setGlbPath(path)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setJob(null)
    }
  }

  async function handleCancel() {
    await job?.cancel()
  }

  return (
    <div className="flex w-full max-w-md flex-col gap-2 border-t border-neutral-800 pt-6">
      <h2 className="text-sm font-medium text-neutral-400">Enclosure Generator</h2>
      <div className="flex gap-2">
        {(['width', 'depth', 'height'] as const).map((dim) => (
          <input
            key={dim}
            type="number"
            className="w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm"
            placeholder={dim}
            value={dims[dim]}
            onChange={(e) => setDims((prev) => ({ ...prev, [dim]: Number(e.target.value) }))}
            disabled={running}
          />
        ))}
      </div>
      <div className="flex gap-2">
        <button
          type="button"
          className="flex-1 rounded bg-neutral-100 px-4 py-2 text-sm font-medium text-neutral-950 disabled:opacity-50"
          onClick={handleGenerate}
          disabled={running}
        >
          {running ? 'Generating…' : 'Generate Enclosure'}
        </button>
        {running && (
          <button
            type="button"
            className="rounded border border-neutral-700 px-4 py-2 text-sm font-medium disabled:opacity-50"
            onClick={handleCancel}
          >
            Cancel
          </button>
        )}
      </div>
      {error && <p className="text-sm text-red-400">{error}</p>}
      {glbPath && (
        <>
          <p className="text-sm text-neutral-400">Generated: {glbPath}</p>
          <EnclosureViewer glbPath={glbPath} />
        </>
      )}
    </div>
  )
}

export default App

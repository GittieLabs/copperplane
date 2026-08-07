import { invoke } from '@tauri-apps/api/core'
import { listen, type UnlistenFn } from '@tauri-apps/api/event'

/** Must match `daemon::DAEMON_RESPONSE_EVENT` in core/tauri-rust/src/daemon.rs. */
export const DAEMON_RESPONSE_EVENT = 'daemon://response'

export interface JsonRpcError {
  code: number
  message: string
}

export interface JsonRpcResponse<T = unknown> {
  jsonrpc: '2.0'
  id: number | null
  result?: T
  error?: JsonRpcError
}

interface PendingRequest {
  resolve: (response: JsonRpcResponse) => void
}

let nextRequestId = 1
let unlisten: UnlistenFn | null = null
let listening: Promise<void> | null = null
const pending = new Map<number, PendingRequest>()
let inFlight = false

async function ensureListening(): Promise<void> {
  if (unlisten) return
  if (!listening) {
    listening = listen<string>(DAEMON_RESPONSE_EVENT, (event) => {
      let response: JsonRpcResponse
      try {
        // Security: the daemon's stdout is untrusted input. Only ever
        // JSON.parse it — never eval() — per SPEC-101's security
        // constraints. A line that isn't valid JSON-RPC is dropped.
        response = JSON.parse(event.payload)
      } catch {
        return
      }

      if (response.id === null || response.id === undefined) return
      const waiter = pending.get(response.id)
      if (!waiter) return
      pending.delete(response.id)
      waiter.resolve(response)
    }).then((fn) => {
      unlisten = fn
    })
  }
  await listening
}

/** True while a dispatch is awaiting its response. */
export function isDispatchInFlight(): boolean {
  return inFlight
}

/**
 * Sends one JSON-RPC request to the Python daemon via the Rust
 * `dispatch_to_daemon` command and resolves with its matching response.
 *
 * Rejects immediately, without touching the daemon's stdin, if another
 * dispatch is already in flight — the daemon processes one line at a
 * time, so queuing a second request here would just spam its stdin
 * buffer with conflicting commands (SPEC-101 §3).
 */
export async function dispatch(
  method: string,
  params: Record<string, unknown> = {},
): Promise<JsonRpcResponse> {
  if (inFlight) {
    throw new Error('A daemon request is already in flight')
  }
  inFlight = true

  const id = nextRequestId++
  try {
    await ensureListening()

    const responsePromise = new Promise<JsonRpcResponse>((resolve) => {
      pending.set(id, { resolve })
    })

    const request = { jsonrpc: '2.0' as const, method, params, id }
    await invoke('dispatch_to_daemon', { request: JSON.stringify(request) })

    return await responsePromise
  } finally {
    inFlight = false
    pending.delete(id)
  }
}

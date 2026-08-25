import { invoke } from '@tauri-apps/api/core'
import { listen, type UnlistenFn } from '@tauri-apps/api/event'

/** Must match `daemon::DAEMON_RESPONSE_EVENT` in core/tauri-rust/src/daemon.rs. */
export const DAEMON_RESPONSE_EVENT = 'daemon://response'

/** CTX-312.3: real native menu clicks -- must match `menu::
 * MENU_SAVE_PROJECT_EVENT`/`MENU_OPEN_PROJECT_EVENT` in
 * `core/tauri-rust/src/menu.rs`. */
export const MENU_SAVE_PROJECT_EVENT = 'menu://save-project'
export const MENU_OPEN_PROJECT_EVENT = 'menu://open-project'

/** CTX-316.1: the rest of the native menu's command surface -- each
 * must match its own const of the same name in
 * `core/tauri-rust/src/menu.rs`. */
export const MENU_OPEN_SETTINGS_EVENT = 'menu://open-settings'
export const MENU_OPEN_DEFAULT_LIBRARY_EVENT = 'menu://open-library-default'
export const MENU_MANAGE_LIBRARIES_EVENT = 'menu://manage-libraries'
export const MENU_DESIGN_SCHEMATIC_OPEN_KICAD_EVENT = 'menu://design/schematic/open-kicad'
export const MENU_DESIGN_SCHEMATIC_PICK_MANUALLY_EVENT = 'menu://design/schematic/pick-manually'
export const MENU_DESIGN_PCB_OPEN_KICAD_EVENT = 'menu://design/pcb/open-kicad'
export const MENU_DESIGN_ENCLOSURE_OPEN_KICAD_EVENT = 'menu://design/enclosure/open-kicad'
export const MENU_DESIGN_ENCLOSURE_PICK_PCB_EVENT = 'menu://design/enclosure/pick-pcb'
export const MENU_DESIGN_ENCLOSURE_GENERATE_EVENT = 'menu://design/enclosure/generate'
/** CTX-319.6, SPEC-319 §2.4: Run Review, one per applicable Design
 * submenu -- Overview/Components have no submenu at all (unchanged by
 * this phase). */
export const MENU_DESIGN_SCHEMATIC_RUN_REVIEW_EVENT = 'menu://design/schematic/run-review'
export const MENU_DESIGN_PCB_RUN_REVIEW_EVENT = 'menu://design/pcb/run-review'
export const MENU_DESIGN_ENCLOSURE_RUN_REVIEW_EVENT = 'menu://design/enclosure/run-review'

/** CTX-316.2: payload is the real, dynamically-listed custom library's
 * own id -- unlike every other MENU_* event above, this one can't have
 * a compile-time-fixed set, so it carries a real payload instead of one
 * const per library. Must match `menu::MENU_OPEN_LIBRARY_EVENT`. */
export const MENU_OPEN_LIBRARY_EVENT = 'menu://open-library'

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

/** A `job.*` event (CTX-105.1) -- unlike a response, it carries no `id`
 * at all, which is exactly how the listener below tells the two apart. */
interface JsonRpcNotification {
  jsonrpc: '2.0'
  method: string
  params?: { job_id?: string; result?: unknown; error?: string }
}

interface PendingRequest {
  resolve: (response: JsonRpcResponse) => void
}

export type JobStatus = 'running' | 'completed' | 'failed' | 'cancelled'

export interface JobUpdate {
  status: JobStatus
  result?: unknown
  error?: string
}

interface JobEntry {
  listeners: Set<(update: JobUpdate) => void>
  resolve: (result: unknown) => void
  reject: (error: Error) => void
}

export interface JobHandle<T = unknown> {
  jobId: string
  /** Resolves on `job.completed`; rejects on `job.failed` or `job.cancelled`. */
  result: Promise<T>
  /** Subscribes to every job.* update for this job, including `job.progress`.
   * Returns an unsubscribe function. */
  onUpdate(listener: (update: JobUpdate) => void): () => void
  /** Requests cancellation via the `job.cancel` route. This does not itself
   * settle `result` -- that still arrives as a `job.cancelled` update, same
   * as it would for a cancellation the daemon decided on its own. */
  cancel(): Promise<void>
}

let nextRequestId = 1
let unlisten: UnlistenFn | null = null
let listening: Promise<void> | null = null
const pending = new Map<number, PendingRequest>()
const jobs = new Map<string, JobEntry>()

function isNotification(payload: unknown): payload is JsonRpcNotification {
  return (
    typeof payload === 'object' &&
    payload !== null &&
    typeof (payload as JsonRpcNotification).method === 'string' &&
    !('id' in payload)
  )
}

function handleJobNotification(notification: JsonRpcNotification): void {
  const jobId = notification.params?.job_id
  if (!jobId) return
  const entry = jobs.get(jobId)
  if (!entry) return

  switch (notification.method) {
    case 'job.progress':
      entry.listeners.forEach((listener) => listener({ status: 'running' }))
      return
    case 'job.completed':
      entry.listeners.forEach((listener) => listener({ status: 'completed', result: notification.params?.result }))
      entry.resolve(notification.params?.result)
      jobs.delete(jobId)
      return
    case 'job.failed': {
      const message = notification.params?.error ?? 'Job failed'
      entry.listeners.forEach((listener) => listener({ status: 'failed', error: message }))
      entry.reject(new Error(message))
      jobs.delete(jobId)
      return
    }
    case 'job.cancelled':
      entry.listeners.forEach((listener) => listener({ status: 'cancelled' }))
      entry.reject(new Error('Job was cancelled'))
      jobs.delete(jobId)
      return
  }
}

async function ensureListening(): Promise<void> {
  if (unlisten) return
  if (!listening) {
    listening = listen<string>(DAEMON_RESPONSE_EVENT, (event) => {
      let payload: unknown
      try {
        // Security: the daemon's stdout is untrusted input. Only ever
        // JSON.parse it — never eval() — per SPEC-101's security
        // constraints. A line that isn't valid JSON-RPC is dropped.
        payload = JSON.parse(event.payload)
      } catch {
        return
      }

      if (isNotification(payload)) {
        handleJobNotification(payload)
        return
      }

      const response = payload as JsonRpcResponse
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

/**
 * Sends one JSON-RPC request to the Python daemon via the Rust
 * `dispatch_to_daemon` command and resolves with its matching response.
 *
 * Concurrent calls are safe: each request gets its own `id`, and the
 * daemon's response always echoes it back, so multiple in-flight
 * dispatches resolve independently regardless of arrival order (CTX-105.2
 * -- CTX-101.1's original hard single-in-flight guard was never protocol
 * load-bearing, only a conservative stdin-spam precaution).
 */
export async function dispatch(
  method: string,
  params: Record<string, unknown> = {},
): Promise<JsonRpcResponse> {
  const id = nextRequestId++
  await ensureListening()

  const responsePromise = new Promise<JsonRpcResponse>((resolve) => {
    pending.set(id, { resolve })
  })

  const request = { jsonrpc: '2.0' as const, method, params, id }
  await invoke('dispatch_to_daemon', { request: JSON.stringify(request) })

  try {
    return await responsePromise
  } finally {
    pending.delete(id)
  }
}

/** Builds a `JobHandle` for an already-known `job_id` -- the shared tail
 * end of `submitJob` and `dispatchTool` (CTX-204.1's `agent.dispatch_tool`
 * only sometimes returns a job_id; when it does, tracking it works
 * identically to any other async route). */
function buildJobHandle<T>(jobId: string): JobHandle<T> {
  let resolveResult!: (result: T) => void
  let rejectResult!: (error: Error) => void
  const result = new Promise<T>((resolve, reject) => {
    resolveResult = resolve
    rejectResult = reject
  })

  const listeners = new Set<(update: JobUpdate) => void>()
  jobs.set(jobId, {
    listeners,
    resolve: resolveResult as (result: unknown) => void,
    reject: rejectResult,
  })

  return {
    jobId,
    result,
    onUpdate(listener) {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    async cancel() {
      const cancelResponse = await dispatch('job.cancel', { job_id: jobId })
      if (cancelResponse.error) {
        throw new Error(cancelResponse.error.message)
      }
    },
  }
}

/**
 * Dispatches a request to an async-flagged route (CTX-105.1) and returns
 * a handle for tracking that job's progress, completion, and cancellation
 * -- rather than the immediate `{"job_id": ...}` acknowledgement response
 * itself, which callers rarely want directly.
 */
export async function submitJob<T = unknown>(
  method: string,
  params: Record<string, unknown> = {},
): Promise<JobHandle<T>> {
  const response = await dispatch(method, params)
  if (response.error) {
    throw new Error(response.error.message)
  }

  const jobId = (response.result as { job_id?: string } | undefined)?.job_id
  if (!jobId) {
    throw new Error(`${method} did not return a job_id -- is it registered in ASYNC_ROUTES?`)
  }

  return buildJobHandle<T>(jobId)
}

/**
 * `dispatchTool`'s result -- a real discriminated union tagged on `kind`,
 * not `PendingToolConfirmation`/`JobHandle` structurally distinguished by
 * which fields happen to be present. `JobHandle` is a plain interface
 * used elsewhere (`submitJob`) with no exclusions on extra fields, so
 * TypeScript's structural typing can't safely narrow "not pending" to
 * "must be a JobHandle" without an explicit tag -- confirmed directly by
 * `tsc` rejecting the untagged version of this type during Phase 1.
 */
export type ToolDispatchOutcome<T> =
  | { kind: 'pending_confirmation'; tool: string; input: Record<string, unknown> }
  | { kind: 'dispatched'; handle: JobHandle<T> }

/**
 * Calls a SPEC-204-registered tool through `agent.dispatch_tool`. An
 * unconfirmed call to a gated tool (e.g. `kicad.inject_component`)
 * returns `{kind: 'pending_confirmation', ...}` synchronously, with no
 * side effects and no job -- the caller must re-invoke with
 * `confirmed: true` to actually run it. A non-gated tool, or an
 * already-confirmed call, returns `{kind: 'dispatched', handle}` with a
 * real `JobHandle` exactly like `submitJob`, since `agent.dispatch_tool`
 * reuses the same async job protocol underneath (CTX-204.1 SS2).
 */
export async function dispatchTool<T = unknown>(
  toolName: string,
  toolInput: Record<string, unknown>,
  confirmed = false,
): Promise<ToolDispatchOutcome<T>> {
  const response = await dispatch('agent.dispatch_tool', { tool_name: toolName, tool_input: toolInput, confirmed })
  if (response.error) {
    throw new Error(response.error.message)
  }

  const result = response.result as { status?: string; tool?: string; input?: Record<string, unknown>; job_id?: string } | undefined
  if (result?.status === 'pending_confirmation') {
    return { kind: 'pending_confirmation', tool: result.tool ?? toolName, input: result.input ?? toolInput }
  }

  if (!result?.job_id) {
    throw new Error(`agent.dispatch_tool for ${toolName} returned neither pending_confirmation nor a job_id`)
  }

  return { kind: 'dispatched', handle: buildJobHandle<T>(result.job_id) }
}

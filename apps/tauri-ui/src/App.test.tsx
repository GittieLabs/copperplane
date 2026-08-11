import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach } from 'vitest'

const submitJobMock = vi.fn()

vi.mock('./lib/ipc', () => ({
  submitJob: (...args: unknown[]) => submitJobMock(...args),
}))

vi.mock('./components/EnclosureViewer', () => ({
  EnclosureViewer: () => null,
}))

const { default: App } = await import('./App')

/** Builds a fake JobHandle whose `result` resolves/rejects on demand --
 * enough for these tests without a real daemon round-trip. A pre-built
 * rejected promise needs a synchronous no-op `.catch` attached here, or
 * Node reports it as an unhandled rejection before `handleInject`'s own
 * `await` ever gets a chance to observe it -- attaching a handler doesn't
 * consume the rejection for other observers, it just satisfies this check. */
function fakeJobHandle<T>(result: Promise<T>) {
  result.catch(() => {})
  return { jobId: 'job_1', result, onUpdate: () => () => {}, cancel: vi.fn() }
}

describe('App: generate then inject', () => {
  beforeEach(() => {
    submitJobMock.mockReset()
  })

  it('TEST-001: a successful generate shows the schema and an Inject button', async () => {
    const schema = { part_number: 'ATtiny85', package: 'SOIC-8', pins: [] }
    submitJobMock.mockResolvedValueOnce(fakeJobHandle(Promise.resolve(schema)))

    render(<App />)
    fireEvent.change(screen.getByPlaceholderText('e.g. ATtiny85'), { target: { value: 'ATtiny85' } })
    fireEvent.click(screen.getByRole('button', { name: 'Generate' }))

    await waitFor(() => screen.getByText(/"part_number": "ATtiny85"/))
    expect(screen.getByRole('button', { name: 'Inject into Board' })).toBeTruthy()
  })

  it('TEST-002: clicking Inject calls kicad.inject_component with the generated schema and reports success', async () => {
    const schema = { part_number: 'ATtiny85', package: 'SOIC-8', pins: [] }
    submitJobMock.mockResolvedValueOnce(fakeJobHandle(Promise.resolve(schema)))
    submitJobMock.mockResolvedValueOnce(
      fakeJobHandle(Promise.resolve({ part_number: 'ATtiny85', package: 'SOIC-8', pins: 8 })),
    )

    render(<App />)
    fireEvent.change(screen.getByPlaceholderText('e.g. ATtiny85'), { target: { value: 'ATtiny85' } })
    fireEvent.click(screen.getByRole('button', { name: 'Generate' }))
    await waitFor(() => screen.getByRole('button', { name: 'Inject into Board' }))

    fireEvent.click(screen.getByRole('button', { name: 'Inject into Board' }))

    await waitFor(() => screen.getByText('Injected into the open board.'))

    expect(submitJobMock).toHaveBeenLastCalledWith('kicad.inject_component', {
      schema,
      x_mm: 50,
      y_mm: 50,
    })
  })

  it('TEST-003: a KiCad write failure shows the real error, not a generic message', async () => {
    const schema = { part_number: 'ATtiny85', package: 'SOIC-8', pins: [] }
    submitJobMock.mockResolvedValueOnce(fakeJobHandle(Promise.resolve(schema)))
    submitJobMock.mockResolvedValueOnce(
      fakeJobHandle(Promise.reject(new Error('Could not connect to KiCad.'))),
    )

    render(<App />)
    fireEvent.change(screen.getByPlaceholderText('e.g. ATtiny85'), { target: { value: 'ATtiny85' } })
    fireEvent.click(screen.getByRole('button', { name: 'Generate' }))
    await waitFor(() => screen.getByRole('button', { name: 'Inject into Board' }))

    fireEvent.click(screen.getByRole('button', { name: 'Inject into Board' }))

    await waitFor(() => screen.getByText('Could not connect to KiCad.'))
    expect(screen.queryByText('Injected into the open board.')).toBeNull()
  })
})

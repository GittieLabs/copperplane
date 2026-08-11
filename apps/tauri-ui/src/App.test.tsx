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
 * Node reports it as an unhandled rejection before the caller's own
 * `await` ever gets a chance to observe it -- attaching a handler
 * doesn't consume the rejection for other observers, it just satisfies
 * this check. */
function fakeJobHandle<T>(result: Promise<T>) {
  result.catch(() => {})
  return { jobId: 'job_1', result, onUpdate: () => () => {}, cancel: vi.fn() }
}

function sendMessage(text: string) {
  fireEvent.change(screen.getByPlaceholderText(/generate ATtiny85/), { target: { value: text } })
  fireEvent.click(screen.getByRole('button', { name: 'Send' }))
}

describe('App: chat & command surface', () => {
  beforeEach(() => {
    submitJobMock.mockReset()
  })

  it('TEST-001: "generate <part>" calls kicad.generate_component and renders the schema', async () => {
    const schema = { part_number: 'ATtiny85', package: 'SOIC-8', pins: [] }
    submitJobMock.mockResolvedValueOnce(fakeJobHandle(Promise.resolve(schema)))

    render(<App />)
    sendMessage('generate ATtiny85')

    await waitFor(() => screen.getByText(/"part_number": "ATtiny85"/))
    expect(submitJobMock).toHaveBeenLastCalledWith('kicad.generate_component', {
      part_number: 'ATtiny85',
    })
    screen.getByText('Generated ATtiny85 (SOIC-8)')
  })

  it('TEST-002: "inject" with a schema already generated calls kicad.inject_component and reports success', async () => {
    const schema = { part_number: 'ATtiny85', package: 'SOIC-8', pins: [] }
    submitJobMock.mockResolvedValueOnce(fakeJobHandle(Promise.resolve(schema)))
    submitJobMock.mockResolvedValueOnce(
      fakeJobHandle(Promise.resolve({ part_number: 'ATtiny85', package: 'SOIC-8', pins: 8 })),
    )

    render(<App />)
    sendMessage('generate ATtiny85')
    await waitFor(() => screen.getByText(/"part_number": "ATtiny85"/))

    sendMessage('inject')

    await waitFor(() => screen.getByText('Injected into the open board.'))
    expect(submitJobMock).toHaveBeenLastCalledWith('kicad.inject_component', {
      schema,
      x_mm: 50,
      y_mm: 50,
    })
  })

  it('TEST-003: "inject" with nothing generated yet shows a clean message, never calls the route', async () => {
    render(<App />)
    sendMessage('inject')

    await waitFor(() => screen.getByText('Nothing to inject yet — generate a component first.'))
    expect(submitJobMock).not.toHaveBeenCalled()
  })

  it('TEST-004: an unrecognized message is a plain chat turn against llm.chat, rendering the real reply', async () => {
    submitJobMock.mockResolvedValueOnce(fakeJobHandle(Promise.resolve('Pin 3 is a GPIO pin.')))

    render(<App />)
    sendMessage('what does pin 3 do?')

    await waitFor(() => screen.getByText('Pin 3 is a GPIO pin.'))
    expect(submitJobMock).toHaveBeenLastCalledWith('llm.chat', {
      prompt: 'what does pin 3 do?',
      history: [],
    })
  })

  it('TEST-005: a second plain chat turn sends the first turn back as history', async () => {
    submitJobMock.mockResolvedValueOnce(fakeJobHandle(Promise.resolve('Got it, 42.')))
    submitJobMock.mockResolvedValueOnce(fakeJobHandle(Promise.resolve('42.')))

    render(<App />)
    sendMessage('my favorite number is 42')
    await waitFor(() => screen.getByText('Got it, 42.'))

    sendMessage('what is my favorite number?')
    await waitFor(() => screen.getByText('42.'))

    expect(submitJobMock).toHaveBeenLastCalledWith('llm.chat', {
      prompt: 'what is my favorite number?',
      history: [
        { role: 'user', content: 'my favorite number is 42' },
        { role: 'assistant', content: 'Got it, 42.' },
      ],
    })
  })

  it('TEST-006: a generate failure shows the real error, not a generic message', async () => {
    submitJobMock.mockResolvedValueOnce(
      fakeJobHandle(Promise.reject(new Error("Package 'FOO-1' is not in the known reference table."))),
    )

    render(<App />)
    sendMessage('generate FOO-1')

    await waitFor(() => screen.getByText("Package 'FOO-1' is not in the known reference table."))
  })
})

import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { RequirementsBanner } from './RequirementsBanner'
import type { DaemonCapabilities } from '../lib/settings'

const READY: DaemonCapabilities = {
  kicad_available: false,
  kicad_socket_path_checked: '/tmp/kicad/api.sock',
  freecad_available: true,
  freecad_path_checked: '/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd',
  freecad_error: null,
  kicad_cli_available: true,
  kicad_cli_path_checked: '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli',
  kicad_cli_path_source: 'install',
  kicad_cli_error: null,
  llm_providers: ['anthropic'],
  log_path: '/tmp/daemon.log',
  python_version: '3.11.9',
  storage_root: '/data',
  github_token_configured: false,
  configured_secret_refs: ['anthropic_api_key'],
}

/** CTX-336.1 Phase 2. SPEC-336 removed its own hard gate and put the weight
 *  here instead: "Blocking the user may not be the answer. We could replace
 *  this with banner messages ... and still let the user get to the main app
 *  and fix later." */
describe('RequirementsBanner', () => {
  it('says nothing at all when everything is present', () => {
    const { container } = render(
      <RequirementsBanner capabilities={READY} onOpenSetup={() => {}} />,
    )

    expect(container.textContent).toBe('')
  })

  it('renders nothing before capabilities have loaded', () => {
    /** A banner that flashes "KiCad not found" for a moment on every launch
     *  would train the user to ignore it. */
    const { container } = render(
      <RequirementsBanner capabilities={null} onOpenSetup={() => {}} />,
    )

    expect(container.textContent).toBe('')
  })

  it('names the tool and what specifically stops working', () => {
    /** SPEC-336 §3 requires this be specific, "not a generic 'setup
     *  incomplete'" -- a generic banner sends the user off to guess. */
    render(
      <RequirementsBanner
        capabilities={{ ...READY, kicad_cli_available: false, kicad_cli_error: 'Could not find the kicad-cli executable.' }}
        onOpenSetup={() => {}}
      />,
    )

    expect(screen.getByText(/KiCad was not found/)).toBeTruthy()
    expect(screen.getByText(/an enclosure cannot be measured from your board/)).toBeTruthy()
  })

  it('blames the configured path when that is what failed', () => {
    /** The likeliest misconfiguration once a picker exists. "Not found" would
     *  send the user hunting for a KiCad they have actually installed. */
    render(
      <RequirementsBanner
        capabilities={{
          ...READY,
          kicad_cli_available: false,
          kicad_cli_path_source: 'override',
          kicad_cli_error: 'Configured kicad-cli path override does not exist: /old/kicad-cli',
        }}
        onOpenSetup={() => {}}
      />,
    )

    expect(screen.getByText(/The configured path did not work/)).toBeTruthy()
    expect(screen.getByText(/\/old\/kicad-cli/)).toBeTruthy()
  })

  it('reports a missing provider without overstating it', () => {
    /** Reviews and chat stop; reading files does not. Saying "nothing works"
     *  would be false and would push a hesitant user into pasting a key. */
    render(
      <RequirementsBanner capabilities={{ ...READY, llm_providers: [] }} onOpenSetup={() => {}} />,
    )

    expect(screen.getByText(/No AI provider is configured/)).toBeTruthy()
    expect(screen.getByText(/Everything that reads your files still works/)).toBeTruthy()
  })

  it('counts more than one missing thing', () => {
    render(
      <RequirementsBanner
        capabilities={{ ...READY, kicad_cli_available: false, freecad_available: false, llm_providers: [] }}
        onOpenSetup={() => {}}
      />,
    )

    expect(screen.getByText('3 things are missing before Copperplane can do everything')).toBeTruthy()
  })

  it('collapses to a strip that still carries the way back into setup', () => {
    /** SPEC-336 §3: "A dismissible banner is the trap in a different
     *  costume ... whatever dismissal exists must keep a way back to the
     *  guided setup permanently visible." */
    const onOpenSetup = vi.fn()
    render(
      <RequirementsBanner
        capabilities={{ ...READY, kicad_cli_available: false }}
        onOpenSetup={onOpenSetup}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Collapse' }))

    expect(screen.queryByText(/Board and schematic checks cannot run/)).toBeNull()
    expect(screen.getByText(/Setup incomplete: KiCad/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Finish setting up' }))
    expect(onOpenSetup).toHaveBeenCalledWith('kicad')
  })

  it('has no control that makes it go away while the problem remains', () => {
    render(
      <RequirementsBanner
        capabilities={{ ...READY, kicad_cli_available: false }}
        onOpenSetup={() => {}}
      />,
    )

    for (const label of [/dismiss/i, /never show/i, /don't show/i, /close/i]) {
      expect(screen.queryByRole('button', { name: label })).toBeNull()
    }
  })

  it('can be expanded again after collapsing', () => {
    render(
      <RequirementsBanner
        capabilities={{ ...READY, kicad_cli_available: false }}
        onOpenSetup={() => {}}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Collapse' }))
    fireEvent.click(screen.getByRole('button', { name: 'Show details' }))

    expect(screen.getByText(/Board and schematic checks cannot run/)).toBeTruthy()
  })

  it('offers a re-check, so fixing it outside the app is noticed', () => {
    const onRecheck = vi.fn()
    render(
      <RequirementsBanner
        capabilities={{ ...READY, kicad_cli_available: false }}
        onOpenSetup={() => {}}
        onRecheck={onRecheck}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Check again' }))
    expect(onRecheck).toHaveBeenCalled()
  })

  it('routes each requirement to its own setup step', () => {
    const onOpenSetup = vi.fn()
    render(
      <RequirementsBanner
        capabilities={{ ...READY, freecad_available: false, llm_providers: [] }}
        onOpenSetup={onOpenSetup}
      />,
    )

    const fixButtons = screen.getAllByRole('button', { name: 'Fix this' })
    fireEvent.click(fixButtons[0])
    expect(onOpenSetup).toHaveBeenCalledWith('freecad')
    fireEvent.click(fixButtons[1])
    expect(onOpenSetup).toHaveBeenCalledWith('provider')
  })
})

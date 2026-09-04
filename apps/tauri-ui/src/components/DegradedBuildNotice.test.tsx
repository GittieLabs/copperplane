import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { DegradedBuildNotice } from './DegradedBuildNotice'
import type { DaemonCapabilities } from '../lib/settings'

const HEALTHY: DaemonCapabilities = {
  kicad_available: true,
  kicad_socket_path_checked: '/tmp/kicad/api.sock',
  freecad_available: true,
  freecad_path_checked: '/f/freecadcmd',
  freecad_error: null,
  kicad_cli_available: true,
  kicad_cli_path_checked: '/k/kicad-cli',
  kicad_cli_path_source: 'install',
  kicad_cli_error: null,
  llm_providers: ['anthropic'],
  log_path: '/Users/k/Library/Logs/copperplane/daemon.log',
  python_version: '3.11.9',
  storage_root: '/s',
  github_token_configured: false,
  degraded_modules: [],
  configured_secret_refs: [],
}

/** SPEC-407 §5. §1 calls this failure worse than a crash: "a crash sends you to
 *  the packaging; a healthy-looking daemon ... sends you hunting for a UI bug
 *  that does not exist." */
describe('DegradedBuildNotice', () => {
  it('says nothing when the build is whole', () => {
    const { container } = render(<DegradedBuildNotice capabilities={HEALTHY} />)

    expect(container.textContent).toBe('')
  })

  it('says nothing before capabilities have loaded', () => {
    const { container } = render(<DegradedBuildNotice capabilities={null} />)

    expect(container.textContent).toBe('')
  })

  it('blames the build, not the app and not the user', () => {
    /** The whole point: a user must not conclude the product is broken, or
     *  file a bug against a UI that is working correctly. */
    render(<DegradedBuildNotice capabilities={{ ...HEALTHY, degraded_modules: ['chat_agents'] }} />)

    expect(screen.getByText(/started with reduced capability/)).toBeTruthy()
    expect(screen.getByText(/the build it came from is incomplete/)).toBeTruthy()
  })

  it("names what is lost in the user's terms, not the module's", () => {
    render(
      <DegradedBuildNotice
        capabilities={{ ...HEALTHY, degraded_modules: ['chat_agents', 'freecad_bridge'] }}
      />,
    )

    expect(screen.getByText(/The project chat and the AI reviews/)).toBeTruthy()
    expect(screen.getByText(/Generating and exporting enclosures/)).toBeTruthy()
  })

  it('names an unrecognised module as itself rather than inventing a description', () => {
    /** This app and KiCad both gain modules. Guessing at one we do not know is
     *  a confident invention in exactly the place a user is already confused. */
    render(
      <DegradedBuildNotice capabilities={{ ...HEALTHY, degraded_modules: ['some_new_module'] }} />,
    )

    expect(screen.getByText(/some_new_module/)).toBeTruthy()
    expect(screen.getByText(/no description for it/)).toBeTruthy()
  })

  it('points at the daemon log, where the reason actually is', () => {
    render(<DegradedBuildNotice capabilities={{ ...HEALTHY, degraded_modules: ['kicad_cli'] }} />)

    expect(screen.getByText('/Users/k/Library/Logs/copperplane/daemon.log')).toBeTruthy()
  })

  it('offers no retry, because nothing here can fix a bad build', () => {
    /** SPEC-407 §5 in as many words. A retry button would imply the user can
     *  do something, and watching it fail twice is worse than not offering. */
    render(<DegradedBuildNotice capabilities={{ ...HEALTHY, degraded_modules: ['kicad_cli'] }} />)

    expect(screen.queryByRole('button', { name: /retry|try again|reload/i })).toBeNull()
    expect(screen.getByText(/needs a rebuilt sidecar/)).toBeTruthy()
  })

  it('can be dismissed, unlike the requirements banner', () => {
    /** The opposite decision from RequirementsBanner, and deliberately: that
     *  one describes something the user can fix, so it never goes away. This
     *  describes something they cannot, so keeping it forever is nagging
     *  without a remedy. */
    render(<DegradedBuildNotice capabilities={{ ...HEALTHY, degraded_modules: ['kicad_cli'] }} />)

    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }))

    expect(screen.queryByText(/reduced capability/)).toBeNull()
  })

  it('lists every degraded module, not just the first', () => {
    render(
      <DegradedBuildNotice
        capabilities={{ ...HEALTHY, degraded_modules: ['kicad_cli', 'library_store', 'context_index'] }}
      />,
    )

    expect(screen.getByText(/Board and schematic checks/)).toBeTruthy()
    expect(screen.getByText(/Saving and loading projects/)).toBeTruthy()
    expect(screen.getByText(/already learned about your parts/)).toBeTruthy()
  })
})

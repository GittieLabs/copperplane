import { beforeEach, describe, expect, it, vi } from 'vitest'

const dispatchMock = vi.fn()

vi.mock('./ipc', () => ({ dispatch: dispatchMock }))

const { genericProfile, validateProfile, setProjectProfile } =
  await import('./fabricationReview')

beforeEach(() => {
  dispatchMock.mockReset()
})

const PROFILE = { house_name: 'H', min_drill: 0.3, provenance: {} }

describe('sync routes', () => {
  it('dispatches all three profile routes plainly, with no async job', async () => {
    dispatchMock.mockResolvedValue({ result: { house_name: 'H', provenance: {} } })

    await genericProfile()
    await validateProfile(PROFILE as never)
    await setProjectProfile('alpha', PROFILE as never)

    expect(dispatchMock.mock.calls.map((c) => c[0])).toEqual([
      'fabrication.generic_profile',
      'fabrication.validate_profile',
      'project.set_fabrication_profile',
    ])
  })

  it('sends the project name and profile the daemon expects', async () => {
    dispatchMock.mockResolvedValue({ result: {} })
    await setProjectProfile('alpha', PROFILE as never)
    expect(dispatchMock).toHaveBeenCalledWith('project.set_fabrication_profile', {
      project_name: 'alpha',
      profile: PROFILE,
    })
  })

  it('surfaces a daemon error rather than returning an undefined result', async () => {
    dispatchMock.mockResolvedValue({ error: { message: 'min_drill must be positive' } })
    await expect(validateProfile(PROFILE as never)).rejects.toThrow('min_drill must be positive')
  })
})

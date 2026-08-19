import { renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import * as THREE from 'three'

vi.mock('@tauri-apps/api/core', () => ({
  convertFileSrc: (path: string) => `asset://localhost/${path}`,
}))

const {
  useGlbScene, disposeScene, sphericalToCartesian, computeFrame, computeDefaultAzimuth, computeCameraClipping,
  computeBoardOffset,
  DEFAULT_CAMERA_RADIUS, DEFAULT_CAMERA_POLAR, DEFAULT_CAMERA_AZIMUTH,
} = await import('./EnclosureViewer')

/** A `GLTFLoaderLike` fake, so tests control load timing/outcome directly
 * instead of mocking the `three` module's GLTFLoader itself. */
function fakeLoader(behavior: (url: string, onLoad: (gltf: { scene: THREE.Group }) => void, onError: (e: unknown) => void) => void) {
  return () => ({
    load(url: string, onLoad: (gltf: { scene: THREE.Group }) => void, _onProgress: undefined, onError: (e: unknown) => void) {
      behavior(url, onLoad, onError)
    },
  })
}

describe('useGlbScene', () => {
  it('TEST-001: converts the path via convertFileSrc before loading', () => {
    let requestedUrl: string | null = null
    const createLoader = fakeLoader((url) => {
      requestedUrl = url
    })

    renderHook(() => useGlbScene('/tmp/enclosure.glb', createLoader))

    expect(requestedUrl).toBe('asset://localhost//tmp/enclosure.glb')
  })

  it('TEST-002: reports loading, then ready with the loaded scene', async () => {
    const scene = new THREE.Group()
    const createLoader = fakeLoader((_url, onLoad) => {
      queueMicrotask(() => onLoad({ scene }))
    })

    const { result } = renderHook(() => useGlbScene('/tmp/enclosure.glb', createLoader))

    expect(result.current.status).toBe('loading')

    await waitFor(() => expect(result.current.status).toBe('ready'))
    expect(result.current.scene).toBe(scene)
    expect(result.current.error).toBeNull()
  })

  it('TEST-003: reports an error status and message when the loader fails', async () => {
    const createLoader = fakeLoader((_url, _onLoad, onError) => {
      queueMicrotask(() => onError(new Error('corrupt glb')))
    })

    const { result } = renderHook(() => useGlbScene('/tmp/enclosure.glb', createLoader))

    await waitFor(() => expect(result.current.status).toBe('error'))
    expect(result.current.error).toBe('corrupt glb')
    expect(result.current.scene).toBeNull()
  })

  it('CTX-311.3: a null glbPath (no lid generated) stays loading, never an error', () => {
    const { result } = renderHook(() => useGlbScene(null))

    expect(result.current.status).toBe('loading')
    expect(result.current.scene).toBeNull()
    expect(result.current.error).toBeNull()
  })

  it('TEST-004: disposes the previous scene when glbPath changes to a new one', async () => {
    const firstScene = new THREE.Group()
    const disposeSpy = vi.spyOn(firstScene, 'traverse')
    const secondScene = new THREE.Group()

    let callCount = 0
    const createLoader = fakeLoader((_url, onLoad) => {
      const scene = callCount === 0 ? firstScene : secondScene
      callCount += 1
      queueMicrotask(() => onLoad({ scene }))
    })

    const { result, rerender } = renderHook(
      ({ path }) => useGlbScene(path, createLoader),
      { initialProps: { path: '/tmp/first.glb' } },
    )
    await waitFor(() => expect(result.current.scene).toBe(firstScene))

    rerender({ path: '/tmp/second.glb' })
    await waitFor(() => expect(result.current.scene).toBe(secondScene))

    expect(disposeSpy).toHaveBeenCalled()
  })
})

describe('disposeScene', () => {
  it('TEST-005: disposes geometry and material on every mesh in the scene', () => {
    const geometry = new THREE.BoxGeometry(1, 1, 1)
    const material = new THREE.MeshStandardMaterial()
    const mesh = new THREE.Mesh(geometry, material)
    const scene = new THREE.Group()
    scene.add(mesh)

    const geometryDisposeSpy = vi.spyOn(geometry, 'dispose')
    const materialDisposeSpy = vi.spyOn(material, 'dispose')

    disposeScene(scene)

    expect(geometryDisposeSpy).toHaveBeenCalledOnce()
    expect(materialDisposeSpy).toHaveBeenCalledOnce()
  })

  it('TEST-005: disposes every texture referenced by a mesh material', () => {
    const geometry = new THREE.BoxGeometry(1, 1, 1)
    const texture = new THREE.Texture()
    const material = new THREE.MeshStandardMaterial({ map: texture })
    const mesh = new THREE.Mesh(geometry, material)
    const scene = new THREE.Group()
    scene.add(mesh)

    const textureDisposeSpy = vi.spyOn(texture, 'dispose')

    disposeScene(scene)

    expect(textureDisposeSpy).toHaveBeenCalledOnce()
  })
})

describe('sphericalToCartesian (CTX-311.3 camera presets)', () => {
  it('CTX-311.8: the default polar angle is steeper than a flat 45-degree isometric corner -- a real 3/4 view that favors seeing into an open-top cavity', () => {
    const [x, y, z] = sphericalToCartesian(DEFAULT_CAMERA_RADIUS, DEFAULT_CAMERA_POLAR, DEFAULT_CAMERA_AZIMUTH)

    // Y (height off the ground) should dominate over the horizontal
    // distance for a real "looking down into it" default, unlike the
    // previous isometric ~54.7 degree angle where X/Y/Z were all equal.
    const horizontalDistance = Math.sqrt(x * x + z * z)
    expect(y).toBeGreaterThan(horizontalDistance)
  })

  it('CTX-311.8: the default polar sits strictly between a flat Top view and the old isometric angle', () => {
    const isometricPolar = Math.acos(1 / Math.sqrt(3))
    expect(DEFAULT_CAMERA_POLAR).toBeGreaterThan(0)
    expect(DEFAULT_CAMERA_POLAR).toBeLessThan(isometricPolar)
  })

  it('a near-zero polar angle is a real top-down view -- Y equals the radius, X/Z collapse to zero', () => {
    const [x, y, z] = sphericalToCartesian(100, 0, 0)

    expect(y).toBeCloseTo(100, 6)
    expect(x).toBeCloseTo(0, 6)
    expect(z).toBeCloseTo(0, 6)
  })

  it('a near-pi polar angle is a real bottom-up view -- Y equals the negative radius', () => {
    const [, y] = sphericalToCartesian(100, Math.PI, 0)

    expect(y).toBeCloseTo(-100, 6)
  })

  it('rotating azimuth by a quarter turn swaps X and Z at a fixed elevation', () => {
    const polar = Math.PI / 2
    const [x1, , z1] = sphericalToCartesian(100, polar, 0)
    const [x2, , z2] = sphericalToCartesian(100, polar, Math.PI / 2)

    expect(x1).toBeCloseTo(100, 6)
    expect(z1).toBeCloseTo(0, 6)
    expect(x2).toBeCloseTo(0, 6)
    expect(z2).toBeCloseTo(100, 6)
  })
})

describe('computeFrame (CTX-311.4: the real fix for the camera-pointed-at-nothing bug)', () => {
  it('CTX-311.4: a real, small, correctly-scaled mesh (post-CTX-109.4, in real meters) gets a real, small camera radius -- not the old hardcoded ~138-unit distance', () => {
    // A real 0.02 x 0.02 x 0.02m (20mm) box, exactly the shape CTX-109.4's
    // own fix now produces -- the pre-fix bug's own mesh (and this
    // viewer's old hardcoded camera) both used raw-mm-as-meters values
    // roughly 1000x this size.
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(0.02, 0.02, 0.02))
    const frame = computeFrame([mesh])

    expect(frame).not.toBeNull()
    expect(frame!.radius).toBeLessThan(1)
    expect(frame!.radius).toBeGreaterThan(0)
    expect(frame!.center.x).toBeCloseTo(0, 6)
  })

  it('a real, large mesh gets a proportionally real, large camera radius -- the frame scales with whatever actually loaded, not a fixed distance', () => {
    const small = computeFrame([new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1))])
    const large = computeFrame([new THREE.Mesh(new THREE.BoxGeometry(10, 10, 10))])

    expect(large!.radius).toBeGreaterThan(small!.radius * 5)
  })

  it('the real center is the object\'s own bounding-box center, not the origin, for an off-origin mesh', () => {
    const geometry = new THREE.BoxGeometry(2, 2, 2)
    geometry.translate(50, 5, 30)
    const mesh = new THREE.Mesh(geometry)

    const frame = computeFrame([mesh])

    expect(frame!.center.x).toBeCloseTo(50, 3)
    expect(frame!.center.y).toBeCloseTo(5, 3)
    expect(frame!.center.z).toBeCloseTo(30, 3)
  })

  it('a real base plus a real lid frames both together -- the union, not just the base alone', () => {
    const base = new THREE.Mesh(new THREE.BoxGeometry(10, 10, 10))
    const lidGeometry = new THREE.BoxGeometry(10, 1, 10)
    lidGeometry.translate(0, 20, 0) // sits well above the base
    const lid = new THREE.Mesh(lidGeometry)

    const baseOnly = computeFrame([base])
    const both = computeFrame([base, lid])

    expect(both!.radius).toBeGreaterThan(baseOnly!.radius)
  })

  it('returns null (never a guessed frame) when nothing real was passed', () => {
    expect(computeFrame([])).toBeNull()
  })
})

describe('computeDefaultAzimuth (CTX-311.10: real broadside bias for elongated boards)', () => {
  it('a roughly-square footprint lands back near the original fixed 45-degree default', () => {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(10, 5, 10))
    expect(computeDefaultAzimuth(mesh)).toBeCloseTo(Math.PI / 4, 6)
  })

  it('CTX-311.10: a real, elongated footprint (the exact real board shape from the user\'s own screenshot) biases well away from 45 degrees, toward a broadside view', () => {
    // The real NFC_Reader_ESP32 board's own real footprint, confirmed
    // live during this session's own research: ~49.5mm x ~106.5mm --
    // Z (106.5) is the real long axis here, so the broadside bias
    // should pull azimuth *below* 45 degrees (camera positioned more
    // along X, looking across the short axis at the long Z face).
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(49.5, 20, 106.5))
    const azimuth = computeDefaultAzimuth(mesh)

    expect(azimuth).toBeLessThan(Math.PI / 4)
    // A meaningfully large bias, not a rounding-error nudge.
    expect(Math.PI / 4 - azimuth).toBeGreaterThan((10 * Math.PI) / 180)
  })

  it('an extreme aspect ratio still keeps a real minimum 3/4 perspective, never a fully flat side-on view', () => {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(1, 5, 1000))
    const azimuth = computeDefaultAzimuth(mesh)

    expect(azimuth).toBeLessThan(Math.PI / 2)
    expect(Math.PI / 2 - azimuth).toBeGreaterThanOrEqual((15 * Math.PI) / 180 - 1e-9)
  })

  it('swapping which horizontal axis is longer swaps the bias direction relative to 45 degrees', () => {
    const longX = computeDefaultAzimuth(new THREE.Mesh(new THREE.BoxGeometry(100, 5, 10)))
    const longZ = computeDefaultAzimuth(new THREE.Mesh(new THREE.BoxGeometry(10, 5, 100)))

    expect(longX).toBeGreaterThan(Math.PI / 4)
    expect(longZ).toBeLessThan(Math.PI / 4)
  })

  it('falls back to the fixed default for a degenerate (empty) object, never a guess', () => {
    expect(computeDefaultAzimuth(new THREE.Group())).toBe(DEFAULT_CAMERA_AZIMUTH)
  })
})

describe('computeCameraClipping (CTX-311.11: real near-plane-clipping fix)', () => {
  it('CTX-311.11: for a real, small enclosure (post-CTX-109.4 scale, in real meters), near is real and much smaller than the object itself -- not the real ~0.1 default that clipped through it', () => {
    // A typical real enclosure radius in this app's own real units --
    // small enough that PerspectiveCamera's own real default near
    // (0.1, confirmed live against the installed three package) would
    // already be larger than the whole object.
    const clipping = computeCameraClipping(0.05)

    expect(clipping.near).toBeLessThan(0.05)
    expect(clipping.near).toBeLessThan(0.1)
    expect(clipping.near).toBeGreaterThan(0)
  })

  it('far comfortably exceeds the real object\'s own scale so nothing gets far-clipped', () => {
    const clipping = computeCameraClipping(0.05)
    expect(clipping.far).toBeGreaterThan(0.05)
  })

  it('minDistance keeps free-orbit zoom from ever reaching inside the real object, maxDistance keeps it from zooming out to nothing', () => {
    const clipping = computeCameraClipping(0.05)

    expect(clipping.minDistance).toBeGreaterThan(0)
    expect(clipping.minDistance).toBeLessThan(0.05)
    expect(clipping.maxDistance).toBeGreaterThan(clipping.minDistance)
  })

  it('all four values scale proportionally with a real, larger radius -- correct at any real enclosure size, not a fixed guess', () => {
    const small = computeCameraClipping(0.05)
    const large = computeCameraClipping(5)

    expect(large.near).toBeGreaterThan(small.near)
    expect(large.far).toBeGreaterThan(small.far)
    expect(large.minDistance).toBeGreaterThan(small.minDistance)
    expect(large.maxDistance).toBeGreaterThan(small.maxDistance)
  })

  it('never divides by zero or returns a non-finite value for a degenerate zero radius', () => {
    const clipping = computeCameraClipping(0)
    for (const value of Object.values(clipping)) {
      expect(Number.isFinite(value)).toBe(true)
      expect(value).toBeGreaterThan(0)
    }
  })
})

describe('computeBoardOffset (CTX-311.15: board-inside-enclosure visual fit check)', () => {
  it('converts real mm margin/floor-and-standoff values to this app\'s own real /1000 glb scale', () => {
    const offset = computeBoardOffset(2.5, 7)

    expect(offset.x).toBeCloseTo(2.5 / 1000)
    expect(offset.y).toBeCloseTo(7 / 1000)
    expect(offset.z).toBeCloseTo(2.5 / 1000)
  })

  it('margin applies identically to both horizontal axes (X and Z) -- the same real value on both, not two independent inputs', () => {
    const offset = computeBoardOffset(3, 10)

    expect(offset.x).toBeCloseTo(offset.z)
  })

  it('a zero margin/floor-and-standoff returns a real zero vector, not a guess', () => {
    const offset = computeBoardOffset(0, 0)

    expect(offset.x).toBe(0)
    expect(offset.y).toBe(0)
    expect(offset.z).toBe(0)
  })
})

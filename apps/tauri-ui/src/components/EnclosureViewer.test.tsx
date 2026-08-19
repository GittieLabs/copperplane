import { renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import * as THREE from 'three'

vi.mock('@tauri-apps/api/core', () => ({
  convertFileSrc: (path: string) => `asset://localhost/${path}`,
}))

const {
  useGlbScene, disposeScene, sphericalToCartesian, computeFrame, applyMeshColor,
  DEFAULT_CAMERA_RADIUS, DEFAULT_CAMERA_POLAR, DEFAULT_CAMERA_AZIMUTH, BODY_COLOR, LID_COLOR,
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
  it('the default radius/polar/azimuth reproduce the viewer\'s own original [80, 80, 80] corner view', () => {
    const [x, y, z] = sphericalToCartesian(DEFAULT_CAMERA_RADIUS, DEFAULT_CAMERA_POLAR, DEFAULT_CAMERA_AZIMUTH)

    expect(x).toBeCloseTo(80, 6)
    expect(y).toBeCloseTo(80, 6)
    expect(z).toBeCloseTo(80, 6)
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

describe('applyMeshColor (CTX-311.6: real body/lid contrast)', () => {
  it('sets the real color on every real mesh material found in the object', () => {
    const material = new THREE.MeshStandardMaterial({ color: 0x000000 })
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), material)
    const group = new THREE.Group()
    group.add(mesh)

    applyMeshColor(group, 0xff0000)

    expect(material.color.getHex()).toBe(0xff0000)
  })

  it('sets every material in a multi-material mesh, not just the first', () => {
    const materials = [
      new THREE.MeshStandardMaterial({ color: 0x000000 }),
      new THREE.MeshStandardMaterial({ color: 0x000000 }),
    ]
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), materials)
    const group = new THREE.Group()
    group.add(mesh)

    applyMeshColor(group, 0x00ff00)

    for (const material of materials) {
      expect(material.color.getHex()).toBe(0x00ff00)
    }
  })

  it('skips non-mesh nodes without throwing', () => {
    const group = new THREE.Group()
    group.add(new THREE.Group())
    expect(() => applyMeshColor(group, 0x0000ff)).not.toThrow()
  })

  it('BODY_COLOR and LID_COLOR are real, distinct colors', () => {
    expect(BODY_COLOR).not.toBe(LID_COLOR)
  })
})

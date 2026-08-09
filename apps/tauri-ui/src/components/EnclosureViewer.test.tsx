import { renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import * as THREE from 'three'

vi.mock('@tauri-apps/api/core', () => ({
  convertFileSrc: (path: string) => `asset://localhost/${path}`,
}))

const { useGlbScene, disposeScene } = await import('./EnclosureViewer')

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

import { useEffect, useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { convertFileSrc } from '@tauri-apps/api/core'

export type ViewerStatus = 'loading' | 'ready' | 'error'

/** The minimal shape `useGlbScene` needs from a loader -- lets tests
 * inject a fake loader instead of mocking the `three` module itself. */
export interface GLTFLoaderLike {
  load(
    url: string,
    onLoad: (gltf: { scene: THREE.Group }) => void,
    onProgress: undefined,
    onError: (event: unknown) => void,
  ): void
}

/** Releases a loaded scene's GPU buffers (geometry/material/texture) --
 * the standard Three.js leak (SPEC-301 §3) if a replaced or unmounted
 * scene is just dropped and left for GC, which never reclaims GPU memory
 * on its own. */
export function disposeScene(scene: THREE.Object3D): void {
  scene.traverse((child) => {
    if (!(child instanceof THREE.Mesh)) return

    child.geometry?.dispose()

    const materials = Array.isArray(child.material) ? child.material : [child.material]
    for (const material of materials) {
      if (!material) continue
      for (const value of Object.values(material)) {
        if (value instanceof THREE.Texture) value.dispose()
      }
      material.dispose()
    }
  })
}

/**
 * Loads a `.glb` from an absolute filesystem path via Tauri's scoped
 * asset protocol (SPEC-301 §2 -- `convertFileSrc` turns it into a URL the
 * WebView is actually allowed to fetch), tracking loading/ready/error
 * state explicitly rather than via Suspense, and disposing of the
 * previous scene's GPU resources whenever it's replaced or this hook
 * unmounts.
 */
export function useGlbScene(
  glbPath: string | null,
  createLoader: () => GLTFLoaderLike = () => new GLTFLoader(),
): { status: ViewerStatus; scene: THREE.Group | null; error: string | null } {
  const [status, setStatus] = useState<ViewerStatus>('loading')
  const [scene, setScene] = useState<THREE.Group | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!glbPath) {
      setStatus('loading')
      setScene(null)
      setError(null)
      return
    }

    let cancelled = false
    setStatus('loading')
    setError(null)

    createLoader().load(
      convertFileSrc(glbPath),
      (gltf) => {
        if (cancelled) return
        setScene(gltf.scene)
        setStatus('ready')
      },
      undefined,
      (event) => {
        if (cancelled) return
        setError(event instanceof Error ? event.message : String(event))
        setStatus('error')
      },
    )

    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [glbPath])

  useEffect(() => {
    return () => {
      if (scene) disposeScene(scene)
    }
  }, [scene])

  return { status, scene, error }
}

export function EnclosureViewer({ glbPath }: { glbPath: string }) {
  const { status, scene, error } = useGlbScene(glbPath)

  if (status === 'loading') {
    return <p className="text-sm text-neutral-400">Loading mesh…</p>
  }
  if (status === 'error') {
    return <p className="text-sm text-red-400">Failed to load mesh: {error}</p>
  }

  return (
    <div className="h-64 w-full overflow-hidden rounded border border-neutral-800">
      <Canvas camera={{ position: [80, 80, 80], fov: 50 }}>
        <ambientLight intensity={0.6} />
        <directionalLight position={[100, 100, 100]} intensity={0.8} />
        {scene && <primitive object={scene} />}
        <OrbitControls makeDefault enableDamping />
      </Canvas>
    </div>
  )
}

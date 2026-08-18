import { type RefObject, useEffect, useRef, useState } from 'react'
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
 *
 * `glbPath: null` (SPEC-311: an optional lid model that may not exist
 * for a given enclosure) is a deliberate, permanent "nothing to load"
 * state -- `status` stays `'loading'` with a `null` scene, never an
 * error, so a caller can tell "no lid was generated" apart from "the
 * lid failed to load."
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

// SPEC-311: camera presets are real, bounded additions to the existing
// free-orbit `OrbitControls` (CTX-301.2) -- not a replacement for it.
// Spherical coordinates around the origin (the enclosure's own build
// origin, matching `OrbitControls`' existing `target` default), Y-up to
// match glTF's own convention (confirmed live during SPEC-311's own
// research: `kicad-cli pcb export glb`'s Y axis is height). The default
// radius/polar below reproduce the exact corner view this viewer's
// camera has always opened with ([80, 80, 80]) -- a preset click is a
// jump to a new canonical view, not a replacement for free dragging;
// the user can keep orbiting from wherever a preset lands them.
export const DEFAULT_CAMERA_RADIUS = 80 * Math.sqrt(3)
export const DEFAULT_CAMERA_POLAR = Math.acos(1 / Math.sqrt(3))
export const DEFAULT_CAMERA_AZIMUTH = Math.PI / 4
const _ROTATE_STEP = Math.PI / 4
const _POLE_EPSILON = 0.001

export function sphericalToCartesian(radius: number, polar: number, azimuth: number): [number, number, number] {
  const x = radius * Math.sin(polar) * Math.cos(azimuth)
  const y = radius * Math.cos(polar)
  const z = radius * Math.sin(polar) * Math.sin(azimuth)
  return [x, y, z]
}

/** The minimal shape this component needs from drei's `OrbitControls`
 * ref -- avoids importing `three-stdlib`'s own type just for this. */
interface OrbitControlsHandle {
  object: THREE.Camera
  target: THREE.Vector3
  update(): void
}

function CameraPresetControls({ controlsRef }: { controlsRef: RefObject<OrbitControlsHandle | null> }) {
  const cameraState = useRef({
    radius: DEFAULT_CAMERA_RADIUS,
    polar: DEFAULT_CAMERA_POLAR,
    azimuth: DEFAULT_CAMERA_AZIMUTH,
  })

  function apply() {
    const controls = controlsRef.current
    if (!controls) return
    const { radius, polar, azimuth } = cameraState.current
    const [x, y, z] = sphericalToCartesian(radius, polar, azimuth)
    controls.object.position.set(x, y, z)
    controls.target.set(0, 0, 0)
    controls.update()
  }

  function handleTop() {
    cameraState.current.polar = _POLE_EPSILON
    apply()
  }
  function handleBottom() {
    cameraState.current.polar = Math.PI - _POLE_EPSILON
    apply()
  }
  function handleRotateLeft() {
    cameraState.current.azimuth -= _ROTATE_STEP
    apply()
  }
  function handleRotateRight() {
    cameraState.current.azimuth += _ROTATE_STEP
    apply()
  }

  const buttonClass = 'rounded border border-neutral-700 px-2 py-1 text-xs text-neutral-200 hover:bg-neutral-800'

  return (
    <div className="flex gap-1">
      <button type="button" className={buttonClass} onClick={handleRotateLeft} title="Rotate left">
        ⟲
      </button>
      <button type="button" className={buttonClass} onClick={handleTop} title="Top view">
        Top
      </button>
      <button type="button" className={buttonClass} onClick={handleBottom} title="Bottom view">
        Bottom
      </button>
      <button type="button" className={buttonClass} onClick={handleRotateRight} title="Rotate right">
        ⟳
      </button>
    </div>
  )
}

export function EnclosureViewer({
  glbPath,
  lidGlbPath = null,
  lidVisible = true,
}: {
  glbPath: string
  /** SPEC-311: a generated enclosure's own real lid, when one was
   * requested -- omitted or null when no lid exists for this result,
   * not an error state (see `useGlbScene`'s own docstring). */
  lidGlbPath?: string | null
  lidVisible?: boolean
}) {
  const base = useGlbScene(glbPath)
  const lid = useGlbScene(lidGlbPath)
  const controlsRef = useRef<OrbitControlsHandle | null>(null)

  if (base.status === 'loading') {
    return <p className="text-sm text-neutral-400">Loading mesh…</p>
  }
  if (base.status === 'error') {
    return <p className="text-sm text-red-400">Failed to load mesh: {base.error}</p>
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="h-96 w-full overflow-hidden rounded border border-neutral-800">
        <Canvas camera={{ position: [80, 80, 80], fov: 50 }}>
          <color attach="background" args={['#3f3f46']} />
          <ambientLight intensity={0.6} />
          <directionalLight position={[100, 100, 100]} intensity={0.8} />
          {base.scene && <primitive object={base.scene} />}
          {lid.scene && lidVisible && <primitive object={lid.scene} />}
          <OrbitControls ref={controlsRef} makeDefault enableDamping />
        </Canvas>
      </div>
      <div className="flex items-center justify-between">
        <CameraPresetControls controlsRef={controlsRef} />
        {lidGlbPath && lid.status === 'error' && (
          <p className="text-xs text-red-400">Failed to load lid: {lid.error}</p>
        )}
      </div>
    </div>
  )
}

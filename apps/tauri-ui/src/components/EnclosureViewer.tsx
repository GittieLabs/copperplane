import { type RefObject, useEffect, useRef, useState } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import type { OrbitControls as OrbitControlsImpl } from 'three-stdlib'
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

// SPEC-311: real user feedback exercising the actual running app -- once
// the lid rendered at all (post-CTX-311.5), the body and lid were still
// "too hard" to tell apart, both rendering almost black regardless of
// scene lighting. Root cause (CTX-311.7): `freecad_bridge.py`'s own
// `.glb` export previously attached no material at all, so glTF's own
// spec-default (fully metallic, fully rough, black with no environment
// map to reflect) applied. Fixed at the source, not here -- `_export_glb`
// now writes a real, matte, distinctly-colored material for the body and
// the lid directly into each file, so both render correctly in any real
// glTF viewer, not just this app's own. Only the background stays a
// frontend concern (it's not part of either mesh's own real data).
export const VIEWER_BACKGROUND_COLOR = '#e5e7eb' // gray-200 -- light enough to read clearly against a matte-shaded body and lid

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
// Spherical coordinates around a real target center (computed from the
// loaded mesh's own bounding box -- see `computeFrame` below, CTX-311.4),
// Y-up to match glTF's own convention (confirmed live during SPEC-311's
// own research: `kicad-cli pcb export glb`'s Y axis is height). These
// constants set the *initial* view every newly generated enclosure opens
// with, before any free orbit or preset click moves the camera.
export const DEFAULT_CAMERA_RADIUS = 80 * Math.sqrt(3)
// CTX-311.8: real user feedback -- the previous default (a classic
// isometric ~54.7° polar angle, the same angle that reproduced this
// viewer's own original [80, 80, 80] corner view) reads fine for a
// closed solid, but this enclosure is a real, open-top hollow shell:
// at that shallow an elevation, the near wall of anything but a short,
// roughly-square shell occludes the opening almost entirely, especially
// on a long, narrow board -- exactly what the user's own screenshot
// showed (a shape read as a solid wedge, no visible floor or interior
// corners, "have to rotate... to see the edges inside"). A steeper,
// more top-down default polar angle keeps a real 3/4 perspective (not
// a flat top-down "Top" preset view) while actually showing the
// cavity/floor on first load, for any real enclosure's proportions --
// not tuned to one board's own aspect ratio.
export const DEFAULT_CAMERA_POLAR = (35 * Math.PI) / 180
export const DEFAULT_CAMERA_AZIMUTH = Math.PI / 4
const _ROTATE_STEP = Math.PI / 4
const _POLE_EPSILON = 0.001
// A real object's own bounding-sphere radius alone puts it right at the
// viewport's edge -- this multiplier leaves real headroom so it doesn't.
const _FRAME_MULTIPLIER = 1.6

export function sphericalToCartesian(radius: number, polar: number, azimuth: number): [number, number, number] {
  const x = radius * Math.sin(polar) * Math.cos(azimuth)
  const y = radius * Math.cos(polar)
  const z = radius * Math.sin(polar) * Math.sin(azimuth)
  return [x, y, z]
}

interface CameraState {
  radius: number
  polar: number
  azimuth: number
  center: THREE.Vector3
}

function applyCameraState(controls: OrbitControlsImpl, state: CameraState) {
  const [dx, dy, dz] = sphericalToCartesian(state.radius, state.polar, state.azimuth)
  controls.object.position.set(state.center.x + dx, state.center.y + dy, state.center.z + dz)
  controls.target.copy(state.center)
  controls.update()
}

/** Real, live user testing (CTX-311.3, the very context that added
 * these presets) found the viewer's own long-fixed `[80, 80, 80]`
 * camera position -- "empirically tuned" (`CTX-109.4`'s own docstring)
 * around the *pre-fix* 1000x-too-large `.glb` scale -- pointed at
 * nothing once `CTX-109.4`'s real unit-scale fix shipped: a correctly-
 * scaled enclosure is now only centimeters across, not "meters," so a
 * camera ~138 units away sees an imperceptible speck against the
 * background color, indistinguishable from "nothing rendered." Framing
 * the camera from the real loaded mesh's own bounding box, computed
 * fresh every time, is correct at any real enclosure size -- not just
 * whichever one the camera was last hand-tuned against (CTX-311.4).
 * Returns `null` (never a guessed frame) for an empty/degenerate box. */
export function computeFrame(objects: THREE.Object3D[]): { radius: number; center: THREE.Vector3 } | null {
  const box = new THREE.Box3()
  let hasAny = false
  for (const object of objects) {
    box.expandByObject(object)
    hasAny = true
  }
  if (!hasAny || box.isEmpty()) return null

  const center = box.getCenter(new THREE.Vector3())
  const size = box.getSize(new THREE.Vector3())
  const radius = Math.max(size.length() * _FRAME_MULTIPLIER, 0.001)
  return { radius, center }
}

function CameraPresetControls({
  controlsRef,
  cameraState,
}: {
  controlsRef: RefObject<OrbitControlsImpl | null>
  cameraState: RefObject<CameraState>
}) {
  function apply() {
    const controls = controlsRef.current
    if (!controls) return
    applyCameraState(controls, cameraState.current)
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
  const controlsRef = useRef<OrbitControlsImpl | null>(null)
  const cameraState = useRef<CameraState>({
    radius: DEFAULT_CAMERA_RADIUS,
    polar: DEFAULT_CAMERA_POLAR,
    azimuth: DEFAULT_CAMERA_AZIMUTH,
    center: new THREE.Vector3(0, 0, 0),
  })

  // Computed synchronously during render (not an effect) so the
  // Canvas's own initial `camera` prop is correct on the very first
  // frame the mesh is available -- no flash of a wrongly-framed camera
  // snapping into place a tick later. `cameraState.current` is updated
  // here too so a later free-orbit or preset click starts from this
  // same real frame, not the hardcoded fallback.
  if (base.scene) {
    const frame = computeFrame([base.scene, lid.scene].filter((s): s is THREE.Group => s !== null))
    if (frame) {
      cameraState.current.radius = frame.radius
      cameraState.current.center = frame.center
    }
  }

  // Handles regeneration: the Canvas/OrbitControls stay mounted across
  // a new `glbPath` (no `key` change), so the synchronous render-time
  // computation above only ever sets the *initial* camera prop once,
  // on first mount -- an already-mounted OrbitControls needs its own
  // imperative re-frame when the loaded mesh changes size.
  useEffect(() => {
    const frame = computeFrame([base.scene, lid.scene].filter((s): s is THREE.Group => s !== null))
    if (!frame || !controlsRef.current) return
    cameraState.current.radius = frame.radius
    cameraState.current.center = frame.center
    applyCameraState(controlsRef.current, cameraState.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [base.scene, lid.scene])

  if (base.status === 'loading') {
    return <p className="text-sm text-neutral-400">Loading mesh…</p>
  }
  if (base.status === 'error') {
    return <p className="text-sm text-red-400">Failed to load mesh: {base.error}</p>
  }

  const [initialX, initialY, initialZ] = sphericalToCartesian(
    cameraState.current.radius, cameraState.current.polar, cameraState.current.azimuth,
  )

  return (
    <div className="flex flex-col gap-2">
      <div className="h-96 w-full overflow-hidden rounded border border-neutral-800">
        <Canvas
          camera={{
            position: [
              cameraState.current.center.x + initialX,
              cameraState.current.center.y + initialY,
              cameraState.current.center.z + initialZ,
            ],
            fov: 50,
          }}
        >
          <color attach="background" args={[VIEWER_BACKGROUND_COLOR]} />
          {/* CTX-311.9: real user feedback, after CTX-311.8's camera fix
           * finally showed the real cavity/floor -- "still hard to see
           * where the edges of the floor meet" the walls. CTX-311.6's own
           * lighting rebalance (raised here to fix a real "hard, dark
           * shadows" complaint) turns out to have overcorrected: that
           * earlier harshness was compounded by (likely caused entirely
           * by) `CTX-311.7`'s own root-cause bug -- the mesh rendering as
           * a fully metallic surface with no environment map, which reads
           * as stark near-black regardless of light balance. Now that the
           * material is real and matte (`CTX-311.7`), a high ambient
           * floor relative to the directional lights actively works
           * against edge visibility instead: ambient light contributes
           * uniformly regardless of a face's own normal, so raising it
           * too far flattens the real brightness difference between the
           * floor (facing up, toward the main light) and a vertical wall
           * (facing sideways) that's exactly what makes their shared
           * crease visible at all. Rebalanced toward the directional
           * lights again -- real per-face contrast for genuine edge
           * definition -- while keeping ambient and the dim fill light
           * non-zero so no face reads as true black the way the old
           * metallic material always did. */}
          <ambientLight intensity={0.5} />
          <directionalLight position={[100, 100, 100]} intensity={1.0} />
          <directionalLight position={[-100, -60, -100]} intensity={0.25} />
          {base.scene && <primitive object={base.scene} />}
          {lid.scene && lidVisible && <primitive object={lid.scene} />}
          <OrbitControls ref={controlsRef} makeDefault enableDamping target={cameraState.current.center} />
        </Canvas>
      </div>
      <div className="flex items-center justify-between">
        <CameraPresetControls controlsRef={controlsRef} cameraState={cameraState} />
        {lidGlbPath && lid.status === 'error' && (
          <p className="text-xs text-red-400">Failed to load lid: {lid.error}</p>
        )}
      </div>
    </div>
  )
}

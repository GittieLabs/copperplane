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
//
// CTX-311.10: real user feedback again -- the original 35° from
// CTX-311.8, combined with the *default*, board-shape-blind azimuth
// below, made a real long/narrow enclosure look like a flat, featureless
// slab: steep enough that the vertical walls (the only real surfaces
// whose lighting differs from the floor, with no real shadow-mapping in
// this Canvas to otherwise reveal depth) had almost no visible on-screen
// height. Eased back to 42° -- still steeper than the original isometric
// angle, but real enough wall area is visible again for that lighting
// difference to actually read as depth, now that `computeDefaultAzimuth`
// below also does its own real part to avoid occlusion.
export const DEFAULT_CAMERA_POLAR = (42 * Math.PI) / 180
export const DEFAULT_CAMERA_AZIMUTH = Math.PI / 4
const _ROTATE_STEP = Math.PI / 4
const _POLE_EPSILON = 0.001
// A real object's own bounding-sphere radius alone puts it right at the
// viewport's edge -- this multiplier leaves real headroom so it doesn't.
const _FRAME_MULTIPLIER = 1.6
// CTX-311.10: never let the default azimuth collapse into a fully flat,
// axis-aligned side view -- always keep at least this much real 3/4
// perspective, even for an extremely elongated real board.
const _MIN_AZIMUTH_OFFSET = (15 * Math.PI) / 180

export function sphericalToCartesian(radius: number, polar: number, azimuth: number): [number, number, number] {
  const x = radius * Math.sin(polar) * Math.cos(azimuth)
  const y = radius * Math.cos(polar)
  const z = radius * Math.sin(polar) * Math.sin(azimuth)
  return [x, y, z]
}

/** Real user feedback (`CTX-311.10`), and something `CTX-311.8`'s own
 * Plan Drift had already named as a real, deferred risk: a fixed 45°
 * default azimuth looks fine for a roughly-square footprint, but for a
 * real, elongated board (the exact real board in both the `CTX-311.8`
 * and `CTX-311.10` screenshots), it can put the camera looking nearly
 * along the *long* axis -- the near end wall, short relative to the
 * board's real length, still reads as a flat, featureless slab under
 * perspective, hiding the opening almost entirely.
 *
 * Derives a real azimuth from the loaded mesh's own real horizontal
 * (X/Z) extents instead: `atan2(sizeX, sizeZ)` biases the camera toward
 * looking *across* the shorter horizontal axis (a real "broadside" view
 * of the longer one), reducing exactly this occlusion -- and, for a
 * roughly-square footprint, `atan2` naturally lands back near the
 * original 45°, so this changes nothing for the common case. Clamped to
 * `_MIN_AZIMUTH_OFFSET` on both sides of the two horizontal axes so an
 * extreme aspect ratio never collapses into a fully flat side view with
 * no perspective at all. Falls back to the fixed default for a
 * degenerate (empty, or zero-width in some real axis) box, never a
 * guess. */
export function computeDefaultAzimuth(object: THREE.Object3D): number {
  const box = new THREE.Box3().setFromObject(object)
  if (box.isEmpty()) return DEFAULT_CAMERA_AZIMUTH
  const size = box.getSize(new THREE.Vector3())
  if (size.x <= 0 || size.z <= 0) return DEFAULT_CAMERA_AZIMUTH
  const raw = Math.atan2(size.x, size.z)
  return Math.min(Math.max(raw, _MIN_AZIMUTH_OFFSET), Math.PI / 2 - _MIN_AZIMUTH_OFFSET)
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

/** Real, confirmed bug found by live user testing (`CTX-311.11`): the
 * user's own screenshot showed a real enclosure rendering as a
 * nonsensical, pointed, notched shape after normal free-orbit/zoom, and
 * described "clipping... allowing me to see inside by removing a wall."
 * Confirmed directly, not guessed: a plain `THREE.PerspectiveCamera`'s
 * own real default `near` is `0.1` (verified live against the actual
 * installed `three` package) -- larger than an entire real enclosure
 * mesh in this app, which is routinely only `0.02`-`0.15` real meters
 * across (post-`CTX-109.4`'s own real unit-scale fix). Any camera
 * position within that real `0.1`-unit near-plane distance of a wall --
 * trivially reached by an ordinary zoom-in gesture, since this viewer
 * never set `near`/`far` explicitly and never bounded `OrbitControls`'
 * own zoom distance either -- clips straight through it, exactly
 * matching "removing a wall." Derives real, scale-proportional camera
 * clipping planes and zoom limits from the same real computed `radius`
 * every other piece of camera framing already uses, so it stays correct
 * at any real enclosure size, not a fixed guess tuned to one. */
export function computeCameraClipping(radius: number): {
  near: number
  far: number
  minDistance: number
  maxDistance: number
} {
  const safeRadius = Math.max(radius, 1e-6)
  return {
    near: safeRadius * 0.001,
    far: safeRadius * 1000,
    minDistance: safeRadius * 0.15,
    maxDistance: safeRadius * 20,
  }
}

/** CTX-311.15 (fixed after a real click-through, see `BOARD_Z_MIRROR`
 * below): real, pure translation for compositing the board-inside-
 * enclosure overlay -- `kicad.export_board_glb` (CTX-311.15) already
 * real-origins the board's own glb to its bounding-box corner
 * server-side, so no board outline data is needed here at all, only the
 * enclosure's own already-known real parameters: `marginMm` (wall
 * thickness + clearance -- the real gap between the enclosure's own
 * local origin, its outer box's own corner, and the board's own edge,
 * confirmed via `daemon.py`'s own standoff-position math) and
 * `floorAndStandoffMm` (wall thickness + standoff height -- how far
 * above the enclosure's own floor the board's own bottom surface
 * sits). Both real mm values, converted to this app's own real `/1000`
 * glb scale (`CTX-109.4`) the same way every other real dimension in
 * this file already is.
 *
 * The Z component is negative, not positive -- `freecad_bridge.py`'s
 * own `_Y_UP_ROTATION` (`CTX-311.5`) leaves the enclosure's own local Z
 * axis running in the negative direction relative to its pre-rotation
 * FreeCAD depth axis, so the board's own offset has to land in that
 * same negative range, combined with `BOARD_Z_MIRROR` below. */
export function computeBoardOffset(marginMm: number, floorAndStandoffMm: number): THREE.Vector3 {
  return new THREE.Vector3(marginMm / 1000, floorAndStandoffMm / 1000, -marginMm / 1000)
}

/** CTX-311.15: a real, empirically-confirmed bug found by a live user
 * click-through, not caught by this file's own tests -- those only
 * checked `computeBoardOffset`'s own math in isolation, never the two
 * real toolchains' actual coordinate conventions against each other
 * (the exact same class of blind spot `CTX-311.5`'s own `_Y_UP_
 * ROTATION` comment already names for the enclosure body itself).
 *
 * `kicad.export_board_glb`'s board glb (a separate toolchain from
 * FreeCAD, never rotated) keeps its own local Z increasing in the same
 * direction as increasing real KiCad Y -- a plain, unflipped
 * `--user-origin` shift, confirmed directly against `kicad-cli`.
 * `freecad_bridge.py`'s own `-90` degree X rotation (`CTX-311.5`,
 * fixing the unrelated Z-up/Y-up mismatch) happens to leave the
 * enclosure's own local Z running in the *opposite* direction from its
 * pre-rotation FreeCAD depth axis. A pure translation can only align
 * one end of two ranges running in opposite directions, not both --
 * verified directly against a real board+enclosure pair via `trimesh`:
 * without this mirror, the board's real Z range sits entirely outside
 * the enclosure's own Z range (the real, disjoint-looking render this
 * fixes); with it, the board's Z range lands inside the enclosure's
 * with exactly the expected wall+clearance margin on both ends. X needs
 * no equivalent mirror -- `CTX-311.5`'s rotation is about the X axis
 * and never touches it, and both toolchains already agree on its
 * direction. */
export const BOARD_Z_MIRROR: [number, number, number] = [1, 1, -1]

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
  onLidVisibleChange,
  boardGlbPath = null,
  boardVisible = false,
  boardOffsetMm = null,
}: {
  glbPath: string
  /** SPEC-311: a generated enclosure's own real lid, when one was
   * requested -- omitted or null when no lid exists for this result,
   * not an error state (see `useGlbScene`'s own docstring). */
  lidGlbPath?: string | null
  lidVisible?: boolean
  /** Real user feedback (CTX-311.14): "Show lid" was mixed in among the
   * Open/Export buttons -- a display toggle for the camera/viewer, not
   * an action on the generated files, so it belongs beside the camera
   * preset buttons it's grouped with here, not the panel's own action
   * row. `EnclosurePanel` still owns the actual `lidVisible` state (it's
   * meaningful to more than just this component); this callback is the
   * only way that state changes when a lid exists. Renders nothing when
   * omitted. */
  onLidVisibleChange?: (visible: boolean) => void
  /** CTX-311.15: the real, assembled board's own glb (`kicad.
   * export_board_glb`), already real-origined server-side to its own
   * bounding-box corner -- `boardOffsetMm` (below) is the only
   * placement data this component needs. */
  boardGlbPath?: string | null
  boardVisible?: boolean
  /** Real mm values (not yet divided by 1000) -- `computeBoardOffset`
   * does that real unit conversion. `margin` is `wall_thickness_mm +
   * clearance_mm`; `floorAndStandoff` is `wall_thickness_mm +
   * standoff_height_mm`. `null` while the board's own real params
   * aren't known yet (e.g. before a board-driven Generate). */
  boardOffsetMm?: { margin: number; floorAndStandoff: number } | null
}) {
  const base = useGlbScene(glbPath)
  const lid = useGlbScene(lidGlbPath)
  const board = useGlbScene(boardGlbPath)
  const controlsRef = useRef<OrbitControlsImpl | null>(null)
  const cameraState = useRef<CameraState>({
    radius: DEFAULT_CAMERA_RADIUS,
    polar: DEFAULT_CAMERA_POLAR,
    azimuth: DEFAULT_CAMERA_AZIMUTH,
    center: new THREE.Vector3(0, 0, 0),
  })
  // CTX-311.10: tracks which real `base.scene` the default azimuth has
  // already been computed for, so a real new generation gets a fresh,
  // shape-aware default while an unrelated re-render (e.g. toggling
  // "Show lid") never silently overwrites a user's own manual rotation.
  const azimuthInitializedFor = useRef<THREE.Group | null>(null)

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
    if (azimuthInitializedFor.current !== base.scene) {
      azimuthInitializedFor.current = base.scene
      cameraState.current.azimuth = computeDefaultAzimuth(base.scene)
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
  const clipping = computeCameraClipping(cameraState.current.radius)

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
            near: clipping.near,
            far: clipping.far,
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
          {board.scene && boardVisible && boardOffsetMm && (
            <primitive
              object={board.scene}
              position={computeBoardOffset(boardOffsetMm.margin, boardOffsetMm.floorAndStandoff)}
              scale={BOARD_Z_MIRROR}
            />
          )}
          <OrbitControls
            ref={controlsRef}
            makeDefault
            enableDamping
            target={cameraState.current.center}
            minDistance={clipping.minDistance}
            maxDistance={clipping.maxDistance}
          />
        </Canvas>
      </div>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <CameraPresetControls controlsRef={controlsRef} cameraState={cameraState} />
          {lidGlbPath && onLidVisibleChange && (
            <label className="flex items-center gap-2 text-xs text-neutral-300">
              <input
                type="checkbox"
                checked={lidVisible}
                onChange={(e) => onLidVisibleChange(e.target.checked)}
              />
              Show lid
            </label>
          )}
        </div>
        {lidGlbPath && lid.status === 'error' && (
          <p className="text-xs text-red-400">Failed to load lid: {lid.error}</p>
        )}
        {boardGlbPath && board.status === 'error' && (
          <p className="text-xs text-red-400">Failed to load board: {board.error}</p>
        )}
      </div>
    </div>
  )
}

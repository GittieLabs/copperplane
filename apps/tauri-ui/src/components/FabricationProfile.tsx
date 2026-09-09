import { useCallback, useEffect, useState } from 'react'

import type { CapabilityProfile } from '../lib/fabricationReview'
import { genericProfile, setProjectProfile } from '../lib/fabricationReview'

/**
 * SPEC-340 §5: choosing the board house, once per project.
 *
 * The numbers shown here are the ones a board is about to be judged against, so
 * two things are non-negotiable:
 *
 * *   **Every value says where it came from and whether the user confirmed it.**
 *     The bundled starting point ships with all nine fields unconfirmed on
 *     purpose (`CTX-114.1` Deviation 6), so this surface has something true to
 *     say rather than implying a vendor published them.
 * *   **The process the numbers describe is named next to the numbers.**
 *     `SPEC-340` §3: a user entering advanced-process figures while ordering the
 *     standard process gets confident findings about a board that is fine, and
 *     naming the process is the whole mitigation.
 */

/** Field order is deliberate: the ones that cause silently-wrong boards first,
 *  matching how the findings themselves are ranked. */
const FIELDS: { key: keyof CapabilityProfile; label: string }[] = [
  { key: 'min_track_width', label: 'Minimum track width' },
  { key: 'min_clearance', label: 'Minimum clearance' },
  { key: 'min_annular_ring', label: 'Minimum annular ring' },
  { key: 'min_drill', label: 'Minimum drill' },
  { key: 'min_hole_to_hole', label: 'Minimum hole to hole' },
  { key: 'min_edge_clearance', label: 'Copper to board edge' },
  { key: 'min_silk_clearance', label: 'Minimum silkscreen clearance' },
  { key: 'min_text_height', label: 'Minimum text height' },
  { key: 'min_text_thickness', label: 'Minimum text thickness' },
]

export function FabricationProfile({
  projectName,
  boardPath,
  profile,
  onProfileChange,
}: {
  projectName: string
  /** Null when no board is linked yet. That is an honest empty state and not an
   *  error -- a profile can legitimately be chosen before a board exists
   *  (`SPEC-114` §2.9). */
  boardPath: string | null
  profile: CapabilityProfile | null
  onProfileChange: (profile: CapabilityProfile | null) => void
}) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setError(null)
  }, [projectName])

  const onUseGeneric = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const generic = await genericProfile()
      await setProjectProfile(projectName, generic)
      onProfileChange(generic)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [projectName, onProfileChange])

  const onClear = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      await setProjectProfile(projectName, null)
      onProfileChange(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [projectName, onProfileChange])

  if (!profile) {
    return (
      <div className="flex flex-col gap-2 rounded border border-line-subtle p-3">
        <h3 className="text-sm font-medium text-fg-bright">Where will this board be made?</h3>
        <p className="text-xs text-fg-tertiary">
          KiCad checks your board against its own default rules, which are more permissive than any
          real board house. Naming the house you intend to order from checks it against what that
          house actually publishes it can build.
        </p>
        {!boardPath && (
          <p className="text-xs text-fg-muted">
            You can choose one now — this project has no linked board yet, so there is nothing to
            check against until it does.
          </p>
        )}
        <p className="text-xs text-fg-muted">
          This does not run a separate check. It changes which rules the board check below uses.
        </p>
        <div>
          <button
            type="button"
            className="rounded border border-line-strong px-3 py-1 text-xs text-fg-bright"
            onClick={onUseGeneric}
            disabled={loading}
          >
            {loading ? 'Setting up…' : 'Start from standard 2-layer numbers'}
          </button>
        </div>
        {error && <p className="text-xs text-danger">{error}</p>}
      </div>
    )
  }

  const stale = isStale(profile)

  return (
    <div className="flex flex-col gap-2 rounded border border-line-subtle p-3">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-medium text-fg-bright">{profile.house_name}</h3>
        <button
          type="button"
          className="text-xs text-fg-muted underline"
          onClick={onClear}
          disabled={loading}
        >
          Choose a different house
        </button>
      </div>

      <p className="text-xs text-fg-tertiary">
        The board check below now runs against these numbers instead of KiCad&rsquo;s defaults, and
        shows both counts so you can see the difference.
      </p>

      {profile.layer_count && (
        <p className="text-xs text-fg-tertiary">
          These are {profile.layer_count}-layer numbers. If you are ordering a different process,
          the limits below are the wrong ones to check against.
        </p>
      )}

      {stale && (
        <p className="text-xs text-warning">
          These numbers were recorded over a year ago. Board houses change what they publish — check
          them against your house&rsquo;s current page before you order.
        </p>
      )}

      <ul className="flex flex-col gap-1">
        {FIELDS.map(({ key, label }) => {
          const value = profile[key] as number | null | undefined
          if (value == null) return null
          const p = profile.provenance?.[key as string]
          return (
            <li key={key as string} className="flex items-baseline justify-between gap-2 text-xs">
              <span className="text-fg-secondary">{label}</span>
              <span className="text-fg-bright">
                {value} mm{' '}
                <span className="text-fg-muted">
                  {p?.confirmed_by_user ? '· you confirmed this' : '· not confirmed'}
                  {p?.recorded_on ? ` · recorded ${p.recorded_on}` : ''}
                </span>
              </span>
            </li>
          )
        })}
      </ul>

      {unconfirmedCount(profile) > 0 && (
        <p className="text-xs text-fg-muted">
          {unconfirmedCount(profile)} of these came from a general standard process, not from your
          board house. Replace them with your house&rsquo;s published numbers before you order.
        </p>
      )}

      {error && <p className="text-xs text-danger">{error}</p>}
    </div>
  )
}

function unconfirmedCount(profile: CapabilityProfile): number {
  return Object.values(profile.provenance ?? {}).filter((p) => !p.confirmed_by_user).length
}

/** Mirrors `capability_profile.is_stale`'s one-year default. Reported, never
 *  silently repaired -- the record says what was actually checked. */
function isStale(profile: CapabilityProfile): boolean {
  const dates = Object.values(profile.provenance ?? {})
    .map((p) => p.recorded_on)
    .filter(Boolean)
  if (dates.length === 0) return true
  const newest = dates.sort().at(-1) as string
  const age = Date.now() - new Date(newest).getTime()
  return age > 365 * 24 * 60 * 60 * 1000
}

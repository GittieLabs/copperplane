// Turns docs/video/shotlist.json into exact times for one cut. Pure, so the
// page and the tests use the same code.

// Must match scripts/check_shotlist.py: the validator promises every caption
// this much time, so the timeline has to give it at least that.
export const readingSeconds = (text) => 0.6 + 0.28 * text.trim().split(/\s+/).length;

// The window is on screen alone for this long before the first pullout lifts.
export const ESTABLISH = 0.7;

export function buildTimeline(shotlist, cut) {
  if (!(cut in shotlist.cuts)) throw new Error(`unknown cut ${cut}`);
  const shots = [];
  let at = 0;
  for (const shot of shotlist.shots) {
    const duration = shot.duration[cut];
    if (!duration) continue;
    const start = at;
    const end = at + duration;
    shots.push({
      ...shot,
      start,
      end,
      captions: captionWindows(shot, cut, start, end),
      beats: beatsFor(shot, start, end),
    });
    at = end;
  }
  return { cut, duration: at, shots };
}

// Each caption gets a share of the shot in proportion to how long it takes to
// read, so a long caption is never squeezed to make room for a short one.
export function captionWindows(shot, cut, start, end) {
  const shown = shot.captions.filter((c) => c.cuts.includes(cut));
  const need = shown.map((c) => readingSeconds(c.text));
  const total = need.reduce((a, b) => a + b, 0);
  const scale = total > 0 ? (end - start) / total : 0;
  let at = start;
  return shown.map((c, i) => {
    const w = { text: c.text, start: at, end: at + need[i] * scale };
    at = w.end;
    return w;
  });
}

// When each pullout lifts, and where a clip plays. A shot with a clip gives the
// clip the second half; the pullouts share what is left after the establish.
export function beatsFor(shot, start, end) {
  const pullouts = shot.pullouts || [];
  const establish = Math.min(ESTABLISH, 0.15 * (end - start));
  const clipStart = shot.clip ? start + (end - start) / 2 : end;
  const each = pullouts.length ? (clipStart - start - establish) / pullouts.length : 0;
  const beats = pullouts.map((p, i) => ({
    kind: 'pullout',
    index: i,
    start: start + establish + i * each,
    end: start + establish + (i + 1) * each,
  }));
  if (shot.clip) beats.push({ kind: 'clip', start: clipStart, end });
  return beats;
}

export function activeShot(timeline, t) {
  for (const s of timeline.shots) if (t >= s.start && t < s.end) return s;
  return timeline.shots[timeline.shots.length - 1];
}

// SubRip captions for platforms that take a sidecar file.
export function toSrt(timeline) {
  const stamp = (s) => {
    const ms = Math.round(s * 1000);
    const p = (n, w) => String(n).padStart(w, '0');
    return `${p(Math.floor(ms / 3600000), 2)}:${p(Math.floor(ms / 60000) % 60, 2)}:${p(Math.floor(ms / 1000) % 60, 2)},${p(ms % 1000, 3)}`;
  };
  const cues = timeline.shots.flatMap((s) => s.captions);
  return cues.map((c, i) => `${i + 1}\n${stamp(c.start)} --> ${stamp(c.end)}\n${c.text}\n`).join('\n');
}

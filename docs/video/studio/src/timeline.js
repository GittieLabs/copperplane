// Turns docs/video/shotlist.json into exact times for one cut. Pure, so the
// page and the tests use the same code.

// Must match scripts/check_shotlist.py: the validator promises every caption
// this much time, so the timeline has to give it at least that.
export const readingSeconds = (text) => 0.6 + 0.28 * text.trim().split(/\s+/).length;

// The window is on screen alone for this long before the first pullout lifts.
export const ESTABLISH = 0.7;
export const SHORT_ESTABLISH = 0.35;

export function buildTimeline(shotlist, cut) {
  if (!(cut in shotlist.cuts)) throw new Error(`unknown cut ${cut}`);
  const shots = [];
  let at = 0;
  for (const shot of shotlist.shots) {
    const duration = shot.duration[cut];
    if (!duration) continue;
    const start = at;
    const end = at + duration;
    const captions = captionWindows(shot, cut, start, end);
    shots.push({ ...shot, start, end, captions, beats: beatsFor(shot, start, end, captions) });
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
    const w = { text: c.text, shows: c.shows, start: at, end: at + need[i] * scale };
    at = w.end;
    return w;
  });
}

// Pictures change a beat before the words that talk about them, so the card is
// already moving when its caption lands.
export const LEAD = 0.15;

// When each pullout lifts, and where a clip plays.
//
// A caption's `shows` anchors what it talks about: the pullout (or clip) starts
// with the first caption in this cut that shows it. A pullout no caption in the
// cut shows is left out of that cut. A shot whose captions anchor nothing falls
// back to an even split, with any clip taking the second half.
export function beatsFor(shot, start, end, captions = []) {
  if (shot.kind === 'illustration') {
    // The breadboard routes itself into a PCB as the caption that asks about it lands.
    const c = captions.find((c) => c.shows === 'morph');
    return c ? [{ kind: 'morph', start: Math.max(start, c.start - LEAD), end }] : [];
  }
  const pullouts = shot.pullouts || [];
  // When the shot's first caption already talks about a card, the window gets a
  // short establish: the viewer needs only a glimpse of where the card comes from.
  const leadsWithCard = captions.length > 0 && captions[0].shows !== undefined;
  const establish = leadsWithCard ? SHORT_ESTABLISH : Math.min(ESTABLISH, 0.15 * (end - start));
  const earliest = start + establish;
  const anchorOf = (key) => {
    const c = captions.find((c) => c.shows === key);
    return c ? Math.max(earliest, c.start - LEAD) : null;
  };
  const anchored = captions.some((c) => c.shows !== undefined);

  let marks;
  if (anchored) {
    marks = pullouts.map((_, i) => ({ kind: 'pullout', index: i, start: anchorOf(i) }));
    if (shot.clip) marks.push({ kind: 'clip', start: anchorOf('clip') });
    marks = marks.filter((m) => m.start !== null);
  } else {
    const clipStart = shot.clip ? start + (end - start) / 2 : end;
    const each = pullouts.length ? (clipStart - earliest) / pullouts.length : 0;
    marks = pullouts.map((_, i) => ({ kind: 'pullout', index: i, start: earliest + i * each }));
    if (shot.clip) marks.push({ kind: 'clip', start: clipStart });
  }
  marks.sort((a, b) => a.start - b.start);
  return marks.map((m, i) => ({ ...m, end: i + 1 < marks.length ? marks[i + 1].start : end }));
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

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { buildTimeline, readingSeconds, toSrt, SHORT_ESTABLISH } from '../src/timeline.js';
import { layoutFor, FORMATS, fit } from '../src/layout.js';
import { spring, track, rng, CARD } from '../src/motion.js';

const shotlist = JSON.parse(readFileSync(fileURLToPath(new URL('../../shotlist.json', import.meta.url)), 'utf8'));
const CUTS = Object.keys(shotlist.cuts);
const BUILT = fileURLToPath(new URL('../build/data.json', import.meta.url));

test('each cut runs as long as its shots add up to', () => {
  for (const cut of CUTS) {
    const sum = shotlist.shots.reduce((a, s) => a + (s.duration[cut] || 0), 0);
    assert.ok(Math.abs(buildTimeline(shotlist, cut).duration - sum) < 1e-9, cut);
  }
});

test('shots follow each other with no gap and no overlap', () => {
  for (const cut of CUTS) {
    const { shots } = buildTimeline(shotlist, cut);
    shots.slice(1).forEach((s, i) => assert.ok(Math.abs(s.start - shots[i].end) < 1e-9, `${cut} ${s.id}`));
  }
});

test('every caption gets at least its reading time, as check_shotlist.py promises', () => {
  for (const cut of CUTS) {
    for (const s of buildTimeline(shotlist, cut).shots) {
      for (const c of s.captions) {
        assert.ok(c.end - c.start >= readingSeconds(c.text) - 1e-9, `${cut} ${s.id}: ${c.text}`);
        assert.ok(c.start >= s.start - 1e-9 && c.end <= s.end + 1e-9, `${cut} ${s.id}: outside its shot`);
      }
    }
  }
});

test('a cut shows only the captions marked for it', () => {
  const t15 = buildTimeline(shotlist, '15');
  const texts = t15.shots.flatMap((s) => s.captions.map((c) => c.text));
  assert.ok(!texts.includes('It asks: is that what you meant?'));
  assert.ok(texts.includes('A symbol with 2 pins.'));
});

test('pullouts lift after the window is established and before the shot ends', () => {
  for (const cut of CUTS) {
    for (const s of buildTimeline(shotlist, cut).shots) {
      for (const b of s.beats) {
        assert.ok(b.start >= s.start + SHORT_ESTABLISH - 1e-9, `${cut} ${s.id}`);
        assert.ok(b.end <= s.end + 1e-9, `${cut} ${s.id}`);
      }
    }
  }
});

test('the SubRip file has one cue per caption, in order', () => {
  const tl = buildTimeline(shotlist, '30');
  const srt = toSrt(tl);
  const cues = tl.shots.flatMap((s) => s.captions);
  assert.equal((srt.match(/ --> /g) || []).length, cues.length);
  assert.match(srt, /^1\n00:00:00,000 --> /);
});

test('every format keeps media and captions inside the frame, without overlapping', () => {
  for (const format of Object.keys(FORMATS)) {
    const L = layoutFor(format);
    for (const box of [L.media, L.caption]) {
      assert.ok(box.x >= 0 && box.y >= 0 && box.x + box.w <= L.W && box.y + box.h <= L.H, format);
    }
    assert.ok(L.media.y + L.media.h <= L.caption.y, `${format}: media runs into the caption band`);
  }
});

test('fit keeps the aspect ratio and stays inside the box', () => {
  const r = fit({ x: 0, y: 0, w: 1000, h: 500 }, 2560, 1800);
  assert.ok(Math.abs(r.w / r.h - 2560 / 1800) < 1e-9);
  assert.ok(r.w <= 1000 + 1e-9 && r.h <= 500 + 1e-9);
});

test('a spring starts at 0 and settles at 1', () => {
  assert.equal(spring(0), 0);
  assert.equal(spring(-1), 0);
  assert.ok(Math.abs(spring(5) - 1) < 1e-6);
});

test('track is continuous when its target changes', () => {
  const keys = [[0, 0], [1, 100], [2, 40]];
  const before = track(1.9999, keys, CARD);
  const after = track(2.0001, keys, CARD);
  assert.ok(Math.abs(before - after) < 0.5);
});

test('seeded noise repeats exactly, so renders are identical', () => {
  const a = rng(408);
  const b = rng(408);
  for (let i = 0; i < 100; i++) assert.equal(a(), b());
});

test('a pullout lifts no later than the caption that shows it', () => {
  for (const cut of CUTS) {
    for (const s of buildTimeline(shotlist, cut).shots) {
      for (const b of s.beats.filter((b) => b.kind === 'pullout')) {
        const c = s.captions.find((c) => c.shows === b.index);
        if (c) assert.ok(b.start <= Math.max(c.start, s.start + SHORT_ESTABLISH) + 1e-9, `${cut} ${s.id} pullout ${b.index}`);
      }
    }
  }
});

// The page draws from build/data.json, not the shot list. A field prepare.py
// forgets to copy is silently undefined in the page: on 2026-10-10 a dropped
// `continues` turned a pan into a card that fell back into the window and
// lifted again. Runs only where build/ exists (it is made from the captures).
test('every pullout field the page reads survives into build/data.json', { skip: !existsSync(BUILT) && 'no build/ here' }, () => {
  const data = JSON.parse(readFileSync(BUILT, 'utf8'));
  for (const shot of shotlist.shots) {
    (shot.pullouts || []).forEach((p, i) => {
      const built = data.shots[shot.id].pullouts[i];
      assert.equal(built.continues, Boolean(p.continues), `${shot.id} pullout ${i}: continues`);
      assert.equal(built.accent, p.accent || 'green', `${shot.id} pullout ${i}: accent`);
      assert.deepEqual(built.crop, p.crop, `${shot.id} pullout ${i}: crop`);
      assert.ok(built.highlights.length > 0, `${shot.id} pullout ${i}: no highlight boxes`);
    });
  }
});

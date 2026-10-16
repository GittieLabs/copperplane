// Paints one frame: draw(ctx, scene, t). A pure function of t. Nothing here
// keeps state between frames, so any frame renders the same in any order.

import { clamp, lerp, springOf, fadeOut, CARD, HEAVY, SNAPPY, TEXT, rng } from './motion.js';
import { activeShot } from './timeline.js';
import { fit } from './layout.js';
import { drawColdOpen } from './coldopen.js';

// brand/README.md palette.
export const INK = '#0A1410';
export const PAPER = '#F4F7F3';
export const BRIGHT = '#4FC17E';
const HIGHLIGHT = { green: '#A6E8C0', copper: '#F3C6A2' };

// The push-in overlaps the lift: one move, not two.
export const ZOOM_DELAY = 0.45;

// The breadboard-to-PCB morph: slow and critically damped, so it settles
// without a wobble in about a second and a half.
const MORPH = [16, 8];

const FONT = '"IBM Plex Sans", system-ui, sans-serif';

let gridCache = null;
function grid(W, H) {
  if (gridCache && gridCache.width === W && gridCache.height === H) return gridCache;
  const c = new OffscreenCanvas(W, H);
  const g = c.getContext('2d');
  // The mark is a trace on an 8-unit grid; the stage is that grid, barely there.
  const pitch = Math.round(Math.min(W, H) / 36);
  const r = rng(408);
  for (let y = pitch / 2; y < H; y += pitch) {
    for (let x = pitch / 2; x < W; x += pitch) {
      g.fillStyle = `rgba(79,193,126,${0.035 + 0.03 * r()})`;
      g.fillRect(Math.round(x), Math.round(y), 2, 2);
    }
  }
  gridCache = c;
  return c;
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

// Where a crop of the source image sits on screen, given where the base is drawn.
function mapCrop(crop, baseCrop, placed) {
  const [x, y, w, h] = crop;
  const [bx, by] = baseCrop ? baseCrop : [0, 0];
  return { x: placed.x + (x - bx) * placed.s, y: placed.y + (y - by) * placed.s, w: w * placed.s, h: h * placed.s };
}

function drawBase(ctx, scene, shot, lt, L) {
  const prep = scene.data.shots[shot.id];
  const name = prep.bases[0];
  const img = scene.images[name];
  const bc = shot.base_crop;
  const sw = bc ? bc[2] : img.width;
  const sh = bc ? bc[3] : img.height;
  const placed = fit(L.media, sw, sh);
  // Entry: the window settles in with weight. The hook keeps pushing in slowly.
  const settle = springOf(lt, HEAVY);
  let scale = lerp(1.035, 1, settle);
  scale *= 1 + (shot.kind === 'still' ? 0.06 : 0.02) * clamp(lt / (shot.end - shot.start));
  const cx = placed.x + placed.w / 2;
  const cy = placed.y + placed.h / 2;
  // A still can push in toward a point (source px) instead of its centre.
  let ox = 0, oy = 0;
  if (shot.push_to) {
    const p = clamp(lt / (shot.end - shot.start));
    const px = placed.x + (shot.push_to[0] - (bc ? bc[0] : 0)) * placed.s;
    const py = placed.y + (shot.push_to[1] - (bc ? bc[1] : 0)) * placed.s;
    const e = p * p * (3 - 2 * p);
    scale *= 1 + 0.32 * e;
    // Zoom about the point (it stays put while everything grows), then carry
    // the point most of the way toward the middle of the frame.
    ox = (cx - px) * (scale - 1) + (cx - px) * 0.6 * e;
    oy = (cy - py) * (scale - 1) + (cy - py) * 0.6 * e;
  }
  const drawn = { x: cx - (placed.w * scale) / 2 + ox, y: cy - (placed.h * scale) / 2 + (1 - settle) * 24 + oy,
                  w: placed.w * scale, h: placed.h * scale, s: placed.s * scale };
  if (bc) {
    ctx.save();
    // A pushed-in base never runs into the caption band.
    ctx.beginPath();
    ctx.rect(0, 0, L.W, L.caption.y - L.pad * 0.4);
    ctx.clip();
    roundRect(ctx, drawn.x, drawn.y, drawn.w, drawn.h, 18);
    ctx.clip();
    ctx.drawImage(img, bc[0], bc[1], bc[2], bc[3], drawn.x, drawn.y, drawn.w, drawn.h);
    ctx.restore();
  } else {
    ctx.drawImage(img, drawn.x, drawn.y, drawn.w, drawn.h);
  }
  return { placed: drawn, baseName: name, baseCrop: bc };
}

function cardTarget(L, w, h) {
  const maxW = L.media.w * 0.98;
  const maxH = L.media.h * 0.92;
  const s = Math.min(maxW / w, maxH / h);
  const tw = w * s;
  const th = h * s;
  return { x: L.media.x + (L.media.w - tw) / 2, y: L.media.y + (L.media.h - th) / 2, w: tw, h: th };
}

// Where a pullout's card sits, how far the camera pushes in on its phrase, and
// the point it pushes in on. All at full lift and full zoom; callers blend.
function cardGeometry(L, img, p) {
  const r = cardTarget(L, img.width, img.height);
  const k0 = r.w / img.width;
  const hb = p.highlights.reduce((u, [hx, hy, hw, hh]) => [
    Math.min(u[0], hx), Math.min(u[1], hy), Math.max(u[2], hx + hw), Math.max(u[3], hy + hh)],
  [Infinity, Infinity, -Infinity, -Infinity]);
  const lineH = p.highlights.reduce((a, h) => a + h[3], 0) / p.highlights.length;
  // Push in until the phrase spans the frame, but never past readable text
  // size: in 16:9 a width-only rule made 1,920-px-wide type.
  const zoom = clamp(Math.min((L.W * L.zoomWidth) / ((hb[2] - hb[0]) * k0), L.cardTextPx / (lineH * k0)), 1, 4);
  return { r, k0, zoom, hc: { x: r.x + ((hb[0] + hb[2]) / 2) * k0, y: r.y + ((hb[1] + hb[3]) / 2) * k0 } };
}

function drawPullouts(ctx, scene, shot, t, L, base) {
  const prep = scene.data.shots[shot.id];
  const beats = shot.beats.filter((b) => b.kind === 'pullout');
  if (!beats.length || t < beats[0].start) return;
  const clip = shot.beats.find((b) => b.kind === 'clip');

  // The window dims once and stays dimmed while cards are up.
  const dimStay = clip ? fadeOut(t - clip.start, SNAPPY) : 1;
  const dim = 0.8 * springOf(t - beats[0].start, CARD) * dimStay;
  ctx.fillStyle = `rgba(10,20,16,${dim})`;
  ctx.fillRect(0, 0, L.W, L.H);

  // Cards never run into the caption band, however far the camera pushes in.
  ctx.save();
  ctx.beginPath();
  ctx.rect(0, 0, L.W, L.caption.y - L.pad * 0.4);
  ctx.clip();

  beats.forEach((b, i) => {
    if (t < b.start) return;
    const p = prep.pullouts[b.index];
    const nextBeat = beats[i + 1];
    const handedOn = nextBeat && prep.pullouts[nextBeat.index].continues;
    if (handedOn && t >= nextBeat.start) return;   // the continuation draws this card now
    const img = scene.images[p.file];
    const g = cardGeometry(L, img, p);
    const prevBeat = beats[i - 1];
    const continuing = p.continues && prevBeat;

    const lift = continuing ? 1 : springOf(t - b.start, CARD);
    const next = nextBeat && !handedOn ? nextBeat.start : (clip ? clip.start : Infinity);
    const stay = handedOn ? 1 : fadeOut(t - next, SNAPPY);
    if (stay < 0.001) return;

    // Zoom in after the card lands. A continuation starts fully zoomed on the
    // previous phrase and pans to its own.
    let zoom, hc;
    const zoomStart = continuing ? b.start : b.start + ZOOM_DELAY;
    const zp = springOf(t - zoomStart, HEAVY);
    if (continuing) {
      const pg = cardGeometry(L, scene.images[prep.pullouts[prevBeat.index].file], prep.pullouts[prevBeat.index]);
      zoom = lerp(pg.zoom, g.zoom, zp);
      hc = { x: lerp(pg.hc.x, g.hc.x, zp), y: lerp(pg.hc.y, g.hc.y, zp) };
    } else {
      zoom = lerp(1, g.zoom, zp);
      hc = g.hc;
    }
    // Never a dead frame: once settled, the camera keeps drifting in slowly.
    zoom *= 1 + 0.018 * Math.max(0, t - (zoomStart + 0.8));
    const focusY = L.media.y + L.media.h / 2;
    const zoomedIn = continuing ? 1 : zp;
    const tx = lerp(hc.x, L.W / 2, zoomedIn);
    const ty = lerp(hc.y, focusY, zoomedIn);

    const fromWindow = p.source === base.baseName;
    const origin = fromWindow ? mapCrop(p.crop, base.baseCrop, base.placed)
      : { x: g.r.x, y: g.r.y + 90, w: g.r.w * 0.94, h: g.r.h * 0.94 };
    const r = {
      x: lerp(origin.x, g.r.x, lift), y: lerp(origin.y, g.r.y, lift) - (1 - stay) * 70,
      w: lerp(origin.w, g.r.w, lift), h: lerp(origin.h, g.r.h, lift),
    };

    ctx.save();
    ctx.translate(tx, ty);
    ctx.scale(zoom, zoom);
    ctx.translate(-hc.x, -hc.y);
    ctx.globalAlpha = (fromWindow || continuing ? 1 : clamp(lift * 2.5)) * stay;
    ctx.shadowColor = 'rgba(0,0,0,0.55)';
    ctx.shadowBlur = 70 * lift;
    ctx.shadowOffsetY = 28 * lift;
    roundRect(ctx, r.x, r.y, r.w, r.h, 16);
    ctx.fillStyle = '#FFFFFF';
    ctx.fill();
    ctx.shadowColor = 'transparent';
    ctx.clip();
    ctx.drawImage(img, r.x, r.y, r.w, r.h);

    // The highlight sweeps across the phrase once the card has landed, line by
    // line, like a marker: multiply keeps the text dark underneath it.
    const k = r.w / img.width;
    ctx.globalCompositeOperation = 'multiply';
    ctx.fillStyle = HIGHLIGHT[p.accent] || HIGHLIGHT.green;
    if (continuing) {
      // The previous phrase's highlight fades as the camera leaves it, instead of
      // vanishing in one frame.
      const prev = prep.pullouts[prevBeat.index];
      ctx.save();
      ctx.globalAlpha *= fadeOut(t - b.start, SNAPPY);
      ctx.fillStyle = HIGHLIGHT[prev.accent] || HIGHLIGHT.green;
      prev.highlights.forEach(([hx, hy, hw, hh]) => ctx.fillRect(r.x + (hx - 6) * k, r.y + (hy - 5) * k, (hw + 12) * k, (hh + 10) * k));
      ctx.restore();
    }
    const sweepAt = continuing ? b.start + 0.35 : b.start + 0.5;
    p.highlights.forEach(([hx, hy, hw, hh], j) => {
      const sweep = springOf(t - (sweepAt + 0.22 * j), SNAPPY);
      if (sweep <= 0) return;
      const padX = 6, padY = 5;
      ctx.fillRect(r.x + (hx - padX) * k, r.y + (hy - padY) * k, (hw + 2 * padX) * k * clamp(sweep), (hh + 2 * padY) * k);
    });
    ctx.restore();
  });

  // A close-up runs off both sides of the frame. Fade the edges into the stage
  // so a cut word reads as a camera move, not a crop accident.
  const edge = L.W * 0.08;
  for (const [x0, x1] of [[0, edge], [L.W, L.W - edge]]) {
    const g = ctx.createLinearGradient(x0, 0, x1, 0);
    g.addColorStop(0, 'rgba(10,20,16,0.95)');
    g.addColorStop(1, 'rgba(10,20,16,0)');
    ctx.fillStyle = g;
    ctx.fillRect(Math.min(x0, x1), 0, edge, L.caption.y);
  }
  ctx.restore();
}

function drawClip(ctx, scene, shot, t, L) {
  const beat = shot.beats.find((b) => b.kind === 'clip');
  if (!beat || t < beat.start) return;
  const prep = scene.data.shots[shot.id].clip;
  // The take is retimed to fill its slot, so the whole orbit is always seen.
  const progress = clamp((t - beat.start) / (beat.end - beat.start));
  const frame = prep.frames[Math.min(prep.frames.length - 1, Math.floor(progress * prep.frames.length))];
  const img = scene.images[frame];
  const enter = springOf(t - beat.start, CARD);
  const box = fit(L.media, img.width, img.height);
  const s = lerp(0.92, 1, enter);
  const w = box.w * s;
  const h = box.h * s;
  ctx.save();
  ctx.globalAlpha = clamp(enter * 2);
  ctx.shadowColor = 'rgba(0,0,0,0.5)';
  ctx.shadowBlur = 60;
  ctx.shadowOffsetY = 24;
  roundRect(ctx, box.x + (box.w - w) / 2, box.y + (box.h - h) / 2, w, h, 18);
  ctx.fillStyle = '#E5E7EB';
  ctx.fill();
  ctx.shadowColor = 'transparent';
  ctx.clip();
  ctx.drawImage(img, box.x + (box.w - w) / 2, box.y + (box.h - h) / 2, w, h);
  ctx.restore();
}

function drawSplit(ctx, scene, shot, lt, L) {
  const names = scene.data.shots[shot.id].bases;
  const vertical = L.H > L.W;
  const gap = L.pad;
  names.forEach((name, i) => {
    const img = scene.images[name];
    const slot = vertical
      ? { x: L.media.x, y: L.media.y + i * (L.media.h + gap) / 2, w: L.media.w, h: (L.media.h - gap) / 2 }
      : { x: L.media.x + i * (L.media.w + gap) / 2, y: L.media.y, w: (L.media.w - gap) / 2, h: L.media.h };
    const box = fit(slot, img.width, img.height);
    const enter = springOf(lt - 0.15 * i, CARD);
    const dx = (vertical ? 0 : (i ? 1 : -1) * 120) * (1 - enter);
    const dy = (vertical ? (i ? 1 : -1) * 120 : 0) * (1 - enter);
    ctx.save();
    ctx.globalAlpha = clamp(enter * 2);
    ctx.drawImage(img, box.x + dx, box.y + dy, box.w, box.h);
    ctx.restore();
  });
}

function drawCard(ctx, scene, shot, lt, L) {
  const img = scene.images[scene.data.lockup];
  const box = fit({ x: L.media.x + L.media.w * 0.2, y: L.media.y, w: L.media.w * 0.6, h: L.media.h * 0.75 },
                  img.width, img.height);
  const enter = springOf(lt, HEAVY);
  const s = lerp(0.9, 1, enter);
  ctx.save();
  ctx.globalAlpha = clamp(enter * 1.5);
  ctx.drawImage(img, box.x + (box.w * (1 - s)) / 2, box.y + (box.h * (1 - s)) / 2, box.w * s, box.h * s);
  ctx.restore();
  (shot.card_text || []).forEach((text, i) => {
    const p = springOf(lt - 0.45 - 0.1 * i, TEXT);
    ctx.save();
    ctx.globalAlpha = clamp(p * 1.5);
    ctx.fillStyle = BRIGHT;
    ctx.font = `600 ${Math.round(L.captionSize * 0.72)}px ${FONT}`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.fillText(text, L.W / 2, box.y + box.h + L.pad + (1 - p) * 20 + i * L.captionSize);
    ctx.restore();
  });
}

function wrap(ctx, words, maxW) {
  const lines = [[]];
  for (const w of words) {
    const line = lines[lines.length - 1];
    const trial = [...line, w].join(' ');
    if (line.length && ctx.measureText(trial).width > maxW) lines.push([w]);
    else line.push(w);
  }
  if (lines.length !== 2) return lines;
  // Two lines: split where the longer line is shortest, so a caption never
  // ends on an orphan ("... Minimum: 0.100 / mm.").
  const width = (ws) => ctx.measureText(ws.join(' ')).width;
  let best = lines;
  let bestW = Math.max(width(lines[0]), width(lines[1]));
  for (let i = 1; i < words.length; i++) {
    const a = words.slice(0, i);
    const b = words.slice(i);
    const w = Math.max(width(a), width(b));
    if (w <= maxW && w < bestW) { best = [a, b]; bestW = w; }
  }
  return best;
}

function drawCaption(ctx, shot, t, L) {
  const c = shot.captions.find((c) => t >= c.start && t < c.end);
  if (!c) return;
  // The cold open's lines are titles, set larger than captions.
  const size = Math.round(L.captionSize * (shot.kind === 'illustration' ? 1.25 : 1));
  ctx.save();
  ctx.font = `600 ${size}px ${FONT}`;
  ctx.textBaseline = 'alphabetic';
  const words = c.text.split(/\s+/);
  const lines = wrap(ctx, words, L.caption.w);
  const lineH = size * 1.2;
  const top = L.caption.y + (L.caption.h - lines.length * lineH) / 2 + size;
  const leave = clamp((t - (c.end - 0.18)) / 0.18);
  let k = 0;
  lines.forEach((line, li) => {
    const widths = line.map((w) => ctx.measureText(w).width);
    const space = ctx.measureText(' ').width;
    const total = widths.reduce((a, b) => a + b, 0) + space * (line.length - 1);
    let x = L.W / 2 - total / 2;
    line.forEach((w, wi) => {
      // Words arrive one after another and settle without overshoot.
      // A caption that opens the cut is fully set at 0 s: that frame is the
      // thumbnail on LinkedIn, and a half-arrived word reads as a glitch.
      const p = c.start < 1e-6 ? 1 : springOf(t - c.start - 0.045 * k, TEXT);
      ctx.globalAlpha = clamp(p * 1.6) * (1 - leave);
      // Numbers carry the argument, so they are set in the accent.
      ctx.fillStyle = /\d/.test(w) ? BRIGHT : PAPER;
      ctx.fillText(w, x, top + li * lineH + (1 - p) * 30 - leave * 14);
      x += widths[wi] + space;
      k += 1;
    });
  });
  ctx.restore();
}

export function draw(ctx, scene, t) {
  const L = scene.layout;
  ctx.fillStyle = INK;
  ctx.fillRect(0, 0, L.W, L.H);
  ctx.drawImage(grid(L.W, L.H), 0, 0);

  const shot = activeShot(scene.timeline, t);
  const lt = t - shot.start;
  if (shot.kind === 'illustration') {
    const m = shot.beats.find((b) => b.kind === 'morph');
    // After the morph settles, the camera leans in on D1 for the rest of the shot.
    const leanFrom = m ? m.start + 1.0 : Infinity;
    const lean = clamp((t - leanFrom) / Math.max(0.5, shot.end - leanFrom));
    ctx.save();
    ctx.beginPath();
    ctx.rect(0, 0, L.W, L.caption.y - L.pad * 0.4);   // never into the caption band
    ctx.clip();
    drawColdOpen(ctx, L.media, m ? springOf(t - m.start, MORPH) : 0, lt, lean);
    ctx.restore();
  } else if (shot.kind === 'card') drawCard(ctx, scene, shot, lt, L);
  else if (shot.kind === 'split') drawSplit(ctx, scene, shot, lt, L);
  else {
    const clip = shot.beats.find((b) => b.kind === 'clip');
    if (!clip || t < clip.start + 0.35) {
      const base = drawBase(ctx, scene, shot, lt, L);
      drawPullouts(ctx, scene, shot, t, L, base);
    }
    drawClip(ctx, scene, shot, t, L);
  }
  drawCaption(ctx, shot, t, L);
}

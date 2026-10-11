// Paints one frame: draw(ctx, scene, t). A pure function of t. Nothing here
// keeps state between frames, so any frame renders the same in any order.

import { clamp, lerp, springOf, CARD, HEAVY, SNAPPY, TEXT, rng } from './motion.js';
import { activeShot } from './timeline.js';
import { fit } from './layout.js';

// brand/README.md palette.
export const INK = '#0A1410';
export const PAPER = '#F4F7F3';
export const BRIGHT = '#4FC17E';
const HIGHLIGHT = { green: '#A6E8C0', copper: '#F3C6A2' };

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
  if (shot.kind === 'still') scale *= 1 + 0.06 * clamp(lt / (shot.end - shot.start));
  const cx = placed.x + placed.w / 2;
  const cy = placed.y + placed.h / 2;
  const drawn = { x: cx - (placed.w * scale) / 2, y: cy - (placed.h * scale) / 2 + (1 - settle) * 24,
                  w: placed.w * scale, h: placed.h * scale, s: placed.s * scale };
  if (bc) {
    ctx.save();
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

function drawPullouts(ctx, scene, shot, t, L, base) {
  const prep = scene.data.shots[shot.id];
  const beats = shot.beats.filter((b) => b.kind === 'pullout');
  if (!beats.length || t < beats[0].start) return;
  const clip = shot.beats.find((b) => b.kind === 'clip');

  // The window dims once and stays dimmed while cards are up.
  const dimOut = clip ? springOf(t - clip.start, SNAPPY) : 0;
  const dim = 0.78 * springOf(t - beats[0].start, CARD) * (1 - dimOut);
  ctx.fillStyle = `rgba(10,20,16,${dim})`;
  ctx.fillRect(0, 0, L.W, L.H);

  beats.forEach((b, i) => {
    if (t < b.start) return;
    const p = prep.pullouts[b.index];
    const img = scene.images[p.file];
    const lift = springOf(t - b.start, CARD);
    const next = beats[i + 1] ? beats[i + 1].start : (clip ? clip.start : Infinity);
    const leave = springOf(t - next, SNAPPY);
    if (leave > 0.999) return;

    const target = cardTarget(L, img.width, img.height);
    const fromWindow = p.source === base.baseName;
    const origin = fromWindow ? mapCrop(p.crop, base.baseCrop, base.placed)
      : { x: target.x, y: target.y + 90, w: target.w * 0.94, h: target.h * 0.94 };
    const r = {
      x: lerp(origin.x, target.x, lift), y: lerp(origin.y, target.y, lift) - leave * 70,
      w: lerp(origin.w, target.w, lift), h: lerp(origin.h, target.h, lift),
    };
    // Second beat: once the card has landed, the camera pushes in on the
    // highlighted phrase until it spans most of the frame. A whole card at phone
    // width is as small as the window it came from; the phrase is what must read.
    const k0 = r.w / img.width;
    const hb = p.highlights.reduce((u, [hx, hy, hw, hh]) => [
      Math.min(u[0], hx), Math.min(u[1], hy), Math.max(u[2], hx + hw), Math.max(u[3], hy + hh)],
    [Infinity, Infinity, -Infinity, -Infinity]);
    const zoomTo = clamp((L.W * 0.92) / ((hb[2] - hb[0]) * k0), 1, 3.2);
    const zp = springOf(t - (b.start + 0.75), HEAVY);
    const z = lerp(1, zoomTo, zp);
    const hcx = r.x + ((hb[0] + hb[2]) / 2) * k0;
    const hcy = r.y + ((hb[1] + hb[3]) / 2) * k0;
    const tx = lerp(hcx, L.W / 2, zp);
    const ty = lerp(hcy, L.media.y + L.media.h / 2, zp);

    ctx.save();
    ctx.translate(tx, ty);
    ctx.scale(z, z);
    ctx.translate(-hcx, -hcy);
    ctx.globalAlpha = (fromWindow ? 1 : clamp(lift * 2.5)) * (1 - leave);
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
    p.highlights.forEach(([hx, hy, hw, hh], j) => {
      const sweep = springOf(t - (b.start + 0.5 + 0.22 * j), SNAPPY);
      if (sweep <= 0) return;
      const padX = 6, padY = 5;
      ctx.fillRect(r.x + (hx - padX) * k, r.y + (hy - padY) * k, (hw + 2 * padX) * k * clamp(sweep), (hh + 2 * padY) * k);
    });
    ctx.restore();
  });
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
  return lines;
}

function drawCaption(ctx, shot, t, L) {
  const c = shot.captions.find((c) => t >= c.start && t < c.end);
  if (!c) return;
  const size = L.captionSize;
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
      const p = springOf(t - c.start - 0.045 * k, TEXT);
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
  if (shot.kind === 'card') drawCard(ctx, scene, shot, lt, L);
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

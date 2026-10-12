// The cold open: an illustrated breadboard that routes itself into a PCB.
//
// This is a metaphor, drawn in vector, and the only illustrated shot in the
// video. Every app screen is a real capture, never redrawn. The parts match the
// example board's story (an Arduino, a resistor, a pushbutton and an LED) so the
// match cut into the real board reads as the same project.
//
// The circuit is wired the way a breadboard actually connects: each half-column
// of five holes is one node, so every jumper lands in the column of the pin it
// feeds. And the PCB it becomes is routable: no two traces cross, and every
// bend is 45 degrees, like the trace in the brand mark. Makers would notice
// otherwise.
//
// drawColdOpen(ctx, box, morph, t): `morph` runs from 0 (breadboard) to 1
// (PCB); `t` is seconds into the shot, for the LED's blink. In a tall box the
// whole illustration stands upright (Arduino above the breadboard) so it fills
// a 9:16 or 4:5 frame instead of floating in it; text stays horizontal.

import { clamp, lerp } from './motion.js';

const PAPER = '#F4F7F3';
const BRIGHT = '#4FC17E';
const COPPER = '#C0703A';
const MASK = '#0B5C34';

export const DESIGN = { w: 1000, h: 560 };

const P = 24;                                   // breadboard pitch
const BB = { x: 380, y: 60, w: 600, h: 440 };   // breadboard body
const ARD = { x: 30, y: 80, w: 270, h: 400 };   // Arduino outline
const PCB = { x: 10, y: 30, w: 980, h: 500 };   // the board it becomes

const col = (c) => BB.x + 30 + c * P;
const ROW = {
  topA: BB.y + 30, topB: BB.y + 54,              // top rail (GND)
  a: BB.y + 110, b: BB.y + 134, c: BB.y + 158, d: BB.y + 182, e: BB.y + 206,
  f: BB.y + 254, g: BB.y + 278, h: BB.y + 302, i: BB.y + 326, j: BB.y + 350,
  botA: BB.y + 392, botB: BB.y + 416,            // bottom rail (GND)
};
const EDGE = ARD.x + ARD.w;                       // the Arduino's header edge

// Arduino pins on its header edge, slightly offset from the rows they feed so
// each PCB trace needs a 45-degree jog: the shape of the brand's mark.
const PIN = {
  gnd1: [EDGE - 16, ROW.topB + 26], d13: [EDGE - 16, ROW.a + 26],
  d2: [EDGE - 16, ROW.g - 26], gnd2: [EDGE - 16, ROW.botA - 26],
};

// Parts, in breadboard holes. R1 bridges columns 0 and 5; the LED sits in 5 and
// 6; the button straddles the channel on columns 12 and 14.
const PART = {
  r1: [[col(0), ROW.c], [col(5), ROW.c]],
  led: { a: [col(5), ROW.b], k: [col(6), ROW.b] },
  sw: [[col(12), ROW.e], [col(14), ROW.e], [col(12), ROW.f], [col(14), ROW.f]],
};

// Jumpers: [from, to, sag, colour]. Routed traces follow `route` (corners only).
const WIRES = [
  { from: PIN.gnd1, to: [col(0), ROW.topB], sag: 80, color: BRIGHT,
    route: [[EDGE + 10, PIN.gnd1[1]], [EDGE + 36, ROW.topB]] },
  { from: PIN.d13, to: [col(0), ROW.a], sag: 110, color: COPPER,
    route: [[EDGE + 10, PIN.d13[1]], [EDGE + 36, ROW.a]] },
  { from: [col(6), ROW.a], to: [col(6), ROW.topB], sag: 40, color: BRIGHT, route: [] },
  { from: PIN.d2, to: [col(12), ROW.g], sag: 150, color: COPPER,
    route: [[EDGE + 10, PIN.d2[1]], [EDGE + 36, ROW.g]] },
  { from: [col(14), ROW.h], to: [col(14), ROW.botA], sag: 50, color: BRIGHT, route: [] },
  { from: PIN.gnd2, to: [col(0), ROW.botA], sag: 70, color: BRIGHT,
    route: [[EDGE + 10, PIN.gnd2[1]], [EDGE + 36, ROW.botA]] },
];

// On the PCB the breadboard's hidden connections become visible copper: the
// rails, and the columns joining each pin to its jumper.
const BUS = [
  [[col(0), ROW.topB], [col(23), ROW.topB]],
  [[col(0), ROW.botA], [col(23), ROW.botA]],
  [[col(0), ROW.a], [col(0), ROW.c]],
  [[col(6), ROW.a], [col(6), ROW.b]],
  [[col(12), ROW.f], [col(12), ROW.g]],
  [[col(14), ROW.f], [col(14), ROW.h]],
];

function resample(points, n) {
  const seg = [];
  let total = 0;
  for (let i = 1; i < points.length; i++) {
    const d = Math.hypot(points[i][0] - points[i - 1][0], points[i][1] - points[i - 1][1]);
    seg.push(d);
    total += d;
  }
  const out = [];
  for (let k = 0; k < n; k++) {
    let target = (total * k) / (n - 1);
    let i = 0;
    while (i < seg.length - 1 && target > seg[i]) { target -= seg[i]; i++; }
    const f = seg[i] ? target / seg[i] : 0;
    out.push([lerp(points[i][0], points[i + 1][0], f), lerp(points[i][1], points[i + 1][1], f)]);
  }
  return out;
}

// A jumper arcs up off the board between its ends, like a real wire.
function jumper(w, n) {
  const [x0, y0] = w.from;
  const [x1, y1] = w.to;
  const pts = [];
  for (let k = 0; k <= 40; k++) {
    const s = k / 40;
    pts.push([lerp(x0, x1, s), lerp(y0, y1, s) - Math.sin(Math.PI * s) * w.sag]);
  }
  return resample(pts, n);
}

const routed = (w, n) => resample([w.from, ...w.route, w.to], n);

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

export function drawColdOpen(ctx, box, morph, t, push = 0) {
  const tall = box.h > box.w * 1.15;
  const dw = tall ? DESIGN.h : DESIGN.w;
  const dh = tall ? DESIGN.w : DESIGN.h;
  const s = Math.min(box.w / dw, box.h / dh);
  const cx = box.x + box.w / 2;
  const cy = box.y + box.h / 2;
  ctx.save();
  ctx.translate(cx, cy);
  if (tall) ctx.rotate(-Math.PI / 2);
  ctx.scale(s, s);
  ctx.translate(-DESIGN.w / 2, -DESIGN.h / 2);
  // Once it is a PCB, the camera leans in on D1: the part the video is about to
  // show was never going to work.
  const fx = (PART.led.a[0] + PART.led.k[0]) / 2;
  const fy = PART.led.a[1] - 20;
  const e = push * push * (3 - 2 * push);
  const z = 1 + 0.45 * e;
  ctx.translate(fx + (DESIGN.w / 2 - fx) * 0.5 * e, fy + (DESIGN.h / 2 - fy) * 0.5 * e);
  ctx.scale(z, z);
  ctx.translate(-fx, -fy);
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  // Text that stays upright when the drawing is turned.
  const label = (text, x, y, size, alpha) => {
    if (alpha <= 0) return;
    ctx.save();
    ctx.translate(x, y);
    if (tall) ctx.rotate(Math.PI / 2);
    ctx.globalAlpha *= alpha;
    ctx.fillStyle = PAPER;
    ctx.font = `600 ${size}px "IBM Plex Sans", system-ui, sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(text, 0, 0);
    ctx.restore();
  };

  const m = clamp(morph);
  const bb = 1 - clamp(m * 1.7);          // the breadboard leaves early
  const pcb = clamp((m - 0.2) / 0.8);      // the board arrives late

  // The PCB: solder mask grows out of the breadboard's footprint.
  if (pcb > 0) {
    ctx.save();
    ctx.globalAlpha = pcb;
    roundRect(ctx, lerp(BB.x, PCB.x, pcb), lerp(BB.y, PCB.y, pcb), lerp(BB.w, PCB.w, pcb), lerp(BB.h, PCB.h, pcb), 20);
    ctx.fillStyle = MASK;
    ctx.fill();
    ctx.strokeStyle = 'rgba(244,247,243,0.5)';
    ctx.lineWidth = 2;
    ctx.stroke();
    for (const [hx, hy] of [[PCB.x + 24, PCB.y + 24], [PCB.x + PCB.w - 24, PCB.y + 24],
                            [PCB.x + 24, PCB.y + PCB.h - 24], [PCB.x + PCB.w - 24, PCB.y + PCB.h - 24]]) {
      ctx.beginPath(); ctx.arc(hx, hy, 10, 0, Math.PI * 2);
      ctx.strokeStyle = COPPER; ctx.lineWidth = 5; ctx.stroke();
    }
    // The connections a breadboard hides inside its strips, now visible copper.
    ctx.strokeStyle = COPPER;
    ctx.lineWidth = 7;
    for (const [a, b] of BUS) {
      ctx.beginPath(); ctx.moveTo(a[0], a[1]); ctx.lineTo(lerp(a[0], b[0], pcb), lerp(a[1], b[1], pcb)); ctx.stroke();
    }
    ctx.restore();
  }

  // The breadboard: body, centre channel, rail stripes and the hole grid.
  if (bb > 0) {
    ctx.save();
    ctx.globalAlpha = bb;
    roundRect(ctx, BB.x, BB.y, BB.w, BB.h, 14);
    ctx.fillStyle = 'rgba(244,247,243,0.04)';
    ctx.fill();
    ctx.strokeStyle = 'rgba(244,247,243,0.7)';
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.fillStyle = 'rgba(244,247,243,0.08)';
    ctx.fillRect(BB.x + 10, ROW.e + 14, BB.w - 20, ROW.f - ROW.e - 28);
    for (const [y, c] of [[ROW.topA - 14, BRIGHT], [ROW.botB + 14, BRIGHT]]) {
      ctx.globalAlpha = bb * 0.7;
      ctx.beginPath(); ctx.moveTo(BB.x + 18, y); ctx.lineTo(BB.x + BB.w - 18, y);
      ctx.strokeStyle = c; ctx.stroke();
    }
    ctx.globalAlpha = bb;
    ctx.fillStyle = 'rgba(244,247,243,0.34)';
    for (const y of Object.values(ROW)) {
      for (let c = 0; c < 24; c++) ctx.fillRect(col(c) - 3, y - 3, 6, 6);
    }
    ctx.restore();
  }

  // The Arduino, which on the PCB becomes A1's outline and header.
  ctx.save();
  roundRect(ctx, ARD.x, ARD.y, ARD.w, ARD.h, 16);
  ctx.fillStyle = `rgba(16,116,63,${lerp(0.35, 0, m)})`;
  ctx.fill();
  ctx.strokeStyle = `rgba(244,247,243,${lerp(0.85, 0.5, m)})`;
  ctx.lineWidth = 2.5;
  ctx.stroke();
  ctx.fillStyle = `rgba(244,247,243,${lerp(0.55, 0, m)})`;
  ctx.fillRect(ARD.x - 8, ARD.y + 60, 64, 52);   // USB jack
  ctx.fillRect(ARD.x - 8, ARD.y + 290, 56, 70);  // power jack
  ctx.fillStyle = COPPER;
  for (let k = 0; k < 14; k++) ctx.fillRect(EDGE - 22, ARD.y + 24 + k * 26, 12, 12);
  ctx.restore();
  label(m < 0.5 ? 'ARDUINO' : 'A1', ARD.x + ARD.w / 2 - 20, ARD.y + ARD.h / 2, 30, m < 0.5 ? 1 - m * 2 : (m - 0.5) * 2);

  // Wires: arcing jumpers that settle into 45-degree traces.
  const N = 48;
  for (const w of WIRES) {
    const a = jumper(w, N);
    const b = routed(w, N);
    ctx.beginPath();
    a.forEach(([x, y], k) => {
      const px = lerp(x, b[k][0], m);
      const py = lerp(y, b[k][1], m);
      if (k) ctx.lineTo(px, py); else ctx.moveTo(px, py);
    });
    ctx.strokeStyle = m > 0.55 ? COPPER : w.color;
    ctx.lineWidth = lerp(6, 7, m);
    ctx.stroke();
  }

  // Pads under every pin, as the board arrives.
  if (pcb > 0) {
    const pins = [...Object.values(PIN), ...PART.r1, PART.led.a, PART.led.k, ...PART.sw];
    ctx.save();
    ctx.globalAlpha = pcb;
    for (const [x, y] of pins) {
      ctx.beginPath(); ctx.arc(x, y, 9, 0, Math.PI * 2); ctx.fillStyle = COPPER; ctx.fill();
      ctx.beginPath(); ctx.arc(x, y, 3.5, 0, Math.PI * 2); ctx.fillStyle = MASK; ctx.fill();
    }
    ctx.restore();
  }

  // R1: a beige body with colour bands, becoming a silkscreen outline.
  const [ra, rb] = PART.r1;
  ctx.save();
  ctx.strokeStyle = PAPER; ctx.lineWidth = 3;
  ctx.beginPath(); ctx.moveTo(ra[0], ra[1]); ctx.lineTo(rb[0], rb[1]); ctx.stroke();
  roundRect(ctx, ra[0] + 30, ra[1] - 12, rb[0] - ra[0] - 60, 24, 9);
  ctx.fillStyle = m > 0.5 ? MASK : '#D8C49A'; ctx.fill(); ctx.stroke();
  ctx.globalAlpha = 1 - m;
  [['#8B4A2B', 0], ['#111', 1], ['#C0703A', 2], ['#B8962E', 4]].forEach(([c, k]) => {
    ctx.fillStyle = c; ctx.fillRect(ra[0] + 40 + k * 10, ra[1] - 11, 5, 22);
  });
  ctx.restore();

  // SW1: a tactile switch across the channel.
  ctx.save();
  const [s1, s2, s3] = PART.sw;
  roundRect(ctx, s1[0] - 10, s1[1] - 10, s2[0] - s1[0] + 20, s3[1] - s1[1] + 20, 6);
  ctx.fillStyle = m > 0.5 ? 'rgba(0,0,0,0)' : 'rgba(30,30,30,0.9)'; ctx.fill();
  ctx.strokeStyle = PAPER; ctx.lineWidth = 3; ctx.stroke();
  ctx.beginPath(); ctx.arc((s1[0] + s2[0]) / 2, (s1[1] + s3[1]) / 2, 15, 0, Math.PI * 2); ctx.stroke();
  ctx.restore();

  // D1 blinks, once a second, until it is a footprint.
  const lx = (PART.led.a[0] + PART.led.k[0]) / 2;
  const ly = PART.led.a[1] - 40;
  // Lit at 0 s: the first frame is the thumbnail.
  const lit = ((Math.cos(t * Math.PI * 2) + 1) / 2) * (1 - m);
  ctx.save();
  if (lit > 0.02) {
    const g = ctx.createRadialGradient(lx, ly, 2, lx, ly, 80);
    g.addColorStop(0, `rgba(79,193,126,${0.6 * lit})`);
    g.addColorStop(1, 'rgba(79,193,126,0)');
    ctx.fillStyle = g;
    ctx.fillRect(lx - 80, ly - 80, 160, 160);
  }
  ctx.strokeStyle = PAPER; ctx.lineWidth = 3;
  ctx.beginPath(); ctx.moveTo(PART.led.a[0], PART.led.a[1]); ctx.lineTo(lx - 6, ly + 14); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(PART.led.k[0], PART.led.k[1]); ctx.lineTo(lx + 6, ly + 14); ctx.stroke();
  ctx.beginPath(); ctx.arc(lx, ly, 17, Math.PI, 0); ctx.lineTo(lx + 17, ly + 14); ctx.lineTo(lx - 17, ly + 14); ctx.closePath();
  ctx.fillStyle = `rgba(79,193,126,${0.22 + 0.78 * lit})`; ctx.fill(); ctx.stroke();
  ctx.restore();

  // D1's pads pulse in copper while the camera leans in: a question mark.
  if (push > 0) {
    const phase = (t * 1.25) % 1;
    ctx.save();
    ctx.globalAlpha = clamp(push * 3) * (1 - phase);
    ctx.strokeStyle = COPPER;
    ctx.lineWidth = 3;
    for (const [x, y] of [PART.led.a, PART.led.k]) {
      ctx.beginPath(); ctx.arc(x, y, 10 + 22 * phase, 0, Math.PI * 2); ctx.stroke();
    }
    ctx.restore();
  }

  const names = clamp((m - 0.55) / 0.45);
  label('R1', (ra[0] + rb[0]) / 2, ra[1] + 30, 22, names);
  label('D1', lx, ly - 34, 22, names);
  label('SW1', (s1[0] + s2[0]) / 2, s3[1] + 34, 22, names);
  ctx.restore();
}

// Motion primitives. Every one is a pure function of time, so `seek(t)` can
// paint any frame without simulating the frames before it, and two renders of
// the same cut are identical.

export const clamp = (x, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, x));

export const lerp = (a, b, p) => a + (b - a) * p;

// Closed-form damped spring from 0 to 1. `k` is stiffness and `d` is damping.
// Under-damped values overshoot a hair, which is what makes motion feel like it
// has mass. Critically damped (z >= 1) settles with no overshoot.
export function spring(t, k = 170, d = 26) {
  if (t <= 0) return 0;
  const w0 = Math.sqrt(k);
  const z = d / (2 * w0);
  if (z < 1) {
    const wd = w0 * Math.sqrt(1 - z * z);
    return 1 - Math.exp(-z * w0 * t) * (Math.cos(wd * t) + (z * w0 / wd) * Math.sin(wd * t));
  }
  return 1 - Math.exp(-w0 * t) * (1 + w0 * t);
}

// Presets. Text never overshoots: a caption that wobbles is harder to read.
export const SNAPPY = [320, 30];   // highlight sweeps, small UI
export const CARD = [170, 24];     // a card lifting out of the window
export const HEAVY = [120, 22];    // the window itself, logo lockups
export const TEXT = [260, 40];     // captions: critically damped, no overshoot

export const springOf = (t, preset) => spring(t, preset[0], preset[1]);

// 1 to 0 on a spring, for anything that fades out. `1 - springOf(...)` is not
// enough: an under-damped preset overshoots 1, the difference goes negative, and
// a canvas ignores a negative globalAlpha and keeps the previous value, so the
// faded thing flashes back at full strength while the spring rings.
export const fadeOut = (t, preset) => clamp(1 - springOf(t, preset));

// A value with several targets: one spring per change, each from its own start
// time, summed. Motion stays continuous across target changes, and any frame is
// still a closed-form evaluation. keys: [[time, value], ...] sorted by time.
export function track(t, keys, preset = CARD) {
  let v = keys[0][1];
  for (let i = 1; i < keys.length; i++) {
    v += (keys[i][1] - keys[i - 1][1]) * springOf(t - keys[i][0], preset);
  }
  return v;
}

// Seeded noise, never Math.random: the render must be identical every run.
export function rng(seed) {
  return () => {
    seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

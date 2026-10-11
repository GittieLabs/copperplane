// One layout per format. Each format gets its own framing (the post's rule, and
// the script's: "a 16:9 export letterboxed into a vertical feed reads as
// somebody else's video"). Nothing is cropped from another format's render.

export const FORMATS = {
  '9x16': { width: 1080, height: 1920 },
  '1x1': { width: 1080, height: 1080 },
  '16x9': { width: 1920, height: 1080 },
};

export function layoutFor(format) {
  const f = FORMATS[format];
  if (!f) throw new Error(`unknown format ${format}`);
  const { width: W, height: H } = f;
  const pad = Math.round(Math.min(W, H) * 0.045);
  if (format === '9x16') {
    return {
      W, H, pad,
      media: { x: pad, y: Math.round(H * 0.1), w: W - 2 * pad, h: Math.round(H * 0.6) },
      caption: { x: pad, y: Math.round(H * 0.72), w: W - 2 * pad, h: Math.round(H * 0.16) },
      captionSize: 68,
      zoomWidth: 0.92,
      cardTextPx: 52,
    };
  }
  if (format === '1x1') {
    return {
      W, H, pad,
      media: { x: pad, y: pad, w: W - 2 * pad, h: Math.round(H * 0.68) },
      caption: { x: pad, y: Math.round(H * 0.76), w: W - 2 * pad, h: Math.round(H * 0.2) },
      captionSize: 52,
      zoomWidth: 0.9,
      cardTextPx: 44,
    };
  }
  return {
    W, H, pad,
    media: { x: pad, y: pad, w: W - 2 * pad, h: Math.round(H * 0.74) },
    caption: { x: pad, y: Math.round(H * 0.82), w: W - 2 * pad, h: Math.round(H * 0.15) },
    captionSize: 56,
    zoomWidth: 0.66,
    cardTextPx: 46,
  };
}

// Largest rect of aspect `aw:ah` that fits inside `box`, centred.
export function fit(box, aw, ah) {
  const s = Math.min(box.w / aw, box.h / ah);
  const w = aw * s;
  const h = ah * s;
  return { x: box.x + (box.w - w) / 2, y: box.y + (box.h - h) / 2, w, h, s };
}

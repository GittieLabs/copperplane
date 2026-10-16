# Product video: review log

The critique loop for the three cuts (`CTX-408.7` Phase 5).

**Method.** Each round renders the cuts and makes three kinds of evidence (`docs/video/studio/sheets.py`):

- **Phone sheet:** the frame in the middle of every caption, at 360 px wide. That is when a viewer is
  reading, at the size they read it.
- **Contact sheet:** one frame every half second, sampled by time.
- **Motion strips:** consecutive frames around the fast moves (a card lifting, a pan between phrases),
  to catch pops that no still shows.

Each round is scored 1–10 by a harsh motion director, not a proud author. The three worst problems get
fixed, and the loop repeats until every score is 8 or more.

**What is scored:**

| Criterion | What it means |
|---|---|
| Hook | The first 2 s |
| Readability | At phone size |
| Motion | Pops, overlaps, dead frames |
| Variety | Something new every 2–3 s |
| Composition | Use of the frame |
| Accuracy | The real app, real numbers, the right words highlighted |

## Scores

| Round | Hook | Readability | Motion | Variety | Composition | Accuracy | Cut reviewed |
|---|---|---|---|---|---|---|---|
| 0 (Phase 4 draft) | 4 | 4 | — | 6 | 4 | 8 | 15s 9:16 |
| 1 | 5 | 7 | — | 7 | 5 | 8 | 15s 9:16, 30s 1:1, 60s 16:9 |
| 2 | 7 | 8 | 6 | 8 | 7 | 8 | 30s 1:1, plus motion strips |
| 3 (final) | 8 | 8 | 8 | 8 | 8 | 9 | 60s 9:16, all nine rendered |

Motion was not scored until round 2 because stills cannot show it. The strips that started in round 2
found the worst defect of the whole loop.

## Round 0: the first full render

- **Pullout text was unreadable on a phone.** A 1,792-px card fitted to a 1,080-px frame has text as
  small as the window it came from. *Fix:* a push-in on the highlighted phrase after the card lands.
- The frame was mostly empty: a landscape window letterboxed into 9:16.
- Captions and cards changed at different times.

## Round 1

- **Captions and cards were out of sync.** "No rule was broken." sat under the "2 pins" zoom.
  *Fix:* each caption names the card it `shows`, and the card lifts with it.
  A `continues` card stays up and re-points its highlight, so "4 pads" pans to "is a 4-pad footprint"
  instead of staying on "2 pins".
- **"2 pins" was readable for under half a second** (lift at +0.7 s, zoom at +0.75 s, handoff at
  8.58 s). *Fix:*
  - a shorter establish when the shot's first caption is about a card;
  - the push-in now overlaps the lift.
- **16:9 zoom overshot.** Aiming the phrase at 92% of 1,920 px made giant type spilling off both
  edges. *Fix:* zoom is capped by text height per format, and cards never enter the caption band.
- **Dead beat:** at 13.9 s nothing moved for half a second, caught by the determinism check.
  *Fix:* a slow drift once a zoom settles, and on every base window.
- **Orbit too small.** *Fix:* the clip crop is the measured union of the case across the take, plus
  60 px. It took three attempts to measure, because the viewport's gray matched the button row
  beneath it.
- **Hook was a shrunken KiCad window.** *Fix:* crop to the board itself, with all four mounting holes
  and SW1, D1, R1.
- **Zoomed cards ended in hard-cut half-words.** *Fix:* the frame edges fade into the stage.

## Round 2

- **Long single-line phrases barely zoomed:** the zoom had to fit the whole phrase.
  - "2 of these were found by Copperplane. ERC and DRC do not report them." became "ERC and DRC do
    not report them."
  - "KiCad reports 4 design-rule violations, 1 unconnected item." became "4 design-rule violations,
    1 unconnected item".
  - The rest of each line runs into the edge fade.
- **Orphaned caption words** ("Minimum: 0.100 / mm."). *Fix:* two-line captions split where the
  longer line is shortest.
- **The motion strip showed a pop no still frame could.** At the "2 pins" → "4 pads" handoff, the
  zoomed card dropped back into the window and a new card lifted.
  - *Cause:* `prepare.py` never copied `continues` into `build/data.json`, so the page saw a new card.
  - *Fix:* copy it.
  - *Guard:* a test that every pullout field the page reads survives into the built data. It failed
    on the stale build and passed after re-preparing.
- The old highlight vanished in one frame at a pan. *Fix:* it fades as the camera leaves.

## Round 3 (final)

- **Hook (7 → 8):** the board now pushes in toward D1, carried toward the middle of the frame. That
  is the LED segment 5 shows was never going to work, so the opening quietly points at the punchline.
- Nothing else scored under 8.

## Round 4: the maintainer's first watch (Phase 6)

**Verdict:** "I'm missing the 'catch your attention quick' moment. Even a maker might miss the fact
this video is for them."

My round-3 score of 8 for the hook was wrong, and this is why.

- **The first frame was a PCB layout in KiCad.** That is the stage a breadboard maker has not
  reached, so it said "for people who already do PCBs".
- **"Your breadboard works." was a statement,** with nothing to make a scroller stop.
- **The tension arrived late:** at 7 s in the 15 s cut, and after 25 s in the 60 s cut.

I had scored the hook on composition and motion, and never asked who it was talking to.

**Fix:** a cold open, "It works on the breadboard." → "Will it work as a PCB?"

- **It is illustrated in vector,** because no breadboard footage exists. An Arduino, R1, a button
  and a blinking LED sit on a breadboard drawn the way breadboards connect.
- **The jumpers settle into 45-degree traces** and the breadboard becomes a routable PCB, with no
  crossing traces.
- **The camera then leans in on D1 while its pads pulse.** That is the LED the next shot shows was
  never going to work.
- **First frame:** the line is already set and the LED is lit, because it is the thumbnail.

**Storyboard critique, before animating:**

- the first layout floated small in 9:16, so tall formats now stand the drawing upright;
- its traces crossed, so the circuit was rewired column by column, the way a breadboard connects;
- the morph finished in half a second and then held still for 1.7 s, so it slowed to about 1 s,
  and the lean-in now fills the rest;
- the leaning board ran into the caption band, so it is clipped.

**The 15 s cut changed shape.** The two hook lines need 4.3 s to read, so it became the cold open
plus the D1 answer, dropping the +5V finding.

## Round 5: 4:5 for the LinkedIn feed (`CTX-408.8`)

The new 4:5 cut was reviewed at the feed's own sizes instead of a bare phone: 390 px (mobile feed)
and 555 px (desktop feed). The cold open fills the frame width, every pullout phrase reads, and the
captions mostly fit on one line.

| Hook | Readability | Motion | Variety | Composition | Accuracy |
|---|---|---|---|---|---|
| 8 | 8 | 8 | 8 | 8 | 9 |

Motion is shared with the other formats; nothing new moves in 4:5.

**Still visible, not fixed:**

- **Weakest contrast in the cut:** "4 design-rule violations, 1 unconnected item" is the app's orange
  text under a green highlight. It reads, but it is the weakest contrast in the cut.
- **The side-by-side (segment 7) is two small windows in every format.** It reads as a concept shot,
  not as detail.
- **In the 15 s cut the hook runs 1.5 s,** so the push toward D1 only gets about half way.

These scores are mine, about my own work. Phase 6 is the maintainer watching each cut on a phone,
muted, and that verdict is the one that counts.

## Round 6: the faded highlight blinks back (2026-10-16)

Found while porting the compositor to Rigovera, not by this loop. Its render showed the previous
phrase's highlight flash back about 1.1 s after a `continues` pan. A motion strip caught it there;
still frames had not.

- **Cause:** round 2's fix faded the old highlight with `globalAlpha *= 1 - spring(SNAPPY)`.
  `SNAPPY` is under-damped, so the spring overshoots 1 and `1 - spring` goes negative (as low as
  -0.008 at +0.32 s). A canvas ignores a negative `globalAlpha` and keeps the previous value, 1.
- **It was worse than reported: four blinks, not one.** The spring rings, so `1 - spring` is
  negative in lobes about 0.32 s long, starting at +0.26, +0.91, +1.55 and +2.2 s. Every lobe draws
  the highlight at full strength, however small the overshoot.
- **Every cut had it.** The "2 pins" → "4 pads" handoff in segment 5 is in all three cuts. The 60 s
  cut also has it at the "14.1mm needed" → "6 components" handoff in segment 6.
- **Fix:** `fadeOut(t, preset)` in `src/motion.js` clamps `1 - spring` to [0, 1]. It is used for
  the old highlight, a card's alpha as it leaves, and the window dim when a clip starts.
  - **Guard:** a test that `fadeOut` stays in [0, 1] over 0-2 s. It also asserts that `SNAPPY`
    still overshoots, so the bound cannot pass vacuously.
- **Only the highlight ever flashed.** Checked in Chrome, not assumed:
  - A card's leave fade was already safe, because it returns once the spring passes 0.999, before
    `1 - leave` goes negative.
  - The dim is an `rgba()` string, and Chrome clamps a negative alpha in a color string to 0.
  - Both now use `fadeOut` anyway, so nothing depends on either accident.

**Evidence.** `sheets.py --strip T0 T1` now makes the strip: every frame at 15 fps, from 0.2 s
before each handoff to 2.4 s after it. It was run on the 9:16 render of each cut, before (the
2026-10-10 renders) and after:

| Cut | Handoff | Before | After |
|---|---|---|---|
| 15 | "2 pins" → "4 pads", 6.20 s | blinks back at 6.47, 7.13, 7.80, 8.40 s | fades by 6.40 s, stays gone |
| 30 | "2 pins" → "4 pads", 23.70 s | blinks back from +0.26 s, four times | fades, stays gone |
| 60 | "2 pins" → "4 pads", 36.55 s | blinks back from +0.26 s, four times | fades, stays gone |
| 60 | "14.1mm needed" → "6 components", 45.96 s | blinks back at 46.23, 46.89, 47.49, 48.16 s | fades, stays gone |

**The fix changed nothing else, and that was checked too.** Each old render was compared with its
new one frame by frame (mean absolute difference), in all four formats at all four handoffs. The
two differ only in the four lobes, at +0.26-0.56, +0.93-1.20, +1.57-1.87 and +2.20-2.43 s. Elsewhere
the difference is encoder noise, a median of 0.05-0.11 on a 0-255 scale. The only motion strips
looked at are from 9:16; the other formats were compared numerically.

**The published cuts are the old renders.** They are the 12 on the `product-video-2026-10` release
and the two site copies in `docs/site/public/video/`. All of them contain the "2 pins" handoff. They
are not replaced here.

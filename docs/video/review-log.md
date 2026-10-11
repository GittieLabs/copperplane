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

**Still visible, not fixed:**

- **Weakest contrast in the cut:** "4 design-rule violations, 1 unconnected item" is the app's orange
  text under a green highlight. It reads, but it is the weakest contrast in the cut.
- **The side-by-side (segment 7) is two small windows in every format.** It reads as a concept shot,
  not as detail.
- **In the 15 s cut the hook runs 1.5 s,** so the push toward D1 only gets about half way.

These scores are mine, about my own work. Phase 6 is the maintainer watching each cut on a phone,
muted, and that verdict is the one that counts.

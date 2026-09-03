import { configure } from '@testing-library/dom'

/** One deadline for the whole suite, set to reflect how it actually runs.
 *
 *  `waitFor` and `findBy*` default to a 1000ms **wall-clock** deadline. This
 *  suite runs 44 files in parallel across shared cores, so a test that
 *  completes in 30ms alone can sit unscheduled for a second under load — and
 *  time out having done nothing wrong.
 *
 *  Two tests in `Overview.test.tsx` did exactly that, on different days,
 *  passing 3/3 in isolation both times. The first was "fixed" by raising that
 *  one call to 5s; the second then failed the same way. Raising a number twice
 *  is the signal that the number was never the problem.
 *
 *  So the deadline is set once, here, for a reason that is about the
 *  environment rather than about any test. It does not weaken an assertion:
 *  every one still has to become true, and a genuinely broken expectation
 *  fails at 5s exactly as it failed at 1s — it just takes longer to say so. */
configure({ asyncUtilTimeout: 5000 })

/* Kept deliberately below vite.config.ts's `testTimeout`. When the two were
   equal, a missing element produced "Test timed out in 5000ms" rather than
   testing-library's own message naming what it waited for -- a worse failure
   than the flake this was meant to fix. */

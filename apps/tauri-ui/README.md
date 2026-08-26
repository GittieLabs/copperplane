# Copperplane — Frontend

The Tauri app's UI: React 19 + TypeScript + Vite, styled with Tailwind. This is one of three real
layers in the project — see [the root README](../../README.md) for the full picture and
[`core/tauri-rust`](../../core/tauri-rust)/[`services/python-daemon`](../../services/python-daemon)
for the other two.

## What's here

*   `src/components/` — real UI surfaces: `Rail` (the project/library navigation shell),
    `ComponentDiscovery` (part search + disambiguation), `PartDetail` (pin table, save-to-library,
    footprint search/attach), `EnclosureViewer` (the 3D `.glb` viewer), `Settings`.
*   `src/lib/` — typed clients for the daemon's real JSON-RPC routes (`ipc.ts` is the shared
    request/job-tracking layer everything else builds on), plus `commands.ts` (the chat surface's
    string-command recognizer — being phased out per `PRODUCT-PLAN.md` §7 in favor of dedicated
    per-stage surfaces like `ComponentDiscovery`).

Every non-trivial piece here has a real `SPEC-*.md`/`CTX-*.md` pair under `specs/`/`context/` in
this directory (or the repo root, for cross-cutting work) — read those before assuming why
something is shaped the way it is.

## Running it

This app doesn't run standalone in a useful way — it's the UI half of a Tauri app whose other half
(the Rust process supervisor) spawns and owns the Python daemon it talks to. From the repo root:

```bash
cd core/tauri-rust
npx @tauri-apps/cli@2 dev
```

That starts this frontend's own dev server for you (`npm run dev`, i.e. plain Vite) as part of
bringing up the whole app. Running `npm run dev` here in isolation is only useful for iterating on
markup/styling without a live daemon connection.

## Testing

```bash
npm install
npx tsc -b            # typecheck
npx oxlint             # lint
npx vitest run         # unit tests (vi.mock'd daemon calls, no live KiCad/FreeCAD needed)
npx vite build          # production build
```

`vitest` tests are colocated with the code they cover (`*.test.ts`/`*.test.tsx`). None of them talk
to a real daemon — they mock `lib/ipc.ts`'s `dispatch`/`submitJob` and assert on the real UI
behavior around the mocked response, which is why they run identically on every platform in CI.

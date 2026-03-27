# CLAUDE.md

## What This Is

A browser-based platformer engine where users bring their own colored pencil art, drop it into tile-map levels, and tune character physics. Mario-style movement (walk, jump, climb) with an edit-then-play tuning panel. Built with React + HTML5 Canvas + TypeScript. No external game engine.

## Key Docs

- `docs/platformer-prd-v1.md` — Full product spec. Physics params, level JSON schema, sprite sheet format, feature details.
- `docs/platformer-build-plan.md` — Module map, data types, interface contracts, phased build order with checkpoints.

Read both before starting work. The build plan defines the implementation phases — follow them in order.

## Running the Project

```bash
npm install
npm run dev
```

Dev server runs at `localhost:5173` (Vite). No backend.

## Architecture Rules

1. **`src/engine/` has zero React imports.** Pure TypeScript. No DOM, no components, no hooks. This is the hardest rule — don't break it.
2. **`src/renderer/` reads state, never mutates it.** One-way data flow from engine → renderer.
3. **`src/ui/` talks to the engine only through `GameCanvas.tsx`.** React never reaches into engine internals.
4. **React never re-renders in response to game loop ticks.** The game loop writes to a plain GameState object. UI reads it via throttled polling (4 Hz for status bar).

## Conventions

- **Immutable updates in engine code.** `PlayerController.update()` returns a new Player, doesn't mutate the old one.
- **World pixel coordinates everywhere in the engine.** Tile coords are only used when parsing level JSON. Name parameters `worldX`, `worldY` — never ambiguous `x`, `y`.
- **All shared types live in `engine/types.ts`.** Don't define entity shapes in component files.
- **Console logging behind a DEBUG flag.** Log state transitions, collisions, entity events — but make it silenceable.

## Dimensions

- Tiles: 64×64 px
- Characters: 64×128 px (1×2 tiles)
- Screen grid: 25×15 tiles = 1600×960 px viewport
- Physics values are in pixels per frame at 60 Hz

## Common Mistakes to Avoid

- **Collision axis order:** Resolve X first, update position, then resolve Y. Doing both at once causes corner-sticking.
- **Jump input:** `jumpPressed` (edge-triggered, one frame only) vs `jump` (held). Getting this wrong ruins the feel.
- **Fixed timestep:** Accumulate real time, step in fixed increments. Never use rAF delta directly as physics dt.
- **Moving platforms:** Calculate platform `vx`/`vy` from path interpolation each frame. Player inherits this velocity when grounded on platform.
- **Sprite flipping:** `ctx.scale(-1, 1)` for facing left — remember to translate context by sprite width.
- **Screen transitions:** Lock player input during the 300ms slide. Snap player position to new screen entry edge when complete.

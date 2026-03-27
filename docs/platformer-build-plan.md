# Platformer Creator — Build Plan for Claude Code

This is the implementation guide for V1. It defines the directory structure, module responsibilities, data shapes that flow between systems, and a phased build order where each step produces something testable.

Reference the PRD (`platformer-prd-v1.md`) for full specs on physics parameters, level JSON schema, sprite sheet conventions, and feature details.

---

## Directory Structure

```
platformer/
├── public/
│   ├── index.html
│   └── assets/
│       ├── tiles/                  # Default tile PNGs (64×64 each)
│       │   ├── ground_top.png
│       │   ├── ground_fill.png
│       │   ├── bridge.png
│       │   └── vine.png
│       ├── sprites/                # Default character/NPC/collectible sprite sheets
│       │   ├── player.png
│       │   ├── player.manifest.json
│       │   ├── coin.png
│       │   └── coin.manifest.json
│       ├── sounds/                 # Default sound effects
│       │   ├── jump.mp3
│       │   ├── land.mp3
│       │   ├── collect.mp3
│       │   ├── transition.mp3
│       │   └── goal.mp3
│       └── levels/
│           └── demo.json           # Starter level for testing
├── src/
│   ├── index.tsx                   # React entry point
│   ├── App.tsx                     # Top-level layout (canvas + sidebar + toolbar)
│   │
│   ├── engine/                     # Game engine (zero React dependencies)
│   │   ├── GameLoop.ts             # requestAnimationFrame loop, fixed timestep
│   │   ├── InputManager.ts         # Keyboard state tracking
│   │   ├── Physics.ts              # Gravity, velocity, acceleration, friction
│   │   ├── Collision.ts            # AABB resolution against tile grid
│   │   ├── PlayerController.ts     # Input → physics → state machine
│   │   ├── Camera.ts               # Screen-by-screen tracking + transitions
│   │   ├── EntityManager.ts        # Manages NPCs, collectibles, moving platforms
│   │   ├── SoundManager.ts         # Event-driven audio playback
│   │   ├── SpriteSheet.ts          # Loads sprite sheet + manifest, provides frames
│   │   ├── TileMap.ts              # Parses level JSON, provides tile lookups
│   │   └── types.ts                # All shared TypeScript types
│   │
│   ├── renderer/                   # Canvas rendering (reads engine state, draws)
│   │   ├── Renderer.ts             # Main render orchestrator
│   │   ├── TileRenderer.ts         # Draws tile grid for current screen
│   │   ├── SpriteRenderer.ts       # Draws animated sprites (player, NPCs, items)
│   │   └── HUD.ts                  # Score, screen label, FPS counter
│   │
│   ├── ui/                         # React UI components
│   │   ├── TuningPanel.tsx         # Physics parameter sliders + presets
│   │   ├── Toolbar.tsx             # Load/save level, import art
│   │   ├── StatusBar.tsx           # Score, screen position, FPS
│   │   └── GameCanvas.tsx          # Canvas element + ref, bridges React ↔ engine
│   │
│   └── data/                       # Static data and defaults
│       ├── defaultPhysics.ts       # Default physics parameter values
│       └── presets.ts              # Named parameter presets (Floaty, Tight, etc.)
│
├── package.json
├── tsconfig.json
└── README.md
```

### Key Structural Rules

**The `engine/` directory has zero React imports.** It is pure TypeScript. It knows nothing about the DOM, components, or state hooks. This is the most important boundary in the codebase — it means the engine can be tested, reasoned about, and modified independently.

**The `renderer/` directory reads engine state but never mutates it.** It receives the current game state and draws it. One-way data flow.

**The `ui/` directory talks to the engine through a thin bridge** — `GameCanvas.tsx` holds the canvas ref, instantiates the engine, and exposes play/stop/parameter-update methods. React never reaches into engine internals.

---

## Core Data Types

These are the shared shapes that flow between modules. Define them all in `engine/types.ts`.

```typescript
// ── World / Level ──────────────────────────────────

type TileType = 'empty' | 'solid' | 'platform' | 'ladder';

interface TileDefinition {
  type: TileType;
  sprite: string;         // key into loaded tile images
}

interface Screen {
  tiles: number[][];      // 15 rows × 25 cols of tile IDs
}

interface EntityDef {
  type: 'player_start' | 'collectible' | 'npc' | 'moving_platform';
  screen: string;         // "col,row"
  x: number;              // tile x within screen
  y: number;              // tile y within screen
  sprite?: string;
  // Collectible-specific
  value?: number;
  sound?: string;
  // NPC-specific
  behavior?: 'static' | 'pace' | 'face_player';
  paceRange?: number;
  // Moving platform-specific
  path?: [number, number][];
  speed?: number;
}

interface GoalDef {
  type: 'reach_tile' | 'collect_all';
  screen?: string;
  x?: number;
  y?: number;
}

interface LevelData {
  name: string;
  screenWidth: 25;
  screenHeight: 15;
  tileSize: 64;
  screens: Record<string, Screen>;
  tileTypes: Record<number, TileDefinition>;
  entities: EntityDef[];
  goal: GoalDef;
}

// ── Physics ────────────────────────────────────────

interface PhysicsParams {
  gravity: number;
  jumpForce: number;
  jumpHoldForce: number;
  maxJumpHoldTime: number;
  walkSpeed: number;
  walkAccel: number;
  airControl: number;
  friction: number;
  climbSpeed: number;
  terminalVelocity: number;
}

// ── Entities at runtime ────────────────────────────

type PlayerState = 'idle' | 'walk' | 'jump' | 'fall' | 'climb';

interface Player {
  // Position in world pixels (not tile coords)
  x: number;
  y: number;
  vx: number;
  vy: number;
  width: 64;
  height: 128;
  state: PlayerState;
  facing: 'left' | 'right';
  grounded: boolean;
  onLadder: boolean;
  jumpHoldTimer: number;
  currentScreen: string;    // "col,row"
}

interface Collectible {
  id: string;
  screenKey: string;
  x: number;               // world pixels
  y: number;
  width: number;
  height: number;
  sprite: string;
  value: number;
  collected: boolean;
}

interface NPC {
  id: string;
  screenKey: string;
  x: number;
  y: number;
  width: 64;
  height: 128;
  sprite: string;
  behavior: 'static' | 'pace' | 'face_player';
  facing: 'left' | 'right';
  paceRange: number;        // pixels
  paceOriginX: number;
  paceDirection: 1 | -1;
}

interface MovingPlatform {
  id: string;
  screenKey: string;
  x: number;
  y: number;
  width: 64;
  height: 64;
  sprite: string;
  path: { x: number; y: number }[];   // world pixels
  speed: number;
  pathIndex: number;
  pathDirection: 1 | -1;
  vx: number;              // current velocity (for player riding)
  vy: number;
}

// ── Sprite sheets ──────────────────────────────────

interface SpriteManifest {
  frameWidth: number;
  frameHeight: number;
  states: Record<string, {
    row: number;
    frames: number;
    fps: number;
  }>;
}

// ── Game state (the full snapshot) ──────────────────

interface GameState {
  level: LevelData;
  player: Player;
  collectibles: Collectible[];
  npcs: NPC[];
  movingPlatforms: MovingPlatform[];
  camera: CameraState;
  score: number;
  goalReached: boolean;
  mode: 'edit' | 'play' | 'transition' | 'goal_complete';
}

interface CameraState {
  currentScreen: string;    // "col,row"
  targetScreen: string | null;
  transitionProgress: number;  // 0.0 – 1.0, null when not transitioning
  offsetX: number;          // pixel offset during transition
  offsetY: number;
}

// ── Input ──────────────────────────────────────────

interface InputState {
  left: boolean;
  right: boolean;
  up: boolean;
  down: boolean;
  jump: boolean;            // true while held
  jumpPressed: boolean;     // true only on the frame it was first pressed
}
```

---

## Module Responsibilities & Contracts

### `GameLoop.ts`

Owns the `requestAnimationFrame` cycle. Runs a fixed-timestep update (60 Hz) with render interpolation.

```
start() → begins the loop
stop()  → halts the loop, resets player to start position
setUpdateCallback(fn: (dt: number) => void)
setRenderCallback(fn: (interpolation: number) => void)
```

The game loop calls `InputManager.poll()`, then `update()`, then `render()`. It does not know what those functions do.

### `InputManager.ts`

Listens to `keydown`/`keyup` on the window. Exposes an `InputState` snapshot. Tracks both held state and edge-triggered "just pressed" for jump.

```
attach()          → adds event listeners
detach()          → removes event listeners
poll(): InputState → returns current frame's input
```

### `TileMap.ts`

Parses a `LevelData` JSON. Provides fast tile lookups by world pixel position.

```
load(data: LevelData)
getTileAt(worldX: number, worldY: number): TileDefinition
getScreenKey(worldX: number, worldY: number): string
getScreenOrigin(screenKey: string): { x: number, y: number }
getTilesInScreen(screenKey: string): number[][]
screenExists(screenKey: string): boolean
```

Internally converts tile coordinates to world pixels on load. All public methods work in world pixel space.

### `Physics.ts`

Pure functions. No state. Takes a player + params + dt, returns updated velocity. Does NOT apply position — that happens after collision.

```
applyGravity(player, params): { vy }
applyWalk(player, input, params): { vx }
applyJump(player, input, params): { vy, jumpHoldTimer }
applyClimb(player, input, params): { vy }
applyFriction(player, input, params): { vx }
```

### `Collision.ts`

Takes a position + velocity + bounding box, resolves against the tile grid. Returns corrected position and collision flags.

```
resolve(
  x, y, vx, vy, width, height,
  tileMap: TileMap
): {
  x: number, y: number,
  vx: number, vy: number,
  grounded: boolean,
  hitCeiling: boolean,
  hitWallLeft: boolean,
  hitWallRight: boolean,
  onLadder: boolean
}
```

Resolves X and Y axes independently (X first, then Y) to avoid corner-sticking.

### `PlayerController.ts`

The integration point. Each frame: reads input, calls Physics functions, calls Collision, updates player state machine (idle/walk/jump/fall/climb), updates facing direction.

```
update(player: Player, input: InputState, params: PhysicsParams, tileMap: TileMap): Player
```

Returns a new Player object (immutable update pattern). The state machine logic:

- **grounded + no horizontal input** → `idle`
- **grounded + horizontal input** → `walk`
- **vy < 0 (moving up)** → `jump`
- **vy > 0 + not grounded** → `fall`
- **onLadder + vertical input** → `climb`

### `Camera.ts`

Tracks which screen the player is on. When the player crosses a screen boundary, initiates a slide transition.

```
update(player: Player, tileMap: TileMap): CameraState
getViewportOffset(camera: CameraState): { x: number, y: number }
```

During transition (`mode = 'transition'`), interpolates `offsetX`/`offsetY` over ~18 frames (300ms at 60fps). Player input is locked during transition.

### `EntityManager.ts`

Updates NPCs, collectibles, and moving platforms each frame.

```
update(state: GameState, tileMap: TileMap): {
  npcs: NPC[],
  collectibles: Collectible[],
  movingPlatforms: MovingPlatform[],
  scoreAdded: number,
  soundsToPlay: string[]
}
```

Handles: NPC pacing/facing logic, collectible overlap detection with player, moving platform path interpolation and velocity calculation. Returns which sounds to play (collision with collectible, etc.) so SoundManager stays decoupled.

### `SpriteSheet.ts`

Loads a PNG + manifest, provides frame rectangles for a given state and animation time.

```
load(imagePath: string, manifestPath: string): Promise<SpriteSheet>
getFrame(state: string, elapsedMs: number): {
  image: HTMLImageElement,
  sx: number, sy: number,     // source rect in sprite sheet
  sw: number, sh: number
}
```

### `SoundManager.ts`

Preloads audio files. Plays sounds by event name. Supports mute + volume.

```
load(soundMap: Record<string, string>): Promise<void>
play(eventName: string): void
setVolume(v: number): void
setMute(muted: boolean): void
```

### `Renderer.ts`

Orchestrates drawing. Called once per frame with the full GameState.

```
render(ctx: CanvasRenderingContext2D, state: GameState, assets: AssetBundle): void
```

Delegates to `TileRenderer`, `SpriteRenderer`, and `HUD`. Applies camera offset so only the current screen (plus transition overlap) is visible.

### `AssetBundle` (loaded at startup)

```typescript
interface AssetBundle {
  tileImages: Record<string, HTMLImageElement>;   // keyed by sprite name
  playerSheet: SpriteSheet;
  npcSheets: Record<string, SpriteSheet>;
  collectibleSheets: Record<string, SpriteSheet>;
  platformImages: Record<string, HTMLImageElement>;
}
```

---

## Build Order

Each phase ends with a testable checkpoint. Don't move on until the checkpoint works.

### Phase 1: Static World

**Goal:** Render a tile grid on a canvas. No player, no movement.

**Files to create:**
- Project scaffolding (package.json, tsconfig, index.html, index.tsx, App.tsx)
- `engine/types.ts` — all type definitions
- `engine/TileMap.ts` — level JSON parser
- `renderer/TileRenderer.ts` — draws tiles as colored rectangles (no art yet)
- `renderer/Renderer.ts` — orchestrator (just calls TileRenderer for now)
- `ui/GameCanvas.tsx` — canvas element with ref
- `data/defaultPhysics.ts` — parameter defaults
- `public/assets/levels/demo.json` — a hand-written 2-screen test level

**Checkpoint:** Browser shows a 1600×960 canvas with a grid of colored rectangles matching the demo level. Ground tiles are brown, platforms are gray, ladders are green, empty is sky blue. No interactivity.

### Phase 2: Player Movement

**Goal:** A rectangle that moves and jumps with physics. No collision yet — it will fall through the floor.

**Files to create:**
- `engine/InputManager.ts`
- `engine/Physics.ts`
- `engine/PlayerController.ts` (without collision, just velocity + position)
- `engine/GameLoop.ts`

**Modifications:**
- `Renderer.ts` — draw the player as a colored rectangle
- `GameCanvas.tsx` — instantiate GameLoop, wire up input

**Checkpoint:** Arrow keys move a rectangle left/right with acceleration. Space makes it jump (and fall with gravity). It passes through all tiles. The fixed-timestep loop runs at 60 Hz.

### Phase 3: Collision

**Goal:** The player lands on solid tiles, bumps into walls, and can stand on platforms.

**Files to create:**
- `engine/Collision.ts`

**Modifications:**
- `PlayerController.ts` — integrate collision resolution after physics

**Checkpoint:** The player rectangle stands on ground tiles, can't walk through walls, falls off edges, and can jump onto platforms. Platform tiles are passable from below. Player can walk and jump around the demo level.

### Phase 4: Climbing & Screen Transitions

**Goal:** Ladders work. Walking off-screen triggers a camera slide to the next screen.

**Files to create:**
- `engine/Camera.ts`

**Modifications:**
- `PlayerController.ts` — add climb state (on ladder + up/down = climb, gravity disabled)
- `Renderer.ts` — apply camera offset, render two screens during transition
- `GameLoop.ts` — lock input during screen transition

**Checkpoint:** Player can climb ladders/vines. Walking to the edge of screen "0,0" triggers a 300ms slide to screen "1,0". Player state persists across transitions.

### Phase 5: Sprite Rendering

**Goal:** Replace colored rectangles with sprite sheet animations.

**Files to create:**
- `engine/SpriteSheet.ts`
- `renderer/SpriteRenderer.ts`
- Placeholder sprite sheets in `public/assets/sprites/` (can be simple colored pencil sketches or programmer art — just needs to be the right grid dimensions)
- Placeholder tile PNGs in `public/assets/tiles/`

**Modifications:**
- `Renderer.ts` — use SpriteRenderer for player, TileRenderer loads tile images
- `PlayerController.ts` — track animation elapsed time per state

**Checkpoint:** Player animates: idle bob when still, walk cycle when moving, jump/fall frames in air, climb frames on ladders. Tiles render as images instead of colored rectangles. Sprites flip horizontally based on facing direction.

### Phase 6: Entities

**Goal:** Collectibles, NPCs, and moving platforms populate the level and behave.

**Files to create:**
- `engine/EntityManager.ts`

**Modifications:**
- `Renderer.ts` — draw collectibles, NPCs, moving platforms
- `PlayerController.ts` — detect standing on moving platform, inherit velocity
- `demo.json` — add entity definitions

**Checkpoint:** Coins float in the level and disappear when touched (score increments). An NPC paces back and forth. A moving platform carries the player up and down. All entities only update/render on their home screen.

### Phase 7: Sound

**Goal:** Game events trigger sound effects.

**Files to create:**
- `engine/SoundManager.ts`
- Placeholder audio files in `public/assets/sounds/`

**Modifications:**
- `GameLoop.ts` / main update — call SoundManager.play() when EntityManager reports sounds
- `PlayerController.ts` — emit jump/land events

**Checkpoint:** Jumping plays a sound. Landing plays a sound. Collecting a coin plays a sound. Screen transitions play a sound. Mute toggle works.

### Phase 8: Tuning Panel & Edit/Play Mode

**Goal:** The sidebar UI lets users adjust physics parameters, play, and stop.

**Files to create:**
- `ui/TuningPanel.tsx`
- `ui/Toolbar.tsx` (stub — just play/stop for now)
- `ui/StatusBar.tsx`
- `data/presets.ts`

**Modifications:**
- `App.tsx` — layout with sidebar
- `GameCanvas.tsx` — expose play/stop/updateParams methods
- `GameLoop.ts` — support pause/resume

**Checkpoint:** Sliders control all 10 physics parameters. Clicking "Floaty" preset makes the character float. Clicking Play starts the game; Stop resets the player to start. Score and screen position display in the status bar.

### Phase 9: Import/Export & Goal Condition

**Goal:** Users can load/save levels and import custom art. Reaching the goal tile shows a completion overlay.

**Modifications:**
- `Toolbar.tsx` — add Load Level (JSON upload), Save Level (JSON download), Import Art (sprite sheet + manifest upload, tile PNG upload, sound upload)
- `GameCanvas.tsx` — handle asset hot-swapping when user imports new art
- `Renderer.ts` — draw goal overlay when `goalReached` is true
- `GameLoop.ts` — check goal condition each frame, set `goalReached`

**Checkpoint:** User can download the demo level as JSON, edit it in a text editor, re-upload it, and play the modified level. User can import a custom sprite sheet PNG + manifest and see their character in-game. Reaching the goal tile shows "Level Complete" with the score. Falling off the bottom of the screen respawns the player at the start position.

---

## Testing Strategy

Since this is a hand-rolled engine (no framework with built-in test harnesses), testing is primarily manual + structural:

**Per-phase manual testing:** Each checkpoint above is a manual verification. Don't move to the next phase until the checkpoint is solid.

**Console instrumentation:** The engine should log key events to the console in development: state transitions, screen changes, collision resolution, entity spawns/despawns. Wrap these in a `DEBUG` flag so they can be silenced.

**Physics sandboxing:** Before Phase 8 formalizes the tuning panel, expose physics params on `window.__physics` so they can be tweaked from the browser console during development.

**Unit-testable by design:** `Physics.ts` and `Collision.ts` are pure functions with no side effects. If you add tests later, these are the highest-value targets. `TileMap.ts` is also purely data-driven and easy to test with fixture JSON.

---

## Common Pitfalls for Claude Code

Things to watch for when implementing:

**Canvas coordinate confusion.** Everything in the engine works in world pixel coordinates. The renderer subtracts the camera offset to get canvas coordinates. Don't mix these up — if a function takes `worldX`, name the parameter `worldX`, not `x`.

**Collision axis order matters.** Resolve X movement first, update position, then resolve Y movement. Doing both simultaneously causes the player to "stick" on corners.

**Input edge detection.** `jumpPressed` must be true for exactly one frame (the frame the key goes down), not while held. `jump` (held) is a separate flag used for variable-height jumps. Getting this wrong makes jumping feel terrible.

**Fixed timestep accumulator.** The game loop must accumulate real elapsed time and step in fixed increments. Don't use `requestAnimationFrame`'s delta directly as the physics dt — frame rate variance will make physics inconsistent.

**Moving platform velocity transfer.** When the player rides a moving platform, they need to inherit the platform's velocity. This means the platform must calculate its own `vx`/`vy` each frame (not just snap to path positions), and the player must add this to their own velocity when grounded on a platform.

**Screen transition edge cases.** When the player triggers a screen transition, snap their position to the entry edge of the new screen after the transition completes. Don't let them end up partially off-screen.

**Sprite sheet row/frame indexing.** Rows in the manifest are 0-indexed. Frame index wraps using modulo: `frameIndex = Math.floor(elapsed * fps / 1000) % totalFrames`. Horizontal flip for facing direction uses `ctx.scale(-1, 1)` — remember to translate the canvas context appropriately.

**React ↔ Canvas isolation.** React should never call `setState` in response to a game loop tick. The game loop writes to a plain JS object (GameState). React reads from this object only when it needs to update UI (score display, FPS counter) via a separate, throttled polling mechanism (e.g., `setInterval` at 4 Hz for the status bar).

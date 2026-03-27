# Platformer Creator — Product Requirements Document (V1)

## Vision

A browser-based platformer engine where the joy is in the art and the feel. Users bring their own sprites, drop them into tile-map levels, and tune character physics until movement feels just right. The game is the creative tool.

This is not a general-purpose game engine. It is an opinionated, Mario-style platformer kit that makes one thing effortless: *creating a world that looks and feels like yours.*

### Art Direction

The visual identity is **colored pencil on paper.** Characters, tiles, and backgrounds should look hand-drawn — visible pencil texture, imperfect edges, warm natural colors. The engine's default assets, rendering choices (no pixel-perfect snapping, slight texture overlays if needed), and any documentation/examples should reinforce this aesthetic. Think *crayon physics* meets *Mario.*

---

## User Personas

**The Doodler** — Has character sketches in colored pencil on paper or in Procreate. Wants to see their art come alive in a playable game without learning Unity. Will photograph their drawings, use Claude to turn them into sprite sheets, and drop them into the engine.

**The Tinkerer** — Loves the feel of movement. Wants to adjust gravity, jump arc, air control, and acceleration until the character feels weighty, floaty, snappy, or sluggish — and understand why. The tuning panel is their main interface.

**The Level Designer** — Thinks in grids. Wants to lay out platforms, place collectibles, position NPCs, and playtest in a tight loop. Cares about pacing and spatial puzzles more than art.

---

## Platform & Delivery

- **Runtime:** Browser (React + HTML5 Canvas)
- **Input:** Keyboard (arrow keys / WASD + action keys). Gamepad support is a stretch goal.
- **Target viewport:** Fixed-resolution window (1600×960) rendered within a browser page, scaled to fit the screen.
- **No backend required for V1.** All state is client-side. Level save/load via JSON export/import.

---

## Core Mechanics

### Movement Model

The player character supports four movement modes:

| Mode | Controls | Description |
|------|----------|-------------|
| Walk | Left / Right | Horizontal ground movement with acceleration and deceleration curves |
| Jump | Action button | Variable-height jump (hold longer = jump higher), with configurable gravity and air control |
| Climb | Up / Down | Ladder/vine traversal, disables gravity while climbing |
| Fall | Automatic | Gravity-driven descent when not grounded and not climbing |

### Physics Parameters (Tunable)

All values editable in the character tuning panel. Sensible defaults provided. Velocity and acceleration values are in pixels per frame (scaled for 64×64 tile grid).

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `gravity` | 1.2 | 0.2 – 4.0 | Downward acceleration per frame |
| `jumpForce` | -24.0 | -40.0 – -8.0 | Initial vertical velocity on jump |
| `jumpHoldForce` | -0.8 | -2.0 – 0.0 | Additional upward force while holding jump |
| `maxJumpHoldTime` | 12 | 1 – 30 | Frames the player can extend a jump by holding |
| `walkSpeed` | 6.0 | 1.0 – 16.0 | Max horizontal speed |
| `walkAccel` | 0.6 | 0.1 – 2.0 | Horizontal acceleration on ground |
| `airControl` | 0.15 | 0.0 – 1.0 | Horizontal acceleration multiplier in air (0 = no air control) |
| `friction` | 0.8 | 0.0 – 1.0 | Ground deceleration when no input (1 = instant stop) |
| `climbSpeed` | 4.0 | 1.0 – 10.0 | Vertical speed on ladders/vines |
| `terminalVelocity` | 20.0 | 4.0 – 40.0 | Max downward speed |

### Collision

- Axis-aligned bounding box (AABB) collision against the tile grid.
- Tiles are either solid, platform (pass-through from below), ladder, or empty.
- Moving platforms are solid tiles with a defined motion path.

---

## Camera

- **Screen-by-screen (NES style).** The viewport is one fixed screen. When the player crosses a screen boundary, the camera transitions to the adjacent screen.
- **Transition style:** Quick slide (approximately 300ms) rather than an instant cut. Configurable later.
- Each level is a grid of screens, and the tile map defines which screens exist.

---

## Level Format

Levels are defined as JSON config files with the following structure:

```json
{
  "name": "World 1-1",
  "screenWidth": 25,
  "screenHeight": 15,
  "tileSize": 64,
  "screens": {
    "0,0": {
      "tiles": [
        [0,0,0,0,0, "... 25 columns"],
        ["... 15 rows of tile IDs"]
      ]
    },
    "1,0": { "tiles": ["..."] },
    "0,1": { "tiles": ["..."] }
  },
  "tileTypes": {
    "0": { "type": "empty" },
    "1": { "type": "solid", "sprite": "ground_top" },
    "2": { "type": "solid", "sprite": "ground_fill" },
    "3": { "type": "platform", "sprite": "bridge" },
    "4": { "type": "ladder", "sprite": "vine" }
  },
  "entities": [
    { "type": "player_start", "screen": "0,0", "x": 3, "y": 12 },
    { "type": "collectible", "screen": "0,0", "x": 10, "y": 8, "sprite": "coin", "value": 1 },
    { "type": "npc", "screen": "1,0", "x": 5, "y": 12, "sprite": "villager", "behavior": "pace", "paceRange": 3 },
    { "type": "moving_platform", "screen": "0,0", "x": 15, "y": 10, "sprite": "platform_wood", "path": [[15,10],[15,5]], "speed": 1.0 }
  ],
  "goal": { "type": "reach_tile", "screen": "1,0", "x": 22, "y": 12 }
}
```

### Tile Grid

- **Tile size:** 64×64 pixels.
- **Screen dimensions:** 25 tiles wide × 15 tiles tall = 1600×960 pixel viewport.
- **Coordinate system:** Origin at top-left. `screen: "col,row"` identifies which screen in the level grid.

---

## Entities

### Player Character
- One player character per level.
- Physics driven by the tunable parameters above.
- States: idle, walk, jump, fall, climb. Each state maps to a sprite sheet row or individual sprite.

### Collectibles
- Placed on the tile grid. Triggered by player overlap.
- Configurable properties: `sprite`, `value` (numeric), optional `sound`.
- V1 effect: increment a score counter displayed on screen. No inventory system.

### NPCs (Decorative / Ambient)
- Non-hostile characters placed in the level.
- Behaviors (V1):
  - `static` — stands in place, plays idle animation
  - `pace` — walks back and forth within a defined range, turns at edges
  - `face_player` — static but flips sprite to face the player
- NPCs do not block the player (no collision). They are purely visual.

### Moving Platforms
- Solid tiles that follow a defined path (array of waypoints in tile coordinates).
- Configurable `speed`.
- Player rides the platform (inherits horizontal/vertical velocity while grounded on it).
- Loops continuously along the path.

---

## Art Pipeline

### Sprite Sheets

The primary art format is a sprite sheet PNG: a grid of equal-sized frames.

**Sheet layout convention:**

```
Row 0: Idle       (1–4 frames)
Row 1: Walk       (4–8 frames)
Row 2: Jump       (1–2 frames: launch, apex)
Row 3: Fall       (1–2 frames)
Row 4: Climb      (2–4 frames)
```

Frame size matches the character's bounding box (configurable, default 64×128 — one tile wide, two tiles tall).

A sprite manifest JSON accompanies each sheet:

```json
{
  "frameWidth": 64,
  "frameHeight": 128,
  "states": {
    "idle":  { "row": 0, "frames": 4, "fps": 4 },
    "walk":  { "row": 1, "frames": 6, "fps": 10 },
    "jump":  { "row": 2, "frames": 1, "fps": 1 },
    "fall":  { "row": 3, "frames": 1, "fps": 1 },
    "climb": { "row": 4, "frames": 2, "fps": 6 }
  }
}
```

### Sprite Sheet Creation (External — via Claude)

Sprite sheet creation is **not part of the game engine.** Instead, users generate sprite sheets in a separate Claude conversation:

1. User provides 1–2 colored pencil reference images of their character to Claude.
2. User describes the states needed (idle, walk, jump, fall, climb) and specifies the frame grid (e.g., 6 columns × 5 rows, 64×128px per frame).
3. Claude generates a sprite sheet image matching the colored pencil style and the layout convention defined below.
4. User downloads the PNG and the corresponding manifest JSON, then imports both into the engine.

This keeps the engine simple (it only consumes sprite sheets, never generates them) while giving users a powerful, iterative art workflow through Claude's image generation. The PRD for the sprite sheet generation prompt/workflow is a separate document.

### Tile Art

- Each tile type maps to a 64×64 sprite.
- V1 ships with a default tile set in the colored pencil art style (textured ground, sketchy platforms, hand-drawn vines). Users can replace with custom PNGs.
- Tile sprites are provided as individual 64×64 PNGs or as a tile atlas (grid of tiles with an index).
- Default tiles should feel consistent with user-generated colored pencil character art — warm tones, visible texture, slightly imperfect geometry.

### Collectible & NPC Art

- Same sprite sheet format as the player character, but typically smaller frames and fewer states.
- Collectibles may be a single frame (static sparkle) or a short animation loop.
- NPCs use the same state model (idle, walk) but may omit jump/fall/climb.

---

## Sound

### V1 Sound Effects

Basic sound effects triggered by game events. Users can replace default sounds with their own audio files (`.mp3`, `.wav`, `.ogg`).

| Event | Default Sound | Configurable |
|-------|--------------|-------------|
| Jump | Short "boing" | Yes |
| Land | Soft thud | Yes |
| Collect item | Bright chime | Yes |
| Screen transition | Soft whoosh | Yes |
| Reach goal | Fanfare jingle | Yes |

- No background music in V1 (stretch goal).
- Sounds are mapped in the level JSON or a global config.
- Volume control: global mute toggle + volume slider.

---

## Character Tuning Panel

### V1: Edit-Then-Play

The tuning panel is a sidebar UI visible alongside the game canvas. Workflow:

1. **Edit mode:** Game is paused. Panel displays all physics parameters as labeled sliders with numeric input fields. Preset buttons for common feels (e.g., "Floaty," "Tight," "Heavy," "Classic Mario").
2. **Play mode:** User clicks "Play" (or presses Enter). Game runs with current parameters. Panel collapses or dims.
3. **Stop:** User clicks "Stop" (or presses Escape). Returns to edit mode. Character resets to starting position.

### V2 (Future): Live Tuning

Parameters adjustable in real-time during play. Slider changes apply immediately on the next frame. No stop/restart needed.

---

## UI Layout

```
┌─────────────────────────────────────────────────────┐
│  Toolbar: [Load Level] [Save Level] [Import Art]    │
├─────────────────────────┬───────────────────────────┤
│                         │  Character Tuning Panel   │
│                         │                           │
│     Game Canvas         │  [Preset: Classic Mario]  │
│     1600 × 960          │                           │
│                         │  Gravity: ──●── 0.6       │
│                         │  Jump Force: ──●── 12.0   │
│                         │  Walk Speed: ──●── 3.0    │
│                         │  Air Control: ──●── 0.15  │
│                         │  ...                      │
│                         │                           │
│                         │  [▶ Play]  [■ Stop]       │
├─────────────────────────┴───────────────────────────┤
│  Status Bar: Score: 0  │  Screen: 0,0  │  FPS: 60  │
└─────────────────────────────────────────────────────┘
```

---

## Save / Load

- **Level JSON:** Export and import the full level definition as a `.json` file via download/upload.
- **Art assets:** Managed as local files. The level JSON references sprite names; the user provides corresponding PNGs.
- **V1 has no cloud storage.** All persistence is local file-based.
- **Future:** Shareable links with embedded level data (base64 encoded or hosted).

---

## Win / Lose Conditions

### V1: Simple Goal

- Each level defines a `goal` in the JSON (e.g., reach a specific tile, collect all items).
- When the goal is met, a "Level Complete" overlay appears with the score.
- **No death/lives system in V1.** Falling off-screen wraps or respawns the player at the level start. Focus is on creative play, not punishment.

### Future

- Optional hazard tiles (spikes, lava) that trigger respawn.
- Multi-level progression.
- Timer and par scores.

---

## Technical Architecture (High Level)

```
React App
├── GameCanvas (HTML5 Canvas, renders at 1600×960)
│   ├── TileRenderer — draws the current screen's tile grid
│   ├── EntityRenderer — draws player, NPCs, collectibles, platforms
│   ├── PhysicsEngine — per-frame update loop (fixed timestep)
│   │   ├── PlayerController — input → velocity → position
│   │   ├── CollisionResolver — AABB vs tile grid
│   │   └── PlatformMover — moving platform path interpolation
│   ├── CameraManager — screen-by-screen transitions
│   └── SoundManager — event-driven audio playback
├── TuningPanel (React sidebar)
│   ├── Parameter sliders + numeric inputs
│   ├── Preset buttons
│   └── Play / Stop controls
├── Toolbar
│   ├── Level JSON import/export
│   └── Art import (sprite sheets, tiles, sounds)
└── StatusBar
```

### Implementation Approach

The engine will be built using **Claude Code** (Anthropic's CLI coding agent). The codebase should be structured for iterability — clean module boundaries, well-commented physics code, and a clear separation between the game loop and React UI so that Claude Code can confidently modify one system without breaking another.

### Key Technical Decisions

- **Fixed timestep game loop** (60 updates/sec) decoupled from render for consistent physics.
- **Canvas 2D** (not WebGL) for simplicity and broad compatibility. Sufficient for tile-based 2D at this resolution.
- **No external game engine dependency.** Physics and rendering are hand-rolled to keep the codebase small and fully controllable.
- **React manages UI only.** The game loop runs independently on a `requestAnimationFrame` cycle; React does not re-render the canvas.

---

## Phasing

### V1 — Core Loop (This Build)
- Player character with full movement model (walk, jump, climb, fall)
- Tuning panel (edit-then-play) with all physics parameters
- Tile-map level loading from JSON
- Screen-by-screen camera
- Collectibles with score counter
- NPCs with static/pace/face_player behaviors
- Moving platforms
- Sprite sheet import + manifest (user provides PNGs created externally via Claude)
- Default tile set and placeholder sprites in colored pencil style
- Basic sound effects (5 events)
- Level save/load via JSON export/import
- Simple goal condition (reach tile or collect all)
- No death — off-screen fall respawns at start

### V2 — Polish & Power
- Live tuning (adjust parameters during play)
- Keyboard remapping
- Background music + ambient loops
- Parallax scrolling backgrounds
- Hazard tiles (spikes, lava) + lives/respawn system
- Tile set editor (paint tiles visually)
- Level editor (click-to-place tiles and entities)

### V3 — Share & Expand
- Shareable level links (encoded or cloud-hosted)
- Multi-level progression (world maps)
- Gamepad support
- Custom scripting for NPC/entity behaviors
- Community level gallery

---

## Resolved Constraints (V1)

1. **Character size:** All characters (player and NPCs) are 1×2 tiles (64×128 pixels). No oversized entities in V1.
2. **Single character per level:** One player character per level, one sprite sheet, one set of physics parameters.
3. **Static tiles:** Tiles do not animate in V1. No flowing water or flickering torches — just solid sprites.
4. **Desktop only:** Keyboard input only, no touch controls. Mobile browser support is out of scope.

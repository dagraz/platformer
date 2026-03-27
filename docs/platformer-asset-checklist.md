# Platformer Creator — Asset Checklist (V1)

Everything the engine needs that isn't code. Organized by when it's needed in the build plan.

---

## Needed by Phase 5: Tile Art

All tiles are 64×64 PNG with transparent backgrounds where appropriate. Colored pencil style — visible strokes, warm tones, slightly imperfect edges.

| Asset | Filename | Description | Notes |
|-------|----------|-------------|-------|
| Ground top | `ground_top.png` | Top surface of ground (grass, dirt, stone — whatever fits the world) | Should tile seamlessly horizontally |
| Ground fill | `ground_fill.png` | Below-surface fill (solid earth/rock texture) | Should tile in all directions |
| Platform | `bridge.png` | Thin walkable surface, passable from below | Visually distinct from solid ground — planks, branches, etc. |
| Ladder / Vine | `vine.png` | Climbable vertical element | Should tile vertically; transparent sides so it overlays on backgrounds |
| Background | `sky.png` | Empty tile background (sky, cave wall, etc.) | Optional — could also just use a CSS background color on the canvas |

### Stretch tiles (not required for demo, but useful soon)

| Asset | Filename | Description |
|-------|----------|-------------|
| Ground left edge | `ground_left.png` | Left edge cap for ground surfaces |
| Ground right edge | `ground_right.png` | Right edge cap for ground surfaces |
| Corner pieces | `ground_corner_*.png` | Inner/outer corners for L-shaped ground |
| Decorative variants | `ground_top_v2.png`, etc. | Alternate versions to break up visual repetition |

---

## Needed by Phase 5: Player Sprite Sheet

One PNG sprite sheet + one JSON manifest. Colored pencil style matching the tile art.

**Sprite sheet layout:** Grid of 64×128 px frames.

| Row | State | Frames needed | Description |
|-----|-------|---------------|-------------|
| 0 | Idle | 4 | Subtle breathing/bobbing animation |
| 1 | Walk | 6 | Full walk cycle |
| 2 | Jump | 2 | Launch pose + apex pose |
| 3 | Fall | 2 | Falling pose + near-landing pose |
| 4 | Climb | 2 | Alternating hand-over-hand |

**Total sheet dimensions:** 384×640 px (6 columns × 5 rows, with some rows having fewer frames — unused cells are transparent).

**Files:**
- `player.png` — the sprite sheet
- `player.manifest.json` — frame definitions (see PRD for manifest format)

**Character design notes:** The character should read clearly at 64×128 px. Simple silhouette, distinct color from the background tiles. Arms and legs should have enough contrast between poses that animation frames feel different even at this scale.

---

## Needed by Phase 6: Collectible Sprite

Simple animated collectible (coin, star, gem — whatever fits the world).

| Row | State | Frames needed | Description |
|-----|-------|---------------|-------------|
| 0 | Idle | 4 | Spinning, bobbing, or sparkling loop |

**Frame size:** 64×64 px (one tile).
**Total sheet dimensions:** 256×64 px (4 columns × 1 row).

**Files:**
- `coin.png` — the sprite sheet
- `coin.manifest.json` — frame definitions

---

## Needed by Phase 6: NPC Sprite Sheet

At least one NPC with idle and walk animations. Same colored pencil style. Same 64×128 frame size as the player.

| Row | State | Frames needed | Description |
|-----|-------|---------------|-------------|
| 0 | Idle | 2–4 | Standing, breathing, looking around |
| 1 | Walk | 4–6 | Walk cycle for pacing behavior |

**Total sheet dimensions:** Up to 384×256 px (6 columns × 2 rows).

**Files:**
- `villager.png` — the sprite sheet (or whatever the NPC is)
- `villager.manifest.json` — frame definitions

---

## Needed by Phase 6: Moving Platform Sprite

A single 64×64 PNG for the moving platform surface.

| Asset | Filename | Description |
|-------|----------|-------------|
| Moving platform | `platform_wood.png` | A standalone floating platform — should look distinct from static ground tiles |

**Notes:** If the platform is wider than one tile, we can repeat this sprite. For V1, single-tile platforms are fine.

---

## Needed by Phase 7: Sound Effects

Five audio files in `.mp3` format (`.wav` or `.ogg` also fine). These are functional placeholder sounds — they don't need to be masterpieces, just appropriate feedback.

| Event | Filename | Description | Duration |
|-------|----------|-------------|----------|
| Jump | `jump.mp3` | Short upward "boing" or whoosh | < 0.5s |
| Land | `land.mp3` | Soft thud or footstep | < 0.3s |
| Collect item | `collect.mp3` | Bright chime, ding, or sparkle | < 0.5s |
| Screen transition | `transition.mp3` | Soft whoosh or slide sound | ~ 0.3s |
| Goal reached | `goal.mp3` | Short celebration fanfare or jingle | 1–2s |

**Notes:** Sounds should feel consistent with the hand-drawn aesthetic — softer and warmer rather than retro chiptune. Think pencil-on-paper, not arcade. Freesound.org is a fine source for placeholders.

---

## Needed by Phase 9: Demo Level JSON

A hand-authored level file exercising all V1 features.

| Asset | Filename | Description |
|-------|----------|-------------|
| Demo level | `demo.json` | 2–3 screen level with ground, platforms, ladders, collectibles, an NPC, a moving platform, and a goal tile |

**Notes:** We'll draft this separately. It's also needed in Phase 1 for rendering, but in early phases it's just tile data — entities get added in Phase 6.

---

## Asset Production Plan

| Asset group | How to produce | When needed |
|-------------|----------------|-------------|
| Tile PNGs | Claude image generation — provide colored pencil reference, request 64×64 tiles | Before Phase 5 |
| Player sprite sheet | Claude image generation — provide character reference + pose descriptions | Before Phase 5 |
| Collectible sprite | Claude image generation — simple spinning object in colored pencil style | Before Phase 6 |
| NPC sprite sheet | Claude image generation — secondary character with idle/walk poses | Before Phase 6 |
| Moving platform | Claude image generation — single 64×64 floating plank/cloud | Before Phase 6 |
| Sound effects | Source from freesound.org or generate with a tool like sfxr/jsfxr | Before Phase 7 |
| Demo level JSON | Hand-author or draft with Claude assistance | Before Phase 1 (tiles only), updated for Phase 6 (entities) |

---

## File Inventory Summary

When all assets are ready, the `public/assets/` directory should contain:

```
public/assets/
├── tiles/
│   ├── ground_top.png
│   ├── ground_fill.png
│   ├── bridge.png
│   ├── vine.png
│   └── sky.png              (optional)
├── sprites/
│   ├── player.png
│   ├── player.manifest.json
│   ├── coin.png
│   ├── coin.manifest.json
│   ├── villager.png
│   ├── villager.manifest.json
│   └── platform_wood.png
├── sounds/
│   ├── jump.mp3
│   ├── land.mp3
│   ├── collect.mp3
│   ├── transition.mp3
│   └── goal.mp3
└── levels/
    └── demo.json
```

**Total unique assets: 16 files** (5 tiles, 7 sprite files, 5 sounds, 1 level).

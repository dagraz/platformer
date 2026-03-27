# Demo Level — Design Notes

This file documents the demo level layout and entity placement. The actual JSON is at the bottom, ready to copy into `public/assets/levels/demo.json`.

## Entity Coordinate Convention

Entity `x` and `y` values are **tile coordinates within their screen** (0-indexed).

- **`player_start`**: The tile the player stands on. The engine places the player's feet on top of this tile (so the 1×2 player sprite occupies the two tile-rows above).
- **`collectible`**: The tile the collectible occupies (1×1 tile).
- **`npc`**: The tile the NPC stands on (same convention as player — feet on this tile, sprite extends upward).
- **`moving_platform`**: Path coordinates are tile positions within the screen. The platform is 1×1 tile (64×64). It moves between waypoints and loops.

## Screen Layout

The demo level has two screens arranged horizontally: `"0,0"` (start) and `"1,0"` (goal).

### Screen 0,0 — "The Garden"

```
Columns: 0         5         10        15        20    24
     ┌─────────────────────────────────────────────────┐
  0  │ . . . . . . . . . . . . . . . . . . . . . . . . . │
  1  │ . . . . . . . . . . . . . . . . . . . . . . . . . │
  2  │ . . . . . . . . . . . . . . . . . . . . . . . . . │
  3  │ . . . . . . . . . . . . . . . . . . ¢ ¢ . . . . . │  coins on high platform
  4  │ . . . . . . . . . . . . . . . . . ═ ═ ═ ═ . . . . │  bridge platform (17-20)
  5  │ . . . . . . . . . . . . . . . . . . . . ‡ . . . . │  vine (col 20)
  6  │ . . . . . . . . . . . ¢ ¢ . . . . . . . ‡ . . . . │  coins on mid platform
  7  │ . . . . . . . . . ═ ═ ═ ═ . . . . . . . ‡ . . . . │  bridge platform (9-12)
  8  │ . . . . . . . . . . . . . . . . . . . . ‡ . . . . │  vine
  9  │ . . . . . ¢ . . . . . . . . . . . . . . ‡ . . . . │  coin on step
 10  │ . . . . . █ █ █ . . . . . . . . . . . . ‡ . . . . │  raised step (5-7), vine
 11  │ . . . . . █ █ █ . . . . . . . . . . . . ‡ . . . . │  fill under step, vine
 12  │ █ █ █ █ █ █ █ █ █ █ █ █ █ █ . . . █ █ █ █ █ █ █ █ │  ground (gap at 14-16)
 13  │ █ █ █ █ █ █ █ █ █ █ █ █ █ █ . . . █ █ █ █ █ █ █ █ │  fill
 14  │ █ █ █ █ █ █ █ █ █ █ █ █ █ █ . . . █ █ █ █ █ █ █ █ │  fill
     └─────────────────────────────────────────────────┘
         P = player start (x:2)
         ¢ = collectible    ‡ = vine    ═ = bridge    █ = solid ground
```

**Features exercised:**
- Ground floor with a gap (requires jumping at cols 14-16)
- Raised step to test climbing up small ledges
- Two tiers of bridge platforms accessible by jumping
- A vine from ground to the high platform (tests climbing)
- Coins at three heights rewarding exploration
- Exit right edge → screen 1,0

### Screen 1,0 — "The Crossing"

```
Columns: 0         5         10        15        20    24
     ┌─────────────────────────────────────────────────┐
  0  │ . . . . . . . . . . . . . . . . . . . . . . . . . │
  1  │ . . . . . . . . . . . . . . . . . . . . . . . . . │
  2  │ . . . . . . . . . . . . . . . . . . . . . . . . . │
  3  │ . . . . . . . . . . . . . . . . . . . . . . . . . │
  4  │ . . . . . . . . . . . . . . . . . . . . . . . . . │
  5  │ . . . . . . . . . . . . ¢ ¢ ¢ . . . . . . . . . . │  coins on bonus bridge
  6  │ . . . . . . . . . . . ═ ═ ═ ═ ═ . . . . . . . . . │  bridge platform (11-15)
  7  │ . . . . . . . . . . . . . . . . . . . . . . . . . │
  8  │ . . . . . . . . . . . . . . . . . . . . . . . . . │
  9  │ . . . . . . . . . . . . . . . . . . . . . . . . . │
 10  │ . . . . . . . . . . . . . . . . . . . . . . . . . │
 11  │ . . . . . . . ◄ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ► . . ¢ . . │  moving platform path, coin
 12  │ █ █ █ █ █ █ . . . . . . . . . . . . . █ █ █ █ █ ★ │  ground (gap 6-18), goal at 24
 13  │ █ █ █ █ █ █ . . . . . . . . . . . . . █ █ █ █ █ █ │  fill
 14  │ █ █ █ █ █ █ . . . . . . . . . . . . . █ █ █ █ █ █ │  fill
     └─────────────────────────────────────────────────┘
         N = NPC pacing (x:21, range 3)    ★ = goal tile
         ◄──► = moving platform path
```

**Features exercised:**
- Large gap requiring the moving platform to cross (cols 6-18)
- Moving platform with horizontal path
- Bonus bridge above the gap with coins (rewards skilled jumping)
- NPC pacing on the right-side ground
- Goal tile at the far right edge
- Coin near the NPC

---

## Level JSON

```json
{
  "name": "Demo Level",
  "screenWidth": 25,
  "screenHeight": 15,
  "tileSize": 64,

  "tileTypes": {
    "0": { "type": "empty",    "sprite": "sky" },
    "1": { "type": "solid",    "sprite": "ground_top" },
    "2": { "type": "solid",    "sprite": "ground_fill" },
    "3": { "type": "platform", "sprite": "bridge" },
    "4": { "type": "ladder",   "sprite": "vine" }
  },

  "screens": {
    "0,0": {
      "tiles": [
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,3,3,3,3,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,4,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,4,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,3,3,3,3,0,0,0,0,0,0,0,4,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,4,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,4,0,0,0,0],
        [0,0,0,0,0,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,4,0,0,0,0],
        [0,0,0,0,0,2,2,2,0,0,0,0,0,0,0,0,0,0,0,0,4,0,0,0,0],
        [1,1,1,1,1,1,1,1,1,1,1,1,1,1,0,0,0,1,1,1,1,1,1,1,1],
        [2,2,2,2,2,2,2,2,2,2,2,2,2,2,0,0,0,2,2,2,2,2,2,2,2],
        [2,2,2,2,2,2,2,2,2,2,2,2,2,2,0,0,0,2,2,2,2,2,2,2,2]
      ]
    },
    "1,0": {
      "tiles": [
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,3,3,3,3,3,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
        [1,1,1,1,1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1,1,1,1,1],
        [2,2,2,2,2,2,0,0,0,0,0,0,0,0,0,0,0,0,0,2,2,2,2,2,2],
        [2,2,2,2,2,2,0,0,0,0,0,0,0,0,0,0,0,0,0,2,2,2,2,2,2]
      ]
    }
  },

  "entities": [
    { "type": "player_start",    "screen": "0,0", "x": 2,  "y": 12 },

    { "type": "collectible",     "screen": "0,0", "x": 5,  "y": 9,  "sprite": "coin", "value": 1 },
    { "type": "collectible",     "screen": "0,0", "x": 10, "y": 6,  "sprite": "coin", "value": 1 },
    { "type": "collectible",     "screen": "0,0", "x": 11, "y": 6,  "sprite": "coin", "value": 1 },
    { "type": "collectible",     "screen": "0,0", "x": 18, "y": 3,  "sprite": "coin", "value": 1 },
    { "type": "collectible",     "screen": "0,0", "x": 19, "y": 3,  "sprite": "coin", "value": 1 },

    { "type": "collectible",     "screen": "1,0", "x": 12, "y": 5,  "sprite": "coin", "value": 1 },
    { "type": "collectible",     "screen": "1,0", "x": 13, "y": 5,  "sprite": "coin", "value": 1 },
    { "type": "collectible",     "screen": "1,0", "x": 14, "y": 5,  "sprite": "coin", "value": 1 },
    { "type": "collectible",     "screen": "1,0", "x": 22, "y": 11, "sprite": "coin", "value": 1 },

    { "type": "npc",             "screen": "1,0", "x": 21, "y": 12, "sprite": "villager", "behavior": "pace", "paceRange": 3 },

    { "type": "moving_platform", "screen": "1,0", "x": 7,  "y": 11, "sprite": "platform_wood", "path": [[7,11],[17,11]], "speed": 1.5 }
  ],

  "goal": { "type": "reach_tile", "screen": "1,0", "x": 24, "y": 12 }
}
```

---

## Playthrough Walkthrough

A successful run through the demo level:

1. **Start** at screen 0,0, standing on the ground (col 2).
2. Walk right, jump onto the **raised step** (cols 5-7), grab the coin.
3. From the step, jump right to the **mid bridge** (cols 9-12), grab two coins.
4. Drop down, walk right to the **vine** (col 20), climb up.
5. At the top, jump left onto the **high bridge** (cols 17-20), grab two coins.
6. Drop back down, jump over the **gap** (cols 14-16).
7. Walk right off the screen edge → **transition** to screen 1,0.
8. Walk right to the gap edge (col 5), wait for the **moving platform**.
9. Ride the platform across the gap. (Skilled players can jump up to the **bonus bridge** at row 6 for three extra coins.)
10. Land on the right side ground (col 19).
11. Walk past the **pacing NPC**, grab the coin near col 22.
12. Reach the **goal tile** at col 24 → "Level Complete."

**Total collectibles:** 10 coins (5 in screen 0,0 + 4 in screen 1,0 + 1 near goal).

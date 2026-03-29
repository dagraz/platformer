# Sprite Sheet Extractor — CLI Toolset PRD (v4)

## Problem

The platformer engine consumes sprite sheets in a precise format: a PNG grid of equally-sized frames with a JSON manifest. The creative starting point is a hand-drawn scan or phone photo — colored pencil characters on graph paper, drawn in a grid of cells with row labels naming the animation state. Getting from that raw image to an engine-ready sprite sheet currently means manual cropping, cleanup, and assembly in an image editor.

## Approach

A set of Unix command line tools forming a pipeline, built as a `tools/` subdirectory within the platformer engine project. Each tool does one job, takes files in, writes files out, and can be composed with others. The user runs them in sequence, inspecting intermediate results and adjusting parameters between steps.

Colocating with the engine means the tools and engine share a single source of truth for sprite sheet format, frame dimensions, and manifest schema.

The pipeline:

```
scan.jpg or photo.jpg
  → sprite-grid-detect    → grid.json + corrected.png (deskew, perspective fix, grid detection)
  → sprite-extract        → cells/*.png + cells.json (individual cell images + metadata)
  → sprite-clean          → cleaned/*.png (background removed, artifacts cleaned)
  → sprite-normalize      → normalized/*.png (scaled, aligned, anchored)
  → sprite-assemble       → player.png + player.manifest.json (final sprite sheet)
```

Each step produces visible intermediate output that can be inspected and manually corrected before feeding into the next step.

---

## Input Format

The input is an image of hand-drawn sprites on graph paper. It may come from:

- **Flatbed scanner** — high quality, minimal distortion, possible slight rotation from page placement
- **Phone photo** — perspective skew from camera angle, rotation from phone tilt, variable lighting, background clutter (table, desk visible around the paper)

### Graph Paper Structure

All sprite sheets are drawn on paper produced by the same program (a spreadsheet). The paper has a specific, deterministic structure:

**Fine grid.** A uniform grid of lines covers the printable area. All lines are the same weight — there are no "heavy" or "bold" lines. The grid squares are 16×16 pixels at print resolution.

**Cells are defined by the absence of grid lines.** The drawing cells are rectangular regions where the fine grid has been removed — blank white paper where artists draw. The surrounding areas (margins, gaps between cells) retain the fine grid.

**Cell dimensions.** Each cell for a character sprite sheet is 4×8 fine-grid squares (64×128 pixels at 16px per square — matching the engine's character frame size).

**Between cells:** The fine grid continues in the narrow strips between adjacent cells. These 1-fine-grid-square-wide strips (16px) of grid texture separate cells in the same row.

**Between state rows:** The fine grid continues in the taller gaps between rows. These contain the printed label text and additional grid texture.

**Labels.** Each state row has a label row above it (e.g., "Idling", "Walking", "Jumping, Launch and Apex", "Falling and near-landing", "Climbing, alternate hands"). Labels are printed by the program in a dedicated row — they are not inside the gutters or the drawing cells. Artists may overwrite or annotate these labels.

**Layout of the standard character sprite sheet:**

```
┌──────────────────────────────────────────────────┐
│ fine grid background                             │
│                                                  │
│  "Idling"                    "Character Sprite   │
│  ┌─blank┐ ┌─blank┐ ┌─blank┐  Sheet"            │
│  │cell  │ │cell  │ │cell  │ ┌─blank┐ ┌─blank┐  │
│  │ 0,0  │ │ 0,1  │ │ 0,2  │ │ 0,3  │ │ 0,4  │  │
│  │      │ │      │ │      │ │      │ │      │  │
│  │4×8sq │ │4×8sq │ │4×8sq │ │4×8sq │ │4×8sq │  │
│  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘  │
│         ↑ 1-square grid strip between cells      │
│                                                  │
│  "Walking"                                       │
│  ┌─blank┐ ┌─blank┐ ┌─blank┐ ┌─blank┐ ┌─blank┐  │
│  │cell  │ │cell  │ │cell  │ │cell  │ │cell  │  │
│  │ 1,0  │ │ 1,1  │ │ 1,2  │ │ 1,3  │ │ 1,4  │  │
│  │      │ │      │ │      │ │      │ │      │  │
│  └──────┘ └──────┘ └──────┘ └──────┘ └──────┘  │
│  ... more rows ...                               │
└──────────────────────────────────────────────────┘
```

**Key insight for detection:** Cells are blank (no grid lines inside). The areas between and around cells retain the fine grid. Scanning horizontally or vertically, the transition from "grid present" (between cells) to "grid absent" (inside a cell) marks a cell boundary. Cells appear as wide valleys in a grid-density signal, separated by narrow peaks of grid texture. This is a strong signal because the contrast is between "lines exist" and "lines don't exist."

### Drawing Conventions

- **Rows** correspond to animation states. Row order matches the engine's state model.
- **Columns** correspond to animation frames. Frame 1 is leftmost.
- **Empty cells** are valid — they mean "no frame drawn yet."
- **Drawings stay within cell boundaries.** Art does not bleed across gutters.
- **Drawings vary in size** within their cells. They won't fill edge-to-edge or be centered.

### Variations

The program can produce sheets with different cell sizes for different asset types:
- Character sprites: 4×8 squares (64×128 px)
- Tiles: could be 4×4 or 8×8 squares
- The fine grid spacing (16px) and gutter convention (1 square) remain the same

---

## Tool 1: `sprite-grid-detect`

**Purpose:** Correct geometric distortion from scanning or photography, then detect the graph paper grid structure and cell boundaries.

**Input:**
- A scan or photo (JPEG, PNG)

**Output:**
- `corrected.png` — the deskewed, perspective-corrected image (or a copy of the original if no correction was needed)
- `grid.json` — detected grid structure with cell boundaries in corrected-image coordinates
- Optionally, a debug image showing detected grid and cells overlaid on the image

### Stage 1: Geometric Correction

Phone photos and crooked scans produce images where the grid lines aren't aligned with the image axes. The tool detects and fixes two types of distortion:

**Rotation** — the paper is flat and parallel to the camera/scanner sensor, but tilted. Grid lines are straight and parallel but at an angle to the image frame. Fixed with an affine rotation.

**Perspective skew** — the camera was not directly above the paper. The paper appears as a trapezoid; parallel grid lines converge toward a vanishing point; cells near the camera appear larger. Fixed with a perspective transform (homography).

**Correction algorithm:**

1. **Detect lines.** Use LSD (Line Segment Detector) or Hough transform to find the fine grid lines. Since all lines are the same weight, any strong line in the image that's part of the regular grid pattern qualifies.
2. **Cluster by angle.** Separate into near-horizontal and near-vertical groups. Filter outliers (drawing edges, table edges, tablecloth patterns).
3. **Assess distortion type.** Compute angle variance within each group:
   - Both groups low variance (< 0.3°): **rotation only** — affine rotate by the median angle.
   - Either group has significant variance: **perspective** — lines are converging.
4. **Compute perspective correction:** Find the four outermost grid lines, compute their intersection corners, determine the target rectangle, compute and apply homography.
5. **Validate.** Reject rotations > `--max-rotation` degrees. Report residual error. Crop to grid boundary. Save `corrected.png`.

### Stage 2: Grid Detection

After correction, the fine grid lines are axis-aligned. Detection exploits the known paper structure:

1. **Detect fine grid spacing.** Project pixel intensities to 1D profiles (sum columns → horizontal profile, sum rows → vertical profile). The fine grid creates regular peaks at uniform intervals. Use autocorrelation or FFT to find the fundamental spacing in pixels. This gives the scale factor between the image and the 16px logical grid.

2. **Find cells via density profile.** Compute a grid-density signal along each axis — measuring how much periodic grid-line texture exists at each position. Cells (no grid lines) appear as **wide valleys**. The grid-filled areas between cells appear as **peaks**. Use autocorrelation strength at the grid spacing to distinguish "grid present" from "grid absent."

3. **Classify valley types.** The density profile has two kinds of valleys:
   - **Cell-sized valleys** (4 or 8 grid squares wide): actual drawing cells
   - **Margin valleys**: large blank regions at the edges of the page (no grid lines)
   Between the cell valleys, narrow peaks of grid texture correspond to the 1-square-wide strips between cells, and wider peaks correspond to the row gaps (with labels and grid texture).

4. **Build cells.** Group valleys into rows and columns. Each valley is a cell rectangle.

5. **Identify state rows.** The wider peaks between rows of cells contain label text. The pattern is: wide peak (with label) → row of cell valleys → wide peak (with label) → row of cell valleys → ...

6. **Classify occupancy.** For each cell, compute pixel variance (grayscale std dev). Empty cells are nearly uniform white (no grid lines, no art). Cells with art have significantly higher variance.

### Output: `grid.json`

```json
{
  "source": "photo.jpg",
  "correctedImage": "corrected.png",
  "correction": {
    "type": "perspective",
    "rotationDegrees": 3.2,
    "residualErrorPx": 0.4
  },
  "imageWidth": 2480,
  "imageHeight": 3200,
  "fineGridSpacing": 18.7,
  "cells": [
    {
      "row": 0,
      "col": 0,
      "x": 84,
      "y": 120,
      "width": 75,
      "height": 150,
      "occupied": true
    },
    {
      "row": 0,
      "col": 1,
      "x": 178,
      "y": 120,
      "width": 75,
      "height": 150,
      "occupied": false
    }
  ]
}
```

Note: `fineGridSpacing` records the detected grid spacing in image pixels. This varies by scan DPI / photo resolution. Cell coordinates are in image pixels, not logical grid squares.

### Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--input, -i` | (required) | Path to scan/photo image |
| `--output, -o` | `grid.json` | Path for output JSON |
| `--corrected-image` | `corrected.png` | Path to save the corrected image |
| `--correct` | `auto` | Correction mode: `auto`, `rotation`, `perspective`, `none` |
| `--max-rotation` | `15` | Maximum auto-correction rotation in degrees |
| `--debug-image` | (none) | Path to write annotated debug image |
| `--min-line-length` | `0.5` | Minimum line length as fraction of image dimension |

**Manual override:** The user can hand-edit `grid.json` to adjust cell boundaries or toggle occupancy. Downstream tools consume `grid.json` and don't care how it was produced.

---

## Tool 2: `sprite-extract`

**Purpose:** Extract individual cell images from the corrected scan using the grid definition, and attach metadata.

**Input:**
- The corrected image (from `sprite-grid-detect`)
- `grid.json`
- A row-to-state mapping

**Output:**
- `cells/` directory with one PNG per occupied cell, named `{state}_{frame}.png`
- `cells.json` — metadata for all extracted cells

**What it does:**

1. Load the corrected image and grid definition.
2. For each occupied cell, crop that region and save as PNG.
3. Map rows to state names via `--rows`.
4. Number frames per row, left-to-right, 0-indexed.
5. Write `cells.json`.

**`cells.json` format:**

```json
{
  "source": "corrected.png",
  "grid": "grid.json",
  "frames": [
    {
      "file": "cells/idle_0.png",
      "state": "idle",
      "frame": 0,
      "sourceRect": { "x": 84, "y": 120, "width": 75, "height": 150 },
      "row": 0,
      "col": 0
    }
  ]
}
```

**Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--input, -i` | `corrected.png` | Path to corrected image |
| `--grid, -g` | `grid.json` | Path to grid definition |
| `--output-dir` | `cells/` | Directory for extracted cell PNGs |
| `--output-meta` | `cells.json` | Path for metadata JSON |
| `--rows` | (required) | Comma-separated row-to-state mapping: `idle,walk,jump,fall,climb` |
| `--skip-empty` | `true` | Skip cells detected as unoccupied |
| `--padding` | `0` | Pixels to inset from cell boundary (positive = inset into cell, trims fine grid lines at edges) |

---

## Tool 3: `sprite-clean`

**Purpose:** Remove background artifacts from extracted cell images — graph paper lines, paper texture, scan shadows, noise — leaving just the drawing on a transparent background.

**Input:**
- Extracted cell PNGs (from `sprite-extract`)

**Output:**
- `cleaned/` directory with processed PNGs (transparent backgrounds)

**Processing pipeline, in order:**

1. **White balance** (optional). Normalize paper background to true white.

2. **Background color removal.** Identify the dominant background color (paper white/cream) and set matching pixels to transparent. Uses HSL distance for tolerance. Auto-detects by sampling corners, or user specifies. Any residual grid lines at cell edges are close to paper white and are removed in this step.

3. **Artifact cleanup.** Connected-component filter removes isolated pixel clusters smaller than `--min-blob-size`.

4. **Edge cleanup.** Optional morphological erosion to remove fringe pixels at drawing/background boundary.

5. **Alpha feathering** (optional). Soften transparency edges.

**Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--input-dir` | `cells/` | Directory of cell PNGs to clean |
| `--output-dir` | `cleaned/` | Directory for cleaned PNGs |
| `--grid` | `grid.json` | Grid definition (for fine grid spacing info) |
| `--white-balance` | `false` | Apply white balance correction |
| `--wb-sample` | `corners` | White balance sample source: `corners` or hex color |
| `--bg-color` | `auto` | Background color to key out (hex). `auto` samples corners |
| `--bg-tolerance` | `30` | HSL distance tolerance (0–100) |
| `--min-blob-size` | `20` | Minimum connected component size to keep |
| `--erode` | `0` | Erosion radius for edge cleanup |
| `--feather` | `0` | Alpha feather radius |
| `--files` | (all) | Process only these filenames (for per-file reruns) |
| `--debug-image` | (none) | Write before/after debug composites |

---

## Tool 4: `sprite-normalize`

**Purpose:** Scale, align, and anchor cleaned cell images to a consistent target size.

**Input:**
- Cleaned cell PNGs

**Output:**
- `normalized/` directory with consistently-sized PNGs

**What it does:**

1. Find bounding box of non-transparent pixels.
2. Scale art to fit within target frame dimensions (configurable fit mode).
3. Anchor within frame (default: bottom, for consistent ground line).
4. Write as exactly-sized PNGs with transparent background.

**Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--input-dir` | `cleaned/` | Directory of cleaned PNGs |
| `--output-dir` | `normalized/` | Directory for normalized PNGs |
| `--width` | `64` | Target frame width |
| `--height` | `128` | Target frame height |
| `--fit` | `contain` | Fit mode: `contain`, `cover`, `stretch`, `none` |
| `--anchor` | `bottom` | Vertical anchor: `bottom`, `center`, `top` |
| `--margin` | `2` | Pixels of margin within frame |

**Consistency report:** Prints scale factor per frame, warns on large variation.

---

## Tool 5: `sprite-assemble`

**Purpose:** Assemble normalized frames into a sprite sheet PNG + engine manifest JSON.

**Input:**
- Normalized cell PNGs
- `cells.json` metadata

**Output:**
- Sprite sheet PNG
- Manifest JSON

**Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--input-dir` | `normalized/` | Directory of normalized PNGs |
| `--meta` | `cells.json` | Path to cell metadata |
| `--output` | `player.png` | Output sprite sheet path |
| `--manifest` | `player.manifest.json` | Output manifest path |
| `--fps` | `idle=4,walk=10,jump=1,fall=1,climb=6` | FPS per state |
| `--columns` | `auto` | Column count (`auto` = max frame count) |
| `--state-order` | `idle,walk,jump,fall,climb` | Row ordering |
| `--padding` | `0` | Transparent padding between frames |
| `--duplicate` | (none) | Fill rules: `idle=4,climb=2` cycles frames to target count |

**Output manifest:**

```json
{
  "frameWidth": 64,
  "frameHeight": 128,
  "states": {
    "idle":  { "row": 0, "frames": 4, "fps": 4 },
    "walk":  { "row": 1, "frames": 4, "fps": 10 },
    "jump":  { "row": 2, "frames": 2, "fps": 1 },
    "fall":  { "row": 3, "frames": 2, "fps": 1 },
    "climb": { "row": 4, "frames": 2, "fps": 6 }
  }
}
```

---

## Full Pipeline Example

```bash
# Step 1: Detect grid (auto-corrects rotation/perspective)
sprite-grid-detect -i photo.jpg -o grid.json \
  --corrected-image corrected.png --debug-image debug_grid.png

# Step 2: Extract cells
sprite-extract -i corrected.png -g grid.json \
  --rows idle,walk,jump,fall,climb --padding 2

# Step 3: Clean backgrounds
sprite-clean --input-dir cells/ --output-dir cleaned/ \
  --bg-tolerance 35 --erode 1

# Step 4: Normalize to engine frame size
sprite-normalize --input-dir cleaned/ --output-dir normalized/ \
  --width 64 --height 128 --anchor bottom --margin 2

# Step 5: Assemble
sprite-assemble --input-dir normalized/ --meta cells.json \
  --output player.png --manifest player.manifest.json \
  --fps idle=4,walk=10,jump=1,fall=1,climb=6 \
  --duplicate idle=4,climb=2
```

---

## Project Structure

```
platformer/
├── tools/
│   ├── pyproject.toml
│   └── sprite_tools/
│       ├── __init__.py
│       ├── cli/
│       │   ├── grid_detect.py
│       │   ├── extract.py
│       │   ├── clean.py
│       │   ├── normalize.py
│       │   └── assemble.py
│       ├── core/
│       │   ├── correction.py
│       │   ├── grid.py
│       │   ├── background.py
│       │   └── transform.py
│       ├── util/
│       │   ├── image_io.py
│       │   ├── color.py
│       │   └── debug.py
│       └── tests/
│           └── fixtures/
│               ├── wizard character sheet.jpg
│               ├── dino character sheet.jpg
│               └── blank sprite sheet.pdf
├── src/                    # Platformer engine (existing)
├── public/                 # Engine assets (existing)
└── ...
```

### Dependencies

```
python >= 3.10
opencv-python >= 4.8
numpy >= 1.24
Pillow >= 10.0
```

### Error Handling

Creative tool philosophy: when ambiguous, pick the most likely answer, warn, continue, suggest the user inspect output. `--debug-image` is the primary diagnostic tool.

---

## Edge Cases

**Perspective-distorted phone photos.** Auto-corrected via homography. The dino photo is the test case.

**Stray marks outside the grid.** Pencil scribbles outside the grid boundary get cropped during correction.

**Label text in row gaps.** Labels are printed text in the grid-filled gaps between state rows. The cell detection distinguishes these from cells because the label rows contain grid texture (high density), while cells are blank (low density).

**Drawings that are very light or small.** The occupancy classifier uses variance against the empty-cell baseline (which is nearly uniform white — no grid lines, no art). Even a faint drawing adds enough variance to register. But very light pencil sketches might be marginal — the user can toggle occupancy in `grid.json`.

**Different cell sizes.** The gutter-detection approach works regardless of cell size. A 4×4 cell (for tiles) creates a different density-profile pattern than a 4×8 cell, but the gutters look the same. The tool reports detected cell dimensions.

**Curved or crumpled paper.** Not correctable with a homography. Out of scope.

---

## Open Questions

1. **OCR on row labels?** Labels are printed (not handwritten), so OCR is more feasible than previously assumed. Still requiring `--rows` for V1, but could auto-detect from the printed text in a later version.

2. **Should `sprite-clean` read `grid.json` for fine grid spacing?** Yes — knowing the exact grid line spacing makes morphological line removal much more precise. Added `--grid` flag.

3. **Tile-specific workflows?** Same pipeline, different `--width`/`--height` on normalize. Document the parameter overrides.

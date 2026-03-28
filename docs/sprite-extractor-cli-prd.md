# Sprite Sheet Extractor — CLI Toolset PRD (v3)

## Problem

The platformer engine consumes sprite sheets in a precise format: a PNG grid of equally-sized frames with a JSON manifest. The creative starting point is a hand-drawn scan or phone photo — colored pencil characters on graph paper, drawn in a grid of cells with row labels naming the animation state. Getting from that raw image to an engine-ready sprite sheet currently means manual cropping, cleanup, and assembly in an image editor.

## Approach

A set of Unix command line tools forming a pipeline, built as a `tools/` subdirectory within the platformer engine project. Each tool does one job, takes files in, writes files out, and can be composed with others. The user runs them in sequence, inspecting intermediate results and adjusting parameters between steps.

Colocating with the engine means the tools and engine share a single source of truth for sprite sheet format, frame dimensions, and manifest schema. We can always extract the tools into a standalone package later.

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
- **Phone photo** — perspective skew from camera angle, rotation from phone tilt, variable lighting, background clutter (table, desk surface visible around the paper)

### Graph Paper Convention

All sprite sheets are drawn on the same type of graph paper (produced by the same program):

- **Two-tier grid:** Fine lines forming small squares, and heavier lines forming larger rectangular cells.
- **The heavier lines always define the cell boundaries.** The fine grid is internal texture within cells.
- **Rows** correspond to animation states, labeled in handwriting (e.g., "Idling", "Walking").
- **Columns** correspond to animation frames. Frame 1 is leftmost.
- **Empty cells** are valid — they mean "no frame drawn yet."
- **Drawings mostly stay within cell boundaries.** Art may bleed slightly across heavy grid lines (a pencil stroke crossing a line by a few pixels). The `--bleed` flag on `sprite-extract` expands the crop region to capture this overshoot.
- **Drawings vary in size** within their cells. They won't fill edge-to-edge or be perfectly centered.
- **The paper may vary in cell count.** Standard character sheets use one cell size; tile sheets might use 4×4 or 8×8 fine-grid cells per tile. The grid detection handles this because it finds heavy lines regardless of their spacing.

---

## Tool 1: `sprite-grid-detect`

**Purpose:** Correct geometric distortion from scanning or photography, then detect the graph paper grid structure and cell boundaries.

**Input:**
- A scan or photo (JPEG, PNG)

**Output:**
- `corrected.png` — the deskewed, perspective-corrected image (or a copy of the original if no correction was needed)
- `grid.json` — detected grid structure with cell boundaries in corrected-image coordinates
- Optionally, a debug image showing detected lines, corners, and grid overlaid on the image

### Stage 1: Geometric Correction

Phone photos and crooked scans produce images where the grid lines aren't aligned with the image axes. The tool detects and fixes two types of distortion:

**Rotation** — the paper is flat and parallel to the camera/scanner sensor, but tilted. Grid lines are straight and parallel but at an angle to the image frame. Fixed with an affine rotation.

**Perspective skew** — the camera was not directly above the paper. The paper appears as a trapezoid; parallel grid lines converge toward a vanishing point; cells near the camera appear larger. Fixed with a perspective transform (homography).

Graph paper is a near-ideal calibration target because the lines are known to be straight, parallel within groups, perpendicular between groups, and uniformly spaced.

**Correction algorithm:**

1. **Detect lines.** Use LSD (Line Segment Detector) or Hough transform to find strong lines in the image.
2. **Cluster by angle.** Separate lines into a near-horizontal group and a near-vertical group. Filter outliers (drawing edges, table edges, tablecloth patterns).
3. **Assess distortion type.** Compute the standard deviation of angles within each line group:
   - Both groups have low angle variance (< 0.3°): **rotation only**.
   - Either group has significant angle variance: **perspective distortion**.
4. **Compute correction transform:**
   - *Rotation:* Affine rotation by the median angle of the horizontal group.
   - *Perspective:* Find the four outermost grid lines (top, bottom, left, right). Compute their four intersection points (apparent corners of the grid). Determine the target rectangle from the grid's cell count and aspect ratio. Compute homography mapping source corners to target rectangle. For robustness, also fit a homography against all grid intersection points (overdetermined least-squares via `cv2.findHomography`) and prefer it if residual error is lower.
5. **Validate.** Reject rotations exceeding `--max-rotation` degrees. Report residual error (mean deviation of corrected intersections from a perfect regular grid). Under 1px is good; over 3px warrants a warning.
6. **Apply transform** using bilinear interpolation. Crop to the grid boundary (removes surrounding table/desk visible in phone photos). Save as `corrected.png`.

**Auto mode decision tree:**

```
detect lines → cluster H and V groups
  → no clear groups found?      → warn, skip correction
  → rotation > max_rotation?    → error, suggest manual rotation
  → angle std < 0.3° both?     → rotation only (affine)
  → else                        → full perspective (homography)
```

### Stage 2: Grid Detection

After correction, the grid lines are axis-aligned. Detection proceeds:

1. **Detect lines** on the corrected image — truly horizontal and truly vertical.
2. **Distinguish heavy vs. fine grid lines.** Since the paper is consistent (same program), we can rely on intensity/thickness clustering. Detect all lines, measure weight, cluster into two groups, keep the heavier group. The `--fine-grid` flag switches to the lighter group (for future tile workflows).
3. **Cluster line positions.** Merge nearby parallel lines (within a threshold) into single positions.
4. **Regularize.** Compute median spacing, snap to even grid with ±10% tolerance.
5. **Build cells.** Each pair of adjacent horizontal lines × adjacent vertical lines defines a cell rectangle.
6. **Classify occupancy.** For each cell, compute pixel variance (std dev of grayscale values). Cells with significantly higher variance than the median empty cell are marked `occupied`.

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
  "gridLines": {
    "horizontal": [45, 520, 1040, 1560, 2080, 2600],
    "vertical": [30, 430, 830, 1230, 1630, 2030, 2430]
  },
  "cells": [
    {
      "row": 0,
      "col": 0,
      "x": 30,
      "y": 45,
      "width": 400,
      "height": 475,
      "occupied": true
    },
    {
      "row": 0,
      "col": 1,
      "x": 430,
      "y": 45,
      "width": 400,
      "height": 475,
      "occupied": false
    }
  ]
}
```

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
| `--line-threshold` | `auto` | Line detection sensitivity. `auto` distinguishes heavy from fine |
| `--fine-grid` | `false` | Detect the fine grid instead of the major grid |

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
      "sourceRect": { "x": 30, "y": 45, "width": 400, "height": 475 },
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
| `--padding` | `0` | Pixels to inset from cell boundary (positive = inset, trims grid lines from edges) |
| `--bleed` | `0` | Pixels to expand crop beyond cell boundary (captures art that bleeds across grid lines) |

---

## Tool 3: `sprite-clean`

**Purpose:** Remove background artifacts from extracted cell images — graph paper lines, paper texture, scan shadows, noise — leaving just the drawing on a transparent background.

**Input:**
- Extracted cell PNGs (from `sprite-extract`)

**Output:**
- `cleaned/` directory with processed PNGs (transparent backgrounds)

**Processing pipeline, in order:**

1. **White balance** (optional). Normalize the paper background to true white. Corrects yellowish color casts from phone photos. Samples the background color and shifts the white point.

2. **Graph paper line removal** (optional, default on). Detect and remove the fine grid lines within the cell using morphological operations — horizontal and vertical kernels isolate thin regular structures. Removed lines are inpainted using surrounding pixel colors. Can be disabled for tile art that intentionally incorporates grid texture.

3. **Background color removal.** Identify the dominant background color (paper white/cream) and set matching pixels to transparent. Uses HSL distance for tolerance. Auto-detects by sampling corners, or user specifies.

4. **Artifact cleanup.** Connected-component filter removes isolated pixel clusters smaller than `--min-blob-size`.

5. **Edge cleanup.** Optional morphological erosion to remove fringe pixels at drawing/background boundary.

6. **Alpha feathering** (optional). Soften transparency edges by a configurable radius.

**Flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--input-dir` | `cells/` | Directory of cell PNGs to clean |
| `--output-dir` | `cleaned/` | Directory for cleaned PNGs |
| `--white-balance` | `false` | Apply white balance correction |
| `--wb-sample` | `corners` | White balance sample source: `corners` or hex color |
| `--remove-grid-lines` | `true` | Remove fine graph paper lines |
| `--grid-line-width` | `auto` | Expected grid line width in pixels |
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

1. Find the bounding box of non-transparent pixels in each image.
2. Scale the art to fit within target frame dimensions (configurable fit mode).
3. Anchor within the frame (default: bottom, for consistent ground line).
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
| `--margin` | `2` | Pixels of margin within the frame |

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

# Step 2: Extract cells (--bleed captures art that crosses grid lines)
sprite-extract -i corrected.png -g grid.json \
  --rows idle,walk,jump,fall,climb --padding 4 --bleed 6

# Step 3: Clean backgrounds
sprite-clean --input-dir cells/ --output-dir cleaned/ \
  --remove-grid-lines --bg-tolerance 35 --erode 1

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
│       │   ├── morphology.py
│       │   └── transform.py
│       ├── util/
│       │   ├── image_io.py
│       │   ├── color.py
│       │   └── debug.py
│       └── tests/
│           ├── test_correction.py
│           ├── test_grid.py
│           ├── test_background.py
│           └── fixtures/
│               ├── wizard_scan.jpg
│               └── dino_photo.jpg
│   └── pyproject.toml
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

### Installation

```bash
cd platformer/tools
pip install -e .
```

### Error Handling

Creative tool philosophy: when ambiguous, pick the most likely answer, warn, continue, suggest the user inspect output and adjust flags. Never crash on recoverable conditions. `--debug-image` is the user's main way to understand what happened.

---

## Edge Cases

**Perspective-distorted phone photos.** Auto-corrected via homography. The dino photo is the test case — visible trapezoid, tablecloth visible around edges, slight color cast.

**Stray marks outside the grid.** The dino photo has pencil scribbles on the left margin. Grid detection should ignore these — they're outside the detected grid boundary and get cropped during correction.

**Inconsistent cell sizes.** Grid regularization tolerates ±10% and snaps to median spacing.

**Completely empty rows.** Omitted from output.

**Poor lighting / color casts.** The `--white-balance` flag on `sprite-clean` handles this. The dino photo has a slight warm cast from indoor lighting.

**Different cell sizes for tiles.** The same pipeline works — different grid line spacing is detected automatically. The user specifies `--width 64 --height 64` (or other sizes) at the normalize step.

---

## Open Questions

1. **OCR on row labels?** Current decision: require `--rows` flag. The labels are handwritten and unreliable for OCR.

2. **Tile-specific semantics?** The pipeline works for tiles with different `--width`/`--height`. No tile-specific tooling for V1 — just document the parameter overrides.

3. **Integration with Claude image generation?** Users with incomplete sheets could use Claude to generate additional frames. Out of scope for V1 but worth considering in export format design.

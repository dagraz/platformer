# Sprite Tools

CLI pipeline for extracting sprite sheets from hand-drawn character art on graph paper. Takes a flatbed scan of a graph paper character sheet and produces a sprite sheet PNG + engine manifest JSON.

## Setup

```bash
cd tools/
pip install -e .
```

This installs six commands: `sprite-grid-detect`, `sprite-extract`, `sprite-clean`, `sprite-normalize`, `sprite-assemble`, and `sprite-pipeline`.

**Requirements:** Python 3.10+, OpenCV, NumPy, Pillow (installed automatically).

## Quick Start

The fastest path from scan to sprite sheet:

```bash
cd tools/

# Generate a template grid from the blank sheet (one-time setup)
sprite-grid-detect \
  -i "sprite_tools/tests/fixtures/blank_sheet-1.png" \
  --correct none \
  -o template_grid.json

# Run the full pipeline
sprite-pipeline \
  -i "sprite_tools/tests/fixtures/wizard character sheet.jpg" \
  --template template_grid.json \
  --rows idle,walk,jump,fall,climb \
  --duplicate idle=4,climb=2 \
  -o wizard.png
```

Output: `wizard.png` (sprite sheet) + `wizard.manifest.json` (engine metadata).

## Input Format

The tools expect a **flatbed scan** of a character sheet drawn on graph paper with this structure:

- **Graph paper background**: Uniform fine grid lines (~16px squares at 300 DPI)
- **Cells**: Blank rectangles where grid lines have been removed (the drawing areas)
- **Cell size**: 4×8 grid squares per cell (e.g., 64×128 px at the grid's scale)
- **Cell spacing**: 1 grid square between cells
- **Rows**: Each row is one animation state (idle, walk, jump, etc.), with label text above
- **Frames**: Each cell in a row is one animation frame, left to right

Camera photos are **not currently supported** — only flatbed scans.

## Template Grid

For reliable results, generate a template from the blank graph paper sheet first:

```bash
sprite-grid-detect \
  -i "sprite_tools/tests/fixtures/blank_sheet-1.png" \
  --correct none \
  -o template_grid.json
```

This detects all cell positions on the empty sheet. When processing a real scan, pass `--template template_grid.json` to scale the known grid layout to the scan's resolution instead of auto-detecting cells (which can miss cells that contain character art).

The template only needs to be generated once per paper format.

## Pipeline Overview

The pipeline has five stages. `sprite-pipeline` runs all of them, or you can run each individually for more control.

### Stage 1: Grid Detection (`sprite-grid-detect`)

Detects the graph paper grid structure and locates drawing cells.

```bash
sprite-grid-detect \
  -i scan.jpg \
  --template template_grid.json \
  --correct none \
  --corrected-image corrected.png \
  -o grid.json \
  --debug-image debug.png
```

**Key flags:**
- `--template <grid.json>` — Scale a known grid layout (recommended)
- `--correct auto|rotation|perspective|none` — Geometric correction mode
- `--corrected-image <path>` — Save the corrected image (needed for extraction)
- `--debug-image <path>` — Annotated image showing detected cells

**Output (`grid.json`):** Cell positions, dimensions, occupancy, fine grid spacing.

### Stage 2: Extraction (`sprite-extract`)

Crops each occupied cell from the corrected image.

```bash
sprite-extract \
  -i corrected.png \
  -g grid.json \
  --rows idle,walk,jump,fall,climb \
  --padding 2 \
  --output-dir cells/ \
  --output-meta cells.json
```

**Key flags:**
- `--rows` — Comma-separated state names, one per grid row (required)
- `--padding <px>` — Inset from cell boundary to trim edge grid lines (default: 0, recommended: 2)

**Output:** One PNG per occupied cell (`idle_0.png`, `walk_0.png`, ...) + `cells.json` metadata.

### Stage 3: Cleaning (`sprite-clean`)

Removes the paper background, leaving drawings on transparency.

```bash
sprite-clean \
  --input-dir cells/ \
  --output-dir cleaned/ \
  --bg-tolerance 30
```

**Key flags:**
- `--bg-tolerance <0-100>` — HSL distance threshold for background removal. Higher = more aggressive. Start at 30, increase if paper color remains.
- `--bg-color <R,G,B>` — Override auto-detected background color
- `--min-blob-size <px>` — Remove isolated pixel clusters smaller than this (default: 20)
- `--erode <px>` — Erosion radius to clean fringe pixels at art edges (default: 0)
- `--feather <px>` — Gaussian blur radius on alpha edges (default: 0)
- `--debug-image <dir>` — Before/after composites on checkerboard

**Tuning:** Background color is auto-detected from corner pixels across all cells. If a cell's art extends to its corners, the global detection still works because most cells have clean corners.

### Stage 4: Normalize (`sprite-normalize`)

Scales and anchors each frame to a consistent target size.

```bash
sprite-normalize \
  --input-dir cleaned/ \
  --output-dir normalized/ \
  --width 64 --height 128 \
  --anchor bottom \
  --margin 2
```

**Key flags:**
- `--width`, `--height` — Target frame size in pixels (default: 64×128, matching the engine's character tile size)
- `--anchor bottom|center|top` — Vertical placement within the frame (default: bottom)
- `--fit contain|cover|none` — Scale mode (default: contain)
- `--margin <px>` — Margin inside the frame edge (default: 2)

### Stage 5: Assemble (`sprite-assemble`)

Composites normalized frames into a grid sprite sheet with an engine manifest.

```bash
sprite-assemble \
  --input-dir normalized/ \
  --meta cells.json \
  --output player.png \
  --manifest player.manifest.json \
  --fps idle=4,walk=10,jump=1,fall=1,climb=6 \
  --duplicate idle=4,climb=2
```

**Key flags:**
- `--fps <state=N,...>` — Animation speed per state
- `--duplicate <state=N,...>` — Pad rows by cycling frames (e.g., `idle=4` repeats the single idle frame 4 times)
- `--columns auto|<N>` — Column count (default: auto = max frames across states)
- `--padding <px>` — Transparent padding between frames (default: 0)

**Output manifest format** (matches engine `SpriteManifest`):

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

## Using in the Engine

Copy the outputs into the engine's asset directory:

```bash
cp wizard.png ../public/assets/sprites/player.png
cp wizard.manifest.json ../public/assets/sprites/player.manifest.json
```

The engine loads these via its `SpriteManifest` interface (defined in `src/engine/types.ts`).

## Test Fixtures

Located in `sprite_tools/tests/fixtures/`:

| File | Description |
|------|-------------|
| `wizard character sheet.jpg` | Flatbed scan of a wizard character (5 states, 10 frames) |
| `blank sprite sheet.pdf` | Empty graph paper template (PDF, ground truth for grid structure) |
| `blank_sheet-1.png` | The blank sheet rasterized at 300 DPI (use this for `--template`) |

### Expected wizard results

| Row | State | Frames | Notes |
|-----|-------|--------|-------|
| 0   | idle  | 1      | Single standing pose |
| 1   | walk  | 4      | Walk cycle |
| 2   | jump  | 2      | Jump up + peak |
| 3   | fall  | 2      | Falling poses |
| 4   | climb | 1      | Climbing pose |

## Troubleshooting

**Background not fully removed:** Increase `--bg-tolerance` (try 35-50). Light-colored art (yellow, pale pink) may be close to the paper color in HSL space — use `--bg-color 255,255,255` to force exact white as the background.

**Art clipped at edges:** Increase `--padding` on extraction (try 4-6) or decrease `--margin` on normalize.

**Wrong cells detected as occupied/empty:** Use `--template` with a grid.json generated from the blank sheet. Auto-detection is less reliable.

**Grid spacing detection warning (H/V disagree):** Usually harmless — the tool takes the smaller value. If results are wrong, check that the scan is straight and use `--correct rotation`.

## Project Structure

```
tools/
├── pyproject.toml
├── README.md
└── sprite_tools/
    ├── cli/
    │   ├── grid_detect.py    # Stage 1: grid detection
    │   ├── extract.py        # Stage 2: cell extraction
    │   ├── clean.py          # Stage 3: background removal
    │   ├── normalize.py      # Stage 4: scale + anchor
    │   ├── assemble.py       # Stage 5: sprite sheet assembly
    │   └── pipeline.py       # All-in-one wrapper
    ├── core/
    │   ├── correction.py     # Rotation/perspective correction
    │   ├── grid.py           # Grid spacing + cell detection
    │   ├── background.py     # Background removal
    │   └── transform.py      # Art bounds + scaling
    ├── util/
    │   ├── image_io.py       # Load/save images
    │   ├── color.py          # HSL conversion, white balance
    │   └── debug.py          # Debug visualization helpers
    └── tests/
        └── fixtures/         # Test images
```

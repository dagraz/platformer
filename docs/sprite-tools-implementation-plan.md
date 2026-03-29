# Sprite Tools — Implementation Plan (v2)

## Overview

Five CLI tools built as a Python package in `platformer/tools/sprite_tools/`. Each phase produces a working tool tested against the primary fixture:

- **Wizard scan** (`wizard character sheet.jpg`) — flatbed scan, straight, clean

**Deferred:** Camera photos (e.g., `dino character sheet.jpg`) are not currently supported. Phone photos introduce noise, uneven lighting, color casts, and perspective distortion that break blank-cell detection and template alignment. Support may be revisited once the core pipeline is solid.

The graph paper format: uniform fine grid (16px squares) covering the background, cells defined as blank rectangles where grid lines have been removed, 4×8 squares per cell (64×128 px), 1-square grid strips between cells, printed labels in dedicated rows above each state row.

A **blank sheet PDF** (`blank sprite sheet.pdf`) serves as ground truth for the grid structure. It can be used as a `--template` for grid detection, which is more reliable than auto-detection.

---

## Phase 1: Project Scaffolding + Core Utilities

**Goal:** Installable package skeleton with shared utilities.

**Build:**

```
tools/
├── pyproject.toml
└── sprite_tools/
    ├── __init__.py
    ├── cli/
    │   ├── __init__.py
    │   ├── grid_detect.py   # stub
    │   ├── extract.py       # stub
    │   ├── clean.py         # stub
    │   ├── normalize.py     # stub
    │   └── assemble.py      # stub
    ├── core/
    │   └── __init__.py
    ├── util/
    │   ├── __init__.py
    │   ├── image_io.py
    │   ├── color.py
    │   └── debug.py
    └── tests/
        ├── __init__.py
        └── fixtures/
            ├── wizard character sheet.jpg
            ├── dino character sheet.jpg
            └── blank sprite sheet.pdf
```

**`util/image_io.py`:**
- `load_image(path) → np.ndarray` — loads via OpenCV (BGR)
- `load_image_rgba(path) → np.ndarray` — loads with alpha, creates if absent
- `save_image(image, path)` — saves PNG (with alpha) or JPEG
- `to_grayscale(image) → np.ndarray`

**`util/color.py`:**
- `rgb_to_hsl(r, g, b) → (h, s, l)`
- `hsl_distance(hsl1, hsl2) → float`
- `sample_background_color(image, method='corners') → (r, g, b)`
- `white_balance(image, sample_color) → image`

**`util/debug.py`:**
- `draw_lines(image, lines, color, thickness) → image`
- `draw_rects(image, rects, colors, labels, thickness) → image`
- `save_side_by_side(image_a, image_b, path)`
- `draw_density_profile(profile, path)` — plot a 1D density signal as an image (for debugging grid detection)

**Checkpoint:** `pip install -e .` from `tools/` works. `sprite-grid-detect --help` prints usage. Loading both fixtures via `image_io` succeeds. `color.sample_background_color()` returns reasonable paper-white from the wizard scan's corners.

---

## Phase 2: Grid Detection — Fine Grid Spacing

**Goal:** Detect the fine grid line spacing in both test fixtures. This is the foundational measurement everything else depends on.

**Build: `core/grid.py` (partial)**

```python
def compute_density_profile(image_gray, axis) -> np.ndarray:
    """Project pixel intensities along an axis.
    axis=0 → sum each column → horizontal profile (detects vertical lines)
    axis=1 → sum each row → vertical profile (detects horizontal lines)
    Returns 1D array of intensity sums, inverted so lines are peaks."""

def detect_fine_grid_spacing(image_gray) -> float:
    """Find the fundamental grid line spacing in pixels.
    Computes density profiles for both axes, runs autocorrelation
    to find the dominant periodic spacing.
    Returns spacing in pixels (will vary by scan DPI / photo resolution)."""
```

**Algorithm detail for `detect_fine_grid_spacing`:**

1. Convert to grayscale, invert (so lines are bright on dark).
2. Compute vertical density profile (sum each row → 1D signal). Fine grid horizontal lines create periodic peaks.
3. Autocorrelate the signal. The first strong peak after lag=0 gives the grid spacing.
4. Repeat for horizontal density profile (sum each column → detects vertical lines).
5. Both axes should give the same spacing (square grid). Average them. Warn if they disagree by > 5%.

**Wire into `cli/grid_detect.py` (partial):** Just detect spacing and report it.

**Checkpoint — wizard scan:** Tool reports fine grid spacing (should be some consistent value, e.g., ~18.7 px depending on scan DPI). Debug output shows the density profile with clear periodic peaks.

**Checkpoint — dino photo:** Spacing detected but may vary across the image (perspective makes cells on one side larger). The raw spacing detection still works because autocorrelation finds the dominant period even with mild frequency variation. Report the detected spacing.

---

## Phase 3: Grid Detection — Cell Finding

**Goal:** From the fine grid spacing, find cells (blank rectangles where grid lines are absent) and build the cell grid.

**Build: Add to `core/grid.py`**

```python
def compute_grid_density(image_gray, spacing, axis) -> np.ndarray:
    """Compute a grid-density signal along an axis — measuring how much
    periodic grid-line texture exists at each position.
    Returns 1D signal where high = grid lines present (between cells),
    low = grid lines absent (inside cells)."""

def find_cells(density_signal, spacing) -> list[CellRegion]:
    """Find wide valleys in the density signal — regions where grid lines
    are absent (= cell interiors). The peaks between valleys correspond to
    1-square grid strips between cells, or wider row gaps with labels.
    Returns list of cell region positions and widths."""

def build_cell_grid(h_cells, v_cells, image_shape) -> list[Cell]:
    """From horizontal and vertical cell regions, compute cell rectangles.
    Each intersection of an h_cell band and a v_cell band is a drawing cell."""

def classify_occupancy(image_gray, cells, fine_grid_spacing) -> list[Cell]:
    """Mark cells as occupied/empty.
    Empty cells are nearly uniform white (no grid lines, no art).
    Cells with art have significantly higher variance."""
```

```python
@dataclass
class GutterRegion:
    position: float      # center position in pixels
    width: float         # width in pixels
    gutter_type: str     # 'cell' (narrow, between cells) or 'row' (wide, between state rows)

@dataclass
class Cell:
    row: int
    col: int
    x: int; y: int
    width: int; height: int
    occupied: bool
```

**Complete `cli/grid_detect.py` (without correction):**

Full pipeline for straight images: detect spacing → compute grid density → find cell valleys → build cell grid → classify occupancy → write `grid.json`.

**Checkpoint — wizard scan:**

Run with `--correct none` (skip correction, the scan is straight). `grid.json` should contain:
- 5 state rows
- Row 0: 1 occupied cell (idle). Remaining empty.
- Row 1: 4 occupied (walk). Remaining empty.
- Row 2: 2 occupied (jump).
- Row 3: 2 occupied (fall).
- Row 4: 1 occupied (climb).

Debug image shows: detected cell regions as colored rectangles, occupied cells highlighted green, empty cells gray. Grid-density peaks (between cells) and row gaps visible as non-cell areas.

Verify: cell dimensions are consistent (all should be roughly 4×8 grid squares in pixel terms). Cell spacing is consistent. Label rows are correctly identified as row gaps, not cells.

---

## Phase 4: Geometric Correction

**Goal:** Add rotation and perspective correction. The dino photo becomes the primary test case.

**Build: `core/correction.py`**

```python
def detect_lines(image_gray, min_length_frac=0.5) -> list[LineSegment]:
    """Find line segments using LSD."""

def cluster_by_angle(lines) -> tuple[list, list]:
    """Separate into near-horizontal and near-vertical groups."""

def assess_distortion(h_lines, v_lines) -> tuple[str, dict]:
    """Returns ('none'|'rotation'|'perspective', stats).
    Checks angle variance within each group."""

def compute_rotation(h_lines) -> float:
    """Median angle of horizontal group."""

def find_grid_corners(h_lines, v_lines) -> np.ndarray:
    """Four outermost grid lines → four intersection points."""

def compute_perspective_transform(corners, image_shape) -> np.ndarray:
    """Homography mapping source corners to axis-aligned rectangle."""

def apply_correction(image, correction_type, matrix) -> np.ndarray:
    """Apply rotation or perspective warp. Crop to grid boundary."""

def compute_residual(corrected_image, h_lines, v_lines) -> float:
    """Mean deviation from perfect regular grid after correction."""
```

**Modify `cli/grid_detect.py`:**

Add `--correct`, `--corrected-image`, `--max-rotation`. Pipeline:
1. Detect lines on original image
2. Assess and apply correction
3. Run grid detection (Phase 3 code) on corrected image
4. Write corrected image + grid.json

**Checkpoint — wizard scan:** Minimal correction (< 1°), output essentially identical.

**Checkpoint — dino photo:** Should detect perspective skew. `corrected.png` shows:
- Grid lines are horizontal/vertical
- Tablecloth and table edges cropped away
- Cells are rectangular and uniformly sized

Then the Phase 3 grid detection runs on the corrected image and produces a valid `grid.json`:
- 5 state rows
- Row 0: 3 occupied (dino has 3 idle frames)
- Row 1: 4 occupied (walk)
- Row 2: 2 occupied (jump)
- Row 3: 2 occupied (fall)
- Row 4: 2 occupied (climb)

**Synthetic tests:** Warp wizard scan by known rotation and perspective. Verify recovery within tolerance.

---

## Phase 5: Extraction

**Goal:** Complete `sprite-extract`.

**Build: `cli/extract.py`**

- Parse `grid.json`, load corrected image
- Crop each occupied cell with optional padding inset
- Map rows to state names via `--rows`
- Number frames per state, 0-indexed
- Save PNGs, write `cells.json`

**Checkpoint — both fixtures:**

```bash
sprite-grid-detect -i wizard character sheet.jpg --debug-image debug.png
sprite-extract -i corrected.png -g grid.json --rows idle,walk,jump,fall,climb --padding 2
```

Wizard: 10 PNGs (`idle_0`, `walk_0..3`, `jump_0..1`, `fall_0..1`, `climb_0`).
Dino: 13 PNGs (`idle_0..2`, `walk_0..3`, `jump_0..1`, `fall_0..1`, `climb_0..1`).

Each PNG shows the character drawing with fine grid lines and paper background intact. Open in image viewer to verify clean crops.

---

## Phase 6: Cleaning — Background Removal

**Goal:** Build `sprite-clean` with background color removal.

**Build: `core/background.py`**

```python
def remove_background(image_rgba, bg_color, tolerance, space='hsl') -> np.ndarray
def detect_bg_color(image, method='corners') -> tuple[int, int, int]
def remove_small_components(alpha, min_size) -> np.ndarray
def erode_alpha(alpha, radius) -> np.ndarray
def feather_alpha(alpha, radius) -> np.ndarray
```

**Build: `cli/clean.py`**

Background removal pipeline. Support `--files` for per-file reruns, `--debug-image` for before/after.

**Checkpoint:** Cleaned PNGs show drawings on transparency. Paper white is gone. Any grid lines at cell edges are partially removed (they're close to background color). Dedicated line removal in Phase 7 handles the rest.

**Tuning:** Try `--bg-tolerance` 20–50 on both fixtures. Find the sweet spot. The dino photo may need `--white-balance` for the warm cast.

---

## Phase 7: Cleaning — Grid Line Removal

**Goal:** Add fine grid line removal. Since we know the grid spacing from `grid.json`, this is precise.

**Build: `core/morphology.py`**

```python
def detect_fine_grid_lines(image, grid_spacing) -> np.ndarray:
    """Find thin horizontal and vertical lines at the known spacing.
    Uses morphological opening with directional kernels sized to the
    known grid spacing. Returns binary mask of detected lines."""

def remove_lines_and_inpaint(image, line_mask) -> np.ndarray:
    """Remove detected lines. Inpaint gaps through drawings using
    cv2.inpaint() with Telea method."""
```

**Key advantage of knowing the grid spacing:** The morphological kernels can be tuned precisely. We know the lines are ~1px wide at a specific spacing. This eliminates false positives from the drawing's own lines (which are thicker and at irregular spacing).

**Modify `cli/clean.py`:** Insert grid line removal as step 2 (after white balance, before background removal). Read `--grid grid.json` for spacing info.

**Checkpoint:** Any grid lines intruding at cell edges are gone. The wizard's own pencil strokes (thicker, irregular) are preserved. Same for the dino.

Compare with `--remove-grid-lines` on vs off to verify.

---

## Phase 8: Normalize

**Goal:** Complete `sprite-normalize`.

**Build: `core/transform.py`**

```python
def find_art_bounds(image_rgba) -> tuple[int, int, int, int]
def fit_to_frame(image_rgba, w, h, fit, anchor, margin) -> np.ndarray
def compute_scale_factor(art_w, art_h, target_w, target_h, fit, margin) -> float
```

**Build: `cli/normalize.py`**

**Checkpoint:** All output PNGs exactly 64×128. Characters bottom-anchored. Scale factors reported. Walk frames consistent. Jump frames may have different scale (drawn larger) — warning expected and correct.

---

## Phase 9: Assemble

**Goal:** Complete `sprite-assemble`. Full pipeline end-to-end.

**Build: `cli/assemble.py`**

- Read `cells.json`, load normalized PNGs
- Handle `--duplicate` (cycle frames)
- Composite grid with Pillow
- Generate manifest JSON

**Checkpoint — wizard end-to-end:**

```bash
sprite-grid-detect -i wizard character sheet.jpg
sprite-extract -i corrected.png -g grid.json --rows idle,walk,jump,fall,climb --padding 2
sprite-clean --input-dir cells/ --output-dir cleaned/ --grid grid.json --remove-grid-lines --bg-tolerance 35 --erode 1
sprite-normalize --input-dir cleaned/ --output-dir normalized/ --width 64 --height 128 --anchor bottom
sprite-assemble --input-dir normalized/ --meta cells.json --output wizard.png --manifest wizard.manifest.json \
  --duplicate idle=4,climb=2
```

- `wizard.png` is 384×640 (6 cols × 5 rows × 64×128)
- Manifest matches engine format
- Idle row: 4 copies of same frame
- Walk row: 4 distinct frames

**Checkpoint — dino end-to-end:** Same pipeline, different frame counts. Verify manifest accuracy.

**Stretch test:** Copy output into `platformer/public/assets/sprites/` as `player.png` + `player.manifest.json`. Run the engine. Character renders and animates.

---

## Phase 10: Convenience & Polish

1. **`sprite-pipeline` wrapper** — all five steps in one command
2. **Preview HTML** — `sprite-assemble --preview preview.html` generates animated preview page
3. **Robustness** — large image downsampling, better error messages, input validation
4. **`tools/README.md`** — quick start, full example, parameter tuning guide

---

## Test Strategy

### Two fixtures + one ground truth
- **Wizard scan** — clean/straight baseline
- **Dino photo** — real-world skew, noise, color cast
- **Blank sheet PDF** — rasterize to verify grid detection against a known-empty sheet (all cells should be detected as empty, spacing should match expected values)

### Unit tests
Pure `core/` functions:
- `test_grid.py` — synthetic density profiles with known gutters → verify gutter detection
- `test_correction.py` — lines with known angles → verify distortion classification
- `test_background.py` — synthetic image with known BG → verify mask
- `test_transform.py` — known art bounds → verify scale/anchor

### Visual inspection
Every `--debug-image` is a test artifact. The density profile plots (Phase 2) are especially important — they show exactly what the algorithm sees and make tuning intuitive.

---

## Risk Log

| Risk | Impact | Mitigation |
|------|--------|------------|
| Fine grid spacing detection fails on dino photo (perspective varies spacing across image) | Can't build grid | Detect spacing locally (windowed autocorrelation) rather than globally. Or: correct perspective first (Phase 4), then detect spacing on corrected image. |
| Cell valleys not deep enough to distinguish from noise | Cells misdetected | The contrast is binary (grid lines present between cells vs absent inside cells), so valleys should be clear. Use ACF-based periodicity detection rather than simple amplitude. |
| Occupancy classifier fooled by label text | Labels detected as occupied cells | Labels are in row gutters, not in cells. The gutter detection separates them structurally. |
| Grid line removal damages art | Inpainting artifacts | Lines are ~1px at scan resolution. At 64×128 output, artifacts are subpixel. Known grid spacing makes kernels precise. |
| Background removal eats light-colored art | Pink hat, yellow feet disappear | HSL distance. Per-file `--files` reruns. Tolerance tuning documented. |
| Perspective correction quality on extreme angles | Stretched pixels | Validate residual error. Warn if > 3px. Document "photograph near-overhead." |

# Sprite Tools — Implementation Plan

## Overview

Five CLI tools built as a Python package in `platformer/tools/sprite_tools/`. Each phase produces a working tool tested against two fixtures:

- **Wizard scan** (`wizard character sheet.jpg`) — flatbed scan, straight, clean
- **Dino photo** (`dino character sheet.jpg`) — phone photo, perspective skew, tablecloth background, slight color cast, pencil marks outside grid

Both are drawn on the same graph paper format.

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
    │   ├── grid_detect.py   # stub: parses args, prints "not implemented"
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
            └── dino character sheet.jpg
```

**`pyproject.toml`** — package metadata, dependencies (`opencv-python>=4.8`, `numpy>=1.24`, `Pillow>=10.0`), console_script entry points for all five tools.

**`util/image_io.py`:**
- `load_image(path) → np.ndarray` — loads via OpenCV (BGR), handles JPEG/PNG
- `load_image_rgba(path) → np.ndarray` — loads with alpha channel, creates alpha if absent
- `save_image(image, path)` — saves PNG (with alpha) or JPEG (without)
- `image_dimensions(path) → (width, height)` — quick size check without full load

**`util/color.py`:**
- `rgb_to_hsl(r, g, b) → (h, s, l)` — single pixel conversion
- `hsl_distance(hsl1, hsl2) → float` — perceptual color distance
- `sample_background_color(image, method='corners') → (r, g, b)` — samples corners (or specified regions), returns median color
- `white_balance(image, sample_color) → image` — shifts white point so sample_color becomes white

**`util/debug.py`:**
- `draw_lines(image, lines, color, thickness) → image` — overlay line segments
- `draw_rects(image, rects, colors, thickness) → image` — overlay rectangles with labels
- `draw_grid(image, h_lines, v_lines, color) → image` — overlay grid
- `save_side_by_side(image_a, image_b, path)` — before/after composite

**Checkpoint:** `pip install -e .` from `tools/` directory works. `sprite-grid-detect --help` prints usage. Loading both test fixtures via `image_io` succeeds and reports correct dimensions.

---

## Phase 2: Grid Detection — Line Fragment Analysis

**Goal:** Detect line fragments and extract the geometric properties needed for correction: dominant grid angles, rough grid period, and spatial angle variation (for perspective estimation). No grid positions yet — those require axis-aligned lines which we won't have until after Phase 3 correction.

**Key insight:** LSD fragments grid lines at every intersection and drawing crossing, producing many short segments (8–30px). This is fine — we don't need long lines. Each fragment carries an angle, and hundreds of fragments give a very robust angle estimate. For perspective-distorted photos, the spatial variation in fragment angles across the image directly encodes the perspective transform.

**Known constraint:** Both fixtures use the same graph paper format: 36×58 fine grid cells at 16px design pitch. This constrains the expected grid period (in image pixels) and validates detection results, though the actual pixel period varies by scan/photo resolution.

**Build: `core/grid.py`**

```python
@dataclass
class LineSegment:
    x1: float; y1: float
    x2: float; y2: float
    angle: float       # degrees from horizontal, [0, 180)
    weight: float      # lsd_width * perpendicular_contrast

@dataclass
class GridGeometry:
    h_angle: float             # dominant horizontal angle (degrees)
    v_angle: float             # dominant vertical angle (degrees)
    h_period: float            # estimated grid period along H direction (pixels)
    v_period: float            # estimated grid period along V direction (pixels)
    h_fragments: list[LineSegment]
    v_fragments: list[LineSegment]
    angle_spatial_model: dict  # spatially-varying angle data for perspective estimation

def detect_fragments(image, min_length=5) -> list[LineSegment]
    """Run LSD, compute weight per fragment (lsd_width * perpendicular_contrast).
    Returns all fragments above min_length."""

def cluster_by_angle(fragments) -> tuple[list[LineSegment], list[LineSegment]]
    """Separate into H/V groups via length-weighted angle histogram.
    Find two peaks (~90° apart), assign each fragment to nearest peak,
    reject outliers >20° from either peak. Returns (horizontal, vertical)."""

def estimate_dominant_angles(h_fragments, v_fragments) -> tuple[float, float]
    """Length-weighted median angle for each group. Returns (h_angle, v_angle)."""

def estimate_period(fragments, is_horizontal, image_dim) -> float
    """Cluster fragment positions (y for H, x for V), compute median spacing
    between clusters. Returns rough grid period in pixels."""

def estimate_spatial_angles(fragments, image_shape, n_zones=3) -> dict
    """Divide image into zones, compute dominant angle per zone.
    Spatial variation reveals perspective distortion.
    Returns dict with per-zone angles and overall model."""

def analyze_grid_geometry(image) -> GridGeometry
    """Full Phase 2 pipeline: detect → cluster → estimate angles/period/spatial."""
```

**Wire into `cli/grid_detect.py`:**

Partial implementation — detects fragments, reports angles and period, writes debug image. No cell building, no correction, no JSON output yet.

**Checkpoint:** Run against wizard scan with `--debug-image debug_wizard.png`. The debug image shows:
- H fragments in red, V fragments in blue, overlaid on the original
- Reports dominant angles (should be near 0° and 90° for a straight scan)
- Reports grid period (should be ~48px based on prototyping)
- Reports spatial angle consistency (low variation = rotation only)

Run against dino photo — fragments detected at non-axis-aligned angles. Debug image shows:
- Fragments follow the grid lines but at angles reflecting the perspective skew
- Reports dominant angles (offset from 0°/90°)
- Spatial angle model shows convergence (angles differ top vs bottom)
- Period estimate may be less reliable (perspective makes it non-uniform)

**Key insight validated:** LSD fragmentation doesn't matter for angle estimation. 300+ horizontal fragments all pointing at ~2.3° gives a robust rotation estimate. Spatial variation in those angles gives perspective information.

---

## Phase 3: Grid Detection — Geometric Correction + Grid Position Finding

**Goal:** Use Phase 2's angle/perspective data to correct the image, then find precise grid positions on the corrected (axis-aligned) image using projection profiles.

**Build: `core/correction.py`**

```python
def assess_distortion(geometry: GridGeometry) -> tuple[str, dict]
    """Returns ('none' | 'rotation' | 'perspective', stats_dict).
    Uses spatial angle model: low variation = rotation, high = perspective."""

def compute_rotation(geometry: GridGeometry) -> float
    """Dominant horizontal angle (should be near 0° for a straight image)."""

def compute_perspective_transform(geometry, image_shape) -> np.ndarray
    """Compute homography from spatial angle model + fragment positions.
    Uses overdetermined system from all grid intersections."""

def apply_correction(image, transform_type, transform_matrix) -> np.ndarray
    """Apply affine rotation or perspective warp. Crops to grid boundary."""

def compute_residual(corrected_intersections, expected_grid) -> float
    """Mean pixel deviation from perfect regular grid after correction."""
```

**Build: Add grid position finding to `core/grid.py`**

After correction, grid lines are axis-aligned and projection profiles work:

```python
def find_grid_positions(corrected_image, expected_rows=58, expected_cols=36) -> GridDetectionResult
    """Run on corrected image where grid lines are axis-aligned.
    Uses projection profiles (row/column intensity sums) to find grid lines:
    1. Build profiles from quiet image strips (median across perpendicular axis)
    2. Autocorrelation to find dominant period
    3. Peak detection at expected period intervals
    4. Classify heavy vs fine lines by peak amplitude
    Returns positions, periods, and heavy line indices."""
```

**Modify `cli/grid_detect.py`:**

Add `--correct`, `--corrected-image`, `--max-rotation` flags. Pipeline becomes:
1. Analyze grid geometry (Phase 2: fragments → angles/period)
2. Assess and apply correction
3. Find precise grid positions on corrected image (projection profiles)
4. Continue to cell building (Phase 4)

**Checkpoint — wizard scan:** Should detect minimal distortion (< 1° rotation), apply trivial correction or skip. `corrected.png` looks essentially identical to the original. Grid positions found via projection profiles match visible grid lines. Report: `"Correction: rotation, 0.3° clockwise, residual 0.2px"`

**Checkpoint — dino photo:** Should detect perspective skew (lines converging). Produces `corrected.png` where:
- Grid lines are horizontal/vertical
- The tablecloth and table edges are cropped away
- The paper fills the frame
- Cells are rectangular and uniformly sized
- Grid positions found cleanly on the corrected image
- Report includes rotation angle, convergence correction, and residual error

**Synthetic test cases:** Use OpenCV `cv2.warpPerspective()` to apply known transforms to the wizard scan (5° rotation, moderate perspective, combined). Verify the tool recovers the parameters within tolerance and the corrected image matches the original.

---

## Phase 4: Grid Detection — Cell Building & JSON Output

**Goal:** From detected grid lines, compute cell boundaries, classify occupancy, write `grid.json`. Completes `sprite-grid-detect`.

**Build: Add to `core/grid.py`**

```python
def build_cells(h_positions, v_positions) -> list[Cell]
    """Create cell rectangles from grid line positions."""

def classify_occupancy(image, cells) -> list[Cell]
    """Mark cells as occupied/empty based on pixel variance.
    Computes grayscale std dev per cell. Cells significantly above
    the median (empty cell baseline) are marked occupied."""

def to_grid_json(source, corrected_image, correction_stats,
                 h_positions, v_positions, cells) -> dict
    """Build the grid.json structure."""
```

```python
@dataclass
class Cell:
    row: int; col: int
    x: int; y: int
    width: int; height: int
    occupied: bool
```

**Complete `cli/grid_detect.py`:**

Full pipeline: correct → detect lines → build cells → classify → write JSON + corrected image.

**Checkpoint — wizard scan:**

`grid.json` should contain:
- Row 0: col 0 occupied (idle). Cols 1–5 empty.
- Row 1: cols 0–3 occupied (walk). Cols 4–5 empty.
- Row 2: cols 0–1 occupied (jump). Cols 2–5 empty.
- Row 3: cols 0–1 occupied (fall). Cols 2–5 empty.
- Row 4: col 0 occupied (climb). Cols 1–5 empty.

Debug image shows grid overlay with green-highlighted occupied cells.

**Checkpoint — dino photo:**

Same structure validation. Additionally verify that:
- Stray pencil marks on the left margin are outside the grid boundary (cropped during correction)
- The "Character Sprite Sheet" title text and row labels don't cause false occupied cells
- Row 0 (idle): 3 occupied cells (the dino has 3 idle frames)
- Row 1 (walk): 4 occupied
- Row 2 (jump): 2 occupied
- Row 3 (fall): 2 occupied
- Row 4 (climb): 2 occupied

Manually edit `grid.json` — change an occupancy flag, adjust a cell boundary by a few pixels — to verify the format is hand-editable and downstream tools respect the edits.

---

## Phase 5: Extraction

**Goal:** Complete `sprite-extract`.

**Build: `cli/extract.py`**

- Parse `grid.json`, load corrected image
- For each occupied cell, crop with optional padding inset and bleed expansion
- Map rows to state names via `--rows`
- Number frames per state, 0-indexed
- Save PNGs, write `cells.json`

Straightforward file I/O and array slicing. The heavy lifting was in grid detection.

**Checkpoint — both fixtures:**

```bash
sprite-grid-detect -i wizard_scan.jpg --debug-image debug.png
sprite-extract -i corrected.png -g grid.json --rows idle,walk,jump,fall,climb --padding 4 --bleed 6
```

Wizard `cells/` should contain 10 PNGs: `idle_0`, `walk_0..3`, `jump_0..1`, `fall_0..1`, `climb_0`.
Dino `cells/` should contain 13 PNGs: `idle_0..2`, `walk_0..3`, `jump_0..1`, `fall_0..1`, `climb_0..1`.

Each PNG is a cropped cell with graph paper background intact (cleaning is next). Open in image viewer — wizard drawings should be cleanly cropped, centered within their cells. The `--padding 4` should trim the heavy grid lines from the cell edges.

`cells.json` should list every extracted frame with correct state name, frame number, and source rectangle.

---

## Phase 6: Cleaning — Background Removal

**Goal:** Build `sprite-clean` with color-based background removal. Grid line removal comes in Phase 7.

**Build: `core/background.py`**

```python
def remove_background(image_rgba, bg_color, tolerance, color_space='hsl') -> np.ndarray
    """Set background-colored pixels to transparent.
    Returns RGBA image with alpha mask applied."""

def detect_bg_color(image, method='corners') -> tuple[int, int, int]
    """Sample corners to find dominant background color."""

def remove_small_components(alpha, min_size) -> np.ndarray
    """Connected component filter. Remove blobs smaller than min_size."""

def erode_alpha(alpha, radius) -> np.ndarray
    """Morphological erosion on alpha channel."""

def feather_alpha(alpha, radius) -> np.ndarray
    """Gaussian blur on alpha edges for soft blending."""
```

**Build: `cli/clean.py`**

Wire up the pipeline: load PNGs from input dir → detect BG → remove BG → cleanup blobs → erode → feather → save. Support `--files` for per-file reruns, `--debug-image` for before/after.

**Checkpoint:** Run on wizard cells and dino cells separately. Cleaned PNGs should show drawings on transparency. Paper texture gone. Heavy grid lines within cells partially removed (they're similar to background color). Fine grid lines still partially visible — that's expected, dedicated line removal is next phase.

**Tuning session:** Try `--bg-tolerance` values from 20 to 50 on the wizard scan. Document the sweet spot where paper is removed but the wizard's light pink and yellow aren't eaten. Try the same on the dino — the green pencil is more saturated and should tolerate higher settings.

The dino photo likely needs `--white-balance` to correct the warm indoor lighting cast before background removal works well. Validate this.

---

## Phase 7: Cleaning — Grid Line Removal

**Goal:** Add fine grid line removal to `sprite-clean`.

**Build: `core/morphology.py`**

```python
def detect_fine_grid_lines(image, line_width='auto') -> np.ndarray
    """Find thin horizontal and vertical structures using morphological opening.
    Returns binary mask of detected grid lines."""

def auto_detect_line_width(image) -> int
    """Estimate grid line width by running opening with increasing kernel sizes
    and finding the width that captures the most regular-interval structures."""

def remove_lines_and_inpaint(image, line_mask) -> np.ndarray
    """Set line pixels to transparent or inpaint with surrounding colors.
    Uses cv2.inpaint() with Telea method for lines that cross through drawings."""
```

**Algorithm detail:**
1. Convert to grayscale
2. Create horizontal kernel (1 × W) and vertical kernel (H × 1) where W, H = estimated line width × 3
3. `cv2.morphologyEx(MORPH_OPEN)` with each kernel — isolates thin structures
4. Threshold → binary mask of grid lines
5. Where mask overlaps non-transparent pixels (the drawing): `cv2.inpaint()` to fill
6. Where mask overlaps background: handled by background removal step

**Modify `cli/clean.py`:** Insert grid line removal as step 2 (after white balance, before background removal). Controlled by `--remove-grid-lines` flag.

**Checkpoint:** Run the full cleaning pipeline on both fixtures. Fine grid lines within the wizard's body should be gone. The wizard's actual drawn lines (thick pencil strokes) should be preserved. Same for the dino.

Compare with and without `--remove-grid-lines` to verify the flag works correctly and that line removal doesn't damage the art.

**Key risk:** Grid lines that cross through the drawing leave thin gaps after removal. The inpainting step must fill these smoothly. Test on the wizard's walk frames where grid lines cross the blue tunic area — inpainting should blend convincingly at 64×128 output resolution (small enough that minor artifacts disappear after downscaling).

---

## Phase 8: Normalize

**Goal:** Complete `sprite-normalize`.

**Build: `core/transform.py`**

```python
def find_art_bounds(image_rgba) -> tuple[int, int, int, int]
    """Bounding box of non-transparent pixels. Returns (x, y, w, h)."""

def fit_art_to_frame(image_rgba, target_w, target_h, fit, anchor, margin) -> np.ndarray
    """Crop to art bounds, scale to fit target frame, anchor within frame.
    Returns RGBA image at exactly target_w × target_h."""

def compute_scale_factor(art_w, art_h, target_w, target_h, fit, margin) -> float
    """Report the scale factor that would be applied."""
```

**Build: `cli/normalize.py`**

Process all PNGs in input dir. Print scale factor report with consistency warnings.

**Checkpoint:** Run pipeline through normalize on both fixtures. All output PNGs are exactly 64×128. Characters are bottom-anchored. Walk frames for each character have consistent scale (wizard is roughly the same size across all four walk frames; dino likewise).

Scale factor report should look reasonable:
```
idle_0.png:  scale=0.42, art_size=148×310
walk_0.png:  scale=0.45, art_size=138×284
...
jump_0.png:  scale=0.38, art_size=165×340  ⚠ 14% below median scale
```

The jump frame is drawn larger on the wizard scan, so a different scale factor is expected and correct.

---

## Phase 9: Assemble

**Goal:** Complete `sprite-assemble`. Full pipeline end-to-end.

**Build: `cli/assemble.py`**

- Read `cells.json` for state/frame metadata
- Read normalized PNGs
- Handle `--duplicate` (cycle frames to reach target count)
- Composite grid using Pillow (`Image.new` + `Image.paste`)
- Generate manifest JSON
- Save both files

**Checkpoint — wizard end-to-end:**

```bash
sprite-grid-detect -i wizard_scan.jpg
sprite-extract -i corrected.png -g grid.json --rows idle,walk,jump,fall,climb --padding 4 --bleed 6
sprite-clean --input-dir cells/ --output-dir cleaned/ --remove-grid-lines --bg-tolerance 35 --erode 1
sprite-normalize --input-dir cleaned/ --output-dir normalized/ --width 64 --height 128 --anchor bottom
sprite-assemble --input-dir normalized/ --meta cells.json --output wizard.png --manifest wizard.manifest.json \
  --duplicate idle=4,climb=2
```

- `wizard.png` is 384×640 (6 cols × 5 rows × 64×128)
- `wizard.manifest.json` matches engine format exactly
- Idle row has 4 copies of the same frame
- Walk row has 4 distinct frames
- Opening the PNG shows the wizard frames on transparent background in correct grid positions

**Checkpoint — dino end-to-end:**

Same pipeline. Dino has more frames (3 idle, 2 climb), so the output differs slightly. Verify manifest reflects actual frame counts.

**Stretch test:** Copy `wizard.png` + `wizard.manifest.json` into `platformer/public/assets/sprites/` as `player.png` + `player.manifest.json`. Run the platformer engine. The wizard should render and animate correctly.

---

## Phase 10: Convenience & Polish

1. **`sprite-pipeline` wrapper:**
   ```bash
   sprite-pipeline -i scan.jpg --rows idle,walk,jump,fall,climb \
     --output-name player --output-dir output/
   ```
   Runs all five steps with sensible defaults into a single output directory. Intermediate files go into subdirectories within the output dir.

2. **Preview HTML:**
   `sprite-assemble --preview preview.html` generates a standalone HTML page showing the sprite sheet with per-state animation playback at configured FPS. Quick visual QA.

3. **Robustness:**
   - Downsample very large images (> 4000px) for line detection, process at full res for extraction
   - Better error messages: "No grid lines detected. Is this graph paper? Try --line-threshold lower" 
   - Input validation on all flags (file exists, values in range, etc.)

4. **Documentation:**
   - `tools/README.md` with quick start, full pipeline example, parameter tuning guide
   - Per-flag documentation in `--help` output

---

## Test Strategy

### Two primary fixtures
Every phase checkpoint tests against both the wizard scan (clean, straight) and the dino photo (skewed, noisy, color cast). If it works on both, it handles the expected input range.

### Synthetic test cases
For Phase 3 (correction): warp the wizard scan by known rotations and perspective transforms using OpenCV. Verify recovery within tolerance. This is the only phase that benefits from synthetic data — all others test better against real drawings.

### Unit tests
`core/` functions are pure and testable:
- `test_grid.py` — known line positions → verify cell computation, regularization
- `test_correction.py` — lines with known angle distributions → verify distortion classification
- `test_background.py` — synthetic image with known BG color → verify mask
- `test_transform.py` — known art bounds → verify scale factor, anchor position

### Visual inspection
Every `--debug-image` output is a test artifact. Save them during development. When tuning parameters, the debug images are the ground truth for "did this work?"

---

## Risk Log

| Risk | Impact | Mitigation |
|------|--------|------------|
| Can't distinguish heavy vs fine grid lines | Grid detection fails completely | Phase 2 doesn't need this distinction (just angles). Phase 3 uses projection profiles on corrected images where amplitude separates heavy from fine. Fallback: heavy = every Nth fine line. |
| Perspective correction quality on extreme angles | Warped output, stretched pixels | Validate residual error. Warn user if > 3px. Document "photograph as close to overhead as possible." |
| Background removal eats light-colored art | Wizard's pink hat edges, yellow feet disappear | HSL distance (not RGB). Expose `--bg-tolerance` for tuning. Per-file `--files` reruns for problem frames. |
| Grid line removal damages art | Inpainting artifacts visible in output | Lines are thin (1–2px) at scan resolution. At 64×128 output, artifacts are subpixel. Validate on both fixtures. |
| Occupancy classification wrong | Empty cells extracted, or occupied cells skipped | Conservative threshold + `grid.json` is hand-editable. User inspects and fixes. |
| Large phone photos slow to process | Multi-second delay per step | Downsample for detection passes. Full-res only for final extraction crop. |

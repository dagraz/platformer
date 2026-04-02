import { TileMap } from '../engine/TileMap';
import {
  TileType,
  TILE_SIZE,
  SCREEN_WIDTH_TILES,
  SCREEN_HEIGHT_TILES,
} from '../engine/types';

const TILE_COLORS: Record<TileType, string> = {
  empty:    '#87CEEB', // sky blue
  solid:    '#8B6914', // brown
  platform: '#999999', // gray
  ladder:   '#228B22', // green
};

/** Cache of loaded tile images keyed by sprite name. */
const tileImageCache: Record<string, HTMLImageElement | null> = {};
let tileImagesLoaded = false;

/** Get a cached tile image by sprite name, or null if unavailable. */
export function getTileImage(spriteName: string): HTMLImageElement | null {
  return tileImageCache[spriteName] ?? null;
}

/**
 * Preload tile images from public/assets/tiles/.
 * Call once at startup. Missing images are silently skipped (fallback to color).
 */
export function loadTileImages(spriteNames: string[]): Promise<void> {
  const promises = spriteNames.map(name => {
    if (tileImageCache[name] !== undefined) return Promise.resolve();
    return new Promise<void>((resolve) => {
      const img = new Image();
      img.onload = () => {
        tileImageCache[name] = img;
        resolve();
      };
      img.onerror = () => {
        tileImageCache[name] = null; // mark as unavailable
        resolve();
      };
      img.src = `/assets/tiles/${name}.png`;
    });
  });
  return Promise.all(promises).then(() => { tileImagesLoaded = true; });
}

export function renderTiles(
  ctx: CanvasRenderingContext2D,
  tileMap: TileMap,
  screenKey: string,
  offsetX: number,
  offsetY: number,
): void {
  const tiles = tileMap.getTilesInScreen(screenKey);
  if (!tiles) return;

  const level = tileMap.getLevel();

  for (let row = 0; row < SCREEN_HEIGHT_TILES; row++) {
    for (let col = 0; col < SCREEN_WIDTH_TILES; col++) {
      const tileId = tiles[row][col];
      const tileDef = level.tileTypes[tileId];
      const tileType = tileDef?.type ?? 'empty';
      const spriteName = tileDef?.sprite;

      const dx = offsetX + col * TILE_SIZE;
      const dy = offsetY + row * TILE_SIZE;

      // Empty tiles: sky image or flat color, then optional decorative sprite on top
      if (tileType === 'empty') {
        const skyImg = tileImageCache['sky'];
        if (skyImg) {
          ctx.drawImage(skyImg, dx, dy, TILE_SIZE, TILE_SIZE);
        } else {
          ctx.fillStyle = TILE_COLORS.empty;
          ctx.fillRect(dx, dy, TILE_SIZE, TILE_SIZE);
        }
        // Draw decorative sprite over sky (e.g. grass tufts)
        const decoImg = spriteName && spriteName !== 'sky' ? tileImageCache[spriteName] : null;
        if (decoImg) {
          ctx.drawImage(decoImg, dx, dy, TILE_SIZE, TILE_SIZE);
        }
        continue;
      }

      // Try to draw tile image
      const img = spriteName ? tileImageCache[spriteName] : null;
      if (img) {
        ctx.drawImage(img, dx, dy, TILE_SIZE, TILE_SIZE);
      } else {
        // Fallback to colored rectangles
        let color = TILE_COLORS[tileType];
        if (tileType === 'solid' && spriteName === 'ground_fill') {
          color = '#6B4400';
        }
        ctx.fillStyle = color;
        ctx.fillRect(dx, dy, TILE_SIZE, TILE_SIZE);

        // Subtle grid lines on fallback tiles
        ctx.strokeStyle = 'rgba(0,0,0,0.15)';
        ctx.strokeRect(dx, dy, TILE_SIZE, TILE_SIZE);
      }
    }
  }
}

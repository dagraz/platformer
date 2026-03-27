import { TileMap } from '../engine/TileMap';
import {
  TileType,
  TILE_SIZE,
  SCREEN_WIDTH_TILES,
  SCREEN_HEIGHT_TILES,
} from '../engine/types';

const TILE_COLORS: Record<TileType, string> = {
  empty:    '#87CEEB', // sky blue
  solid:    '#8B6914', // brown (ground_top uses same for now)
  platform: '#999999', // gray
  ladder:   '#228B22', // green
};

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

      // Differentiate ground_top vs ground_fill visually
      let color = TILE_COLORS[tileType];
      if (tileType === 'solid' && tileDef?.sprite === 'ground_fill') {
        color = '#6B4400'; // darker brown for fill
      }

      ctx.fillStyle = color;
      ctx.fillRect(
        offsetX + col * TILE_SIZE,
        offsetY + row * TILE_SIZE,
        TILE_SIZE,
        TILE_SIZE,
      );

      // Draw subtle grid lines
      if (tileType !== 'empty') {
        ctx.strokeStyle = 'rgba(0,0,0,0.15)';
        ctx.strokeRect(
          offsetX + col * TILE_SIZE,
          offsetY + row * TILE_SIZE,
          TILE_SIZE,
          TILE_SIZE,
        );
      }
    }
  }
}

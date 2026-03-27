import {
  LevelData,
  TileDefinition,
  TILE_SIZE,
  SCREEN_WIDTH_TILES,
  SCREEN_HEIGHT_TILES,
} from './types';

const EMPTY_TILE: TileDefinition = { type: 'empty', sprite: 'sky' };

export class TileMap {
  private level: LevelData | null = null;

  load(data: LevelData): void {
    this.level = data;
  }

  getLevel(): LevelData {
    if (!this.level) throw new Error('No level loaded');
    return this.level;
  }

  /** Returns the screen key ("col,row") for a world pixel position. */
  getScreenKey(worldX: number, worldY: number): string {
    const col = Math.floor(worldX / (SCREEN_WIDTH_TILES * TILE_SIZE));
    const row = Math.floor(worldY / (SCREEN_HEIGHT_TILES * TILE_SIZE));
    return `${col},${row}`;
  }

  /** Returns the top-left world pixel origin of a screen. */
  getScreenOrigin(screenKey: string): { worldX: number; worldY: number } {
    const [col, row] = screenKey.split(',').map(Number);
    return {
      worldX: col * SCREEN_WIDTH_TILES * TILE_SIZE,
      worldY: row * SCREEN_HEIGHT_TILES * TILE_SIZE,
    };
  }

  /** Returns the tile definition at a world pixel position. */
  getTileAt(worldX: number, worldY: number): TileDefinition {
    if (!this.level) return EMPTY_TILE;

    const screenKey = this.getScreenKey(worldX, worldY);
    const screen = this.level.screens[screenKey];
    if (!screen) return EMPTY_TILE;

    const origin = this.getScreenOrigin(screenKey);
    const tileCol = Math.floor((worldX - origin.worldX) / TILE_SIZE);
    const tileRow = Math.floor((worldY - origin.worldY) / TILE_SIZE);

    if (tileRow < 0 || tileRow >= SCREEN_HEIGHT_TILES) return EMPTY_TILE;
    if (tileCol < 0 || tileCol >= SCREEN_WIDTH_TILES) return EMPTY_TILE;

    const tileId = screen.tiles[tileRow][tileCol];
    return this.level.tileTypes[tileId] ?? EMPTY_TILE;
  }

  /** Returns the raw tile grid for a screen. */
  getTilesInScreen(screenKey: string): number[][] | null {
    if (!this.level) return null;
    return this.level.screens[screenKey]?.tiles ?? null;
  }

  /** Checks if a screen exists in the level. */
  screenExists(screenKey: string): boolean {
    if (!this.level) return false;
    return screenKey in this.level.screens;
  }
}

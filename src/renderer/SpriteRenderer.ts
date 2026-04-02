import { SpriteSheet } from '../engine/SpriteSheet';
import { PlayerState } from '../engine/types';

/**
 * Draws animated sprites from a sprite sheet onto a canvas.
 * Lives in the renderer layer — may use Canvas/DOM APIs.
 */
export class SpriteRenderer {
  private readonly sheet: SpriteSheet;
  private readonly image: HTMLImageElement;
  private readonly npcSheets: Map<string, { sheet: SpriteSheet; image: HTMLImageElement }> = new Map();
  private readonly collectibleSheets: Map<string, { sheet: SpriteSheet; image: HTMLImageElement }> = new Map();

  constructor(sheet: SpriteSheet, image: HTMLImageElement) {
    this.sheet = sheet;
    this.image = image;
  }

  /** Register an NPC sprite sheet by sprite name. */
  addNpcSheet(spriteName: string, sheet: SpriteSheet, image: HTMLImageElement): void {
    this.npcSheets.set(spriteName, { sheet, image });
  }

  /** Register a collectible sprite sheet by sprite name. */
  addCollectibleSheet(spriteName: string, sheet: SpriteSheet, image: HTMLImageElement): void {
    this.collectibleSheets.set(spriteName, { sheet, image });
  }

  /**
   * Draw the player sprite at (dx, dy) on the canvas.
   * Flips horizontally when facing === 'left'.
   */
  drawPlayer(
    ctx: CanvasRenderingContext2D,
    state: PlayerState,
    elapsedMs: number,
    dx: number,
    dy: number,
    facing: 'left' | 'right',
  ): void {
    this.drawSprite(ctx, this.sheet, this.image, state, elapsedMs, dx, dy, facing);
  }

  /**
   * Draw an NPC sprite. Falls back to idle state if the NPC's behavior
   * state isn't in the sheet. Returns false if no sheet is registered
   * for this sprite name (caller should draw a fallback).
   */
  drawNpc(
    ctx: CanvasRenderingContext2D,
    spriteName: string,
    behavior: 'static' | 'pace' | 'face_player',
    elapsedMs: number,
    dx: number,
    dy: number,
    facing: 'left' | 'right',
  ): boolean {
    const entry = this.npcSheets.get(spriteName);
    if (!entry) return false;

    // Map NPC behavior to animation state
    const state: PlayerState = behavior === 'pace' ? 'walk' : 'idle';
    this.drawSprite(ctx, entry.sheet, entry.image, state, elapsedMs, dx, dy, facing);
    return true;
  }

  /**
   * Draw an animated collectible. Returns false if no sheet is registered.
   */
  drawCollectible(
    ctx: CanvasRenderingContext2D,
    spriteName: string,
    elapsedMs: number,
    dx: number,
    dy: number,
    width: number,
    height: number,
  ): boolean {
    const entry = this.collectibleSheets.get(spriteName);
    if (!entry) return false;

    const { sx, sy, sw, sh } = entry.sheet.getFrame('idle', elapsedMs);
    ctx.drawImage(entry.image, sx, sy, sw, sh, dx, dy, width, height);
    return true;
  }

  private drawSprite(
    ctx: CanvasRenderingContext2D,
    sheet: SpriteSheet,
    image: HTMLImageElement,
    state: PlayerState,
    elapsedMs: number,
    dx: number,
    dy: number,
    facing: 'left' | 'right',
  ): void {
    const { sx, sy, sw, sh } = sheet.getFrame(state, elapsedMs);

    if (facing === 'left') {
      ctx.save();
      ctx.translate(dx + sw, dy);
      ctx.scale(-1, 1);
      ctx.drawImage(image, sx, sy, sw, sh, 0, 0, sw, sh);
      ctx.restore();
    } else {
      ctx.drawImage(image, sx, sy, sw, sh, dx, dy, sw, sh);
    }
  }
}

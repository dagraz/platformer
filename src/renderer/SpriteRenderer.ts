import { SpriteSheet } from '../engine/SpriteSheet';
import { PlayerState } from '../engine/types';

/**
 * Draws animated sprites from a sprite sheet onto a canvas.
 * Lives in the renderer layer — may use Canvas/DOM APIs.
 */
export class SpriteRenderer {
  private readonly sheet: SpriteSheet;
  private readonly image: HTMLImageElement;

  constructor(sheet: SpriteSheet, image: HTMLImageElement) {
    this.sheet = sheet;
    this.image = image;
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
    const { sx, sy, sw, sh } = this.sheet.getFrame(state, elapsedMs);

    if (facing === 'left') {
      ctx.save();
      ctx.translate(dx + sw, dy);
      ctx.scale(-1, 1);
      ctx.drawImage(this.image, sx, sy, sw, sh, 0, 0, sw, sh);
      ctx.restore();
    } else {
      ctx.drawImage(this.image, sx, sy, sw, sh, dx, dy, sw, sh);
    }
  }
}

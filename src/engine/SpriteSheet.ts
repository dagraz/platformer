import { SpriteManifest, PlayerState } from './types';

/**
 * Pure data class for a sprite sheet. Computes which source rectangle
 * to sample for a given animation state and elapsed time.
 * No DOM or Canvas imports — this belongs in the engine layer.
 */
export class SpriteSheet {
  readonly frameWidth: number;
  readonly frameHeight: number;
  private readonly states: SpriteManifest['states'];

  constructor(manifest: SpriteManifest) {
    this.frameWidth = manifest.frameWidth;
    this.frameHeight = manifest.frameHeight;
    this.states = manifest.states;
  }

  /**
   * Returns the source rectangle {sx, sy, sw, sh} for the current frame.
   * Falls back to 'idle' row 0 / frame 0 if the state is missing.
   */
  getFrame(state: PlayerState, elapsedMs: number): { sx: number; sy: number; sw: number; sh: number } {
    // 'land' uses the last frame of the 'fall' row
    if (state === 'land') {
      const fallInfo = this.states['fall'];
      if (fallInfo && fallInfo.frames > 1) {
        return {
          sx: (fallInfo.frames - 1) * this.frameWidth,
          sy: fallInfo.row * this.frameHeight,
          sw: this.frameWidth,
          sh: this.frameHeight,
        };
      }
    }

    const info = this.states[state] ?? this.states['idle'];
    if (!info) {
      // Absolute fallback: top-left frame
      return { sx: 0, sy: 0, sw: this.frameWidth, sh: this.frameHeight };
    }

    const frameIndex = info.frames > 1
      ? Math.floor(elapsedMs * info.fps / 1000) % info.frames
      : 0;

    return {
      sx: frameIndex * this.frameWidth,
      sy: info.row * this.frameHeight,
      sw: this.frameWidth,
      sh: this.frameHeight,
    };
  }
}

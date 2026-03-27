import {
  CameraState,
  Player,
  VIEWPORT_WIDTH,
  VIEWPORT_HEIGHT,
  DEBUG,
} from './types';
import { TileMap } from './TileMap';

const TRANSITION_FRAMES = 18; // ~300ms at 60 Hz
const TRANSITION_STEP = 1 / TRANSITION_FRAMES;

/**
 * Detect screen boundary crossings and manage screen slide transitions.
 * Returns updated camera state and whether input should be locked.
 */
export function updateCamera(
  camera: CameraState,
  player: Player,
  tileMap: TileMap,
): { camera: CameraState; inputLocked: boolean } {
  // ── During a transition, animate the slide ──────
  if (camera.targetScreen !== null) {
    const progress = Math.min(camera.transitionProgress + TRANSITION_STEP, 1);

    const currentOrigin = tileMap.getScreenOrigin(camera.currentScreen);
    const targetOrigin = tileMap.getScreenOrigin(camera.targetScreen);

    const dx = targetOrigin.worldX - currentOrigin.worldX;
    const dy = targetOrigin.worldY - currentOrigin.worldY;

    // Slide direction: offset moves from 0 toward ±viewport size
    const dirX = dx > 0 ? 1 : dx < 0 ? -1 : 0;
    const dirY = dy > 0 ? 1 : dy < 0 ? -1 : 0;

    const offsetX = dirX * VIEWPORT_WIDTH * progress;
    const offsetY = dirY * VIEWPORT_HEIGHT * progress;

    if (progress >= 1) {
      // Transition complete
      if (DEBUG) {
        console.log(`[Camera] transition complete → ${camera.targetScreen}`);
      }
      return {
        camera: {
          currentScreen: camera.targetScreen,
          targetScreen: null,
          transitionProgress: 0,
          offsetX: 0,
          offsetY: 0,
        },
        inputLocked: false,
      };
    }

    return {
      camera: {
        ...camera,
        transitionProgress: progress,
        offsetX,
        offsetY,
      },
      inputLocked: true,
    };
  }

  // ── Check if player has crossed a screen boundary ──
  const playerScreen = tileMap.getScreenKey(
    player.worldX + player.width / 2,
    player.worldY + player.height / 2,
  );

  if (playerScreen !== camera.currentScreen && tileMap.screenExists(playerScreen)) {
    if (DEBUG) {
      console.log(`[Camera] transition: ${camera.currentScreen} → ${playerScreen}`);
    }
    return {
      camera: {
        ...camera,
        targetScreen: playerScreen,
        transitionProgress: 0,
        offsetX: 0,
        offsetY: 0,
      },
      inputLocked: true,
    };
  }

  return { camera, inputLocked: false };
}

import { TileMap } from '../engine/TileMap';
import { CameraState, VIEWPORT_WIDTH, VIEWPORT_HEIGHT } from '../engine/types';
import { renderTiles } from './TileRenderer';

export function render(
  ctx: CanvasRenderingContext2D,
  tileMap: TileMap,
  camera: CameraState,
): void {
  // Clear
  ctx.clearRect(0, 0, VIEWPORT_WIDTH, VIEWPORT_HEIGHT);

  // Draw the current screen
  renderTiles(ctx, tileMap, camera.currentScreen, -camera.offsetX, -camera.offsetY);

  // During a transition, also draw the target screen
  if (camera.targetScreen) {
    const origin = tileMap.getScreenOrigin(camera.currentScreen);
    const target = tileMap.getScreenOrigin(camera.targetScreen);
    const dx = (target.worldX - origin.worldX) > 0 ? VIEWPORT_WIDTH : (target.worldX - origin.worldX) < 0 ? -VIEWPORT_WIDTH : 0;
    const dy = (target.worldY - origin.worldY) > 0 ? VIEWPORT_HEIGHT : (target.worldY - origin.worldY) < 0 ? -VIEWPORT_HEIGHT : 0;

    renderTiles(
      ctx,
      tileMap,
      camera.targetScreen,
      dx - camera.offsetX,
      dy - camera.offsetY,
    );
  }
}

import { TileMap } from '../engine/TileMap';
import { CameraState, Player, VIEWPORT_WIDTH, VIEWPORT_HEIGHT } from '../engine/types';
import { renderTiles } from './TileRenderer';
import { SpriteRenderer } from './SpriteRenderer';

export function render(
  ctx: CanvasRenderingContext2D,
  tileMap: TileMap,
  camera: CameraState,
  player?: Player,
  spriteRenderer?: SpriteRenderer,
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

  // Draw player
  if (player) {
    const screenOrigin = tileMap.getScreenOrigin(camera.currentScreen);
    const px = player.worldX - screenOrigin.worldX - camera.offsetX;
    const py = player.worldY - screenOrigin.worldY - camera.offsetY;

    if (spriteRenderer) {
      spriteRenderer.drawPlayer(
        ctx,
        player.state,
        player.animationElapsedMs,
        px,
        py,
        player.facing,
      );
    } else {
      // Fallback: red rectangle if sprites not loaded
      ctx.fillStyle = '#E74C3C';
      ctx.fillRect(px, py, player.width, player.height);
    }
  }
}

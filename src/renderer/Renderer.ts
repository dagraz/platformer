import { TileMap } from '../engine/TileMap';
import { CameraState, Player, VIEWPORT_WIDTH, VIEWPORT_HEIGHT } from '../engine/types';
import { renderTiles } from './TileRenderer';

export function render(
  ctx: CanvasRenderingContext2D,
  tileMap: TileMap,
  camera: CameraState,
  player?: Player,
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

    ctx.fillStyle = '#E74C3C'; // red rectangle
    ctx.fillRect(px, py, player.width, player.height);

    // Direction indicator (small triangle)
    ctx.fillStyle = '#C0392B';
    const cx = player.facing === 'right' ? px + player.width - 8 : px + 8;
    const cy = py + 20;
    ctx.beginPath();
    if (player.facing === 'right') {
      ctx.moveTo(cx, cy - 6);
      ctx.lineTo(cx + 10, cy);
      ctx.lineTo(cx, cy + 6);
    } else {
      ctx.moveTo(cx, cy - 6);
      ctx.lineTo(cx - 10, cy);
      ctx.lineTo(cx, cy + 6);
    }
    ctx.fill();
  }
}

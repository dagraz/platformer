import { TileMap } from '../engine/TileMap';
import {
  CameraState,
  Collectible,
  MovingPlatform,
  NPC,
  Player,
  TILE_SIZE,
  VIEWPORT_WIDTH,
  VIEWPORT_HEIGHT,
} from '../engine/types';
import { renderTiles, getTileImage } from './TileRenderer';
import { SpriteRenderer } from './SpriteRenderer';

export interface RenderEntities {
  collectibles: Collectible[];
  npcs: NPC[];
  movingPlatforms: MovingPlatform[];
  score: number;
}

export function render(
  ctx: CanvasRenderingContext2D,
  tileMap: TileMap,
  camera: CameraState,
  player?: Player,
  spriteRenderer?: SpriteRenderer,
  entities?: RenderEntities,
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

  // Draw entities
  if (entities) {
    const screenOrigin = tileMap.getScreenOrigin(camera.currentScreen);
    const ox = -screenOrigin.worldX - camera.offsetX;
    const oy = -screenOrigin.worldY - camera.offsetY;

    // Moving platforms (behind player)
    for (const plat of entities.movingPlatforms) {
      if (plat.screenKey !== camera.currentScreen) continue;
      const px = plat.worldX + ox;
      const py = plat.worldY + oy;

      // Try to tile wood texture across platform width
      const tileImg = getTileImage('bridge');
      if (tileImg) {
        const tileCount = Math.ceil(plat.width / TILE_SIZE);
        for (let i = 0; i < tileCount; i++) {
          const tw = Math.min(TILE_SIZE, plat.width - i * TILE_SIZE);
          ctx.drawImage(tileImg, 0, 0, tw, TILE_SIZE, px + i * TILE_SIZE, py, tw, plat.height);
        }
      } else {
        ctx.fillStyle = '#8B7355';
        ctx.fillRect(px, py, plat.width, plat.height);
        ctx.strokeStyle = '#5C4033';
        ctx.lineWidth = 2;
        ctx.strokeRect(px, py, plat.width, plat.height);
      }
    }

    // Collectibles
    for (const c of entities.collectibles) {
      if (c.collected || c.screenKey !== camera.currentScreen) continue;
      const cdx = c.worldX + ox;
      const cdy = c.worldY + oy;

      // Try sprite rendering, fall back to gold circle
      if (!spriteRenderer?.drawCollectible(ctx, c.sprite, c.animationElapsedMs, cdx, cdy, c.width, c.height)) {
        const cx = cdx + c.width / 2;
        const cy = cdy + c.height / 2;
        ctx.fillStyle = '#FFD700';
        ctx.beginPath();
        ctx.arc(cx, cy, c.width * 0.35, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = '#DAA520';
        ctx.lineWidth = 2;
        ctx.stroke();
      }
    }

    // NPCs (behind player)
    for (const npc of entities.npcs) {
      if (npc.screenKey !== camera.currentScreen) continue;
      const nx = npc.worldX + ox;
      const ny = npc.worldY + oy;

      // Try sprite rendering, fall back to colored rectangle
      if (!spriteRenderer?.drawNpc(ctx, npc.sprite, npc.behavior, npc.animationElapsedMs, nx, ny, npc.facing)) {
        ctx.fillStyle = '#9B59B6';
        ctx.fillRect(nx, ny, npc.width, npc.height);
        ctx.fillStyle = '#7D3C98';
        const eyeX = npc.facing === 'right' ? nx + npc.width - 12 : nx + 4;
        ctx.fillRect(eyeX, ny + 16, 8, 8);
      }
    }

    // Score display
    ctx.fillStyle = '#FFF';
    ctx.font = 'bold 20px monospace';
    ctx.textAlign = 'left';
    ctx.fillText(`Score: ${entities.score}`, 12, 28);
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

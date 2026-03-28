import { TileMap } from './TileMap';
import { TILE_SIZE, DEBUG } from './types';

export interface CollisionResult {
  worldX: number;
  worldY: number;
  vx: number;
  vy: number;
  grounded: boolean;
  hitCeiling: boolean;
  hitWallLeft: boolean;
  hitWallRight: boolean;
  onLadder: boolean;
}

/**
 * Resolve movement against the tile grid using swept AABB.
 * X axis is resolved first, then Y, to avoid corner-sticking.
 */
export function resolve(
  worldX: number,
  worldY: number,
  vx: number,
  vy: number,
  width: number,
  height: number,
  tileMap: TileMap,
  isClimbing: boolean = false,
): CollisionResult {
  let resultX = worldX;
  let resultY = worldY;
  let resultVx = vx;
  let resultVy = vy;
  let hitWallLeft = false;
  let hitWallRight = false;
  let hitCeiling = false;
  let grounded = false;

  // ── Resolve X axis ──────────────────────────────
  resultX = worldX + vx;

  if (vx !== 0) {
    // Check tiles along the leading edge
    const leadingEdgeX = vx > 0 ? resultX + width - 1 : resultX;
    const topRow = Math.floor(worldY / TILE_SIZE);
    const bottomRow = Math.floor((worldY + height - 1) / TILE_SIZE);

    for (let row = topRow; row <= bottomRow; row++) {
      const tile = tileMap.getTileAt(leadingEdgeX, row * TILE_SIZE);
      if (tile.type === 'solid') {
        if (vx > 0) {
          // Snap to left edge of the tile we hit
          const tileLeft = Math.floor(leadingEdgeX / TILE_SIZE) * TILE_SIZE;
          resultX = tileLeft - width;
          hitWallRight = true;
        } else {
          // Snap to right edge of the tile we hit
          const tileRight = Math.floor(leadingEdgeX / TILE_SIZE) * TILE_SIZE + TILE_SIZE;
          resultX = tileRight;
          hitWallLeft = true;
        }
        resultVx = 0;
        break;
      }
    }
  }

  // ── Resolve Y axis (using X-corrected position) ─
  resultY = worldY + vy;

  if (vy !== 0) {
    const leadingEdgeY = vy > 0 ? resultY + height - 1 : resultY;
    const leftCol = Math.floor(resultX / TILE_SIZE);
    const rightCol = Math.floor((resultX + width - 1) / TILE_SIZE);

    for (let col = leftCol; col <= rightCol; col++) {
      const tile = tileMap.getTileAt(col * TILE_SIZE, leadingEdgeY);

      if (tile.type === 'solid') {
        if (vy > 0) {
          // Falling: land on top of tile
          const tileTop = Math.floor(leadingEdgeY / TILE_SIZE) * TILE_SIZE;
          resultY = tileTop - height;
          grounded = true;
        } else {
          // Jumping: bonk on ceiling
          const tileBottom = Math.floor(leadingEdgeY / TILE_SIZE) * TILE_SIZE + TILE_SIZE;
          resultY = tileBottom;
          hitCeiling = true;
        }
        resultVy = 0;
        break;
      }

      // Platform tiles: only block from above (falling onto them), never while climbing
      if (tile.type === 'platform' && vy > 0 && !isClimbing) {
        const tileTop = Math.floor(leadingEdgeY / TILE_SIZE) * TILE_SIZE;
        const previousFeetY = worldY + height - 1;
        // Allow landing if feet were above the platform, OR if there's a
        // ladder directly below this platform (player climbed through it).
        const centerX = worldX + width / 2;
        const hasLadderBelow = tileMap.getTileAt(centerX, tileTop + TILE_SIZE).type === 'ladder';
        if (previousFeetY <= tileTop || hasLadderBelow) {
          resultY = tileTop - height;
          resultVy = 0;
          grounded = true;
          break;
        }
      }
    }
  }

  // ── Ladder detection ────────────────────────────
  // Check if any tile from the player's center down to their feet is a ladder.
  // Scanning the lower body (not just center) lets tall characters climb all
  // the way up until their feet clear the ladder before dismounting.
  // Also check one tile below feet so the player can start climbing down
  // from a platform that sits directly above a ladder.
  const centerX = resultX + width / 2;
  const topCheckRow = Math.floor((resultY + height / 2) / TILE_SIZE);
  const bottomCheckRow = Math.floor((resultY + height - 1) / TILE_SIZE);
  const belowFeetRow = Math.floor((resultY + height) / TILE_SIZE);
  let onLadder = false;
  for (let row = topCheckRow; row <= belowFeetRow + 1; row++) {
    if (tileMap.getTileAt(centerX, row * TILE_SIZE).type === 'ladder') {
      onLadder = true;
      break;
    }
  }

  if (DEBUG && (hitWallLeft || hitWallRight || hitCeiling || grounded)) {
    const flags = [
      grounded && 'grounded',
      hitCeiling && 'ceiling',
      hitWallLeft && 'wallL',
      hitWallRight && 'wallR',
    ].filter(Boolean).join(', ');
    console.log(`[Collision] ${flags}`);
  }

  return {
    worldX: resultX,
    worldY: resultY,
    vx: resultVx,
    vy: resultVy,
    grounded,
    hitCeiling,
    hitWallLeft,
    hitWallRight,
    onLadder,
  };
}

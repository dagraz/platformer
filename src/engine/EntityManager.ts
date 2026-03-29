import {
  Collectible,
  NPC,
  MovingPlatform,
  Player,
  TILE_SIZE,
} from './types';

/**
 * Initialize runtime entity arrays from level entity definitions.
 */
export function createEntities(
  level: { entities: any[]; screenWidth: number; screenHeight: number; tileSize: number },
): { collectibles: Collectible[]; npcs: NPC[]; movingPlatforms: MovingPlatform[] } {
  const collectibles: Collectible[] = [];
  const npcs: NPC[] = [];
  const movingPlatforms: MovingPlatform[] = [];

  for (const def of level.entities) {
    const [col, row] = def.screen.split(',').map(Number);
    const originX = col * level.screenWidth * level.tileSize;
    const originY = row * level.screenHeight * level.tileSize;

    if (def.type === 'collectible') {
      collectibles.push({
        id: `collectible_${collectibles.length}`,
        screenKey: def.screen,
        worldX: originX + def.x * TILE_SIZE,
        worldY: originY + def.y * TILE_SIZE,
        width: TILE_SIZE,
        height: TILE_SIZE,
        sprite: def.sprite ?? 'coin',
        value: def.value ?? 1,
        collected: false,
      });
    } else if (def.type === 'npc') {
      const worldX = originX + def.x * TILE_SIZE;
      npcs.push({
        id: `npc_${npcs.length}`,
        screenKey: def.screen,
        worldX,
        worldY: originY + def.y * TILE_SIZE - 128, // feet at top of tile (2-tile tall entity)
        width: 64,
        height: 128,
        sprite: def.sprite ?? 'villager',
        behavior: def.behavior ?? 'static',
        facing: 'right',
        paceRange: (def.paceRange ?? 3) * TILE_SIZE,
        paceOriginX: worldX,
        paceDirection: 1,
      });
    } else if (def.type === 'moving_platform') {
      const path = (def.path as [number, number][]).map(([tx, ty]) => ({
        worldX: originX + tx * TILE_SIZE,
        worldY: originY + ty * TILE_SIZE,
      }));
      movingPlatforms.push({
        id: `platform_${movingPlatforms.length}`,
        screenKey: def.screen,
        worldX: path[0].worldX,
        worldY: path[0].worldY,
        width: (def.widthTiles ?? 3) * TILE_SIZE,
        height: TILE_SIZE,
        sprite: def.sprite ?? 'platform_wood',
        path,
        speed: def.speed ?? 1,
        pathIndex: 0,
        pathDirection: 1,
        vx: 0,
        vy: 0,
      });
    }
  }

  return { collectibles, npcs, movingPlatforms };
}

// ── Per-frame update ────────────────────────────────

export interface EntityUpdateResult {
  collectibles: Collectible[];
  npcs: NPC[];
  movingPlatforms: MovingPlatform[];
  scoreAdded: number;
  soundsToPlay: string[];
}

function aabbOverlap(
  ax: number, ay: number, aw: number, ah: number,
  bx: number, by: number, bw: number, bh: number,
): boolean {
  return ax < bx + bw && ax + aw > bx && ay < by + bh && ay + ah > by;
}

export function updateEntities(
  player: Player,
  collectibles: Collectible[],
  npcs: NPC[],
  movingPlatforms: MovingPlatform[],
  currentScreen: string,
): EntityUpdateResult {
  let scoreAdded = 0;
  const soundsToPlay: string[] = [];

  // ── Collectibles: overlap detection ──────────────
  const updatedCollectibles = collectibles.map(c => {
    if (c.collected || c.screenKey !== currentScreen) return c;
    if (aabbOverlap(
      player.worldX, player.worldY, player.width, player.height,
      c.worldX, c.worldY, c.width, c.height,
    )) {
      scoreAdded += c.value;
      soundsToPlay.push(c.sprite === 'coin' ? 'coin' : 'pickup');
      return { ...c, collected: true };
    }
    return c;
  });

  // ── NPCs: pacing and facing ──────────────────────
  const updatedNPCs = npcs.map(npc => {
    if (npc.screenKey !== currentScreen) return npc;

    if (npc.behavior === 'face_player') {
      const facing = player.worldX > npc.worldX ? 'right' as const : 'left' as const;
      return facing !== npc.facing ? { ...npc, facing } : npc;
    }

    if (npc.behavior === 'pace') {
      const paceSpeed = 1; // px/frame
      let worldX = npc.worldX + npc.paceDirection * paceSpeed;
      let paceDirection = npc.paceDirection;
      let facing = npc.facing;

      // Reverse at range boundaries
      if (worldX > npc.paceOriginX + npc.paceRange) {
        worldX = npc.paceOriginX + npc.paceRange;
        paceDirection = -1 as const;
        facing = 'left';
      } else if (worldX < npc.paceOriginX) {
        worldX = npc.paceOriginX;
        paceDirection = 1 as const;
        facing = 'right';
      }

      return { ...npc, worldX, paceDirection, facing };
    }

    return npc;
  });

  // ── Moving platforms: path interpolation ─────────
  const updatedPlatforms = movingPlatforms.map(plat => {
    if (plat.screenKey !== currentScreen) return plat;

    const target = plat.path[plat.pathIndex];
    const dx = target.worldX - plat.worldX;
    const dy = target.worldY - plat.worldY;
    const dist = Math.sqrt(dx * dx + dy * dy);

    if (dist < plat.speed) {
      // Reached waypoint — advance to next
      let nextIndex = plat.pathIndex + plat.pathDirection;
      let pathDirection = plat.pathDirection;
      if (nextIndex >= plat.path.length) {
        nextIndex = plat.path.length - 2;
        pathDirection = -1 as const;
      } else if (nextIndex < 0) {
        nextIndex = 1;
        pathDirection = 1 as const;
      }
      return {
        ...plat,
        worldX: target.worldX,
        worldY: target.worldY,
        vx: 0,
        vy: 0,
        pathIndex: nextIndex,
        pathDirection,
      };
    }

    // Move toward target
    const vx = (dx / dist) * plat.speed;
    const vy = (dy / dist) * plat.speed;
    return {
      ...plat,
      worldX: plat.worldX + vx,
      worldY: plat.worldY + vy,
      vx,
      vy,
    };
  });

  return {
    collectibles: updatedCollectibles,
    npcs: updatedNPCs,
    movingPlatforms: updatedPlatforms,
    scoreAdded,
    soundsToPlay,
  };
}

/**
 * Resolve player collision against moving platforms.
 * Only supports landing on top (like a platform tile).
 * Call after updatePlayer so tile collision is already resolved.
 */
export function resolveMovingPlatformCollision(
  player: Player,
  prevWorldY: number,
  prevState: Player['state'],
  prevElapsedMs: number,
  dt: number,
  platforms: MovingPlatform[],
  currentScreen: string,
): Player {
  // Only resolve when falling or stationary vertically
  if (player.vy < 0) return player;

  const playerLeft = player.worldX;
  const playerRight = player.worldX + player.width;
  const feetY = player.worldY + player.height;
  const prevFeetY = prevWorldY + player.height;

  for (const plat of platforms) {
    if (plat.screenKey !== currentScreen) continue;

    // Horizontal overlap check
    if (playerRight <= plat.worldX || playerLeft >= plat.worldX + plat.width) continue;

    const platTop = plat.worldY;

    // Player's feet must have been above (or at) the platform top last frame,
    // and now at or below it — i.e. they crossed the top edge this frame.
    if (prevFeetY <= platTop + 2 && feetY >= platTop - 2) {
      const state = Math.abs(player.vx) > 0.1 ? 'walk' as const : 'idle' as const;
      // Use dt directly: updatePlayer resets animationElapsedMs to 0 every
      // frame (idle→fall transition), so we can't use its value.
      const elapsed = prevState === state ? prevElapsedMs + dt : 0;
      return {
        ...player,
        worldY: platTop - player.height,
        vy: 0,
        grounded: true,
        state,
        animationElapsedMs: elapsed,
      };
    }
  }

  return player;
}

/**
 * Check if the player is standing on a moving platform.
 * Returns the platform's velocity if so, or null.
 */
export function getMovingPlatformUnderPlayer(
  player: Player,
  platforms: MovingPlatform[],
  currentScreen: string,
): { vx: number; vy: number } | null {
  if (!player.grounded) return null;

  const feetY = player.worldY + player.height;
  const playerLeft = player.worldX;
  const playerRight = player.worldX + player.width;

  for (const plat of platforms) {
    if (plat.screenKey !== currentScreen) continue;
    // Player feet must be at the platform top (within 2px tolerance)
    if (Math.abs(feetY - plat.worldY) > 2) continue;
    // Horizontal overlap
    if (playerRight > plat.worldX && playerLeft < plat.worldX + plat.width) {
      return { vx: plat.vx, vy: plat.vy };
    }
  }
  return null;
}

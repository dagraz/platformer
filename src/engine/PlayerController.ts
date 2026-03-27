import { Player, InputState, PhysicsParams, PlayerState, DEBUG } from './types';
import { TileMap } from './TileMap';
import { applyGravity, applyWalk, applyJump, applyFriction } from './Physics';
import { resolve } from './Collision';

/**
 * Updates the player for one physics frame.
 * Applies physics, then resolves collision against the tile grid.
 */
export function updatePlayer(
  player: Player,
  input: InputState,
  params: PhysicsParams,
  tileMap: TileMap,
): Player {
  // 1. Apply physics to get desired velocity
  const walk = applyWalk(player, input, params);
  const friction = applyFriction({ ...player, vx: walk.vx }, input, params);
  const jump = applyJump(player, input, params);
  const gravity = applyGravity({ ...player, vy: jump.vy }, params);

  const vx = friction.vx;
  const vy = gravity.vy;

  // 2. Resolve collision (X first, then Y)
  const col = resolve(
    player.worldX, player.worldY,
    vx, vy,
    player.width, player.height,
    tileMap,
  );

  // 3. Determine facing direction
  let facing = player.facing;
  if (input.left && !input.right) facing = 'left';
  if (input.right && !input.left) facing = 'right';

  // 4. Determine player state
  let state: PlayerState;
  if (col.vy < -0.1) {
    state = 'jump';
  } else if (col.vy > 0.1 && !col.grounded) {
    state = 'fall';
  } else if (Math.abs(col.vx) > 0.1) {
    state = 'walk';
  } else {
    state = 'idle';
  }

  const newPlayer: Player = {
    ...player,
    worldX: col.worldX,
    worldY: col.worldY,
    vx: col.vx,
    vy: col.vy,
    facing,
    state,
    jumpHoldTimer: jump.jumpHoldTimer,
    grounded: col.grounded,
    onLadder: col.onLadder,
  };

  if (DEBUG && state !== player.state) {
    console.log(`[Player] state: ${player.state} → ${state}`);
  }

  return newPlayer;
}

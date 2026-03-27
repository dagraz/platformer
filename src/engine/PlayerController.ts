import { Player, InputState, PhysicsParams, PlayerState, DEBUG } from './types';
import { applyGravity, applyWalk, applyJump, applyFriction } from './Physics';

/**
 * Updates the player for one physics frame.
 * Phase 2: no collision — player falls through tiles.
 */
export function updatePlayer(
  player: Player,
  input: InputState,
  params: PhysicsParams,
): Player {
  // 1. Apply physics
  const walk = applyWalk(player, input, params);
  const friction = applyFriction({ ...player, vx: walk.vx }, input, params);
  const jump = applyJump(player, input, params);
  const gravity = applyGravity({ ...player, vy: jump.vy }, params);

  const vx = friction.vx;
  const vy = gravity.vy;

  // 2. Update position (no collision yet)
  const worldX = player.worldX + vx;
  const worldY = player.worldY + vy;

  // 3. Determine facing direction
  let facing = player.facing;
  if (input.left && !input.right) facing = 'left';
  if (input.right && !input.left) facing = 'right';

  // 4. Determine player state
  let state: PlayerState;
  if (vy < -0.1) {
    state = 'jump';
  } else if (vy > 0.1 && !player.grounded) {
    state = 'fall';
  } else if (Math.abs(vx) > 0.1) {
    state = 'walk';
  } else {
    state = 'idle';
  }

  const newPlayer: Player = {
    ...player,
    worldX,
    worldY,
    vx,
    vy,
    facing,
    state,
    jumpHoldTimer: jump.jumpHoldTimer,
    grounded: false, // No collision yet — always falling
  };

  if (DEBUG && state !== player.state) {
    console.log(`[Player] state: ${player.state} → ${state}`);
  }

  return newPlayer;
}

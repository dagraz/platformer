import { Player, InputState, PhysicsParams, PlayerState, DEBUG, TILE_SIZE } from './types';
import { TileMap } from './TileMap';
import { applyGravity, applyWalk, applyJump, applyFriction, applyClimb } from './Physics';
import { resolve } from './Collision';

/**
 * Updates the player for one physics frame.
 * Applies physics (or climb), then resolves collision against the tile grid.
 */
export function updatePlayer(
  player: Player,
  input: InputState,
  params: PhysicsParams,
  tileMap: TileMap,
): Player {
  // Determine if we're climbing
  const wantsClimb = (input.up || input.down) && player.onLadder;
  const isClimbing = player.state === 'climb';

  // Allow climbing to continue briefly past the ladder top so the player
  // can smoothly reach the platform above instead of snapping. Limited to
  // one tile past the ladder — once there's no ladder within a tile below
  // the player's feet, the grace period ends.
  const centerX = player.worldX + player.width / 2;
  const feetY = player.worldY + player.height;
  const ladderNearFeet =
    tileMap.getTileAt(centerX, feetY).type === 'ladder' ||
    tileMap.getTileAt(centerX, feetY + TILE_SIZE).type === 'ladder';
  const climbingPastTop = isClimbing && !player.onLadder && input.up && ladderNearFeet;

  const shouldClimb = wantsClimb || (isClimbing && player.onLadder && !input.jumpPressed) || climbingPastTop;

  let vx: number;
  let vy: number;
  let jumpHoldTimer = player.jumpHoldTimer;

  if (shouldClimb) {
    // Climbing: no gravity, no horizontal walk, just vertical movement
    const climb = applyClimb(player, input, params);
    vx = 0;
    vy = climb.vy;
    jumpHoldTimer = -1;

    // Allow jumping off a ladder
    if (input.jumpPressed) {
      const jump = applyJump({ ...player, grounded: true }, input, params);
      vy = jump.vy;
      jumpHoldTimer = jump.jumpHoldTimer;
    }
  } else {
    // Normal movement: walk, jump, gravity, friction
    const walk = applyWalk(player, input, params);
    const friction = applyFriction({ ...player, vx: walk.vx }, input, params);
    const jump = applyJump(player, input, params);
    const gravity = applyGravity({ ...player, vy: jump.vy }, params);

    vx = friction.vx;
    vy = gravity.vy;
    jumpHoldTimer = jump.jumpHoldTimer;
  }

  // Resolve collision (X first, then Y).
  // During climbingPastTop, don't mark as climbing in collision so platforms
  // can catch the player once their feet clear the platform edge. The player
  // is moving upward (vy < 0) during this phase, so platforms won't block
  // the upward movement — they only activate when vy > 0.
  const col = resolve(
    player.worldX, player.worldY,
    vx, vy,
    player.width, player.height,
    tileMap,
    shouldClimb && !climbingPastTop,
  );

  // Determine facing direction
  let facing = player.facing;
  if (input.left && !input.right) facing = 'left';
  if (input.right && !input.left) facing = 'right';

  // Determine player state
  let state: PlayerState;
  if (shouldClimb && (col.onLadder || climbingPastTop) && !col.grounded) {
    state = 'climb';
  } else if (col.vy < -0.1) {
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
    jumpHoldTimer,
    grounded: col.grounded,
    onLadder: col.onLadder,
  };

  if (DEBUG && state !== player.state) {
    console.log(`[Player] state: ${player.state} → ${state}`);
  }

  return newPlayer;
}

import { Player, InputState, PhysicsParams } from './types';

/** Apply gravity to vertical velocity. */
export function applyGravity(player: Player, params: PhysicsParams): { vy: number } {
  const vy = Math.min(player.vy + params.gravity, params.terminalVelocity);
  return { vy };
}

/** Apply horizontal walk acceleration from input. */
export function applyWalk(player: Player, input: InputState, params: PhysicsParams): { vx: number } {
  let targetVx = 0;
  if (input.left) targetVx -= params.walkSpeed;
  if (input.right) targetVx += params.walkSpeed;

  const accel = player.grounded ? params.walkAccel : params.walkAccel * params.airControl;

  let vx = player.vx;
  if (targetVx !== 0) {
    // Accelerate toward target
    vx += Math.sign(targetVx - vx) * accel;
    // Clamp to walk speed
    if (Math.abs(vx) > params.walkSpeed) {
      vx = Math.sign(vx) * params.walkSpeed;
    }
  }

  return { vx };
}

/** Apply jump initiation and variable-height hold. */
export function applyJump(
  player: Player,
  input: InputState,
  params: PhysicsParams,
): { vy: number; jumpHoldTimer: number } {
  let vy = player.vy;
  let jumpHoldTimer = player.jumpHoldTimer;

  // Initiate jump on edge-triggered press while grounded
  if (input.jumpPressed && player.grounded) {
    vy = params.jumpForce;
    jumpHoldTimer = 0;
  }

  // Extend jump while held (variable height)
  if (input.jump && jumpHoldTimer >= 0 && jumpHoldTimer < params.maxJumpHoldTime && !player.grounded) {
    vy += params.jumpHoldForce;
    jumpHoldTimer += 1;
  }

  // Release jump hold when key released
  if (!input.jump) {
    jumpHoldTimer = -1; // sentinel: jump hold exhausted
  }

  return { vy, jumpHoldTimer };
}

/** Apply friction when no horizontal input. */
export function applyFriction(player: Player, input: InputState, params: PhysicsParams): { vx: number } {
  const hasHorizontalInput = input.left || input.right;
  if (hasHorizontalInput || !player.grounded) {
    return { vx: player.vx };
  }
  // Decelerate toward zero
  let vx = player.vx * params.friction;
  if (Math.abs(vx) < 0.1) vx = 0;
  return { vx };
}

/** Apply climb velocity on ladders. */
export function applyClimb(player: Player, input: InputState, params: PhysicsParams): { vy: number } {
  let vy = 0;
  if (input.up) vy = -params.climbSpeed;
  if (input.down) vy = params.climbSpeed;
  return { vy };
}

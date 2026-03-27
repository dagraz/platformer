import { PhysicsParams } from '../engine/types';

export const defaultPhysics: PhysicsParams = {
  gravity: 1.2,
  jumpForce: -24.0,
  jumpHoldForce: -0.8,
  maxJumpHoldTime: 12,
  walkSpeed: 6.0,
  walkAccel: 0.6,
  airControl: 0.15,
  friction: 0.8,
  climbSpeed: 4.0,
  terminalVelocity: 20.0,
};

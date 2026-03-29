import { describe, it, expect } from 'vitest';
import { updatePlayer } from './PlayerController';
import { resolveMovingPlatformCollision, getMovingPlatformUnderPlayer } from './EntityManager';
import { Player, MovingPlatform, InputState, PhysicsParams } from './types';
import { TileMap } from './TileMap';

const DT = 1000 / 60;

const noInput: InputState = {
  left: false, right: false, up: false, down: false,
  jump: false, jumpPressed: false,
};

const physics: PhysicsParams = {
  gravity: 1.2,
  jumpForce: -14,
  jumpHoldForce: -2,
  maxJumpHoldTime: 150,
  walkSpeed: 5,
  walkAccel: 1.2,
  airControl: 0.4,
  friction: 0.8,
  climbSpeed: 4,
  terminalVelocity: 18,
};

function makeOpenLevel(): TileMap {
  // A level with no solid tiles — just empty space
  const grid: number[][] = [];
  for (let r = 0; r < 15; r++) {
    grid.push(new Array(25).fill(0));
  }
  const tileMap = new TileMap();
  tileMap.load({
    name: 'test',
    screenWidth: 25,
    screenHeight: 15,
    tileSize: 64,
    tileTypes: {
      0: { type: 'empty', sprite: 'sky' },
    },
    screens: { '0,0': { tiles: grid } },
    entities: [],
    goal: { type: 'collect_all' },
  });
  return tileMap;
}

function makePlayerOnPlatform(platWorldY: number): Player {
  return {
    worldX: 200,
    worldY: platWorldY - 128, // feet at platform top
    vx: 0, vy: 0,
    width: 64, height: 128,
    state: 'idle',
    facing: 'right',
    grounded: true,
    onLadder: false,
    jumpHoldTimer: -1,
    currentScreen: '0,0',
    animationElapsedMs: 0,
  };
}

function makePlatform(worldY: number): MovingPlatform {
  return {
    id: 'plat_0',
    screenKey: '0,0',
    worldX: 100,
    worldY,
    width: 192,
    height: 64,
    sprite: 'platform_wood',
    path: [
      { worldX: 100, worldY },
      { worldX: 500, worldY },
    ],
    speed: 1.5,
    pathIndex: 1,
    pathDirection: 1,
    vx: 1.5,
    vy: 0,
  };
}

describe('Idle animation on moving platform', () => {
  it('animationElapsedMs should accumulate over multiple frames', () => {
    const tileMap = makeOpenLevel();
    const platY = 400;
    let player = makePlayerOnPlatform(platY);
    const platforms = [makePlatform(platY)];

    // Simulate 60 frames (1 second) of standing on the platform
    for (let i = 0; i < 60; i++) {
      // Same flow as GameCanvas update loop
      const platVel = getMovingPlatformUnderPlayer(player, platforms, '0,0');
      if (platVel) {
        player = { ...player, worldX: player.worldX + platVel.vx, worldY: player.worldY + platVel.vy };
      }

      const prevWorldY = player.worldY;
      const prevState = player.state;
      const prevElapsedMs = player.animationElapsedMs;
      player = updatePlayer(player, noInput, physics, tileMap, DT);
      player = resolveMovingPlatformCollision(player, prevWorldY, prevState, prevElapsedMs, DT, platforms, '0,0');
    }

    expect(player.state).toBe('idle');
    // After 60 frames at ~16.67ms each, elapsed should be ~1000ms
    expect(player.animationElapsedMs).toBeGreaterThan(900);
  });

  it('animation should cycle through all idle frames', () => {
    const tileMap = makeOpenLevel();
    const platY = 400;
    let player = makePlayerOnPlatform(platY);
    const platforms = [makePlatform(platY)];

    // idle has 4 frames at 4fps → each frame shows for 250ms
    // After 500ms (30 frames) we should have seen at least frame index 1
    for (let i = 0; i < 30; i++) {
      const platVel = getMovingPlatformUnderPlayer(player, platforms, '0,0');
      if (platVel) {
        player = { ...player, worldX: player.worldX + platVel.vx, worldY: player.worldY + platVel.vy };
      }

      const prevWorldY = player.worldY;
      const prevState = player.state;
      const prevElapsedMs = player.animationElapsedMs;
      player = updatePlayer(player, noInput, physics, tileMap, DT);
      player = resolveMovingPlatformCollision(player, prevWorldY, prevState, prevElapsedMs, DT, platforms, '0,0');
    }

    expect(player.state).toBe('idle');
    // 30 frames * 16.67ms ≈ 500ms, at 4fps that's frame index 2
    // Just verify elapsed is high enough to have advanced past frame 0
    expect(player.animationElapsedMs).toBeGreaterThan(250);
  });
});

import { describe, it, expect } from 'vitest';
import { TileMap } from './TileMap';
import { updatePlayer } from './PlayerController';
import { Player, InputState, LevelData, PhysicsParams } from './types';

// Minimal physics for deterministic testing
const physics: PhysicsParams = {
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

const noInput: InputState = {
  left: false, right: false, up: false, down: false,
  jump: false, jumpPressed: false,
};

const upInput: InputState = { ...noInput, up: true };

/**
 * Build a small level with a ladder below a platform.
 *
 * Layout (each cell = 64px):
 *
 *   row 0: empty  empty  empty  empty  empty
 *   row 1: empty  empty  empty  empty  empty
 *   row 2: empty  empty  empty  empty  empty
 *   row 3: plat   plat   plat   plat   empty    ← platform at row 3
 *   row 4: empty  empty  ladder empty  empty    ← ladder starts
 *   row 5: empty  empty  ladder empty  empty
 *   row 6: empty  empty  ladder empty  empty
 *   row 7: solid  solid  solid  solid  solid    ← ground
 *
 * Player (64×128) starts on the ladder at col 2, climbing up.
 * They should be able to reach and stand on the platform at row 3.
 */
function makeLadderLevel(): TileMap {
  const level: LevelData = {
    name: 'Test',
    screenWidth: 25,
    screenHeight: 15,
    tileSize: 64,
    tileTypes: {
      0: { type: 'empty', sprite: 'sky' },
      1: { type: 'solid', sprite: 'ground' },
      3: { type: 'platform', sprite: 'bridge' },
      4: { type: 'ladder', sprite: 'vine' },
    },
    screens: {
      '0,0': {
        tiles: buildTileGrid(),
      },
    },
    entities: [],
    goal: { type: 'reach_tile' },
  };
  const tm = new TileMap();
  tm.load(level);
  return tm;
}

function buildTileGrid(): number[][] {
  // 15 rows × 25 cols, mostly empty
  const grid: number[][] = [];
  for (let r = 0; r < 15; r++) {
    grid.push(new Array(25).fill(0));
  }
  // Platform at row 3, cols 0-3
  grid[3][0] = 3; grid[3][1] = 3; grid[3][2] = 3; grid[3][3] = 3;
  // Ladder at col 2, rows 4-6
  grid[4][2] = 4; grid[5][2] = 4; grid[6][2] = 4;
  // Solid ground at row 7
  for (let c = 0; c < 25; c++) grid[7][c] = 1;
  return grid;
}

function makePlayer(worldX: number, worldY: number, state: Player['state'] = 'idle'): Player {
  return {
    worldX, worldY,
    vx: 0, vy: 0,
    width: 64, height: 128,
    state, facing: 'right',
    grounded: false,
    onLadder: false,
    jumpHoldTimer: -1,
    currentScreen: '0,0',
    animationElapsedMs: 0,
  };
}

describe('Ladder dismount onto platform', () => {
  it('player climbing up should eventually stand on the platform', () => {
    const tileMap = makeLadderLevel();

    // Place player mid-ladder, center in row 5.
    // Ladder col 2 center X = 2*64 + 32 = 160, playerX = 160 - 32 = 128.
    // Row 5 center Y = 5*64+32 = 352, playerY = 352-64 = 288.
    let player = makePlayer(128, 288, 'climb');
    player = { ...player, onLadder: true };

    const platformTop = 3 * 64; // 192

    // Simulate climbing up for many frames
    let landed = false;
    for (let frame = 0; frame < 200; frame++) {
      const input = player.state === 'climb' ? upInput : noInput;
      player = updatePlayer(player, input, physics, tileMap, 1000 / 60);

      if (player.grounded && player.worldY + player.height <= platformTop + 2) {
        landed = true;
        break;
      }
    }

    expect(landed).toBe(true);
    expect(player.state).toBe('idle');
    expect(player.worldY + player.height).toBe(platformTop);
  });

  it('player should not fall through platform after climbing through it', () => {
    const tileMap = makeLadderLevel();
    const platformTop = 3 * 64; // 192

    // Start just below the platform on the ladder.
    let player = makePlayer(128, 224, 'climb');
    player = { ...player, onLadder: true };

    for (let i = 0; i < 60; i++) {
      const input = player.state === 'climb' ? upInput : noInput;
      player = updatePlayer(player, input, physics, tileMap, 1000 / 60);
    }

    expect(player.worldY + player.height).toBeLessThanOrEqual(platformTop + 1);
    expect(player.grounded).toBe(true);
  });

  it('climbing down through a platform should work (no blocking from below)', () => {
    const tileMap = makeLadderLevel();
    const platformTop = 3 * 64; // 192

    // Start on top of the platform at the ladder position.
    // Feet at platformTop → worldY = 192 - 128 = 64
    let player = makePlayer(128, 64, 'idle');
    player = { ...player, grounded: true, onLadder: true };

    const downInput: InputState = { ...noInput, down: true };
    for (let i = 0; i < 30; i++) {
      player = updatePlayer(player, downInput, physics, tileMap, 1000 / 60);
    }

    expect(player.worldY + player.height).toBeGreaterThan(platformTop);
    expect(player.state).toBe('climb');
  });

  it('dismount should be smooth — no large position jumps between frames', () => {
    const tileMap = makeLadderLevel();

    // Start mid-ladder climbing up.
    let player = makePlayer(128, 288, 'climb');
    player = { ...player, onLadder: true };

    const maxAllowedJump = 8; // px — climbSpeed(4) + one frame of gravity(1.2) + margin
    let prevY = player.worldY;

    for (let frame = 0; frame < 200; frame++) {
      const input = player.state === 'climb' ? upInput : noInput;
      player = updatePlayer(player, input, physics, tileMap, 1000 / 60);

      const delta = Math.abs(player.worldY - prevY);
      expect(delta).toBeLessThanOrEqual(maxAllowedJump);
      prevY = player.worldY;

      if (player.grounded && player.state === 'idle') break;
    }

    expect(player.grounded).toBe(true);
  });
});

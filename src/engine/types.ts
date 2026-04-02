// ── World / Level ──────────────────────────────────

export type TileType = 'empty' | 'solid' | 'platform' | 'ladder';

export interface TileDefinition {
  type: TileType;
  sprite: string;
}

export interface Screen {
  tiles: number[][];  // 15 rows × 25 cols of tile IDs
}

export interface EntityDef {
  type: 'player_start' | 'collectible' | 'npc' | 'moving_platform';
  screen: string;       // "col,row"
  x: number;            // tile x within screen
  y: number;            // tile y within screen
  sprite?: string;
  value?: number;
  sound?: string;
  behavior?: 'static' | 'pace' | 'face_player';
  paceRange?: number;
  path?: [number, number][];
  speed?: number;
}

export interface GoalDef {
  type: 'reach_tile' | 'collect_all';
  screen?: string;
  x?: number;
  y?: number;
}

export interface LevelData {
  name: string;
  screenWidth: 25;
  screenHeight: 15;
  tileSize: 64;
  screens: Record<string, Screen>;
  tileTypes: Record<number, TileDefinition>;
  entities: EntityDef[];
  goal: GoalDef;
}

// ── Physics ────────────────────────────────────────

export interface PhysicsParams {
  gravity: number;
  jumpForce: number;
  jumpHoldForce: number;
  maxJumpHoldTime: number;
  walkSpeed: number;
  walkAccel: number;
  airControl: number;
  friction: number;
  climbSpeed: number;
  terminalVelocity: number;
}

// ── Entities at runtime ────────────────────────────

export type PlayerState = 'idle' | 'walk' | 'jump' | 'fall' | 'land' | 'climb';

export interface Player {
  worldX: number;
  worldY: number;
  vx: number;
  vy: number;
  width: 64;
  height: 128;
  state: PlayerState;
  facing: 'left' | 'right';
  grounded: boolean;
  onLadder: boolean;
  jumpHoldTimer: number;
  currentScreen: string;
  animationElapsedMs: number;
}

export interface Collectible {
  id: string;
  screenKey: string;
  worldX: number;
  worldY: number;
  width: number;
  height: number;
  sprite: string;
  value: number;
  collected: boolean;
}

export interface NPC {
  id: string;
  screenKey: string;
  worldX: number;
  worldY: number;
  width: 64;
  height: 128;
  sprite: string;
  behavior: 'static' | 'pace' | 'face_player';
  facing: 'left' | 'right';
  paceRange: number;
  paceOriginX: number;
  paceDirection: 1 | -1;
  animationElapsedMs: number;
}

export interface MovingPlatform {
  id: string;
  screenKey: string;
  worldX: number;
  worldY: number;
  width: number;
  height: number;
  sprite: string;
  path: { worldX: number; worldY: number }[];
  speed: number;
  pathIndex: number;
  pathDirection: 1 | -1;
  vx: number;
  vy: number;
}

// ── Sprite sheets ──────────────────────────────────

export interface SpriteManifest {
  frameWidth: number;
  frameHeight: number;
  states: Record<string, {
    row: number;
    frames: number;
    fps: number;
  }>;
}

// ── Game state ─────────────────────────────────────

export interface GameState {
  level: LevelData;
  player: Player;
  collectibles: Collectible[];
  npcs: NPC[];
  movingPlatforms: MovingPlatform[];
  camera: CameraState;
  score: number;
  goalReached: boolean;
  mode: 'edit' | 'play' | 'transition' | 'goal_complete';
}

export interface CameraState {
  currentScreen: string;
  targetScreen: string | null;
  transitionProgress: number;
  offsetX: number;
  offsetY: number;
}

// ── Input ──────────────────────────────────────────

export interface InputState {
  left: boolean;
  right: boolean;
  up: boolean;
  down: boolean;
  jump: boolean;
  jumpPressed: boolean;
}

// ── Constants ──────────────────────────────────────

export const TILE_SIZE = 64;
export const SCREEN_WIDTH_TILES = 25;
export const SCREEN_HEIGHT_TILES = 15;
export const VIEWPORT_WIDTH = SCREEN_WIDTH_TILES * TILE_SIZE;   // 1600
export const VIEWPORT_HEIGHT = SCREEN_HEIGHT_TILES * TILE_SIZE; // 960

export const DEBUG = true;

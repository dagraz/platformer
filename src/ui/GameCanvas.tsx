import { useRef, useEffect } from 'react';
import { TileMap } from '../engine/TileMap';
import { InputManager } from '../engine/InputManager';
import { GameLoop } from '../engine/GameLoop';
import { updatePlayer } from '../engine/PlayerController';
import { updateCamera } from '../engine/Camera';
import { createEntities, updateEntities, getMovingPlatformUnderPlayer, resolveMovingPlatformCollision } from '../engine/EntityManager';
import { SpriteSheet } from '../engine/SpriteSheet';
import { SpriteRenderer } from '../renderer/SpriteRenderer';
import { SoundManager } from '../engine/SoundManager';
import { defaultPhysics } from '../data/defaultPhysics';
import {
  CameraState,
  Collectible,
  InputState,
  LevelData,
  MovingPlatform,
  NPC,
  Player,
  SpriteManifest,
  VIEWPORT_WIDTH,
  VIEWPORT_HEIGHT,
  TILE_SIZE,
} from '../engine/types';
import { render } from '../renderer/Renderer';
import { loadTileImages } from '../renderer/TileRenderer';

const EMPTY_INPUT: InputState = {
  left: false,
  right: false,
  up: false,
  down: false,
  jump: false,
  jumpPressed: false,
};

function findPlayerStart(level: LevelData): { worldX: number; worldY: number; screenKey: string } {
  const entity = level.entities.find(e => e.type === 'player_start');
  if (entity) {
    const [col, row] = entity.screen.split(',').map(Number);
    const screenOriginX = col * level.screenWidth * level.tileSize;
    const screenOriginY = row * level.screenHeight * level.tileSize;
    return {
      worldX: screenOriginX + entity.x * TILE_SIZE,
      worldY: screenOriginY + entity.y * TILE_SIZE - 128, // player stands ON this tile
      screenKey: entity.screen,
    };
  }
  // Default: top-left of screen 0,0
  return { worldX: 128, worldY: 128, screenKey: '0,0' };
}

export function GameCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const tileMap = new TileMap();
    const inputManager = new InputManager();
    const gameLoop = new GameLoop();
    const soundManager = new SoundManager();

    let player: Player | null = null;
    let camera: CameraState = {
      currentScreen: '0,0',
      targetScreen: null,
      transitionProgress: 0,
      offsetX: 0,
      offsetY: 0,
    };
    let inputLocked = false;
    let spriteRenderer: SpriteRenderer | undefined;
    let collectibles: Collectible[] = [];
    let npcs: NPC[] = [];
    let movingPlatforms: MovingPlatform[] = [];
    let score = 0;

    // Load a sprite sheet image + manifest pair
    function loadSpriteSheet(name: string): Promise<{ manifest: SpriteManifest; image: HTMLImageElement }> {
      return Promise.all([
        fetch(`/assets/sprites/${name}.manifest.json`).then(r => r.json()) as Promise<SpriteManifest>,
        new Promise<HTMLImageElement>((resolve, reject) => {
          const img = new Image();
          img.onload = () => resolve(img);
          img.onerror = reject;
          img.src = `/assets/sprites/${name}.png`;
        }),
      ]).then(([manifest, image]) => ({ manifest, image }));
    }

    // Load player sprites
    const loadSprites = loadSpriteSheet('player').then(({ manifest, image }) => {
      spriteRenderer = new SpriteRenderer(new SpriteSheet(manifest), image);
    });

    // Load NPC sprites (non-blocking — falls back to colored rects if missing)
    const loadNpcSprites = loadSpriteSheet('wizard').then(({ manifest, image }) => {
      return { name: 'wizard', manifest, image };
    }).catch(() => null);

    // Load collectible sprites (coin + star variants)
    const collectibleNames = ['coin', 'star_1', 'star_2', 'star_3', 'star_4'];
    const loadCollectibleSprites = Promise.all(
      collectibleNames.map(name =>
        loadSpriteSheet(name)
          .then(({ manifest, image }) => ({ name, manifest, image }))
          .catch(() => null)
      ),
    );

    Promise.all([
      fetch('/assets/levels/demo.json').then(res => res.json()) as Promise<LevelData>,
      loadSprites,
      loadNpcSprites,
      loadCollectibleSprites,
    ]).then(([levelData, , npcResult, collectibleResults]) => {
        // Register NPC sprite sheets
        if (npcResult && spriteRenderer) {
          spriteRenderer.addNpcSheet(npcResult.name, new SpriteSheet(npcResult.manifest), npcResult.image);
        }
        // Register collectible sprite sheets
        for (const result of collectibleResults) {
          if (result && spriteRenderer) {
            spriteRenderer.addCollectibleSheet(result.name, new SpriteSheet(result.manifest), result.image);
          }
        }
        tileMap.load(levelData);

        // Load tile images (non-blocking — falls back to colored rects if missing)
        const spriteNames = Object.values(levelData.tileTypes)
          .map(t => t.sprite)
          .filter((s): s is string => !!s);
        loadTileImages(spriteNames);

        const start = findPlayerStart(levelData);
        player = {
          worldX: start.worldX,
          worldY: start.worldY,
          vx: 0,
          vy: 0,
          width: 64,
          height: 128,
          state: 'idle',
          facing: 'right',
          grounded: true,
          onLadder: false,
          jumpHoldTimer: -1,
          currentScreen: start.screenKey,
          animationElapsedMs: 0,
        };

        camera.currentScreen = start.screenKey;

        // Initialize entities from level data
        const entities = createEntities(levelData);
        collectibles = entities.collectibles;
        npcs = entities.npcs;
        movingPlatforms = entities.movingPlatforms;

        // Expose for console tuning (per build plan)
        (window as any).__physics = { ...defaultPhysics };
        (window as any).__sound = soundManager;

        inputManager.attach();

        gameLoop.setUpdateCallback((dt: number) => {
          if (!player) return;

          // Lock input during screen transitions
          const input = inputLocked ? EMPTY_INPUT : inputManager.poll();
          const params = (window as any).__physics ?? defaultPhysics;
          // Apply moving platform velocity before physics
          const platVel = getMovingPlatformUnderPlayer(player, movingPlatforms, camera.currentScreen);
          if (platVel) {
            player = {
              ...player,
              worldX: player.worldX + platVel.vx,
              worldY: player.worldY + platVel.vy,
            };
          }

          const prevWorldY = player.worldY;
          const prevState = player.state;
          const prevElapsedMs = player.animationElapsedMs;
          player = updatePlayer(player, input, params, tileMap, dt);

          // Resolve collision against moving platforms (tile collision doesn't cover these)
          player = resolveMovingPlatformCollision(player, prevWorldY, prevState, prevElapsedMs, dt, movingPlatforms, camera.currentScreen);

          // Sound: jump and land detection
          if (player.state === 'jump' && prevState !== 'jump') {
            soundManager.play('jump');
          }
          if (player.state === 'land' && prevState === 'fall') {
            soundManager.play('land');
          }

          // Update entities
          const entityResult = updateEntities(player, collectibles, npcs, movingPlatforms, camera.currentScreen);
          collectibles = entityResult.collectibles;
          npcs = entityResult.npcs;
          movingPlatforms = entityResult.movingPlatforms;
          score += entityResult.scoreAdded;

          // Sound: entity events (coin collection etc.)
          for (const s of entityResult.soundsToPlay) {
            soundManager.play(s);
          }

          // Update camera (detect transitions)
          const prevTargetScreen = camera.targetScreen;
          const camResult = updateCamera(camera, player, tileMap);
          camera = camResult.camera;
          inputLocked = camResult.inputLocked;

          // Sound: screen transition start
          if (camera.targetScreen !== null && prevTargetScreen === null) {
            soundManager.play('transition');
          }

          // Track current screen on player
          player = { ...player, currentScreen: camera.currentScreen };

          // Respawn if player falls way off screen
          if (player.worldY > start.worldY + 2000) {
            player = {
              ...player,
              worldX: start.worldX,
              worldY: start.worldY,
              vx: 0,
              vy: 0,
              state: 'idle',
              grounded: false,
              jumpHoldTimer: -1,
              currentScreen: start.screenKey,
              animationElapsedMs: 0,
            };
            camera = {
              currentScreen: start.screenKey,
              targetScreen: null,
              transitionProgress: 0,
              offsetX: 0,
              offsetY: 0,
            };
            inputLocked = false;
          }
        });

        gameLoop.setRenderCallback(() => {
          render(ctx, tileMap, camera, player ?? undefined, spriteRenderer, {
            collectibles,
            npcs,
            movingPlatforms,
            score,
          });
        });

        gameLoop.start();
      });

    return () => {
      gameLoop.stop();
      inputManager.detach();
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      width={VIEWPORT_WIDTH}
      height={VIEWPORT_HEIGHT}
      style={{ border: '2px solid #444', display: 'block' }}
      tabIndex={0}
    />
  );
}

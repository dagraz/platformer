import { useRef, useEffect } from 'react';
import { TileMap } from '../engine/TileMap';
import { InputManager } from '../engine/InputManager';
import { GameLoop } from '../engine/GameLoop';
import { updatePlayer } from '../engine/PlayerController';
import { defaultPhysics } from '../data/defaultPhysics';
import {
  CameraState,
  LevelData,
  Player,
  VIEWPORT_WIDTH,
  VIEWPORT_HEIGHT,
  TILE_SIZE,
} from '../engine/types';
import { render } from '../renderer/Renderer';

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

    let player: Player | null = null;
    const camera: CameraState = {
      currentScreen: '0,0',
      targetScreen: null,
      transitionProgress: 0,
      offsetX: 0,
      offsetY: 0,
    };

    fetch('/assets/levels/demo.json')
      .then(res => res.json())
      .then((levelData: LevelData) => {
        tileMap.load(levelData);

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
        };

        camera.currentScreen = start.screenKey;

        // Expose physics for console tuning (per build plan)
        (window as any).__physics = { ...defaultPhysics };

        inputManager.attach();

        gameLoop.setUpdateCallback(() => {
          if (!player) return;
          const input = inputManager.poll();
          const params = (window as any).__physics ?? defaultPhysics;
          player = updatePlayer(player, input, params, tileMap);

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
            };
          }
        });

        gameLoop.setRenderCallback(() => {
          render(ctx, tileMap, camera, player ?? undefined);
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

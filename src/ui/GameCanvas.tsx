import { useRef, useEffect } from 'react';
import { TileMap } from '../engine/TileMap';
import { CameraState, LevelData, VIEWPORT_WIDTH, VIEWPORT_HEIGHT } from '../engine/types';
import { render } from '../renderer/Renderer';

export function GameCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Load the demo level
    fetch('/assets/levels/demo.json')
      .then(res => res.json())
      .then((levelData: LevelData) => {
        const tileMap = new TileMap();
        tileMap.load(levelData);

        const camera: CameraState = {
          currentScreen: '0,0',
          targetScreen: null,
          transitionProgress: 0,
          offsetX: 0,
          offsetY: 0,
        };

        render(ctx, tileMap, camera);
      });
  }, []);

  return (
    <canvas
      ref={canvasRef}
      width={VIEWPORT_WIDTH}
      height={VIEWPORT_HEIGHT}
      style={{ border: '2px solid #444', display: 'block' }}
    />
  );
}

const FIXED_DT = 1000 / 60; // ~16.667ms per physics step

export class GameLoop {
  private running = false;
  private rafId: number | null = null;
  private accumulator = 0;
  private lastTime = 0;
  private updateFn: ((dt: number) => void) | null = null;
  private renderFn: ((interpolation: number) => void) | null = null;

  setUpdateCallback(fn: (dt: number) => void): void {
    this.updateFn = fn;
  }

  setRenderCallback(fn: (interpolation: number) => void): void {
    this.renderFn = fn;
  }

  start(): void {
    if (this.running) return;
    this.running = true;
    this.accumulator = 0;
    this.lastTime = performance.now();
    this.rafId = requestAnimationFrame(this.tick);
  }

  stop(): void {
    this.running = false;
    if (this.rafId !== null) {
      cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }
  }

  private tick = (now: number): void => {
    if (!this.running) return;

    let elapsed = now - this.lastTime;
    this.lastTime = now;

    // Clamp large gaps (e.g. tab was inactive) to prevent spiral of death
    if (elapsed > 200) elapsed = 200;

    this.accumulator += elapsed;

    // Fixed timestep physics updates
    while (this.accumulator >= FIXED_DT) {
      this.updateFn?.(FIXED_DT);
      this.accumulator -= FIXED_DT;
    }

    // Render with interpolation factor
    const interpolation = this.accumulator / FIXED_DT;
    this.renderFn?.(interpolation);

    this.rafId = requestAnimationFrame(this.tick);
  };
}

/**
 * SoundManager: plays game event sounds using Web Audio API.
 *
 * Uses synthesized oscillator tones as placeholder sounds so the game
 * works out of the box without audio files. Users can replace these
 * by dropping .mp3/.wav/.ogg files into public/assets/sounds/ and
 * calling load() with a sound map.
 */

type SoundDef = {
  buffer: AudioBuffer | null;
  synth: ((ctx: AudioContext, gain: GainNode) => void) | null;
};

export class SoundManager {
  private ctx: AudioContext | null = null;
  private masterGain: GainNode | null = null;
  private sounds: Record<string, SoundDef> = {};
  private muted = false;
  private volume = 0.5;

  constructor() {
    this.registerDefaults();
  }

  private ensureContext(): AudioContext {
    if (!this.ctx) {
      this.ctx = new AudioContext();
      this.masterGain = this.ctx.createGain();
      this.masterGain.gain.value = this.volume;
      this.masterGain.connect(this.ctx.destination);
    }
    if (this.ctx.state === 'suspended') {
      this.ctx.resume();
    }
    return this.ctx;
  }

  private registerDefaults(): void {
    // Jump: short rising tone
    this.sounds['jump'] = {
      buffer: null,
      synth: (ctx, gain) => {
        const osc = ctx.createOscillator();
        osc.type = 'square';
        osc.frequency.setValueAtTime(300, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(600, ctx.currentTime + 0.1);
        gain.gain.setValueAtTime(0.3, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.15);
        osc.connect(gain);
        osc.start();
        osc.stop(ctx.currentTime + 0.15);
      },
    };

    // Land: short low thud
    this.sounds['land'] = {
      buffer: null,
      synth: (ctx, gain) => {
        const osc = ctx.createOscillator();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(150, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(60, ctx.currentTime + 0.1);
        gain.gain.setValueAtTime(0.3, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.12);
        osc.connect(gain);
        osc.start();
        osc.stop(ctx.currentTime + 0.12);
      },
    };

    // Collect: bright two-tone chime
    this.sounds['coin'] = {
      buffer: null,
      synth: (ctx, gain) => {
        const osc1 = ctx.createOscillator();
        osc1.type = 'square';
        osc1.frequency.setValueAtTime(880, ctx.currentTime);
        gain.gain.setValueAtTime(0.2, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.2);
        osc1.connect(gain);
        osc1.start();
        osc1.stop(ctx.currentTime + 0.1);

        const osc2 = ctx.createOscillator();
        osc2.type = 'square';
        osc2.frequency.setValueAtTime(1320, ctx.currentTime + 0.08);
        const gain2 = ctx.createGain();
        gain2.gain.setValueAtTime(0.2, ctx.currentTime + 0.08);
        gain2.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.25);
        gain2.connect(this.masterGain!);
        osc2.connect(gain2);
        osc2.start(ctx.currentTime + 0.08);
        osc2.stop(ctx.currentTime + 0.25);
      },
    };

    // Screen transition: soft whoosh (noise-like)
    this.sounds['transition'] = {
      buffer: null,
      synth: (ctx, gain) => {
        const osc = ctx.createOscillator();
        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(200, ctx.currentTime);
        osc.frequency.exponentialRampToValueAtTime(100, ctx.currentTime + 0.3);
        gain.gain.setValueAtTime(0.1, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);
        osc.connect(gain);
        osc.start();
        osc.stop(ctx.currentTime + 0.3);
      },
    };

    // Goal: short fanfare (ascending arpeggio)
    this.sounds['goal'] = {
      buffer: null,
      synth: (ctx, gain) => {
        const notes = [523, 659, 784, 1047]; // C5, E5, G5, C6
        gain.gain.setValueAtTime(0.25, ctx.currentTime);
        gain.gain.setValueAtTime(0.25, ctx.currentTime + 0.4);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.8);
        notes.forEach((freq, i) => {
          const osc = ctx.createOscillator();
          osc.type = 'square';
          osc.frequency.value = freq;
          osc.connect(gain);
          osc.start(ctx.currentTime + i * 0.1);
          osc.stop(ctx.currentTime + i * 0.1 + 0.15);
        });
      },
    };
  }

  /**
   * Load audio files to replace synthesized defaults.
   * soundMap: { 'jump': '/assets/sounds/jump.mp3', ... }
   */
  async load(soundMap: Record<string, string>): Promise<void> {
    const ctx = this.ensureContext();
    const entries = Object.entries(soundMap);
    await Promise.all(entries.map(async ([name, url]) => {
      try {
        const response = await fetch(url);
        const arrayBuffer = await response.arrayBuffer();
        const buffer = await ctx.decodeAudioData(arrayBuffer);
        this.sounds[name] = { buffer, synth: null };
      } catch {
        // Keep existing synth fallback if file fails to load
      }
    }));
  }

  play(name: string): void {
    if (this.muted) return;
    const sound = this.sounds[name];
    if (!sound) return;

    const ctx = this.ensureContext();
    const gain = ctx.createGain();
    gain.connect(this.masterGain!);

    if (sound.buffer) {
      const source = ctx.createBufferSource();
      source.buffer = sound.buffer;
      source.connect(gain);
      gain.gain.value = 1;
      source.start();
    } else if (sound.synth) {
      sound.synth(ctx, gain);
    }
  }

  setVolume(v: number): void {
    this.volume = Math.max(0, Math.min(1, v));
    if (this.masterGain) {
      this.masterGain.gain.value = this.volume;
    }
  }

  setMute(muted: boolean): void {
    this.muted = muted;
  }

  isMuted(): boolean {
    return this.muted;
  }

  getVolume(): number {
    return this.volume;
  }
}

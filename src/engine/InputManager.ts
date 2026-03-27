import { InputState } from './types';

const KEY_MAP: Record<string, keyof Omit<InputState, 'jumpPressed'>> = {
  ArrowLeft:  'left',
  ArrowRight: 'right',
  ArrowUp:    'up',
  ArrowDown:  'down',
  ' ':        'jump',
};

export class InputManager {
  private held: Record<string, boolean> = {};
  private justPressed: Set<string> = new Set();
  private onKeyDown: (e: KeyboardEvent) => void;
  private onKeyUp: (e: KeyboardEvent) => void;

  constructor() {
    this.onKeyDown = (e: KeyboardEvent) => {
      if (KEY_MAP[e.key] !== undefined) {
        e.preventDefault();
        if (!this.held[e.key]) {
          this.justPressed.add(e.key);
        }
        this.held[e.key] = true;
      }
    };

    this.onKeyUp = (e: KeyboardEvent) => {
      if (KEY_MAP[e.key] !== undefined) {
        e.preventDefault();
        this.held[e.key] = false;
      }
    };
  }

  attach(): void {
    window.addEventListener('keydown', this.onKeyDown);
    window.addEventListener('keyup', this.onKeyUp);
  }

  detach(): void {
    window.removeEventListener('keydown', this.onKeyDown);
    window.removeEventListener('keyup', this.onKeyUp);
    this.held = {};
    this.justPressed.clear();
  }

  /** Returns current input state and clears edge-triggered flags. */
  poll(): InputState {
    const state: InputState = {
      left:        !!this.held['ArrowLeft'],
      right:       !!this.held['ArrowRight'],
      up:          !!this.held['ArrowUp'],
      down:        !!this.held['ArrowDown'],
      jump:        !!this.held[' '],
      jumpPressed: this.justPressed.has(' '),
    };
    this.justPressed.clear();
    return state;
  }
}

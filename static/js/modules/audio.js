/**
 * Interactive Web Audio Synthesizer module for premium tactile UI sounds.
 * Synthesizes click, success, and error tones entirely in-browser.
 */

const fabAudio = {
  ctx: null,

  init() {
    if (this.ctx) return;
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (AudioContext) {
      this.ctx = new AudioContext();
    }
  },

  playClick() {
    this.init();
    if (!this.ctx) return;
    if (this.ctx.state === 'suspended') this.ctx.resume();

    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();

    osc.connect(gain);
    gain.connect(this.ctx.destination);

    osc.type = 'sine';
    osc.frequency.setValueAtTime(900, this.ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(1300, this.ctx.currentTime + 0.04);

    gain.gain.setValueAtTime(0.02, this.ctx.currentTime); // very subtle
    gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + 0.04);

    osc.start();
    osc.stop(this.ctx.currentTime + 0.04);
  },

  playSuccess() {
    this.init();
    if (!this.ctx) return;
    if (this.ctx.state === 'suspended') this.ctx.resume();

    const now = this.ctx.currentTime;
    const playTone = (freq, time, duration) => {
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.type = 'sine';
      osc.frequency.setValueAtTime(freq, time);
      gain.gain.setValueAtTime(0.04, time);
      gain.gain.exponentialRampToValueAtTime(0.001, time + duration);
      osc.start(time);
      osc.stop(time + duration);
    };

    playTone(523.25, now, 0.12); // C5
    playTone(659.25, now + 0.06, 0.18); // E5
  },

  playError() {
    this.init();
    if (!this.ctx) return;
    if (this.ctx.state === 'suspended') this.ctx.resume();

    const now = this.ctx.currentTime;
    const playTone = (freq, time, duration) => {
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(freq, time);
      gain.gain.setValueAtTime(0.06, time);
      gain.gain.exponentialRampToValueAtTime(0.001, time + duration);
      osc.start(time);
      osc.stop(time + duration);
    };

    playTone(329.63, now, 0.12); // E4
    playTone(261.63, now + 0.08, 0.2); // C4
  }
};

export function initAudioModule() {
  // Bind global helpers
  window.playSuccessSound = () => fabAudio.playSuccess();
  window.playErrorSound = () => fabAudio.playError();
  window.playClickSound = () => fabAudio.playClick();

  // Play click on buttons and links
  document.addEventListener('click', (event) => {
    const el = event.target.closest('button, a, input[type="submit"], input[type="button"], .btn, .nav-link, .menu-item');
    if (el) {
      fabAudio.playClick();
    }
  }, { passive: true });
}

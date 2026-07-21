/**
 * Upgraded Web Audio Synthesizer module for FABOuanes.
 * Features an organic acoustic click sound (low-pass pluck envelope),
 * warm harmonic chimes, and a persisted mute/unmute state in localStorage.
 */

const fabAudio = {
  ctx: null,
  enabled: true,

  init() {
    // Load preference
    const stored = localStorage.getItem('fab_audio_enabled');
    this.enabled = stored !== 'false';

    if (this.ctx) return;
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (AudioContext) {
      this.ctx = new AudioContext();
    }
  },

  toggle() {
    this.init();
    this.enabled = !this.enabled;
    localStorage.setItem('fab_audio_enabled', String(this.enabled));
    this.updateUI();
    if (this.enabled) {
      this.playClick();
    }
  },

  updateUI() {
    const icon = document.getElementById('audioToggleIcon');
    const btn = document.getElementById('audioToggleBtnNavbar');
    if (icon) {
      if (this.enabled) {
        icon.className = 'bi bi-volume-up-fill';
        if (btn) btn.title = 'Effets sonores : Activés';
      } else {
        icon.className = 'bi bi-volume-mute-fill';
        if (btn) btn.title = 'Effets sonores : Désactivés';
      }
    }
  },

  playClick() {
    this.init();
    if (!this.enabled || !this.ctx) return;
    if (this.ctx.state === 'suspended') this.ctx.resume();

    const now = this.ctx.currentTime;
    
    // Create an organic click sound (softer pluck) using sine + low-pass filter
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();
    const filter = this.ctx.createBiquadFilter();

    osc.connect(filter);
    filter.connect(gain);
    gain.connect(this.ctx.destination);

    // lowpass filter makes it less harsh and more wooden
    filter.type = 'lowpass';
    filter.frequency.setValueAtTime(1000, now);
    filter.frequency.exponentialRampToValueAtTime(300, now + 0.05);

    osc.type = 'sine';
    osc.frequency.setValueAtTime(600, now);
    osc.frequency.exponentialRampToValueAtTime(150, now + 0.05);

    gain.gain.setValueAtTime(0.04, now); // smooth decay
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.05);

    osc.start(now);
    osc.stop(now + 0.05);
  },

  playSuccess() {
    this.init();
    if (!this.enabled || !this.ctx) return;
    if (this.ctx.state === 'suspended') this.ctx.resume();

    const now = this.ctx.currentTime;
    
    // Warm harmonic chord (major triad arpeggio)
    const playTone = (freq, time, duration) => {
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();
      osc.connect(gain);
      gain.connect(this.ctx.destination);
      
      osc.type = 'sine';
      osc.frequency.setValueAtTime(freq, time);
      
      gain.gain.setValueAtTime(0.05, time);
      gain.gain.exponentialRampToValueAtTime(0.001, time + duration);
      
      osc.start(time);
      osc.stop(time + duration);
    };

    playTone(523.25, now, 0.2);       // C5
    playTone(659.25, now + 0.05, 0.2);  // E5
    playTone(783.99, now + 0.1, 0.3);   // G5
  },

  playError() {
    this.init();
    if (!this.enabled || !this.ctx) return;
    if (this.ctx.state === 'suspended') this.ctx.resume();

    const now = this.ctx.currentTime;
    
    // Warm detuned/low warning tone
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

    playTone(220.00, now, 0.15); // A3
    playTone(196.00, now + 0.08, 0.25); // G3
  }
};

export function initAudioModule() {
  // Initialize state and update Navbar icon on startup
  fabAudio.init();
  fabAudio.updateUI();

  // Bind global helpers
  window.playSuccessSound = () => fabAudio.playSuccess();
  window.playErrorSound = () => fabAudio.playError();
  window.playClickSound = () => fabAudio.playClick();
  window.toggleFabAudio = () => fabAudio.toggle();

  // Attach navbar toggle button event
  const toggleBtn = document.getElementById('audioToggleBtnNavbar');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      fabAudio.toggle();
    });
  }

  // Play click on buttons and links
  document.addEventListener('click', (event) => {
    const el = event.target.closest('button, a, input[type="submit"], input[type="button"], .btn, .nav-link, .menu-item');
    // Don't play default click sound on the audio toggle button itself to avoid double sounds
    if (el && el.id !== 'audioToggleBtnNavbar') {
      fabAudio.playClick();
    }
  }, { passive: true });
}

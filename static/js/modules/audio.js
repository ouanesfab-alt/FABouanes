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

  playClick(style = 'soft') {
    this.init();
    if (!this.enabled || !this.ctx) return;
    if (this.ctx.state === 'suspended') this.ctx.resume();

    const now = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();
    const filter = this.ctx.createBiquadFilter();

    osc.connect(filter);
    filter.connect(gain);
    gain.connect(this.ctx.destination);

    filter.type = 'lowpass';

    if (style === 'crisp') {
      // Glassy/metallic snap for primary action/save buttons
      filter.frequency.setValueAtTime(1600, now);
      filter.frequency.exponentialRampToValueAtTime(500, now + 0.04);
      osc.type = 'triangle';
      osc.frequency.setValueAtTime(800, now);
      osc.frequency.exponentialRampToValueAtTime(300, now + 0.04);
      gain.gain.setValueAtTime(0.03, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.04);
      osc.start(now);
      osc.stop(now + 0.04);
    } else if (style === 'warning') {
      // Dull rubbery thud for destructive or cancel actions
      filter.frequency.setValueAtTime(400, now);
      filter.frequency.exponentialRampToValueAtTime(100, now + 0.08);
      osc.type = 'sine';
      osc.frequency.setValueAtTime(220, now);
      osc.frequency.exponentialRampToValueAtTime(60, now + 0.08);
      gain.gain.setValueAtTime(0.05, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.08);
      osc.start(now);
      osc.stop(now + 0.08);
    } else {
      // Default soft organic wooden pop for general clicks
      filter.frequency.setValueAtTime(900, now);
      filter.frequency.exponentialRampToValueAtTime(250, now + 0.03);
      osc.type = 'sine';
      osc.frequency.setValueAtTime(500, now);
      osc.frequency.exponentialRampToValueAtTime(120, now + 0.03);
      gain.gain.setValueAtTime(0.02, now);
      gain.gain.exponentialRampToValueAtTime(0.001, now + 0.03);
      osc.start(now);
      osc.stop(now + 0.03);
    }
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
  window.playClickSound = (style) => fabAudio.playClick(style);
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
      let style = 'soft';
      
      // Determine click style based on button classification/color/action
      if (
        el.classList.contains('btn-primary') || 
        el.classList.contains('btn-success') || 
        el.type === 'submit' ||
        el.id === 'globalSearchBtn' ||
        el.classList.contains('btn-save')
      ) {
        style = 'crisp';
      } else if (
        el.classList.contains('btn-danger') || 
        el.classList.contains('text-danger') || 
        el.classList.contains('btn-outline-danger') ||
        el.classList.contains('mac-modal-close')
      ) {
        style = 'warning';
      }
      
      fabAudio.playClick(style);
    }
  }, { passive: true });
}

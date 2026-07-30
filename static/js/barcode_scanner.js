/**
 * FABOuanes — Camera Barcode Scanner Module
 * Uses Html5Qrcode to scan EAN-13, EAN-8, CODE-128, QR codes from mobile or PC camera.
 */

let html5QrcodeScanner = null;
let activeTargetCallback = null;

// Dynamically load html5-qrcode library if not present
function loadHtml5QrcodeLibrary() {
  return new Promise((resolve, reject) => {
    if (window.Html5Qrcode) {
      return resolve();
    }
    const script = document.createElement('script');
    script.src = 'https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js';
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Impossible de charger la bibliothèque de scan de code-barres."));
    document.head.appendChild(script);
  });
}

/**
 * Open the camera barcode scanner modal and call `onSuccessCallback(scannedCode)` when detected.
 * @param {Function} onSuccessCallback - Callback receiving the decoded string.
 */
export async function openBarcodeScanner(onSuccessCallback) {
  activeTargetCallback = onSuccessCallback;
  const modalEl = document.getElementById('barcodeScannerModal');
  if (!modalEl) {
    console.error("Barcode scanner modal not found in DOM.");
    return;
  }

  const bsModal = bootstrap.Modal.getOrCreateInstance(modalEl);
  bsModal.show();

  const feedbackEl = document.getElementById('barcodeScanFeedback');
  if (feedbackEl) {
    feedbackEl.textContent = "Initialisation de la caméra...";
    feedbackEl.className = "mt-2 text-muted small fw-medium";
  }

  try {
    await loadHtml5QrcodeLibrary();
  } catch (err) {
    if (feedbackEl) {
      feedbackEl.textContent = "Erreur: Connexion Internet requise pour le premier chargement du scanner.";
      feedbackEl.className = "mt-2 text-danger small fw-medium";
    }
    return;
  }

  startCameraScanner();
}

async function startCameraScanner() {
  const feedbackEl = document.getElementById('barcodeScanFeedback');
  try {
    if (html5QrcodeScanner) {
      try { await html5QrcodeScanner.stop(); } catch (e) {}
    }

    html5QrcodeScanner = new Html5Qrcode("barcodeReader");
    const config = {
      fps: 15,
      qrbox: { width: 250, height: 120 },
      aspectRatio: 1.777778
    };

    await html5QrcodeScanner.start(
      { facingMode: "environment" }, // Prefer back camera on mobile
      config,
      onBarcodeDetected,
      () => {} // Ignored frame scan errors
    );

    if (feedbackEl) {
      feedbackEl.textContent = "Caméra active — Orientez vers le code-barres";
      feedbackEl.className = "mt-2 text-success small fw-medium";
    }
  } catch (err) {
    console.warn("Camera start failed, trying any camera:", err);
    try {
      await html5QrcodeScanner.start(
        { facingMode: "user" },
        { fps: 10, qrbox: { width: 250, height: 120 } },
        onBarcodeDetected,
        () => {}
      );
    } catch (err2) {
      if (feedbackEl) {
        feedbackEl.textContent = "Accès caméra refusé ou indisponible. Utilisez la saisie manuelle ci-dessous.";
        feedbackEl.className = "mt-2 text-warning small fw-medium";
      }
    }
  }
}

export async function stopBarcodeScanner() {
  if (html5QrcodeScanner) {
    try {
      await html5QrcodeScanner.stop();
      html5QrcodeScanner.clear();
    } catch (e) {}
    html5QrcodeScanner = null;
  }
}

function onBarcodeDetected(decodedText, decodedResult) {
  // Beep feedback using Web Audio API
  playScanBeep();

  // Vibrational feedback on mobile
  if (navigator.vibrate) {
    navigator.vibrate(100);
  }

  const feedbackEl = document.getElementById('barcodeScanFeedback');
  if (feedbackEl) {
    feedbackEl.textContent = `Code décelé : ${decodedText}`;
    feedbackEl.className = "mt-2 text-success fw-bold small";
  }

  stopBarcodeScanner();

  // Hide modal
  const modalEl = document.getElementById('barcodeScannerModal');
  if (modalEl) {
    const bsModal = bootstrap.Modal.getInstance(modalEl);
    if (bsModal) bsModal.hide();
  }

  if (typeof activeTargetCallback === 'function') {
    activeTargetCallback(decodedText.trim());
  }
}

function playScanBeep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(880, ctx.currentTime); // 880Hz A5 pitch
    gain.gain.setValueAtTime(0.15, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.15);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.15);
  } catch (e) {}
}

// Manual fallback listener
document.addEventListener('DOMContentLoaded', () => {
  const manualBtn = document.getElementById('submitManualBarcodeBtn');
  const manualInput = document.getElementById('manualBarcodeInput');
  if (manualBtn && manualInput) {
    const triggerManual = () => {
      const val = manualInput.value.trim();
      if (val && typeof activeTargetCallback === 'function') {
        onBarcodeDetected(val, null);
        manualInput.value = '';
      }
    };
    manualBtn.addEventListener('click', triggerManual);
    manualInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        triggerManual();
      }
    });
  }
});

// Make available globally
window.openBarcodeScanner = openBarcodeScanner;
window.stopBarcodeScanner = stopBarcodeScanner;

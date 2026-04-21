const STORAGE_KEYS = {
  serverUrl: "fab_mobile_server_url",
};

const appNode = document.getElementById("app");

const state = {
  serverUrl: normalizeUrl(localStorage.getItem(STORAGE_KEYS.serverUrl) || ""),
  serverDraft: normalizeUrl(localStorage.getItem(STORAGE_KEYS.serverUrl) || ""),
  banner: null,
  connectionStatus: navigator.onLine ? "online" : "offline",
  qrScannerOpen: false,
  testing: false,
};

const qrScanner = {
  detector: null,
  stream: null,
  rafId: 0,
  lastValue: "",
};

class ApiError extends Error {
  constructor(message) {
    super(message);
    this.name = "ApiError";
  }
}

function normalizeUrl(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  if (!/^https?:\/\//i.test(raw)) {
    return `http://${raw}`;
  }
  return raw.replace(/\/+$/, "");
}

function setupRequested() {
  try {
    return new URLSearchParams(window.location.search).get("setup") === "1";
  } catch {
    return false;
  }
}

function fullAppUrl(path = "/login") {
  const target = new URL(normalizeUrl(state.serverUrl));
  target.pathname = path.startsWith("/") ? path : `/${path}`;
  target.searchParams.set("mobile_shell", "1");
  return target.toString();
}

function openFullApp(path = "/login") {
  if (!state.serverUrl) {
    setBanner("Enregistre d'abord l'URL du serveur.", "warning");
    return;
  }
  window.location.replace(fullAppUrl(path));
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function extractServerUrl(rawValue) {
  const raw = String(rawValue || "").trim();
  if (!raw) return "";

  const candidates = [raw];
  const embeddedHttp = raw.match(/https?:\/\/[^\s"'<>]+/i);
  if (embeddedHttp) {
    candidates.push(embeddedHttp[0]);
  }

  if (/^fabouanes?:\/\//i.test(raw)) {
    try {
      const customUrl = new URL(raw);
      const nestedUrl =
        customUrl.searchParams.get("url")
        || customUrl.searchParams.get("server")
        || customUrl.searchParams.get("server_url")
        || "";
      if (nestedUrl) {
        candidates.push(nestedUrl);
      }
    } catch {
      // ignored
    }
  }

  if (raw.startsWith("{")) {
    try {
      const parsed = JSON.parse(raw);
      const nestedUrl = parsed.url || parsed.server || parsed.server_url || "";
      if (nestedUrl) {
        candidates.push(String(nestedUrl));
      }
    } catch {
      // ignored
    }
  }

  for (const candidate of candidates) {
    try {
      const normalized = normalizeUrl(candidate);
      const parsed = new URL(normalized);
      if (parsed.protocol === "http:" || parsed.protocol === "https:") {
        return parsed.toString().replace(/\/+$/, "");
      }
    } catch {
      // ignored
    }
  }

  return "";
}

function setBanner(message, kind = "info") {
  state.banner = message ? { message, kind } : null;
  render();
}

function setScannerStatus(message, kind = "info") {
  const node = document.getElementById("scannerStatus");
  if (node) {
    node.textContent = message;
    node.dataset.kind = kind;
  }
}

function saveServerUrl(url) {
  const normalized = normalizeUrl(url);
  if (!normalized) {
    throw new ApiError("Saisis l'URL du serveur FABOuanes.");
  }
  state.serverUrl = normalized;
  state.serverDraft = normalized;
  localStorage.setItem(STORAGE_KEYS.serverUrl, normalized);
}

async function testServerConnection() {
  if (!state.serverDraft) {
    setBanner("Saisis ou scanne d'abord l'URL du serveur.", "warning");
    return;
  }

  const candidate = normalizeUrl(state.serverDraft);
  state.testing = true;
  render();

  try {
    const pingUrl = new URL("/api/v1/ping", `${candidate}/`);
    const response = await fetch(pingUrl.toString(), {
      method: "GET",
      headers: { Accept: "application/json" },
    });
    if (!response.ok) {
      throw new ApiError("Le serveur repond avec une erreur.");
    }
    saveServerUrl(candidate);
    setBanner("Connexion valide. L'application complete peut maintenant s'ouvrir.", "success");
  } catch (error) {
    const message = error instanceof Error ? error.message : "Connexion impossible.";
    setBanner(`${message} Verifie l'URL, le reseau local et que le pare-feu Windows autorise l'application.`, "error");
  } finally {
    state.testing = false;
    render();
  }
}

function renderBanner() {
  if (!state.banner) return "";
  return `
    <div class="banner is-${escapeHtml(state.banner.kind)}">
      ${escapeHtml(state.banner.message)}
    </div>
  `;
}

function renderFullAppLauncher() {
  const statusLabel = state.connectionStatus === "online" ? "Appareil en ligne" : "Appareil hors ligne";
  const statusClass = state.connectionStatus === "online" ? "" : " is-offline";
  const serverLabel = state.serverUrl || "Aucun serveur enregistre";
  return `
    <section class="card hero-card">
      <div class="brand-row">
        <div class="brand-logo">
          <img src="./logo-shield.png" alt="FABOuanes">
        </div>
        <div class="brand-copy">
          <span class="eyebrow">FABOuanes Mobile</span>
          <h1>Configuration reseau et ouverture de l'application complete</h1>
          <p>Ce client Android sert a enregistrer l'URL du serveur, scanner un QR puis ouvrir l'application complete dans la WebView mobile.</p>
        </div>
        <span class="status-pill${statusClass}">${escapeHtml(statusLabel)}</span>
      </div>
      ${renderBanner()}
      <div class="server-summary">
        <span class="server-summary-label">Serveur actif</span>
        <strong>${escapeHtml(serverLabel)}</strong>
      </div>
    </section>
  `;
}

function renderScannerModal() {
  if (!state.qrScannerOpen) return "";
  return `
    <div class="scanner-modal" id="scannerModal" role="dialog" aria-modal="true" aria-labelledby="scannerTitle">
      <div class="scanner-sheet">
        <div class="scanner-header">
          <div>
            <span class="eyebrow">Scan QR</span>
            <h2 id="scannerTitle">Scanner QR de l'URL</h2>
            <p>Le QR peut contenir directement une URL HTTP(S) ou un lien de type <code>fabouanes://server</code>.</p>
          </div>
          <button type="button" class="icon-btn" data-action="close-scanner" aria-label="Fermer le scanner">&times;</button>
        </div>
        <div class="scanner-preview">
          <video id="qrScannerVideo" autoplay playsinline muted></video>
          <div class="scanner-frame" aria-hidden="true"></div>
        </div>
        <p class="scanner-status" id="scannerStatus" data-kind="info">Initialisation de la camera...</p>
      </div>
    </div>
  `;
}

function render() {
  appNode.innerHTML = `
    <main class="setup-shell">
      ${renderFullAppLauncher()}

      <section class="card config-card">
        <div class="section-head">
          <div>
            <span class="eyebrow">Serveur</span>
            <h2>Configurer l'acces reseau</h2>
            <p>Entre l'URL du serveur FABOuanes, puis ouvre l'application complete. Toutes les operations restent synchronisees avec le serveur.</p>
          </div>
        </div>
        <form id="serverForm" class="field-grid">
          <label class="field" for="serverUrlInput">
            <span>URL du serveur</span>
            <input
              id="serverUrlInput"
              class="text-input"
              type="url"
              inputmode="url"
              autocomplete="off"
              placeholder="http://192.168.1.50:5000"
              value="${escapeHtml(state.serverDraft)}"
            >
          </label>
          <div class="action-row">
            <button type="submit" class="primary-btn">Enregistrer</button>
            <button type="button" class="secondary-btn" data-action="test-server">${state.testing ? "Test..." : "Tester le serveur"}</button>
            <button type="button" class="ghost-btn" data-action="open-scanner">Scanner QR de l'URL</button>
          </div>
        </form>
      </section>

      <section class="card launch-card">
        <div class="section-head">
          <div>
            <span class="eyebrow">Ouverture</span>
            <h2>Lancer l'application complete</h2>
            <p>Une fois l'URL enregistree, FABOuanes Mobile ouvre l'application complete. La base et les donnees restent synchronisees avec le serveur.</p>
          </div>
        </div>
        <div class="action-row">
          <button type="button" class="primary-btn" data-action="open-app">Ouvrir l'application complete</button>
          <button type="button" class="ghost-btn" data-action="reset-server">Effacer l'URL</button>
        </div>
      </section>

      <section class="card tips-card">
        <div class="section-head">
          <div>
            <span class="eyebrow">Conseils</span>
            <h2>Checklist reseau</h2>
          </div>
        </div>
        <ul class="tips-list">
          <li>Le PC et le telephone doivent etre sur le meme Wi-Fi.</li>
          <li>Le QR peut contenir une URL brute ou un lien personnalise FABOuanes.</li>
          <li>Si le test echoue, verifie que le pare-feu Windows autorise l'application et Python/Waitress.</li>
          <li>Ajoute <code>?setup=1</code> a l'URL locale du wrapper pour revenir sur cet ecran.</li>
        </ul>
      </section>
    </main>
    ${renderScannerModal()}
  `;

  const serverInput = document.getElementById("serverUrlInput");
  const serverForm = document.getElementById("serverForm");

  serverInput?.addEventListener("input", (event) => {
    state.serverDraft = event.target.value;
  });

  serverForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    try {
      saveServerUrl(state.serverDraft);
      setBanner("URL du serveur enregistree.", "success");
    } catch (error) {
      const message = error instanceof Error ? error.message : "URL invalide.";
      setBanner(message, "error");
    }
  });

  appNode.querySelector('[data-action="test-server"]')?.addEventListener("click", () => {
    testServerConnection();
  });

  appNode.querySelector('[data-action="open-app"]')?.addEventListener("click", () => {
    try {
      saveServerUrl(state.serverDraft || state.serverUrl);
      openFullApp("/login");
    } catch (error) {
      const message = error instanceof Error ? error.message : "URL invalide.";
      setBanner(message, "error");
    }
  });

  appNode.querySelector('[data-action="open-scanner"]')?.addEventListener("click", () => {
    state.qrScannerOpen = true;
    render();
  });

  appNode.querySelector('[data-action="reset-server"]')?.addEventListener("click", () => {
    stopQrScanner();
    state.serverUrl = "";
    state.serverDraft = "";
    localStorage.removeItem(STORAGE_KEYS.serverUrl);
    setBanner("URL du serveur supprimee.", "warning");
  });

  document.querySelector('[data-action="close-scanner"]')?.addEventListener("click", () => {
    stopQrScanner();
    state.qrScannerOpen = false;
    render();
  });

  if (state.qrScannerOpen) {
    queueMicrotask(() => {
      startQrScanner();
    });
  }
}

async function startQrScanner() {
  const video = document.getElementById("qrScannerVideo");
  if (!video || qrScanner.stream) return;

  if (!("BarcodeDetector" in window)) {
    setScannerStatus("BarcodeDetector indisponible sur cet appareil. Saisis l'URL manuellement.", "error");
    return;
  }

  try {
    qrScanner.detector = qrScanner.detector || new BarcodeDetector({ formats: ["qr_code"] });
    qrScanner.stream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: { facingMode: { ideal: "environment" } },
    });
    video.srcObject = qrScanner.stream;
    await video.play();
    setScannerStatus("Scanner actif. Place le QR dans le cadre.", "success");
    scanQrFrame();
  } catch (error) {
    const message = error instanceof Error ? error.message : "Camera inaccessible.";
    setScannerStatus(`${message} Verifie les permissions camera.`, "error");
  }
}

async function scanQrFrame() {
  const video = document.getElementById("qrScannerVideo");
  if (!video || !qrScanner.detector || !state.qrScannerOpen) return;

  try {
    const codes = await qrScanner.detector.detect(video);
    if (codes.length > 0) {
      const rawValue = String(codes[0].rawValue || "").trim();
      if (rawValue && rawValue !== qrScanner.lastValue) {
        qrScanner.lastValue = rawValue;
        const serverUrl = extractServerUrl(rawValue);
        if (!serverUrl) {
          setScannerStatus("QR detecte, mais aucune URL serveur valide n'a ete trouvee.", "error");
        } else {
          saveServerUrl(serverUrl);
          setScannerStatus(`Serveur detecte: ${serverUrl}`, "success");
          stopQrScanner();
          state.qrScannerOpen = false;
          setBanner("Serveur enregistre depuis le QR. Ouverture de l'application complete...", "success");
          window.setTimeout(() => openFullApp("/login"), 220);
          return;
        }
      }
    }
  } catch {
    // ignored while the stream is warming up
  }

  qrScanner.rafId = window.requestAnimationFrame(scanQrFrame);
}

function stopQrScanner() {
  if (qrScanner.rafId) {
    window.cancelAnimationFrame(qrScanner.rafId);
    qrScanner.rafId = 0;
  }
  if (qrScanner.stream) {
    qrScanner.stream.getTracks().forEach((track) => track.stop());
    qrScanner.stream = null;
  }
  qrScanner.lastValue = "";
}

function bootstrap() {
  if (state.serverUrl && !setupRequested()) {
    openFullApp("/login");
    return;
  }
  render();
}

window.addEventListener("online", () => {
  state.connectionStatus = "online";
  render();
});

window.addEventListener("offline", () => {
  state.connectionStatus = "offline";
  render();
});

window.addEventListener("beforeunload", stopQrScanner);

bootstrap();

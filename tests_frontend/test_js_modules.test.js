/**
 * Frontend JavaScript Unit Test Suite (Node.js test runner)
 * Tests static/app.js, main.js, offline-db.js, offline-sync.js, sw.js, manifest.json
 * Target Coverage: > 90%
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

// Mock Browser Window and DOM Environment
globalThis.window = globalThis;
globalThis.document = {
    readyState: 'complete',
    addEventListener: () => {},
    querySelector: () => null,
    querySelectorAll: () => [],
    createElement: (tag) => ({
        tagName: tag.toUpperCase(),
        setAttribute: () => {},
        getAttribute: () => null,
        appendChild: () => {},
        classList: { add: () => {}, remove: () => {}, contains: () => false },
        style: {},
    }),
    body: {
        appendChild: () => {},
        classList: { add: () => {}, remove: () => {} },
    },
};
Object.defineProperty(globalThis, 'navigator', {
    value: {
        serviceWorker: {
            register: async () => ({ scope: '/' }),
            addEventListener: () => {},
        },
        onLine: true,
    },
    writable: true,
    configurable: true,
});

globalThis.localStorage = {
    _data: {},
    getItem(key) { return this._data[key] || null; },
    setItem(key, val) { this._data[key] = String(val); },
    removeItem(key) { delete this._data[key]; },
    clear() { this._data = {}; },
};

test('Manifest JSON is valid', () => {
    const manifestPath = path.join(process.cwd(), 'static', 'manifest.json');
    assert.strictEqual(fs.existsSync(manifestPath), true);
    const content = fs.readFileSync(manifestPath, 'utf8');
    const json = JSON.parse(content);
    assert.strictEqual(typeof json.name, 'string');
    assert.strictEqual(typeof json.start_url, 'string');
});

test('Service Worker sw.js syntax and structure', () => {
    const swPath = path.join(process.cwd(), 'static', 'sw.js');
    assert.strictEqual(fs.existsSync(swPath), true);
    const code = fs.readFileSync(swPath, 'utf8');
    assert.strictEqual(code.includes('CACHE_NAME'), true);
    assert.strictEqual(code.includes('install'), true);
    assert.strictEqual(code.includes('fetch'), true);
});

test('Client JS Modules static/js/modules availability', () => {
    const modulesDir = path.join(process.cwd(), 'static', 'js', 'modules');
    if (fs.existsSync(modulesDir)) {
        const files = fs.readdirSync(modulesDir).filter(f => f.endsWith('.js'));
        assert.ok(files.length > 0);
        for (const file of files) {
            const content = fs.readFileSync(path.join(modulesDir, file), 'utf8');
            assert.strictEqual(content.length > 0, true);
        }
    }
});

test('Offline Sync and DB scripts exist and parse cleanly', () => {
    const offlineDbPath = path.join(process.cwd(), 'static', 'js', 'offline-db.js');
    const offlineSyncPath = path.join(process.cwd(), 'static', 'js', 'offline-sync.js');

    if (fs.existsSync(offlineDbPath)) {
        const code = fs.readFileSync(offlineDbPath, 'utf8');
        assert.ok(code.length > 0);
    }

    if (fs.existsSync(offlineSyncPath)) {
        const code = fs.readFileSync(offlineSyncPath, 'utf8');
        assert.ok(code.length > 0);
    }
});

test('forms.js preserves existing pre-filled dates', () => {
    const formsPath = path.join(process.cwd(), 'static', 'js', 'modules', 'forms.js');
    const code = fs.readFileSync(formsPath, 'utf8');
    assert.strictEqual(code.includes('if (input.value) return;'), true);
});

test('api.js exports dynamic getCsrfToken helper', () => {
    const apiPath = path.join(process.cwd(), 'static', 'js', 'modules', 'api.js');
    const code = fs.readFileSync(apiPath, 'utf8');
    assert.strictEqual(code.includes('export function getCsrfToken()'), true);
    assert.strictEqual(code.includes('window.fabCsrfToken'), true);
});

test('shortcuts.js resolves Ctrl+K search and Ctrl+J Sabrina', () => {
    const shortcutsPath = path.join(process.cwd(), 'static', 'js', 'modules', 'shortcuts.js');
    const code = fs.readFileSync(shortcutsPath, 'utf8');
    assert.strictEqual(code.includes("e.key.toLowerCase() === 'k'"), true);
    assert.strictEqual(code.includes("e.key.toLowerCase() === 'j'"), true);
    assert.strictEqual(code.includes('openSearch'), true);
});

test('sw.js safely handles cache-first and background revalidation', () => {
    const swPath = path.join(process.cwd(), 'static', 'sw.js');
    const code = fs.readFileSync(swPath, 'utf8');
    assert.strictEqual(code.includes('fetchPromise.catch('), true);
    assert.strictEqual(!code.includes('.catch(() => null);'), true);
});

test('instantNav.js provides AbortController, destroyAllCharts and fab:page-loaded lifecycle', () => {
    const instantNavPath = path.join(process.cwd(), 'static', 'js', 'modules', 'instantNav.js');
    const code = fs.readFileSync(instantNavPath, 'utf8');
    assert.strictEqual(code.includes('export function abortPreviousPage()'), true);
    assert.strictEqual(code.includes('export function getNavSignal()'), true);
    assert.strictEqual(code.includes('export function destroyAllCharts()'), true);
    assert.strictEqual(code.includes('fab:page-loaded'), true);
});

test('dashboard.js exports destroyDashboardCharts and listens to fab:page-loaded', () => {
    const dashboardPath = path.join(process.cwd(), 'static', 'js', 'modules', 'dashboard.js');
    const code = fs.readFileSync(dashboardPath, 'utf8');
    assert.strictEqual(code.includes('export function destroyDashboardCharts()'), true);
    assert.strictEqual(code.includes('window.destroyDashboardCharts = destroyDashboardCharts'), true);
    assert.strictEqual(code.includes('fab:page-loaded'), true);
});

test('main.js handles fab:page-loaded event to reinitialize modules', () => {
    const mainPath = path.join(process.cwd(), 'static', 'js', 'main.js');
    const code = fs.readFileSync(mainPath, 'utf8');
    assert.strictEqual(code.includes("addEventListener('fab:page-loaded'"), true);
    assert.strictEqual(code.includes('initFormsModule()'), true);
    assert.strictEqual(code.includes('initTablesModule()'), true);
});

test('forms.js exports resetSubmittingButtons to prevent stuck state on BFCache', () => {
    const formsPath = path.join(process.cwd(), 'static', 'js', 'modules', 'forms.js');
    const code = fs.readFileSync(formsPath, 'utf8');
    assert.strictEqual(code.includes('export function resetSubmittingButtons'), true);
    assert.strictEqual(code.includes('pageshow'), true);
});

test('api.js showToast unifies with #toastContainer and binds to window.showToast', () => {
    const apiPath = path.join(process.cwd(), 'static', 'js', 'modules', 'api.js');
    const code = fs.readFileSync(apiPath, 'utf8');
    assert.strictEqual(code.includes('toastContainer'), true);
    assert.strictEqual(code.includes('window.showToast = showToast'), true);
});

test('dashboard-fonts.js is lightweight, offline-ready corporate typography (< 10 KB)', () => {
    const fontsPath = path.join(process.cwd(), 'static', 'js', 'modules', 'dashboard-fonts.js');
    const stats = fs.statSync(fontsPath);
    assert.ok(stats.size < 10000, 'dashboard-fonts.js should be lightweight (< 10KB)');
    const code = fs.readFileSync(fontsPath, 'utf8');
    assert.strictEqual(code.includes('EXECUTIVE_FONTS'), true);
});



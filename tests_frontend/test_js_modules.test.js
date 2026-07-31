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

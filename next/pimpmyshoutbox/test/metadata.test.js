import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const metadata = await readFile(new URL('../metadata.user.js', import.meta.url), 'utf8');
const header = metadata.match(/^\/\/ ==UserScript==\n([\s\S]*?)^\/\/ ==\/UserScript==/m)?.[1] ?? '';
const entries = [...header.matchAll(/^\/\/\s*@(\S+)\s+(.*)$/gm)].map(([, key, value]) => [key, value.trim()]);
const valuesOf = key => entries.filter(([entryKey]) => entryKey === key).map(([, value]) => value);

const SINGLETON_KEYS = [
    'name', 'namespace', 'version', 'description', 'author', 'icon',
    'homepageURL', 'supportURL', 'updateURL', 'downloadURL', 'run-at',
];
const BASE = 'https://raw.githubusercontent.com/SaltedButch/tr4ker-scripting/userscripts/';

test('metadata block is present and declares the required keys', () => {
    assert.ok(header, 'metadata.user.js must contain a userscript header');
    for (const key of ['name', 'version', 'description', 'match']) {
        assert.ok(valuesOf(key).length > 0, `@${key} is missing`);
    }
});

test('singleton metadata keys are declared exactly once', () => {
    for (const key of SINGLETON_KEYS) {
        assert.ok(valuesOf(key).length <= 1, `@${key} is declared ${valuesOf(key).length} times`);
    }
});

test('version is numeric and update/download URLs stay stable', () => {
    assert.match(valuesOf('version')[0], /^\d+(?:\.\d+)*$/);
    assert.deepEqual(valuesOf('updateURL'), [`${BASE}pimpmyshoutbox-next.meta.js`]);
    assert.deepEqual(valuesOf('downloadURL'), [`${BASE}pimpmyshoutbox-next.user.js`]);
});

test('every @connect host is a bare hostname', () => {
    for (const host of valuesOf('connect')) {
        assert.match(host, /^[a-z0-9.-]+$/i, `unexpected @connect value: ${host}`);
    }
});

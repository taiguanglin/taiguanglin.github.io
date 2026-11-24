import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

// This repository has no package.json declaring the JavaScript module type.
// Load the browser module through a data URL so this test works with plain
// `node --test` without changing the site's module loading semantics.
const source = await readFile(new URL('../assets/review_status.js', import.meta.url), 'utf8');
const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`;
const { areAllItemsConfirmed } = await import(moduleUrl);

test('an empty list is not a confirmed lecture', () => {
    assert.equal(areAllItemsConfirmed([]), false);
    assert.equal(areAllItemsConfirmed(null), false);
});

test('played items are confirmed', () => {
    assert.equal(areAllItemsConfirmed([
        { meta: { lastPlayed: '2026-11-24 15:00' } },
        { meta: { lastPlayed: true } },
    ]), true);
});

test('zero-length items count as confirmed', () => {
    assert.equal(areAllItemsConfirmed([
        { meta: { lastPlayed: '2026-11-24 15:00' } },
        { zero: true },
    ]), true);
});

test('one unconfirmed item prevents lecture completion', () => {
    assert.equal(areAllItemsConfirmed([
        { meta: { lastPlayed: '2026-11-24 15:00' } },
        { meta: {} },
    ]), false);
});

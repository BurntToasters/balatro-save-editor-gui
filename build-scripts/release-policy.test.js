'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const { assertStableReleaseOverridesAllowed, isStableReleaseVersion } = require('./release-policy');

test('only plain x.y.z counts as stable', () => {
  assert.equal(isStableReleaseVersion('1.0.0'), true);
  assert.equal(isStableReleaseVersion('1.0.0-beta.1'), false);
  assert.equal(isStableReleaseVersion('01.0.0'), false);
});

test('stable releases refuse SKIP_WIN_CODESIGN', () => {
  assert.throws(() => assertStableReleaseOverridesAllowed({ SKIP_WIN_CODESIGN: '1' }, '1.0.0'), /refuses SKIP_WIN_CODESIGN/);
  assert.throws(() => assertStableReleaseOverridesAllowed({ SKIP_WIN_CODESIGN: 'true' }, '1.0.0'), /refuses/);
  assert.doesNotThrow(() => assertStableReleaseOverridesAllowed({ SKIP_WIN_CODESIGN: '0' }, '1.0.0'));
  assert.doesNotThrow(() => assertStableReleaseOverridesAllowed({}, '1.0.0'));
});

test('betas may skip signing', () => {
  assert.doesNotThrow(() => assertStableReleaseOverridesAllowed({ SKIP_WIN_CODESIGN: '1' }, '1.1.0-beta.1'));
});

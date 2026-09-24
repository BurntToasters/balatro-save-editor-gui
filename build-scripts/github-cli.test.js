'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const {
  githubApiArgs,
  githubCliEnvironment,
  githubStatusCode,
  releaseAssetUploadArgs,
} = require('./github-cli');

test('gh uses its stored login, never token env vars', () => {
  assert.deepEqual(githubCliEnvironment({ PATH: '/bin', GH_TOKEN: 'old', GITHUB_TOKEN: 'old-too' }), { PATH: '/bin' });
});

test('API calls pass the method, endpoint and a stdin body', () => {
  assert.deepEqual(githubApiArgs('GET', '/repos/o/r/releases'), ['api', '--method', 'GET', '/repos/o/r/releases']);
  assert.deepEqual(githubApiArgs('POST', '/repos/o/r/releases', true), [
    'api',
    '--method',
    'POST',
    '/repos/o/r/releases',
    '--input',
    '-',
  ]);
});

test('HTTP status is recovered from gh error output', () => {
  assert.equal(githubStatusCode('gh: Not Found (HTTP 404)'), 404);
  assert.equal(githubStatusCode('unexpected status code 503'), 503);
  assert.equal(githubStatusCode('connection reset'), undefined);
});

test('uploads go only to the GitHub uploads host with the file name and type', () => {
  const args = releaseAssetUploadArgs(
    'https://uploads.github.com/repos/o/r/releases/1/assets{?name,label}',
    '/tmp/release/SHA256SUMS-win-x64.txt',
  );
  assert.deepEqual(args.slice(0, 4), [
    'api',
    '--method',
    'POST',
    'https://uploads.github.com/repos/o/r/releases/1/assets?name=SHA256SUMS-win-x64.txt',
  ]);
  assert.ok(args.includes('Content-Type: text/plain'));
  assert.equal(args.at(-1), '/tmp/release/SHA256SUMS-win-x64.txt');

  const exe = releaseAssetUploadArgs('https://uploads.github.com/repos/o/r/releases/1/assets', 'app.exe');
  assert.ok(exe.includes('Content-Type: application/octet-stream'));

  assert.throws(() => releaseAssetUploadArgs('https://example.test/upload', 'app.exe'), /unexpected GitHub upload URL/);
});

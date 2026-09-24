'use strict';

// Runs every E2E suite and writes e2e-artifacts/summary.json (each suite's report sits next to it).
// Exits non-zero if any suite fails. Usage: npm run e2e [-- save gui ...] to run only some.
// The installer suite needs NSIS: makensis on PATH, or MAKENSIS=<path to makensis.exe>.

const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const { ROOT, ensureVenvPython } = require('../venv-python');

const SUITES = {
  save: 'build-scripts/e2e/save.py',
  gui: 'build-scripts/e2e/gui.py',
  smoke: 'build-scripts/smoke-gui.py',
  installer: 'build-scripts/e2e/installer.py',
  gpg: 'build-scripts/e2e/gpg.py',
  release: 'build-scripts/e2e/release.py',
  build: 'build-scripts/e2e/build.py',
};

const ARTIFACTS = process.env.BSE_E2E_ARTIFACTS || path.join(ROOT, 'e2e-artifacts');
const wanted = process.argv.slice(2);
const unknown = wanted.filter((name) => !SUITES[name]);
if (unknown.length) {
  console.error(`Unknown suite(s): ${unknown.join(', ')}. Known: ${Object.keys(SUITES).join(', ')}`);
  process.exit(1);
}

const py = ensureVenvPython();
const summary = { started: new Date().toISOString(), suites: {} };
for (const name of wanted.length ? wanted : Object.keys(SUITES)) {
  console.log(`\n=== ${name} ===`);
  const r = spawnSync(py, [SUITES[name]], { stdio: 'inherit', cwd: ROOT });
  const reportFile = path.join(ARTIFACTS, `${name}.json`);
  let report = null;
  try {
    report = JSON.parse(fs.readFileSync(reportFile, 'utf8'));
  } catch {
    /* suite crashed before writing its report */
  }
  const checks = report ? report.checks : [];
  summary.suites[name] = {
    passed: r.status === 0 && !!report && report.passed,
    exit_code: r.status,
    checks: checks.length,
    failed: checks.filter((c) => !c.ok).map((c) => c.name),
    skipped: report ? report.skipped.map((s) => s.name) : [],
    report: report ? path.relative(ARTIFACTS, reportFile) : null,
  };
}
summary.finished = new Date().toISOString();
summary.passed = Object.values(summary.suites).every((s) => s.passed);
fs.mkdirSync(ARTIFACTS, { recursive: true });
fs.writeFileSync(path.join(ARTIFACTS, 'summary.json'), JSON.stringify(summary, null, 2) + '\n');

console.log('\n=== summary ===');
for (const [name, s] of Object.entries(summary.suites)) {
  const state = s.passed ? 'PASS' : 'FAIL';
  console.log(`${state}  ${name}: ${s.checks - s.failed.length}/${s.checks}${s.skipped.length ? `, ${s.skipped.length} skipped` : ''}`);
}
console.log(`Artifacts: ${ARTIFACTS}`);
process.exit(summary.passed ? 0 : 1);

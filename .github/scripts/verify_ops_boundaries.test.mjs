import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { verifyOpsBoundaries } from './verify_ops_boundaries.mjs';

const SCRIPTS_DIR = path.dirname(fileURLToPath(import.meta.url));
const GITHUB_DIR = path.resolve(SCRIPTS_DIR, '..');

test('all ParallelLines workflows and scripts belong to one domain with zero cross-domain imports', () => {
	const summary = verifyOpsBoundaries(GITHUB_DIR);
	assert.equal(summary.ok, true);
	assert.deepEqual(summary.domains, ['chat', 'entertainment', 'main', 'unified']);
	assert.ok(summary.workflow_count >= 7);
	assert.ok(summary.script_count >= 18);
});

test('select_compose_files.sh supports persistent gateway-sites-enabled opt-in marker', () => {
	const script = fs.readFileSync(path.join(SCRIPTS_DIR, 'select_compose_files.sh'), 'utf8');
	assert.match(script, /\.deployment\/gateway-sites-enabled/);
	assert.match(script, /docker-compose\.gateway-sites\.yml/);
	assert.match(script, /deploy\/nginx\/sites\.d\/00-include-sites\.conf/);
	assert.match(script, /verify-gateway-sites\.mjs/);
	assert.match(script, /--require-route/);
});

test('entertainment-ops.yml uses current reviewed runtime source without legacy 1abefac5 split', () => {
	const workflow = fs.readFileSync(path.join(GITHUB_DIR, 'workflows', 'entertainment-ops.yml'), 'utf8');
	assert.doesNotMatch(workflow, /REGISTERED_RUNTIME_OPERATIONS/);
	assert.doesNotMatch(workflow, /1abefac5b9b20af63f9821d010cfe7efb1b88752/);
	assert.match(workflow, /native_path='\.github\/scripts\/entertainment_ops\.py'/);
});

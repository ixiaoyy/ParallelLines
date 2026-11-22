import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { verifySharedFacilitiesBoundaries } from './verify_shared_facilities_boundaries.mjs';

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');

test('current ParallelLines satisfies all shared facilities write and queue boundaries', () => {
	const summary = verifySharedFacilitiesBoundaries(REPO_ROOT);
	assert.equal(summary.ok, true);
	assert.equal(summary.email_worker_isolated, true);
	assert.ok(summary.scanned_files >= 180);
});

test('background_jobs worker supports BACKGROUND_WORKER_QUEUES and BACKGROUND_WORKER_ENQUEUE_SCHEDULED', () => {
	const worker = fs.readFileSync(
		path.join(REPO_ROOT, 'apps', 'api', 'app', 'workers', 'background_jobs.py'),
		'utf8'
	);
	assert.match(worker, /BACKGROUND_WORKER_QUEUES/);
	assert.match(worker, /BACKGROUND_WORKER_ENQUEUE_SCHEDULED/);
});

test('BackgroundJobService.acquire_next uses atomic conditional UPDATE CAS claim', () => {
	const service = fs.readFileSync(
		path.join(REPO_ROOT, 'apps', 'api', 'app', 'services', 'background_jobs.py'),
		'utf8'
	);
	assert.match(service, /update\(BackgroundJob\)/);
	assert.match(service, /BackgroundJob\.status == "queued"/);
	assert.match(service, /claim\.rowcount/);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import {
	ACCOUNT_CORE_WRITERS,
	REGISTERED_LEGACY_WRITERS,
	scanAccountWritesInSource,
	verifyAccountWriteBoundaries
} from './verify_account_write_boundaries.mjs';

const API_APP_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'apps', 'api', 'app');

test('current ParallelLines apps/api/app satisfies account write boundary guard', () => {
	const summary = verifyAccountWriteBoundaries(API_APP_ROOT);
	assert.equal(summary.ok, true);
	assert.deepEqual(summary.core_writers, [...ACCOUNT_CORE_WRITERS].sort());
	assert.deepEqual(summary.legacy_writers, Object.keys(REGISTERED_LEGACY_WRITERS).sort());
});

test('ignores read comparisons while detecting actual assignments and ORM writes', () => {
	const readOnly = 'if user.status == "active" and user.role == "admin": pass\n';
	assert.deepEqual(scanAccountWritesInSource(readOnly), []);

	const mutation = 'user.status = "suspended"\ndb.add(UserSession(user_id=user.id))\n';
	assert.deepEqual(scanAccountWritesInSource(mutation), ['UserSession(', 'user.status=']);
});

test('blocks unauthorized business module from directly writing account tables', () => {
	const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'pl-account-guard-'));
	try {
		fs.mkdirSync(path.join(tmp, 'services'), { recursive: true });
		fs.writeFileSync(
			path.join(tmp, 'services', 'catalog.py'),
			'def hack(user):\n    user.role = "admin"\n'
		);
		assert.throws(
			() => verifyAccountWriteBoundaries(tmp),
			/unauthorized_account_write:services\/catalog\.py:user\.role=/
		);
	} finally {
		fs.rmSync(tmp, { recursive: true, force: true });
	}
});

test('blocks registered legacy writer from expanding to new account write types', () => {
	const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'pl-account-legacy-'));
	try {
		fs.mkdirSync(path.join(tmp, 'services'), { recursive: true });
		fs.writeFileSync(
			path.join(tmp, 'services', 'growth.py'),
			'def bad(user):\n    event = UserPointEvent(user_id=user.id)\n    user.role = "admin"\n'
		);
		assert.throws(
			() => verifyAccountWriteBoundaries(tmp),
			/legacy_writer_expanded:services\/growth\.py:user\.role=/
		);
	} finally {
		fs.rmSync(tmp, { recursive: true, force: true });
	}
});

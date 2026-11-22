import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const ACCOUNT_MAIN = path.join(REPO_ROOT, 'apps', 'api', 'app', 'account_main.py');
const PILOT_COMPOSE = path.join(REPO_ROOT, 'docker-compose.account-pilot.yml');

test('account_main.py mounts only narrow auth/SSO routers and excludes users, invites, and business routers', () => {
	const text = fs.readFileSync(ACCOUNT_MAIN, 'utf8');
	for (const allowed of ['auth.router', 'auth_chat_sso.router', 'auth_unified.router']) {
		assert.equal(text.includes(allowed), true, `expected ${allowed} in account_main.py`);
	}
	for (const forbidden of [
		'users.router',
		'invites.router',
		'catalog.router',
		'boards.router',
		'topics.router',
		'posts.router',
		'admin.router',
		'traffic.router',
		'space.router',
		'moderation.router'
	]) {
		assert.equal(text.includes(forbidden), false, `forbidden router ${forbidden} found in account_main.py`);
	}
});

test('account_main.py implements real DB /readyz probe', () => {
	const text = fs.readFileSync(ACCOUNT_MAIN, 'utf8');
	assert.match(text, /@app\.get\("\/readyz"/);
	assert.match(text, /SELECT 1/);
	assert.match(text, /status_code=503/);
});

test('docker-compose.account-pilot.yml binds loopback only, never runs alembic, and probes /readyz', () => {
	const compose = fs.readFileSync(PILOT_COMPOSE, 'utf8');
	assert.match(compose, /127\.0\.0\.1:8001:8001/);
	assert.match(compose, /uvicorn app\.account_main:app/);
	assert.match(compose, /\/readyz/);
	assert.equal(/^\s*command:.*alembic/m.test(compose), false, 'account-api must never run alembic migrations');
});

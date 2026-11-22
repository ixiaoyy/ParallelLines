// 主站账号域静态防越界守卫（阶段 1 · 同进程收口，不改表、不切流）。
// 禁止非账号业务模块新增对账号核心表的直接写入；历史跨界写入按文件与操作精确锁定，只减不增。
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const ACCOUNT_CORE_WRITERS = new Set([
	'services/account_commands.py',
	'services/auth.py',
	'services/chat_sso.py',
	'services/unified_auth.py',
	'services/product_access.py',
	'services/users.py',
	'services/privacy.py'
]);

// 已登记的历史跨界写入点：只允许收口减少，不允许在现有文件扩大写入类型或新增其他跨界文件。
export const REGISTERED_LEGACY_WRITERS = Object.freeze({
	'services/daily_reading.py': ['User('],
	'services/growth.py': ['UserPointEvent(', 'user.experience_total=', 'user.points_balance=']
});

const WRITE_MODELS = [
	'User',
	'UserSession',
	'EmailVerificationCode',
	'UserSecurityToken',
	'UserRecoveryCode',
	'ProductAccessGrant',
	'UserPointEvent'
];

const CTOR_RE = new RegExp(`\\b(?:${WRITE_MODELS.join('|')})\\s*\\(`, 'g');
const SQL_WRITE_RE = new RegExp(`\\b(?:update|delete|insert)\\s*\\(\\s*(?:${WRITE_MODELS.join('|')})\\b`, 'g');
// 凭据级敏感字段（不限变量名，任何对象赋值均拦截）
const CREDENTIAL_ASSIGN_RE =
	/\b[a-zA-Z_][a-zA-Z0-9_]*\.(hashed_password|password_hash|two_factor_secret|two_factor_enabled|totp_secret|totp_enabled)\s*=(?!=)/g;
const ATTR_ASSIGN_RE =
	/\b(?:user|target_user|current_user|account|owner)\.(email|email_verified|email_verified_at|is_active|role|status|deleted_at|anonymized_at|session_version|token_version|username|display_name|avatar_url|bio|points_balance|experience_total|trust_level)\s*=(?!=)/g;

function walkPythonFiles(dir) {
	let files = [];
	for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
		if (entry.name === '__pycache__') continue;
		const fullPath = path.join(dir, entry.name);
		if (entry.isDirectory()) {
			files = files.concat(walkPythonFiles(fullPath));
		} else if (entry.isFile() && entry.name.endsWith('.py')) {
			files.push(fullPath);
		}
	}
	return files.sort();
}

export function scanAccountWritesInSource(text) {
	const hits = new Set();
	for (const re of [CTOR_RE, SQL_WRITE_RE, CREDENTIAL_ASSIGN_RE, ATTR_ASSIGN_RE]) {
		re.lastIndex = 0;
		let match;
		while ((match = re.exec(text)) !== null) {
			hits.add(match[0].replace(/\s+/g, ''));
		}
	}
	return [...hits].sort();
}

export function verifyAccountWriteBoundaries(apiAppRoot) {
	const root = path.resolve(apiAppRoot);
	if (!fs.existsSync(root) || !fs.statSync(root).isDirectory()) {
		throw new Error(`api_app_root_missing:${root}`);
	}

	const files = walkPythonFiles(root);
	const violations = [];
	const coreWriterHits = {};
	const legacyWriterHits = {};

	for (const filePath of files) {
		const rel = path.relative(root, filePath).replace(/\\/g, '/');
		if (rel.startsWith('models/')) continue;

		const hits = scanAccountWritesInSource(fs.readFileSync(filePath, 'utf8'));
		if (hits.length === 0) continue;

		if (ACCOUNT_CORE_WRITERS.has(rel)) {
			coreWriterHits[rel] = hits;
			continue;
		}

		if (Object.prototype.hasOwnProperty.call(REGISTERED_LEGACY_WRITERS, rel)) {
			const allowed = new Set(REGISTERED_LEGACY_WRITERS[rel]);
			const unexpected = hits.filter((h) => !allowed.has(h));
			if (unexpected.length > 0) {
				violations.push(`legacy_writer_expanded:${rel}:${unexpected.join(',')}`);
			} else {
				legacyWriterHits[rel] = hits;
			}
			continue;
		}

		violations.push(`unauthorized_account_write:${rel}:${hits.join(',')}`);
	}

	if (violations.length > 0) {
		throw new Error(`account_write_boundary_violation:\n${violations.join('\n')}`);
	}

	return {
		ok: true,
		scanned_files: files.length,
		core_writers: Object.keys(coreWriterHits).sort(),
		legacy_writers: Object.keys(legacyWriterHits).sort()
	};
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
	const defaultRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'apps', 'api', 'app');
	const targetRoot = process.argv[2] || defaultRoot;
	console.log(JSON.stringify(verifyAccountWriteBoundaries(targetRoot)));
}

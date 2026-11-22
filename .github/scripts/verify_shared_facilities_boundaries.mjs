// 主站内部共享设施边界守卫（媒体上传、后台队列、邮件投递、队列/调度隔离）。
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ALLOWED_UPLOAD_CONSTRUCTORS = new Set(['services/uploads.py']);
const ALLOWED_JOB_CONSTRUCTORS = new Set(['services/background_jobs.py']);
const ALLOWED_RAW_SEND_EMAIL = new Set([
	'services/email.py',
	'services/background_jobs.py',
	'workers/background_jobs.py'
]);

function walkPythonFiles(dir) {
	let files = [];
	for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
		if (entry.name === '__pycache__') continue;
		const fullPath = path.join(dir, entry.name);
		if (entry.isDirectory()) files = files.concat(walkPythonFiles(fullPath));
		else if (entry.isFile() && entry.name.endsWith('.py')) files.push(fullPath);
	}
	return files.sort();
}

export function verifySharedFacilitiesBoundaries(repoRoot) {
	const root = path.resolve(repoRoot);
	const apiAppRoot = path.join(root, 'apps', 'api', 'app');
	const files = walkPythonFiles(apiAppRoot);
	const violations = [];

	for (const filePath of files) {
		const rel = path.relative(apiAppRoot, filePath).replace(/\\/g, '/');
		if (rel.startsWith('models/')) continue;
		const text = fs.readFileSync(filePath, 'utf8');

		if (/\bUpload\s*\(/.test(text) && !ALLOWED_UPLOAD_CONSTRUCTORS.has(rel)) {
			violations.push(`unauthorized_upload_write:${rel}`);
		}
		if (/\bBackgroundJob\s*\(/.test(text) && !ALLOWED_JOB_CONSTRUCTORS.has(rel)) {
			violations.push(`unauthorized_background_job_write:${rel}`);
		}
		if (/\bsend_email\s*\(/.test(text) && !ALLOWED_RAW_SEND_EMAIL.has(rel)) {
			violations.push(`unauthorized_raw_send_email:${rel}`);
		}
	}

	// 核对独立邮件 worker 试点叠加文件关闭定时入队（保持唯一调度方）。
	const emailPilot = path.join(root, 'docker-compose.email-worker-pilot.yml');
	if (!fs.existsSync(emailPilot)) {
		violations.push('missing_email_worker_pilot_compose');
	} else {
		const compose = fs.readFileSync(emailPilot, 'utf8');
		if (!/BACKGROUND_WORKER_QUEUES:\s*["']?mail["']?/.test(compose)) {
			violations.push('email_worker_pilot_missing_mail_queue');
		}
		if (!/BACKGROUND_WORKER_ENQUEUE_SCHEDULED:\s*["']?false["']?/.test(compose)) {
			violations.push('email_worker_pilot_must_disable_scheduler');
		}
	}

	if (violations.length > 0) {
		throw new Error(`shared_facilities_boundary_violation:\n${violations.join('\n')}`);
	}

	return {
		ok: true,
		scanned_files: files.length,
		email_worker_isolated: true
	};
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
	const defaultRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
	console.log(JSON.stringify(verifySharedFacilitiesBoundaries(process.argv[2] || defaultRoot)));
}

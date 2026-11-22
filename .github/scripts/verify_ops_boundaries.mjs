// 校验 ParallelLines/.github/ 下跨站运维工作流与脚本的域归属和防耦合边界。
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export function verifyOpsBoundaries(githubDir) {
	const root = path.resolve(githubDir);
	const manifest = JSON.parse(fs.readFileSync(path.join(root, 'ops-domains.json'), 'utf8'));
	const domains = manifest.domains || {};

	const workflowOwner = new Map();
	const scriptOwner = new Map();

	for (const [domain, spec] of Object.entries(domains)) {
		for (const wf of spec.workflows || []) {
			if (workflowOwner.has(wf)) throw new Error(`duplicate_workflow_owner:${wf}`);
			workflowOwner.set(wf, domain);
		}
		for (const sc of spec.scripts || []) {
			if (scriptOwner.has(sc)) throw new Error(`duplicate_script_owner:${sc}`);
			scriptOwner.set(sc, domain);
		}
	}

	const workflowsDir = path.join(root, 'workflows');
	const actualWorkflows = fs
		.readdirSync(workflowsDir, { withFileTypes: true })
		.filter((e) => e.isFile() && (e.name.endsWith('.yml') || e.name.endsWith('.yaml')))
		.map((e) => e.name)
		.sort();

	for (const wf of actualWorkflows) {
		if (!workflowOwner.has(wf)) throw new Error(`unowned_workflow:${wf}`);
	}
	for (const wf of workflowOwner.keys()) {
		if (!actualWorkflows.includes(wf)) throw new Error(`missing_declared_workflow:${wf}`);
	}

	const scriptsDir = path.join(root, 'scripts');
	const actualScripts = fs
		.readdirSync(scriptsDir, { withFileTypes: true })
		.filter((e) => e.isFile())
		.map((e) => e.name)
		.sort();

	for (const sc of actualScripts) {
		if (!scriptOwner.has(sc)) throw new Error(`unowned_script:${sc}`);
	}
	for (const sc of scriptOwner.keys()) {
		if (!actualScripts.includes(sc)) throw new Error(`missing_declared_script:${sc}`);
	}

	// 检查每个非 test Python 脚本不反向 import 其他业务域的脚本模块。
	const moduleOwner = new Map();
	for (const [sc, domain] of scriptOwner.entries()) {
		if (sc.endsWith('.py') && !sc.startsWith('test_')) {
			moduleOwner.set(sc.slice(0, -3), domain);
		}
	}

	for (const [sc, domain] of scriptOwner.entries()) {
		if (!sc.endsWith('.py') || sc.startsWith('test_')) continue;
		const text = fs.readFileSync(path.join(scriptsDir, sc), 'utf8');
		const importRegex = /^(?:from|import)\s+([a-zA-Z0-9_]+)/gm;
		let match;
		while ((match = importRegex.exec(text)) !== null) {
			const targetDomain = moduleOwner.get(match[1]);
			if (targetDomain && targetDomain !== domain) {
				throw new Error(`cross_domain_import:${sc}(${domain})->${match[1]}(${targetDomain})`);
			}
		}
	}

	return {
		ok: true,
		domains: Object.keys(domains).sort(),
		workflow_count: actualWorkflows.length,
		script_count: actualScripts.length
	};
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
	const githubDir = process.argv[2] || path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
	console.log(JSON.stringify(verifyOpsBoundaries(githubDir)));
}

const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { buildConfig } = require('./config.cjs');

// This runs inside the user's server container; never print credentials or write them into generated YAML.
for (const key of ['JWT_SECRET', 'JWT_REFRESH_SECRET']) {
  if ((process.env[key] || '').length < 32) throw new Error('Initialize the server-local .env once before starting LibreChat.');
}
if (!/^[a-f0-9]{64}$/i.test(process.env.CREDS_KEY || '') || !/^[a-f0-9]{32}$/i.test(process.env.CREDS_IV || '')) {
  throw new Error('Initialize the server-local encryption settings before starting LibreChat.');
}
const generated = buildConfig(process.env);
const directory = '/app/data/family-config';
fs.mkdirSync(directory, { recursive: true });
const configPath = path.join(directory, 'librechat.yaml');
fs.writeFileSync(configPath, JSON.stringify(generated.config, null, 2), { mode: 0o600 });
// Operator imports this secret-free override only into an explicitly selected USER profile.
fs.writeFileSync(path.join(directory, 'approved-user-profile.yaml'), JSON.stringify(generated.approvedProfile, null, 2), { mode: 0o600 });
// Candidates are preserved without a Key; this file grants no account access.
const labels = { 'gpt-6-luna': 'GPT-6 Luna', 'gpt-6.1-sol': 'GPT-6.1 Sol' };
fs.writeFileSync(path.join(directory, 'selected-models.json'), JSON.stringify({
  models: generated.selectedModels.map(id => ({ id, label: labels[id] || id })),
  defaultAccountAccess: false
}, null, 2), { mode: 0o600 });
const env = {
  ...process.env,
  OPENAI_API_KEY: generated.runtimeKey,
  OPENAI_MODELS: generated.models.join(','),
  ENDPOINTS: 'openAI',
  CONFIG_PATH: configPath,
  CUSTOM_FOOTER: generated.footer
};
console.log(JSON.stringify({ familyGptConfigured: generated.enabled, defaultAccountAccess: false, reason: generated.reason, models: generated.models }));
const child = spawn(process.execPath, ['/app/api/server/index.js'], { cwd: '/app/api', env, stdio: 'inherit' });
for (const signal of ['SIGTERM', 'SIGINT']) process.on(signal, () => child.kill(signal));
child.on('error', () => { console.error('LibreChat process could not start.'); process.exitCode = 1; });
child.on('exit', code => { process.exitCode = code ?? 1; });

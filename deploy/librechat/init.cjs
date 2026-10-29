const fs = require('node:fs');
const path = require('node:path');
const { randomBytes } = require('node:crypto');

// Server-owner bootstrap only. Preserve an existing .env without reading it.
const root = __dirname;
const output = path.join(root, '.env');
if (fs.existsSync(output)) {
  console.log('Existing server .env preserved without reading or changing it.');
} else {
  let content = fs.readFileSync(path.join(root, '.env.example'), 'utf8');
  for (const [name, bytes] of Object.entries({ CREDS_KEY: 32, CREDS_IV: 16, JWT_SECRET: 32, JWT_REFRESH_SECRET: 32, ADMIN_PANEL_SESSION_SECRET: 32 })) {
    content = content.replace(new RegExp(`^${name}=$`, 'm'), `${name}=${randomBytes(bytes).toString('hex')}`);
  }
  fs.writeFileSync(output, content, { flag: 'wx', mode: 0o600 });
  console.log('Server-local .env initialized. OpenAI key and model selection remain empty.');
}

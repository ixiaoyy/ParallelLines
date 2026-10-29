'use strict';
const fs = require('node:fs');
const path = require('node:path');

const selectedModels = Object.freeze(['gpt-6-luna', 'gpt-6.1-sol']);
const prefix = Buffer.from('OPENAI_CHAT_MODELS=');

/** Replace exactly the one model-setting line; all unrelated bytes stay opaque. */
function replaceModelLine(source) {
  const chunks = [];
  let start = 0;
  let matches = 0;
  for (let index = 0; index <= source.length; index++) {
    if (index !== source.length && source[index] !== 10) continue;
    const end = index < source.length ? index + 1 : index;
    const line = source.subarray(start, end);
    if (line.subarray(0, prefix.length).equals(prefix)) {
      matches++;
      const ending = line.at(-1) === 10 ? (line.at(-2) === 13 ? '\r\n' : '\n') : '';
      chunks.push(Buffer.from('OPENAI_CHAT_MODELS=' + selectedModels.join(',') + ending));
    } else {
      // Do not decode, log, parse, or transform unrelated credential/settings lines.
      chunks.push(line);
    }
    start = end;
  }
  if (matches !== 1) throw new Error('model_line_count');
  return Buffer.concat(chunks);
}

function configure() {
  const file = path.join(__dirname, '.env');
  const stat = fs.lstatSync(file);
  if (!stat.isFile() || stat.isSymbolicLink() || (stat.mode & 0o777) !== 0o600 || stat.uid !== process.getuid()) {
    throw new Error('env_owner_or_mode');
  }
  const original = fs.readFileSync(file);
  const updated = replaceModelLine(original);
  const temporary = file + '.models-' + process.pid;
  let opened = false;
  try {
    const fd = fs.openSync(temporary, 'wx', stat.mode & 0o777);
    opened = true;
    try {
      fs.fchownSync(fd, -1, stat.gid);
      fs.fchmodSync(fd, stat.mode & 0o777);
      fs.writeFileSync(fd, updated);
      fs.fsyncSync(fd);
    } finally { fs.closeSync(fd); }
    if (!fs.readFileSync(file).equals(original)) throw new Error('env_changed_concurrently');
    fs.renameSync(temporary, file);
    opened = false;
    if (!fs.readFileSync(file).equals(updated)) throw new Error('write_verification');
  } finally {
    if (opened && fs.existsSync(temporary)) fs.unlinkSync(temporary);
  }
  console.log(JSON.stringify({ models: selectedModels, changedField: 'OPENAI_CHAT_MODELS', otherBytesPreserved: true, fileMode: '0600' }));
}

if (require.main === module) {
  try { configure(); }
  catch {
    console.error('Model-list configuration stopped; no credential values were printed.');
    process.exitCode = 1;
  }
}
module.exports = { replaceModelLine, selectedModels };

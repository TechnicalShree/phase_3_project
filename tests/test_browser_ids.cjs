// Public HTTP lacks crypto.randomUUID; getRandomValues still works there.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {webcrypto} = require('node:crypto');
const context = {crypto: {getRandomValues: webcrypto.getRandomValues.bind(webcrypto)}};
vm.createContext(context);
vm.runInContext(fs.readFileSync('app/static/app.js', 'utf8').split('\n')[0], context);
const first = context.newId(), second = context.newId();
assert.match(first, /^[a-f0-9]{32}$/);
assert.notEqual(first, second);
console.log('PASS: browser IDs work without crypto.randomUUID.');

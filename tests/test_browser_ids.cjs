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

const elements = {'connection': {open: false}, 'connection-label': {}, 'token': {focus() {this.focused = true;}}};
context.$ = id => elements[id];
const source = fs.readFileSync('app/static/app.js', 'utf8');
vm.runInContext(source.slice(source.indexOf('function requireConnection()'), source.indexOf('async function call(')), context);
assert.throws(() => context.checkAuth({status: 401}), /workspace access token/);
assert.equal(elements.connection.open, true);
assert.equal(elements.token.focused, true);
assert.doesNotThrow(() => context.checkAuth({status: 200}));
console.log('PASS: unauthorized responses open the connection panel.');

vm.runInContext(source.slice(source.indexOf('function requestTitle('), source.indexOf("$('token').value =")), context);
assert.equal(context.requestTitle({values:{text:'Campus wifi outage'}}), 'Campus wifi outage');
assert.equal(context.requestTitle({values:{}}), 'Untitled request');
assert.equal(context.progressText(['tools']), 'Checking campus information');
assert.equal(context.progressText(['draft']), 'Preparing a ticket for your review');
console.log('PASS: friendly request names and progress stages.');

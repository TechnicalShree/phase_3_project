const $ = id => document.getElementById(id);
let state;
async function call(path, body) {
  const response = await fetch(path, {method: body ? 'POST' : 'GET', headers: {'Content-Type': 'application/json', ...($('token').value ? {Authorization: `Bearer ${$('token').value}`} : {})}, ...(body ? {body: JSON.stringify(body)} : {})});
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail));
  return data;
}
function show(data) {
  state = data;
  $('output').textContent = data.values.response;
  $('review').hidden = !data.pending.length;
  if (data.pending.length) $('draft').value = JSON.stringify(data.pending[0].draft, null, 2);
}
async function act(fn) {try {await fn();} catch(error) {$('output').textContent = error.message;}}
$('run').onclick = () => act(async () => show(await call('/run', {thread_id: $('thread').value, text: $('text').value})));
$('load').onclick = () => act(async () => show(await call(`/threads/${encodeURIComponent($('thread').value)}`)));
document.querySelectorAll('[data-action]').forEach(button => button.onclick = () => act(async () => show(await call(`/${button.dataset.action}`, {thread_id: state.thread_id, checkpoint_id: state.checkpoint_id, ...(button.dataset.action === 'edit-and-approve' ? {draft: JSON.parse($('draft').value)} : {})}))));

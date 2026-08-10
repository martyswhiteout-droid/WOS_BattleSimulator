import { renderEntryCard, mountEntry, wireEntry, renderUpgradeNote, wireUpgradeNote } from './screens/entry.mjs';

function fetchMe() {
  return fetch('/shell/me', { credentials: 'same-origin' }).then((r) => r.json());
}
async function checkAccess() {
  try {
    const me = await fetchMe();
    const plan = me && me.user && me.user.plan;
    return { allowed: plan === 'pro', plan: plan || null, reachable: true };
  } catch (err) {
    return { allowed: false, plan: null, reachable: false };
  }
}
function checkout() {
  return fetch('/shell/billing/checkout', { method: 'POST', credentials: 'same-origin' })
    .then((r) => { if (!r.ok) throw new Error('checkout unavailable'); return r.json(); });
}

function showUpgradeNote() {
  const wrap = document.createElement('div');
  wrap.innerHTML = renderUpgradeNote();
  const node = wrap.firstElementChild;
  document.body.appendChild(node);
  node.removeAttribute('inert');
  node.setAttribute('aria-hidden', 'false');
  wireUpgradeNote(node, { checkout });
}

function boot() {
  const entryNode = mountEntry({ root: document });
  if (!entryNode) return;   // this page has no #statPanel — nothing to attach to
  wireEntry(entryNode, {
    checkAccess,
    onProceed: () => { /* Task 6 replaces this with "open S1" */ },
    onNeedsUpgrade: showUpgradeNote,
  });
}

if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
}

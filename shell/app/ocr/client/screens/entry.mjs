export function renderEntryCard() {
  return `
<section class="ocrf-entry" id="ocrfEntry">
  <button type="button" class="ocrf-cta" id="ocrfCtaScreenshots">
    <span class="ocrf-cta-emoji" aria-hidden="true">\u{1F4F7}</span> Fill from screenshots
  </button>
  <p class="ocrf-cta-note">Fastest way. No typing.</p>
</section>`.trim();
}

export function renderUpgradeNote() {
  return `
<div class="ocrf-modal-scrim" id="ocrfUpgradeScrim" aria-hidden="true" inert>
  <div class="ocrf-sheet" role="dialog" aria-modal="true" aria-labelledby="ocrfUpgradeTitle">
    <h2 id="ocrfUpgradeTitle" tabindex="-1">This needs a paid plan</h2>
    <p>Reading screenshots is a paid feature. Typing the numbers in yourself is always free.</p>
    <div class="ocrf-sheet-actions">
      <button type="button" class="ocrf-btn-ghost" id="ocrfUpgradeClose">Type it in myself</button>
      <button type="button" class="ocrf-btn-primary" id="ocrfUpgradeCta">See plans</button>
    </div>
  </div>
</div>`.trim();
}

export async function decideEntryAction(checkAccess) {
  const access = await checkAccess();
  return access.allowed ? 'proceed' : 'upgrade';
}

export function mountEntry({ root = document } = {}) {
  const statPanel = root.getElementById('statPanel');
  if (!statPanel) return null;
  const anchor = statPanel.closest('.iblock') || statPanel;
  const wrap = root.createElement('div');
  wrap.innerHTML = renderEntryCard();
  const node = wrap.firstElementChild;
  anchor.parentNode.insertBefore(node, anchor);
  return node;
}

export function wireEntry(node, { checkAccess, onProceed, onNeedsUpgrade }) {
  const button = node.querySelector('#ocrfCtaScreenshots');
  button.addEventListener('click', async () => {
    const action = await decideEntryAction(checkAccess);
    if (action === 'proceed') onProceed();
    else onNeedsUpgrade();
  });
}

export function wireUpgradeNote(node, { checkout } = {}) {
  const close = node.querySelector('#ocrfUpgradeClose');
  const cta = node.querySelector('#ocrfUpgradeCta');
  close.addEventListener('click', () => node.remove());
  cta.addEventListener('click', async () => {
    cta.disabled = true;
    cta.textContent = 'Opening…';
    try {
      const result = await (checkout ? checkout() : Promise.reject(new Error('no checkout configured')));
      if (result && result.url) { window.location.href = result.url; return; }
      throw new Error('no checkout url');
    } catch (err) {
      cta.textContent = 'Try again from the account panel';
    }
  });
}

/* shell/app/overlay/overlay.js — floating account/quota chip (Agent A).
 * Implements PRODUCTION_PLAN.md §2: login state, plan, remaining quota,
 * upgrade prompt — injected at serve time, never edited into the prototype.
 * Self-contained: no CDNs, no external fonts (inherits the page's local
 * Chakra Petch / Inter / IBM Plex Mono faces via font-family fallbacks).
 * All dynamic strings are set via textContent (hostile-client rule: never
 * trust user_id/email into innerHTML). */
(function () {
  "use strict";
  if (window.__wosShellOverlay) return;   // double-injection guard
  window.__wosShellOverlay = true;

  var css = document.createElement("link");
  css.rel = "stylesheet";
  css.href = "/shell/overlay.css";
  document.head.appendChild(css);

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  var root = el("div", "wos-shell-chip");
  root.id = "wos-shell-overlay";
  root.setAttribute("role", "status");

  var head = el("div", "wos-sc-head");
  head.appendChild(el("span", "wos-sc-eyebrow", "WOSTESTS"));
  var toggle = el("button", "wos-sc-toggle", "–");
  toggle.type = "button";
  toggle.setAttribute("aria-label", "Collapse account panel");
  head.appendChild(toggle);
  root.appendChild(head);

  var body = el("div", "wos-sc-body");
  root.appendChild(body);

  // F8 / PRODUCTION_CRITERIA F2 (EVAL_ROUND_1.md): a visible disclaimer is
  // required, and the overlay is the only place the shell can add one
  // without editing the prototype (boundary rule 1). Kept OUTSIDE the
  // collapsible body (not hidden by the –/+ toggle) since a compliance
  // disclaimer should not be collapsible. Canonical wording, verbatim per
  // shell/legal/disclaimer.md ("keep it verbatim wherever it is rendered").
  // textContent only (hostile-client rule) — the two links are local,
  // static paths, not user data.
  var legal = el("div", "wos-sc-legal");
  legal.appendChild(document.createTextNode(
    "Fan-made tool. Not affiliated with or endorsed by Century Games. "));
  var tosLink = el("a", null, "Terms");
  tosLink.href = "/legal/tos";
  legal.appendChild(tosLink);
  legal.appendChild(document.createTextNode(" · "));
  var privacyLink = el("a", null, "Privacy");
  privacyLink.href = "/legal/privacy";
  legal.appendChild(privacyLink);
  root.appendChild(legal);

  toggle.addEventListener("click", function () {
    var collapsed = root.classList.toggle("wos-collapsed");
    toggle.textContent = collapsed ? "+" : "–";
    toggle.setAttribute("aria-label",
      (collapsed ? "Expand" : "Collapse") + " account panel");
  });

  function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }

  function renderSignedOut(signInUrl) {
    clear(body);
    body.appendChild(el("div", "wos-sc-user", "Not signed in"));
    var a = el("a", "wos-sc-btn wos-sc-cta", "Sign in");
    a.href = signInUrl || "/";
    body.appendChild(a);
  }

  function renderError() {
    clear(body);
    body.appendChild(el("div", "wos-sc-user wos-sc-muted", "Account status unavailable"));
  }

  function render(me) {
    clear(body);
    var user = me.user || {};
    var remaining = me.remaining || {};
    var ent = me.entitlements || {};

    var who = el("div", "wos-sc-user");
    who.appendChild(el("span", "wos-sc-name", user.email || user.user_id || "player"));
    who.appendChild(el("span",
      "wos-sc-plan" + (user.plan === "pro" ? " wos-sc-plan-pro" : ""),
      (user.plan || "free").toUpperCase()));
    body.appendChild(who);

    var quota = el("div", "wos-sc-quota");
    var sims = el("div", "wos-sc-quota-row");
    sims.appendChild(el("span", "wos-sc-quota-label", "Sims left today"));
    sims.appendChild(el("span", "wos-sc-quota-val",
      remaining.sims != null ? String(remaining.sims)
        : String(ent.daily_sim_quota != null ? ent.daily_sim_quota : "—")));
    quota.appendChild(sims);
    if (user.plan === "pro") {
      var ocr = el("div", "wos-sc-quota-row");
      ocr.appendChild(el("span", "wos-sc-quota-label", "OCR left today"));
      ocr.appendChild(el("span", "wos-sc-quota-val",
        remaining.ocr != null ? String(remaining.ocr)
          : String(ent.daily_ocr_quota != null ? ent.daily_ocr_quota : "—")));
      quota.appendChild(ocr);
    }
    body.appendChild(quota);

    var row = el("div", "wos-sc-actions");
    if (user.plan !== "pro") {
      var up = el("button", "wos-sc-btn wos-sc-cta", "Upgrade");
      up.type = "button";
      up.addEventListener("click", function () {
        up.disabled = true;
        up.textContent = "Opening…";
        // Billing endpoint is Agent B's; degrade gracefully while it is absent.
        fetch("/shell/billing/checkout", { method: "POST", credentials: "same-origin" })
          .then(function (r) {
            if (!r.ok) throw new Error("checkout unavailable");
            return r.json();
          })
          .then(function (j) {
            if (j && j.url) { window.location.href = j.url; }
            else { throw new Error("no checkout url"); }
          })
          .catch(function () {
            up.disabled = true;
            up.classList.add("wos-sc-muted");
            up.textContent = "Billing unavailable";
          });
      });
      row.appendChild(up);
    }
    var out = el("button", "wos-sc-btn wos-sc-ghost", "Sign out");
    out.type = "button";
    out.addEventListener("click", function () {
      // F6 (EVAL_ROUND_1.md): Clerk's session cookie is HttpOnly, so a
      // client-side assignment via the `document.cookie` setter can never
      // clear it — the user stayed fully authenticated after "signing
      // out". POST /shell/signout clears it server-side (Set-Cookie),
      // which HttpOnly does not block. Redirect only AFTER the request
      // settles (success or failure) so the clear has actually happened by
      // the time navigation starts.
      out.disabled = true;
      fetch("/shell/signout", { method: "POST", credentials: "same-origin" })
        .catch(function () {})
        .then(function () { window.location.href = me.sign_in_url || "/"; });
    });
    row.appendChild(out);
    body.appendChild(row);
  }

  fetch("/shell/me", { credentials: "same-origin" })
    .then(function (r) {
      if (r.ok) return r.json().then(render);
      return r.json()
        .then(function (j) { renderSignedOut(j && j.sign_in_url); })
        .catch(function () { renderSignedOut(null); });
    })
    .catch(renderError);

  function mount() { document.body.appendChild(root); }
  if (document.body) mount();
  else document.addEventListener("DOMContentLoaded", mount);
})();

/* Asset fallback (M3, EVAL_ROUND_1.md F18 / EVAL_ROUND_2.md M3): a promoted
 * bundle strips ALL raster art (Century Games IP) from prototype/ and
 * wos_sim/ before it ships (shell/promote.py step3_assemble) — but the
 * mounted prototype's own JS still emits <img src="avatars/...">,
 * "assets/Icons/*.png", "assets/ui/*.png" unconditionally, so those
 * requests 404 in that exact deployment. prototype/ is READ-ONLY from
 * shell/ (ARCHITECTURE.md boundary rule 1), so this reacts to the browser's
 * own "error" event on an <img> instead — which fires ONLY when a src
 * actually fails to load, so an ordinary dev checkout with the raster art
 * still in place never triggers any of this. On a real failure: swap in
 * the matching original-art SVG shipped at /shell/assets/ (mounted by
 * main.py from shell/assets_prod/) when a 1:1 replacement exists (class
 * icons, rally/garrison role icons); otherwise hide the broken image and
 * show its `alt` text instead — assets_prod's manifest has only 22
 * abstract category keys (no per-hero or per-skill entries), so per-hero
 * avatars and skill/proc icons fall back to "accept text-only ... and
 * suppress the <img>", the alternative F18 explicitly sanctions. */
(function () {
  "use strict";
  if (window.__wosAssetFallback) return;   // double-injection guard
  window.__wosAssetFallback = true;

  // Path fragment (matched case-insensitively) -> shell/assets_prod/
  // manifest.json key. Only the categories the prototype's own JS actually
  // emits as <img src> today are listed — everything else (per-hero
  // avatars, per-skill icons) has no 1:1 replacement and is suppressed.
  var PATTERNS = [
    { test: /icons\/infantry\.png(?:[?#]|$)/i, key: "class.infantry" },
    { test: /icons\/lancer\.png(?:[?#]|$)/i, key: "class.lancer" },
    { test: /icons\/marksman\.png(?:[?#]|$)/i, key: "class.marksman" },
    { test: /assets\/ui\/rally-swords\.png(?:[?#]|$)/i, key: "role.rally" },
    { test: /assets\/ui\/garrison-shield\.png(?:[?#]|$)/i, key: "role.garrison" }
  ];

  var manifestPromise = null;
  function loadManifest() {
    if (!manifestPromise) {
      manifestPromise = fetch("/shell/assets/manifest.json", { credentials: "same-origin" })
        .then(function (r) { return r.ok ? r.json() : null; })
        .catch(function () { return null; });
    }
    return manifestPromise;
  }

  function keyFor(src) {
    for (var i = 0; i < PATTERNS.length; i++) {
      if (PATTERNS[i].test.test(src)) return PATTERNS[i].key;
    }
    return null;
  }

  // Hides the broken image and, if it carries alt text, inserts that text
  // as a plain visible label right after it (textContent only — hostile-
  // client rule; the alt text originates from the prototype's own trusted
  // markup, not remote user data, but there is no reason to ever use
  // innerHTML here).
  function suppress(el) {
    el.style.visibility = "hidden";
    el.setAttribute("aria-hidden", "true");
    var alt = el.getAttribute("alt");
    if (alt && !el.dataset.wosAssetLabel) {
      el.dataset.wosAssetLabel = "1";
      var label = document.createElement("span");
      label.className = "wos-asset-fallback-label";
      label.textContent = alt;
      if (el.parentNode) el.parentNode.insertBefore(label, el.nextSibling);
    }
  }

  document.addEventListener("error", function (ev) {
    var el = ev.target;
    if (!el || el.tagName !== "IMG") return;
    if (el.dataset.wosAssetFallback) {   // the swapped-in replacement ALSO failed
      suppress(el);
      return;
    }
    el.dataset.wosAssetFallback = "1";
    var key = keyFor(el.getAttribute("src") || "");
    if (!key) { suppress(el); return; }
    loadManifest().then(function (manifest) {
      var file = manifest && manifest.assets && manifest.assets[key];
      if (file) { el.src = "/shell/assets/" + file; }
      else { suppress(el); }
    });
  }, true);
})();

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
      document.cookie = "__session=; Max-Age=0; path=/";
      window.location.href = me.sign_in_url || "/";
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

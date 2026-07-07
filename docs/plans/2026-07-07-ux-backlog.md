# UX Backlog Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Address the UX defects in `UX_BACKLOG.md` without regressing the working predictor flow, telemetry panel, Final Stats contract, or encoding.

**Architecture:** Keep this as a scoped front-end pass centered on `prototype/index.html`, with small data/doc edits only when explicitly called out. Use the existing serializers (`formToConfig`, `configToForm`) as the shared state boundary for tabs, autosave, save/load, and API payloads. Add small UI state helpers around the existing single-file app rather than introducing a framework.

**Tech Stack:** Static HTML/CSS/vanilla JS served by FastAPI/uvicorn from `wos_sim.predictor.server`; Python unit tests via `unittest`; JS syntax checked with local `node --check`.

---

## Global Rules

- Preserve UTF-8. After every edit to `prototype/index.html`, run a corruption scan. Prefer this PowerShell-safe Python version:
  ```powershell
  @'
  from pathlib import Path
  text = Path("prototype/index.html").read_text(encoding="utf-8-sig")
  bad = ["\\u00c3\\u201a", "\\u00c3\\u00a2\\u20ac", "\\u00c3\\u00a2\\u20ac\\u201d", "\\u00c3\\u00a2\\u00c5\\u00a1"]
  hits = [b for b in bad if b in text]
  print("encoding check:", "FAIL " + repr(hits) if hits else "0 matches")
  '@ | .venv\Scripts\python -
  ```
- Preserve newer post-backlog decisions:
  - Uncalibrated forecast badge stays `Uncalibrated - directional`.
  - The haze/band remains visible, but in uncalibrated mode it is narrow and sized to sampling error.
  - Final Stats are the only panel sent to the engine.
  - Passive troop skills stay filtered out of the skill details panel.
  - Gwen avatar stays `Gwen-official.jpg`.
- Do not redo already-fixed items unless a task explicitly changes them.
- Use `apply_patch` for manual edits. The current workspace is not a git repo, so skip commit steps unless a repo is initialized later.

## Baseline Verification

**Files:**
- Read: `E:/WOS/Battle Simulator/UX_BACKLOG.md`
- Read/modify later: `E:/WOS/Battle Simulator/prototype/index.html`

**Step 1: Verify encoding guard is clean**

Run the Python encoding scan from Global Rules.

Expected: `encoding check: 0 matches`.

**Step 2: Verify current tests before UX edits**

Run:
```powershell
.venv\Scripts\python -m unittest discover -s wos_sim/predictor/tests -p "test_*.py"
```
Expected: all tests pass, with the existing expected failures only.

**Step 3: Verify inline JS parses**

Run:
```powershell
@'
from pathlib import Path
import re, subprocess, tempfile, os
html = Path("prototype/index.html").read_text(encoding="utf-8-sig")
js = "\n".join(m.group(1) for m in re.finditer(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S | re.I))
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
    f.write(js)
    name = f.name
try:
    r = subprocess.run(["node", "--check", name], capture_output=True, text=True)
    print("node --check exit", r.returncode)
    if r.stderr:
        print(r.stderr)
finally:
    os.unlink(name)
'@ | .venv\Scripts\python -
```
Expected: `node --check exit 0`.

---

## Task 1: Real Per-Tab State

**Files:**
- Modify: `E:/WOS/Battle Simulator/prototype/index.html` around tab CSS/HTML and `initInteractions()`.

**Implementation:**

1. Add module state near the current globals:
   ```js
   const tabState = new Map();
   let applyingConfig = false;
   ```
2. Add helpers:
   ```js
   function activeTab(){ return document.querySelector('#tabs .tab[aria-selected="true"]'); }
   function snapshotTab(tab){
     if(!tab) return;
     tabState.set(tab,{config:formToConfig(), forecast:FORECAST});
   }
   function restoreTab(tab){
     const st=tabState.get(tab);
     applyingConfig=true;
     try{
       if(st&&st.config) configToForm(st.config);
       FORECAST=st&&st.forecast?st.forecast:null;
       if(FORECAST){ renderCharts(false); clearForecastStale(); }
       else markForecastStale('Run this config');
     } finally { applyingConfig=false; }
   }
   function selectTab(tab){
     const prev=activeTab();
     if(prev===tab) return;
     snapshotTab(prev);
     document.querySelectorAll('#tabs .tab').forEach(x=>x.setAttribute('aria-selected','false'));
     tab.setAttribute('aria-selected','true');
     restoreTab(tab);
   }
   ```
3. Replace the current tab click handler so it calls `selectTab(t)` instead of `loadForecast(...)`.
4. Initialize `tabState` for the first tab after builders/interactions run.
5. New tabs should snapshot the current form as their starting state; store it immediately in `tabState`.
6. Give every tab, including the first, a real close button:
   ```html
   <button class="x" type="button" aria-label="Close config">x</button>
   ```
7. When closing the active tab, select the previous sibling or next sibling. Never leave zero selected tabs.
8. Disable `#tabAdd` at five tabs and set title `Maximum 5 configs`.

**Verify:**
- Create two tabs, set different troop totals/heroes, run each, switch back and forth.
- Inputs and rendered forecast must restore without re-running.
- Close the active tab; a neighbor becomes active.
- At five tabs, the add button is disabled and explains why.

---

## Task 2: Stale Forecast Invalidation

**Files:**
- Modify: `prototype/index.html` CSS near `.forecast`.
- Modify: `prototype/index.html` JS near `renderCharts`, `runForecast`, and input listeners.

**Implementation:**

1. Add a chip inside `.forecast` or create it dynamically:
   ```html
   <div class="stale-chip" id="staleChip" hidden>inputs changed - re-run</div>
   ```
2. Add CSS:
   ```css
   .forecast.stale .fc-body{opacity:.55;filter:saturate(.6)}
   .stale-chip{position:absolute;right:18px;top:54px;z-index:3}
   ```
3. Add helpers:
   ```js
   function markForecastStale(msg='inputs changed - re-run'){
     if(applyingConfig) return;
     const fc=document.querySelector('.forecast'), chip=$('#staleChip');
     if(fc) fc.classList.add('stale');
     if(chip){ chip.hidden=false; chip.textContent=msg; }
   }
   function clearForecastStale(){
     document.querySelector('.forecast')?.classList.remove('stale');
     const chip=$('#staleChip'); if(chip) chip.hidden=true;
   }
   ```
4. In the delegated `.input` `input/change/herochange` listener, call `markForecastStale()` after `updateFinalStats()`, but skip while `applyingConfig`.
5. In successful `runForecast()` after `FORECAST=await res.json()`, call `clearForecastStale()`.
6. During tab restore and config load, wrap `configToForm()` with `applyingConfig=true/false`.

**Verify:**
- Run forecast.
- Change a formation slider.
- Forecast dims and chip appears.
- Run again; dim/chip clear.
- Switch tabs; restore does not mark stale by itself.

---

## Task 3: Inline Run Status Chip

**Files:**
- Modify: `prototype/index.html` near `#runBtn`.

**Implementation:**

1. Add a status element adjacent to the Run button:
   ```html
   <button class="run-status" id="runStatus" type="button" hidden></button>
   ```
2. Add CSS for compact mobile-friendly states: `.running`, `.done`, `.failed`.
3. Add:
   ```js
   function setRunStatus(state,msg){
     const c=$('#runStatus'); if(!c) return;
     c.hidden=!state;
     c.className='run-status '+(state||'');
     c.textContent=msg||'';
   }
   ```
4. In `runForecast()`:
   - before request: `setRunStatus('running','Running...')`
   - on success: `setRunStatus('done','Done')`
   - on error: `setRunStatus('failed','Failed')`
5. On click, status chip scrolls to forecast or error banner.

**Verify:**
- At desktop and 375px, click Run and confirm chip is visible near the button.
- Success chip scrolls to forecast.
- Trigger a 0-troops error; failed chip scrolls to banner.

---

## Task 4: Run-Flow Hardening

**Files:**
- Modify: `prototype/index.html` `runForecast()` and run/refresh handlers.

**Implementation:**

1. Add global:
   ```js
   let activeRun=null;
   ```
2. In `runForecast()`, abort any existing controller before starting a new one:
   ```js
   if(activeRun) activeRun.abort();
   const controller=new AbortController();
   activeRun=controller;
   ```
3. Pass `{signal: controller.signal}` to `fetch`.
4. Disable `#runBtn` and `#refreshBtn` while running, and set `aria-busy="true"` on `.forecast`.
5. Ignore `AbortError` except for cleanup.
6. Only apply the response if `activeRun===controller`.
7. Add Enter-to-run:
   - If focus is inside `.input`
   - no hero picker is open
   - target is not textarea/button/select
   - key is Enter
   then call `runForecast()`.
8. Leave seed re-roll out for now. It is explicitly optional and should be asked before implementation.

**Verify:**
- Double-click Run; only the latest response renders.
- Buttons are disabled while running.
- Enter in a numeric input starts a run.
- Escape/Enter behavior in hero picker is not broken.

---

## Task 5: Keyboard And Screen Reader Cluster

**Files:**
- Modify: `prototype/index.html`.

**Implementation:**

1. Restore slider focus rings:
   ```css
   .form-ctl input[type=range]:focus-visible{
     outline:2px solid var(--ice);
     outline-offset:2px;
   }
   ```
   Remove any local `outline:none` that suppresses it.
2. Hero picker ARIA:
   - trigger: `aria-haspopup="listbox"`, `aria-expanded`
   - popover list: `role="listbox"`
   - item: `role="option"`
   - selected item: `aria-selected="true"`
3. Hero picker keyboard:
   - ArrowDown/ArrowUp moves active option.
   - Enter selects active option.
   - Escape closes and returns focus to trigger.
4. Add a visually hidden live region:
   ```html
   <div id="liveStatus" class="sr-only" aria-live="polite"></div>
   ```
   On success: `Forecast updated - win chance 55.0%`.
5. Convert tab close spans to real buttons with `aria-label`.
6. Add F2 rename path for selected tab.
7. Stats inputs:
   - `aria-label="My Infantry Attack %"` and enemy equivalent.
   - Add visible `%` suffix without changing saved/API values.
8. Final Stats comparison glyphs:
   - higher: append `up`
   - lower: append `down`
   - equal: append `=`
   - keep color, but glyph/text makes it non-color-only.

**Verify:**
- Keyboard-only walk through role toggle, sliders, hero picker, tabs, run.
- Screen reader labels are meaningful.
- Final Stats can be interpreted without color.

---

## Task 6: Mobile And Persistence

**Files:**
- Modify: `prototype/index.html`.

**Implementation:**

1. Tap targets:
   - Keep visuals small where needed.
   - Add padding or pseudo-element hit areas to checkboxes, tab close buttons, steppers.
   - Minimum hit area: 24px now; 44px where layout permits.
2. Bucket labels:
   - Let labels wrap or shrink in forecast bars at 375px.
   - Avoid clipping inside `overflow:hidden` parents.
3. Autosave:
   - Debounce `formToConfig()` to `localStorage` key `wos:lastConfig:v1`.
   - On load, if stored config exists and differs from defaults, restore with `configToForm()`.
   - Show dismissible note: `Restored your last session`.
4. Touch tooltips:
   - Keep `title` for desktop.
   - On tap/click of skill icon, show a small popover with the same effect text.
   - Second tap outside closes.

**Verify:**
- 375px viewport: no horizontal overflow.
- Refresh page after edits; last session restores.
- Skill tooltip works on touch/click and hover.

---

## Task 7: P3 Polish

**Files:**
- Modify: `prototype/index.html`.
- Possibly create: `prototype/assets/fonts/*`.

**Implementation:**

1. Type/contrast:
   - Floor all text at 10px.
   - Consolidate sizes to a small scale.
   - Lighten low-contrast gray tokens until >= 4.5:1.
2. Remove rail selected side stripe:
   - Remove selected `border-left-color`.
   - Keep full border/background selected state.
3. Demo verdict flash:
   - Initial verdict should show `--` or skeleton.
   - Do not show hardcoded 68.4% before first real forecast.
4. Progress copy:
   - Replace fake staged text with generic `Simulating...` / `Finalizing...`.
5. Telemetry empty state:
   - If telemetry absent, show muted line `No skill telemetry for this matchup.`
6. Semantics:
   - Prefer proper tab semantics (`role="tablist"` and `role="tab"`) because tabs will hold real state after Task 1.
7. Copy consistency:
   - Choose `Infantry`, `Lancers`, `Marksmen` for class display labels.
8. Self-host fonts:
   - Download required woff2 files into `prototype/assets/fonts/`.
   - Replace Google Fonts import with `@font-face`.

**Verify:**
- No hardcoded forecast appears before a run.
- Contrast spot checks pass.
- App works offline with fonts.

---

## Task 8: Data-Side Follow-Up

**Files:**
- Review: `wos_sim/data/skill_display/hero_skills.json`
- Review generated front-end copy: `prototype/assets/skill_display.js`

**Implementation:**

1. Identify user-facing typos/mojibake in skill text.
2. Fix source JSON first.
3. Regenerate or patch `prototype/assets/skill_display.js` from the corrected source.
4. Reword engine confidence note if it leaks internal QA language.

**Verify:**
```powershell
rg -n "replacement-character|QA locks|TURN_PARAMS" wos_sim/data prototype/assets/skill_display.js
```
Also hover/tap a corrected skill icon and confirm tooltip text is user-facing.

---

## Final Regression Bar

Run after each task and at the end:

```powershell
.venv\Scripts\python -m unittest discover -s wos_sim/predictor/tests -p "test_*.py"
```

Run the encoding scan and JS syntax check from Baseline Verification.

Manual end-to-end:

- Start or refresh server: `.venv\Scripts\python -m uvicorn wos_sim.predictor.server:app --port 8000`
- Load `http://localhost:8000/?v=ux-backlog`
- Run a healthy forecast.
- Run a 0-troops error.
- Test keyboard-only hero picker and sliders.
- Test 375px mobile viewport.
- Confirm no passive troop skills return to the telemetry panel.

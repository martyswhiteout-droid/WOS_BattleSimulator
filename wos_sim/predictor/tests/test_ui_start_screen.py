"""Static regression test for the start journey / mode / generation-picker
contract (docs/UX_START_JOURNEY_SPEC.md, owner directive 2026-09-20).

This does not execute JS (no browser) — it checks that the static HTML the
prototype ships still carries the ids/classes/copy the shell builder codes
against, and that a couple of retired phrases never creep back in. Real
interactive behaviour (routing, mode switching, the generation picker) is
verified separately via Playwright — see the build report for that run.
"""
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PAGE = REPO / "prototype" / "index.html"


def read_page():
    return PAGE.read_text(encoding="utf-8")


class TestUiStartScreen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = read_page()

    # ---- view switch ----

    def test_body_starts_in_view_start(self):
        self.assertRegex(
            self.text, r'<body\s+class="view-start">',
            "body must carry class=\"view-start\" in the static markup so "
            "there is no flash of the workspace before JS runs.")

    # ---- start screen contract (§1.1) ----

    def test_start_screen_contract_ids_present(self):
        for needle in (
            'id="startScreen"', 'id="startGrid"', 'id="startSlotReports"',
            'id="startResume"', 'id="modeBar"', 'id="modeBarSlot"',
            'id="runBottom"', 'id="genMe"', 'id="genFoe"',
        ):
            self.assertIn(needle, self.text, f"missing contract id: {needle}")

    def test_start_screen_aria_labelledby(self):
        self.assertIn('aria-labelledby="startTitle"', self.text)
        self.assertIn('id="startTitle"', self.text)

    def test_start_slot_is_first_child_before_native_cards(self):
        grid_match = re.search(
            r'<div class="start-grid" id="startGrid">(.*?)</div>\s*<button type="button" class="start-resume"',
            self.text, re.S)
        self.assertIsNotNone(grid_match, "could not isolate #startGrid contents")
        grid_html = grid_match.group(1)
        slot_pos = grid_html.find('id="startSlotReports"')
        quick_pos = grid_html.find('data-start="quick"')
        custom_pos = grid_html.find('data-start="custom"')
        self.assertNotEqual(slot_pos, -1, "#startSlotReports not found inside #startGrid")
        self.assertNotEqual(quick_pos, -1, "quick card not found inside #startGrid")
        self.assertNotEqual(custom_pos, -1, "custom card not found inside #startGrid")
        self.assertLess(
            slot_pos, quick_pos,
            "#startSlotReports must come before the quick card (contract §1.1 order)")
        self.assertLess(
            quick_pos, custom_pos,
            "the quick card must come before the custom card (contract §1.1 order)")

    def test_start_slot_hidden_by_default(self):
        self.assertIn(
            '<div class="start-slot" id="startSlotReports" hidden></div>', self.text,
            "#startSlotReports must be empty and hidden in static markup — the "
            "shell fills it and removes hidden at serve time.")

    def test_native_start_cards_have_required_structure(self):
        for mode in ("quick", "custom"):
            m = re.search(
                r'<button type="button" class="start-card" data-start="%s">(.*?)</button>' % mode,
                self.text, re.S)
            self.assertIsNotNone(m, f"native start card for data-start={mode!r} not found")
            card_html = m.group(1)
            self.assertIn('class="start-card-icon"', card_html)
            self.assertIn('class="start-card-title"', card_html)
            self.assertIn('class="start-card-line"', card_html)
            self.assertIn('class="start-card-go"', card_html)

    def test_start_card_primary_class_defined_in_css(self):
        # the shell mounts its own card with this class; the prototype owns the style.
        self.assertIn(".start-card--primary", self.text)

    # ---- copy (§2.1, final unless a gate changes it) ----

    def test_start_screen_copy(self):
        for phrase in (
            "Who wins this battle?",
            "Choose how to set it up.",
            "Quick test",
            "Test heroes and formations. Stats are already filled in.",
            "Custom test",
            "Enter every stat yourself.",
            "Continue your last setup",
        ):
            self.assertIn(phrase, self.text, f"missing start-screen copy: {phrase!r}")

    def test_retired_phrase_absent(self):
        self.assertNotIn(
            "Fill from screenshots", self.text,
            "'Fill from screenshots' is retired (contract §3.1) and must not "
            "appear anywhere in the prototype.")

    # ---- JS API surface (§1.1) ----

    def test_wos_start_api_exposed(self):
        self.assertIn("window.wosStart", self.text)
        for member in ("enter:", "showStart:", "view:", "mode:"):
            self.assertIn(member, self.text, f"wosStart.{member.rstrip(':')} not defined")

    def test_wos_view_event_dispatched(self):
        self.assertIn("wos:view", self.text)

    # ---- mode bar (§2.2) ----

    def test_mode_bar_structure(self):
        self.assertIn('class="modebar-btn modebar-back"', self.text)
        self.assertIn('class="modebar-slot" id="modeBarSlot"', self.text)
        self.assertIn("Edit all stats", self.text)

    # ---- generation picker (§2.6) ----

    def test_generation_picker_markup(self):
        self.assertIn('class="duo gen-pick-row"', self.text)
        self.assertIn('<select id="genMe"', self.text)
        self.assertIn('<select id="genFoe"', self.text)
        self.assertIn("Captain heroes", self.text)

    # ---- bottom run button (§2.5) ----

    def test_run_bottom_is_inside_input_section_and_glossy(self):
        self.assertIn('class="run-bottom" id="runBottom"', self.text)
        self.assertIn("See who wins", self.text)

    # ---- Gate-1 round 2 (Round 18c) ----

    def test_header_run_button_is_a_secondary_re_run(self):
        """UXE-005: one primary action per screen.

        #runBottom is THE primary CTA; the header control keeps its id,
        handlers and the Runs select but is a compact secondary shortcut and
        must never carry the primary wording again.
        """
        m = re.search(r'<button[^>]*id="runBtn"[^>]*>(.*?)</button>', self.text, re.S)
        self.assertIsNotNone(m, "#runBtn not found")
        label = m.group(0)
        self.assertIn("Re-run", label, "the header control must read 'Re-run'")
        for retired in ("See who wins", "Run forecast"):
            self.assertNotIn(
                retired, label,
                f"the header #runBtn must never read {retired!r} again "
                "(owner constraint 5 / UXE-005)")

    def test_header_run_button_label_is_restored_if_something_relabels_it(self):
        """The shell's OCR arrival relabels #runBtn at runtime
        (shell/app/ocr/client/screens/setup.mjs relabelForecastCta, pinned by
        its own node test), so the prototype guards its own label."""
        self.assertIn("keepRerun", self.text)
        self.assertRegex(self.text, r"MutationObserver\(keepRerun\)")

    def test_custom_mode_has_the_reciprocal_action_back_to_quick(self):
        """UXE-027: Custom's only exit used to be '< Start'."""
        self.assertIn('id="modeBarQuick"', self.text)
        self.assertIn("Use prefilled stats", self.text)
        self.assertIn("mb-only mb-custom", self.text)

    def test_mode_change_is_announced_politely(self):
        """UXE-007: the programmatic focus move stays for screen readers, the
        923px focus ring does not."""
        self.assertRegex(
            self.text,
            r'<div class="modebar-info"[^>]*aria-live="polite"',
            "the mode bar title/helper must be a polite live region")
        self.assertIn("#modeBarTitle:focus,#startTitle:focus{outline:none}", self.text)

    def test_primary_start_card_has_a_contrast_scrim_and_text_shadow(self):
        """UXE-002: white copy on the glossy ramp measured 2.2-2.9:1."""
        self.assertIn(".start-card--primary::before", self.text)
        self.assertIn(
            ".start-card--primary .start-card-tag{background:rgba(2,26,47,.4)", self.text)

    def test_start_cards_lift_and_sink(self):
        """UXE-006: fill-mode:both pinned transform:none and swallowed both."""
        self.assertIn(".start-grid .start-card{animation-fill-mode:backwards}", self.text)
        self.assertIn(".start-card:active{transform:translateY(2px)}", self.text)
        self.assertIn(".start-card:not(.start-card--primary):hover", self.text)

    def test_scenario_add_button_renders_one_plus(self):
        """The label already starts with '+'; Round 11's <=960px ::before added
        a second one that Round 16 left in place."""
        self.assertIn(".rail-add::before{content:none}", self.text)


    # ---- Round 18e / Gate-1 UX review round 3 ----

    def test_hero_picker_closes_on_page_scroll_not_on_list_scroll(self):
        """UXE-037: .hpick-pop is position:fixed and placed once, so a page
        scroll used to detach it ~550px from the row it edits while still
        intercepting taps. One persistent capture listener closes it when the
        ANCHOR moves; the reviewer's {once:true} sketch would have closed the
        picker on the first scroll of the hero list instead."""
        self.assertIn("window.addEventListener('scroll', function(e){", self.text)
        start = self.text.index("window.addEventListener('scroll', function(e){")
        handler = self.text[start:self.text.index("}, {passive:true, capture:true});", start)]
        self.assertIn("{passive:true, capture:true}", self.text)
        self.assertNotIn("once", handler,
                         "a one-shot handler would close the picker on the first "
                         "wheel/touch scroll of the hero list")
        # the popover's own list scroll is ignored ...
        self.assertIn("openPop.contains(src)", self.text)
        # ... and only a real anchor displacement closes it
        self.assertIn("openAnchorRect", self.text)
        self.assertIn(
            "if(Math.abs(r.top-openAnchorRect.top)<=8 && "
            "Math.abs(r.left-openAnchorRect.left)<=8) return;", self.text)
        # never returnFocus on this path (it would scroll the page back)
        self.assertIn("trigger.focus({preventScroll:true})", self.text)
        self.assertIn("search.focus({preventScroll:true})", self.text)
        self.assertIn(".hpick-pop{overscroll-behavior:contain}", self.text)

    def test_route_change_targets_paint_a_keyboard_only_focus_ring(self):
        """UXE-038: Round 18c's `#modeBarTitle:focus,#startTitle:focus
        {outline:none}` (1,1,0) beat `.modebar-title:focus-visible` (0,2,0),
        so a keyboard user got no indicator at all. Restated at id
        specificity AFTER the 18c rule, so pointer/touch still get none."""
        none_at = self.text.find("#modeBarTitle:focus,#startTitle:focus{outline:none}")
        mode_at = self.text.find(
            "#modeBarTitle:focus-visible{outline:2px solid #5AAEF3;"
            "outline-offset:2px;border-radius:4px}")
        start_at = self.text.find(
            "#startTitle:focus-visible{outline:2px solid #5AAEF3;"
            "outline-offset:6px;border-radius:6px;")
        self.assertNotEqual(none_at, -1, "the Round 18c outline:none rule vanished")
        self.assertGreater(mode_at, none_at, "#modeBarTitle ring must come later in source")
        self.assertGreater(start_at, none_at, "#startTitle ring must come later in source")
        # the heading is a full-width block: hug the words, don't ring the column
        self.assertIn("width:fit-content;margin-inline:auto}", self.text)

    def test_outcome_chart_scroll_edges_fade_and_are_edge_aware(self):
        """UXE-039: the auto-scrolled chart showed sliced label tails at its
        boundaries. A 20px mask replaces them, and two classes keep it from
        fading a side that has no hidden content."""
        for rule in (
            ".cats.cats--more-l.cats--more-r{",
            ".cats.cats--more-l:not(.cats--more-r){",
            ".cats.cats--more-r:not(.cats--more-l){",
        ):
            self.assertIn(rule, self.text, f"missing edge-aware mask rule: {rule}")
        self.assertIn(
            "mask-image:linear-gradient(90deg,transparent 0,#fff 20px,"
            "#fff calc(100% - 20px),transparent 100%)", self.text)
        self.assertIn("cats.classList.toggle(MORE_L, l>padL+1)", self.text)
        self.assertIn("cats.classList.toggle(MORE_R, l<max-padR-1)", self.text)

    def test_touch_sweep_finishes_at_44px(self):
        """UXE-040-P: the three prototype-owned stragglers. Sizes only, and
        strictly inside any-pointer:coarse so desktop is untouched."""
        for rule in (
            ".hpick-pop .hpick-it{min-height:44px}",
            "#runBtn{height:44px;min-height:44px}",
            ".lead-row .gear-check{min-height:44px}",
        ):
            self.assertIn(rule, self.text, f"missing 44px rule: {rule}")
        # the 18e block, named explicitly: Round 19 appends a coarse block of its
        # own after it, so rindex() would point at the wrong one.
        coarse = self.text.index("@media (any-pointer:coarse){",
                                 self.text.index("UXE-040-P: the prototype's half"))
        self.assertGreater(
            self.text.find("#runBtn{height:44px;min-height:44px}"), coarse,
            "the 44px sweep must live inside the Round 18e coarse block")

    def test_allow_none_picker_row_never_requests_an_empty_avatar(self):
        """OOS-H: avatar('') === 'avatars/', and the row image used to be
        created (and its src set) before the h.none branch, so every joiner
        picker fired a detached GET /avatars/ -> 404."""
        self.assertIn(
            "else { const im=el('img'); im.src=avatar(h.f); im.alt=''; "
            "im.loading='lazy'; it.appendChild(im); }", self.text)
        self.assertNotIn(
            "const it=el('button','hpick-it'); const im=el('img'); im.src=avatar(h.f);",
            self.text)

    # ---- Round 19 / Gate-2 first-time-user round 1 ----

    def test_round19_is_one_appended_css_block_and_one_new_script(self):
        """House rule: a new CSS round is appended at the very end of <style>
        and new JS goes in a new <script> before </body>; earlier rounds are
        never rewritten."""
        marker = "/* === Round 19 - Gate-2 first-time-user round 1 (2026-09-21) === */"
        self.assertEqual(self.text.count(marker), 1, "exactly one Round 19 CSS block")
        self.assertGreater(
            self.text.index(marker),
            self.text.index("Round 18e - Gate-1 UX review round 3"),
            "Round 19 must come after Round 18e (it wins by source order, not !important)")
        self.assertLess(
            self.text.index(marker), self.text.index("</style>"),
            "the Round 19 block must live inside the <style> element")
        r19_js = self.text.index("Round 19 - Gate-2 first-time-user round 1 (tester reports")
        self.assertGreater(
            r19_js, self.text.index("Round 18e - Gate-1 UX review round 3 (reviewer report"),
            "the Round 19 script must come after the Round 18e script")
        self.assertLess(
            r19_js,
            self.text.index("Round 20 - Gate-2 first-time-user round 3 (tester report"),
            "the Round 19 script must come before the Round 20 one "
            "(the 'last script before </body>' check moved to the Round 20 test)")

    def test_formation_percent_box_is_a_real_type_in_field(self):
        """P1 (U1-D1 desktop T2 score 4, U1-M1 mobile T2 score 3): `.fval`
        wears the porcelain input recipe and both testers clicked it first,
        but it was an inert <div>. It now types - and commits through the
        row's OWN input[type=range] + an 'input' event, so recalc() stays the
        only place formation maths happens."""
        # affordance
        self.assertIn(".form-ctl:not(.auto) .fval{cursor:text", self.text)
        self.assertIn(".form-ctl:not(.auto) .fval:focus-visible{outline:2px solid #5AAEF3",
                      self.text)
        # the editor is a SIBLING that stands in the hidden div's place - paint()
        # rewrites .fval.textContent on every recalc and would destroy a child
        self.assertIn(".form-ctl .fval.is-editing{display:none}", self.text)
        self.assertIn("box.parentNode.insertBefore(ed, box.nextSibling);", self.text)
        self.assertIn("ed.className='fval fval-edit';", self.text)
        # the one write path
        self.assertIn("r.dispatchEvent(new Event('input',{bubbles:true}));", self.text)
        # clamped to a whole 0-100 before it is handed over
        self.assertIn("n=Math.max(0,Math.min(100,n));", self.text)
        # Marksman is the derived remainder: never a tab stop, never a caret
        self.assertIn("if(!row || row.classList.contains('auto')) return false;", self.text)
        self.assertIn("stack.querySelectorAll('.form-ctl:not(.auto) .fval')", self.text)
        # count mode is untouched
        self.assertIn("if(!stack || stack.classList.contains('count-mode')) return false;",
                      self.text)
        # keyboard contract: Enter / Escape / arrows, blur and Tab commit via blur
        for needle in ("if(k==='Enter'){ e.preventDefault(); endEdit(true,true); }",
                       "else if(k==='Escape'||k==='Esc'){ e.preventDefault(); endEdit(false,true); }",
                       "else if(k==='ArrowUp'){ e.preventDefault(); stepBy(1); }",
                       "function onEditorBlur(){ endEdit(true,false); }"):
            self.assertIn(needle, self.text, f"missing P1 key handling: {needle}")
        # named for screen readers
        self.assertIn("' percent')", self.text)

    def test_formation_builder_was_not_forked(self):
        """P1 follows Round 18e's 'decorate, never rebuild': buildFormation()
        still creates the same inert <div class=fval>, and the delegation sits
        on the two stacks because the rows are rebuilt wholesale."""
        self.assertIn("const val=el('div','fval'); val.textContent=init[cl]+'%';", self.text)
        build = self.text[self.text.index("function buildFormation()"):
                          self.text.index("function setFormationMode(")]
        self.assertNotIn("fval-edit", build, "buildFormation() must stay untouched")
        self.assertIn("var STACK_SEL=['#formMe','#formFoe'];", self.text)
        self.assertIn("observe(stack,{childList:true})", self.text)

    def test_formation_percent_box_is_a_44px_touch_target(self):
        """P1 (touch): >=44x52 with >=16px type while editing, so the keypad
        opens and iOS never zooms the page on focus."""
        self.assertIn(".troops-formation-block .form-ctl .fval{", self.text)
        self.assertIn("min-height:44px;min-width:52px;padding-block:0;", self.text)
        self.assertIn(".troops-formation-block .form-ctl:not(.auto) .fval-edit{font-size:16px",
                      self.text)
        self.assertIn("ed.inputMode='numeric';", self.text)
        self.assertIn("ed.setAttribute('pattern','[0-9]*');", self.text)
        # the editor stands in the box's exact footprint instead of an <input>'s
        # ~20-character intrinsic width (which shoved the slider aside)
        self.assertIn("ed.style.width=Math.round(r0.width)+'px';", self.text)

    def test_header_logo_goes_home(self):
        """P2 (U1-M6, the mobile tester's #1 annoyance): tapping the brand did
        nothing at all. The .flake tile is the single tab stop so the <h1>
        keeps its heading semantics; .brand is a pointer-only target."""
        self.assertIn(
            '<div class="flake" role="button" tabindex="0" aria-label="Back to start">',
            self.text)
        self.assertIn('<div class="brand"><h1>Whiteout Tactics</h1>', self.text)
        brand = self.text[self.text.index('<div class="brand">'):]
        brand = brand[:brand.index("</div>")]
        self.assertNotIn("tabindex", brand, ".brand must not be a second tab stop")
        self.assertIn(".bar .flake,.bar .brand{cursor:pointer}", self.text)
        self.assertIn(".bar .flake:focus-visible{outline:2px solid #5AAEF3", self.text)
        # silent no-op when the start screen is already showing
        self.assertIn("if(typeof api.view==='function' && api.view()==='start') return;",
                      self.text)
        self.assertIn("api.showStart();", self.text)

    def test_generation_pickers_read_as_section_headers_on_mobile(self):
        """P3 (U1-M2): the mobile tester scrolled straight past ENEMY
        GENERATION - it sat 7px under my last hero card with its divider
        BELOW it. Keep the Round 18b placement, make it a band with the break
        (and the divider) above. <=700px only: desktop/tablet is untouched."""
        band = self.text.index("#capMe>.gen-pick,#capFoe>.gen-pick{\n      justify-content:flex-start")
        media = self.text.rindex("@media (max-width:700px){", 0, band)
        self.assertGreater(band, media, "the band must live inside a <=700px media block")
        self.assertIn("border:1px solid rgba(255,255,255,.09);border-left:3px solid #55BFFF;",
                      self.text)
        self.assertIn("#capFoe>.gen-pick{position:relative;margin-top:28px;"
                      "border-left-color:#FF8181}", self.text)
        # the divider moves from below the picker to above the enemy block
        self.assertIn("#capFoe>.gen-pick::after{content:\"\";position:absolute;"
                      "left:0;right:0;top:-14px;", self.text)

    def test_stat_rows_say_which_column_is_whose(self):
        """P4 (U1-M5): on a phone the MY SIDE / ENEMY heading scrolls away and
        12 rows of identical white boxes are left. (a) tint each input's outer
        edge, (b) a sticky caption row, (c) one fixed centre column so the two
        input columns stop being ragged (measured 78-95px before)."""
        self.assertIn("#statPanel .duo .me input{border-left:3px solid var(--ice)}", self.text)
        self.assertIn("#statPanel .duo .foe input{border-right:3px solid var(--ember)}",
                      self.text)
        self.assertIn("#statPanel .duo,.stat-cap{grid-template-columns:"
                      "minmax(0,1fr) 92px minmax(0,1fr)}", self.text)
        self.assertIn("#statPanel .duo .lab.stat-name{white-space:normal", self.text)
        self.assertIn("position:sticky;\n      top:var(--wos-sticky-top,60px);", self.text)
        # built as a SIBLING before #statPanel, because buildStats() clears the panel
        self.assertIn("host.insertBefore(cap, panel);", self.text)
        self.assertIn("cap.setAttribute('aria-hidden','true');", self.text)
        self.assertIn("me.textContent='MY SIDE';", self.text)
        self.assertIn("foe.textContent='ENEMY';", self.text)
        build = self.text[self.text.index("function buildStats()"):
                          self.text.index("function buildFinalStats()")]
        self.assertIn("p.innerHTML='';", build, "buildStats() must stay untouched")
        self.assertNotIn("stat-cap", build)

    def test_formation_step_buttons_repeat_when_held(self):
        """P5 (U1-M3): 50% -> 60% cost the mobile tester nine taps. A held
        button repeats its OWN click handler, and the release click is
        swallowed so a hold never lands one step extra."""
        self.assertIn("var HOLD_DELAY=400, HOLD_EVERY=80;", self.text)
        self.assertIn("holdTick=setInterval(fireRepeat, HOLD_EVERY);", self.text)
        self.assertIn("try{ btn.click(); }", self.text)
        self.assertIn("if(holdFiring) return;", self.text)
        self.assertIn(".fbtn{touch-action:manipulation;user-select:none;", self.text)
        self.assertIn("if(!btn || btn.disabled) return;", self.text)

    def test_custom_from_start_admits_it_kept_your_numbers(self):
        """P6 (U1-D3): picking Custom test fresh from the start screen quietly
        shows the previous numbers (correct per spec 2.4 - enter() never
        touches data). Say so instead of resetting anything."""
        self.assertIn("if(d.view!=='work' || d.mode!=='custom' || d.from!=='start') return;",
                      self.text)
        self.assertIn("showSessionNote('Your last numbers are still here')", self.text)
        handler = self.text[self.text.index("function initStartOverNote()"):
                            self.text.index("/* ---------------- wiring ----------------")]
        for forbidden in ("configToForm", "buildStats(", "localStorage", ".value="):
            self.assertNotIn(forbidden, handler,
                             "the start-over note must never reset or overwrite data")

    # ---- Round 20 / Gate-2 first-time-user round 3 ----

    def test_round20_is_one_appended_css_block_and_one_new_script(self):
        """House rule: a new CSS round is appended at the very end of <style>
        and new JS goes in a new <script> before </body>; earlier rounds are
        never rewritten."""
        marker = "/* === Round 20 - Gate-2 first-time-user round 3 (2026-09-22) === */"
        self.assertEqual(self.text.count(marker), 1, "exactly one Round 20 CSS block")
        self.assertGreater(
            self.text.index(marker),
            self.text.index(
                "/* === Round 19 - Gate-2 first-time-user round 1 (2026-09-21) === */"),
            "Round 20 must come after Round 19 (it wins by source order)")
        self.assertLess(
            self.text.index(marker), self.text.index("</style>"),
            "the Round 20 block must live inside the <style> element")
        r20_js = self.text.index("Round 20 - Gate-2 first-time-user round 3 (tester report")
        self.assertGreater(
            r20_js,
            self.text.index("Round 19 - Gate-2 first-time-user round 1 (tester reports"),
            "the Round 20 script must come after the Round 19 script")
        self.assertEqual(
            self.text.count("</script>\n</body>"), 1,
            "the Round 20 script must be the last one before </body>")

    def test_run_bottom_is_pinned_while_the_inputs_are_on_screen(self):
        """U3D-T4 (Gate-2 round 3, top annoyance #3, "the run button moves
        around"): the tester typed two stats in Custom test, found no run
        control on screen and had to scroll past the hero roster and the whole
        FINAL STATS table to reach one. #runBottom now sticks to the foot of
        the viewport for as long as section.input is in view and comes to rest
        in flow at the end of the section. No new control - the header stays a
        secondary "Re-run" (UXE-005)."""
        self.assertIn(
            "body.view-work #runBottom{position:sticky;bottom:44px;z-index:5}", self.text,
            "#runBottom must be pinned in the workspace")
        self.assertIn(
            "body.view-work #runBottom{bottom:calc(10px + env(safe-area-inset-bottom))}",
            self.text,
            "at <=700px the legal strip is in flow, so only the safe-area inset is owed")
        # 5 has to stay UNDER everything that must be able to cover the button
        for higher in ("z-index:60", "z-index:120", "z-index:150", "z-index:200"):
            self.assertIn(higher, self.text)
        # position only: a pinned CTA must not depend on anything the
        # reduced-motion kill-switch strips, and must not need an override
        rule = self.text[self.text.index("body.view-work #runBottom{"):]
        rule = rule[:rule.index("}") + 1]
        for forbidden in ("transition", "animation", "transform", "!" + "important"):
            self.assertNotIn(forbidden, rule)

    def test_quick_mode_shows_the_heroes_before_the_troop_tabs(self):
        """U3D-T2 (Gate-2 round 3, top annoyance #1): entering Quick test at
        1440x900 put #genMe/#genFoe at top=897 in a 900px viewport and #capMe
        at top=950, so every generation select and every hero portrait started
        below the fold. In quick mode the two .hero-block panels now sit
        directly under .sides-head, above the Troops & formation tab group."""
        # a DOM move, put back on every non-quick entry
        for needle in ("sec.insertBefore(cap, tabs);", "sec.insertBefore(join, tabs);",
                       "sec.insertBefore(cap, home);", "sec.insertBefore(join, home);",
                       "document.body.dataset.mode==='quick'",
                       "document.addEventListener('wos:view', sync);"):
            self.assertIn(needle, self.text)
        # a #quick deep link never dispatches wos:view, so boot has to place too
        self.assertIn(
            "if(document.readyState==='loading') "
            "window.addEventListener('DOMContentLoaded', sync);",
            self.text)
        # NOT a CSS reorder: section.input must stay a block container, or
        # custom mode's margin collapsing (and therefore its geometry) changes
        self.assertNotRegex(
            self.text, r"section\.input\{[^}]*display:\s*flex",
            "section.input must stay a block container")
        self.assertNotIn('.iblock.hero-block{order:', self.text)

    def test_empty_generation_row_is_collapsed_on_phones_in_quick_mode(self):
        """Follow-on to U3D-T2: at <=700px the Round 18b script relocates both
        .gen-pick labels into #capMe/#capFoe, which leaves .duo.gen-pick-row an
        empty 19px box still carrying a 10px margin, 10px padding and a 1px
        divider - 40px of dead band with a stray rule, now sitting directly
        under MY SIDE / ENEMY. Collapsed only while the row really is empty, so
        a browser that never ran the relocation still shows its two selects."""
        self.assertIn(
            'body[data-mode="quick"] .hero-block .duo.gen-pick-row'
            ':not(:has(.gen-pick)){display:none}', self.text)


if __name__ == "__main__":
    unittest.main()

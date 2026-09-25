#!/usr/bin/env python3
"""Build the project page from `docs/data.json`.

The paper has eight pages and the study produced a great deal more than that. Everything cut for
space lands here instead of being lost: the full operating-point front, the utility grid with its
paired tests, every attack cell, the prior-quality sweep, exposure on both routes and under every
denominator, and the stability grid.

**Nothing is typed by hand.** Every number is read from `data.json`, which
`experiments/` writes from the result files on the cluster, so the page cannot drift from the
measurements the way a hand-maintained table does. Regenerate with:

    python docs/build_site.py

`data.json` carries aggregates only — no corpus text, no surface form, no identity — because
CARDIO:DE is DUA-restricted and Enron contains real personal data.
"""

from __future__ import annotations

import json
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = json.loads((HERE / "data.json").read_text(encoding="utf-8"))

CORPORA = ["cardiode", "tab", "ontonotes", "enron"]
NICE = {"cardiode": "CARDIO:DE", "tab": "TAB", "ontonotes": "OntoNotes", "enron": "Enron"}
RULES = ["union", "vote2", "vote3", "intersection"]
REC_TAG = "union-single0.5-13det-1797ba"
TAG_NICE = {REC_TAG: "recommended 13", "15det": "15-detector pool"}
RULE_NICE = {"union": "union", "vote2": "vote 2", "vote3": "vote 3", "intersection": "intersection"}


def f(value, digits=3, dash="—"):
    if value is None:
        return dash
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return escape(str(value))


def pct(value, digits=1, dash="—"):
    return dash if value is None else f"{float(value) * 100:.{digits}f}%"


def num(value, dash="—"):
    return dash if value is None else f"{int(value):,}"


def table(headers, rows, cls="", note="", groups=""):
    """``groups`` is an optional pre-rendered <tr> placed above the header, for paired columns."""
    head = groups + "<tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr>"
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    caption = f"<p class='note'>{note}</p>" if note else ""
    return (f"<div class='tw'><table class='{cls}'><thead>{head}</thead>"
            f"<tbody>{body}</tbody></table></div>{caption}")


def bar(value, maximum, label, tone="a"):
    """A horizontal bar, drawn in CSS rather than fetched, so the page has no dependencies."""
    width = 0 if not maximum else max(0.6, 100 * float(value) / maximum)
    return (f"<div class='bar'><span class='bl'>{label}</span>"
            f"<span class='bt'><i class='b{tone}' style='width:{width:.1f}%'></i></span>"
            f"<span class='bv'>{f(value)}</span></div>")


# ---------------------------------------------------------------- detection
def section_detection():
    rows = []
    for c in CORPORA:
        pts = DATA["operating_points"].get(c, {})
        for i, (name, p) in enumerate(pts.items()):
            rows.append([
                f"<b>{NICE[c]}</b>" if i == 0 else "",
                name.replace("-", " ").lower(),
                p["rule"], f(p["sensitivity"]), f(p["specificity"], 4),
                f(p["precision"]), f(p["information_weighted_precision"]),
                f(p["cost_parallel_s"], 3), f(p["cost_serial_s"], 3), len(p["ensemble"]),
            ])
    # The recommended 13 lie outside a sweep over singles, pairs and triples, so say by how much
    # they beat its "maximum" row rather than asserting where they do.
    beats = []
    for c in CORPORA:
        top = (DATA["operating_points"].get(c) or {}).get("MAX-SENSITIVITY") or {}
        rec = ((DATA.get("both_rates") or {}).get(c) or {}).get("union", {}).get("overall") or {}
        if top.get("sensitivity") is not None and rec.get("sensitivity") is not None:
            beats.append(f"{NICE[c]} {f(rec['sensitivity'])} against {f(top['sensitivity'])}")
    enron_pts = DATA["operating_points"].get("enron") or {}
    regold = next((p for p in enron_pts.values() if p.get("superseded")), None)
    t1 = table(["Corpus", "Operating point", "Rule", "Sens.", "Spec.", "Prec.", "IW prec.",
                "Cost ∥ (s)", "Cost Σ (s)", "Members"], rows,
               note="Cost ∥ is the slowest member, which is what a parallel run pays; Cost Σ is the "
                    "sum, which is what a serial one pays. The paper reports only the first. "
                    "Information-weighted precision scales each masked token by how poorly its "
                    "context predicts it. This search covers singles, pairs and triples only, so "
                    "the recommended 13-detector ensemble lies outside it and exceeds the "
                    "&ldquo;maximum&rdquo; row on every corpus — " + "; ".join(beats) + ". "
                    + ("<b>Enron's four rows are re-scored against the corrected gold</b> "
                       "described under the next table. The <em>selection</em> was not re-run: "
                       f"these triples were chosen by the {num(regold['sweep_sources'])}-source "
                       "sweep as it scored on the superseded gold, so a fresh sweep could pick "
                       "different members. The rows say what these ensembles achieve now, not "
                       "that they would still win. Their information-weighted precision is left "
                       "blank rather than filled, because it was "
                       f"{escape(regold['information_weighted_precision_note'])}."
                       if regold else ""))

    br = DATA.get("both_rates") or {}
    rows = []
    for c in CORPORA:
        rec = DATA["recommended"].get(c, {})
        for i, (rule, key) in enumerate((("union", "union"), ("vote2", "vote-2"),
                                         ("vote3", "vote-3"), ("intersection", "intersection"))):
            m = (br.get(c) or {}).get(key, {}).get("overall")
            r = rec.get(rule) or {}
            if not m:
                continue
            first = i == 0
            rows.append([
                f"<b>{NICE[c]}</b>" if first else "",
                RULE_NICE[rule] + (" <span class='sd'>(max. sensitivity)</span>" if first else ""),
                f"<b>{f(m['sensitivity'], 4)}</b>", f"<b>{f(m['specificity'], 4)}</b>",
                f(m["person_sensitivity"], 4), f(m["precision"], 3),
                num(r.get("replacements")),
            ])
    t2 = table(["Corpus", "Rule", "Sensitivity", "Specificity", "Person sensitivity",
                "Precision", "Replacements"], rows,
               note="The 13 detectors under each combining rule, both error rates together. "
                    "<b>Union is the maximum-sensitivity configuration of this ensemble</b>: no "
                    "other rule over the same members can find more, and every leakage figure on "
                    "this page describes that release. The rows beneath it price the alternative — "
                    "agreement buys specificity and pays for it in sensitivity. Precision mixes the "
                    "two denominators and is reported beside them, never optimised for.")
    return t1, t2


def enron_correction_callout():
    """What the Enron gold correction of 2026-09-25 changed, and what it did not."""
    block = DATA.get("enron_gold_correction")
    if not block:
        return ""
    was = block["superseded"]
    now_u = DATA["both_rates"]["enron"]["union"]["overall"]
    was_u = was["union_overall"]
    body_now = DATA["enron_header_split"]["regions"]["body"]["person_sensitivity"]
    body_was = was["header_split_person_sensitivity"]["body"]
    return (
        f"<div class='callout'><p><b>Enron's gold layer was corrected on "
        f"{escape(block['corrected'])}.</b> Every Enron figure on this page, the cost&ndash;quality "
        f"front above included, is read against the corrected version. "
        f"The corpus adapter matched a correspondent's display name as an "
        f"unanchored substring, so a short mailbox name was found inside ordinary English words "
        f"and role accounts — <code>info@</code>, <code>questions@</code>, <code>news@</code> — "
        f"entered the gold as people whose mentions were common nouns. Word-boundary anchoring and "
        f"a role-account filter remove them: {num(was_u['person_gold_tokens'])} person identifier "
        f"tokens become {num(now_u['person_gold_tokens'])}, and person sensitivity rises from "
        f"{f(was_u['person_sensitivity'], 4)} to {f(now_u['person_sensitivity'], 4)}. The document "
        f"text is byte-identical under the fix, so nothing was re-detected and both published patch "
        f"sets are unchanged.</p>"
        f"<p><b>Specificity does not move: {f(was_u['specificity'], 4)} before, "
        f"{f(now_u['specificity'], 4)} after.</b> It is read over the non-identifier tokens, which "
        f"the defect barely touched, so Enron's over-replacement is a property of this ensemble on "
        f"this corpus and not an artefact of the gold. The same correction lifts person sensitivity "
        f"in the message <em>body</em> from {f(body_was, 4)} to {f(body_now, 4)}, so the earlier "
        f"reading that detection fails on prose and succeeds only on headers was a reading of the "
        f"defect.</p></div>")


# ---------------------------------------------------------------- languages
LANG_ROWS = [
    ("German", "cardiode", None), ("English", "tab", None), ("English", "enron", None),
    ("English", "ontonotes", "english"), ("Chinese", "ontonotes", "chinese"),
    ("Arabic", "ontonotes", "arabic"),
]


def section_languages():
    br = DATA.get("both_rates") or {}
    if not br:
        return "", ""

    def cell(corpus, lang, rule="union"):
        block = (br.get(corpus) or {}).get(rule)
        if not block:
            return None
        return block["by_language"][lang] if lang else block["overall"]

    rows, last = [], None
    for language, corpus, lang in LANG_ROWS:
        m = cell(corpus, lang)
        if not m:
            continue
        rows.append([
            f"<b>{language}</b>" if language != last else "",
            NICE[corpus] + (f" <span class='sd'>({lang})</span>" if lang else ""),
            num(m["documents"]),
            f"<b>{f(m['sensitivity'], 3)}</b>", f"<b>{f(m['specificity'], 4)}</b>",
            f(m["person_sensitivity"], 3), f(m["precision"], 3),
            num(m["sensitivity_gold_tokens"]), num(m["total_tokens"]),
        ])
        last = language
    t1 = table(["Language", "Source", "Docs", "Sensitivity", "Specificity",
                "Person sensitivity", "Precision", "Identifier tokens", "Tokens"], rows,
               note="The 13-detector union throughout, so every row describes the release the "
                    "attacks were run against. Only OntoNotes is multilingual; German, and the "
                    "English of TAB and Enron, are whole corpora. Sensitivity and specificity are "
                    "read against their own denominators — identifier tokens and everything else — "
                    "so neither can be judged without the other.")

    onto = br.get("ontonotes") or {}
    rows = []
    for lang in ("english", "chinese", "arabic"):
        for i, key in enumerate(("union", "vote-2", "vote-3", "intersection")):
            m = (onto.get(key) or {}).get("by_language", {}).get(lang)
            if not m:
                continue
            rows.append([
                f"<b>{lang.capitalize()}</b>" if i == 0 else "",
                key + (" <span class='sd'>(max. sens.)</span>" if key == "union" else ""),
                f(m["sensitivity"], 3), f(m["specificity"], 4),
                f(m["person_sensitivity"], 3), f(m["precision"], 3), num(m["documents"]),
            ])
    t2 = table(["Language", "Rule", "Sensitivity", "Specificity", "Person sensitivity",
                "Precision", "Docs"], rows,
               note="What the combining rule costs, language by language. The gap between "
                    "sensitivity and person sensitivity is the point: the three languages differ "
                    "far more on the full identifier set than on people, and people are what the "
                    "attacks recover.")
    return t1, t2


# ---------------------------------------------------------------- utility
def section_cross_corpus_utility():
    """Entity agreement on all four corpora — the same task, the same two rules, four genres."""
    util = DATA["utility_by_corpus"]
    rows = []
    for c in CORPORA:
        for i, rule in enumerate(("union", "vote")):
            d = (util.get(c, {}).get(rule) or {}).get("ner_agreement")
            if not d:
                continue
            cells = []
            for cond in ("A", "B", "C"):
                v = d.get(cond)
                cells.append("—" if not v else
                             f"{v['mean']:.3f} <span class='sd'>± {v['sd']:.3f}</span>")
            rows.append([f"<b>{NICE[c]}</b>" if i == 0 else "",
                         "permissive (union of 15)" if rule == "union" else "precise (8 of 15)",
                         *cells, num(d.get("A", {}).get("n"))])
    t = table(["Corpus", "Rule", "A — original", "B — surrogates", "C — placeholders", "Docs"], rows,
              note="Mean ± one standard deviation over documents, every document of each corpus. "
                   "<b>Column A is 1.000 everywhere by construction and is not a result</b>: "
                   "<code>ner_agreement</code> scores the frozen recogniser against its own output "
                   "on the unmodified text, so A is the definition of perfect agreement, not a "
                   "measurement of it. It is printed because the paired design requires the "
                   "original-text score beside every condition. Read B and C down the two rules of "
                   "one corpus, never across corpora: the genres differ in how much of a document "
                   "is a name.")

    def span(rule, cond):
        vals = [util[c][rule]["ner_agreement"][cond]["mean"] for c in CORPORA
                if (util.get(c, {}).get(rule) or {}).get("ner_agreement", {}).get(cond)]
        return (min(vals), max(vals)) if vals else (None, None)

    ulo, uhi = span("union", "B")
    vlo, vhi = span("vote", "B")
    callout = (f"<div class='callout'><p><b>Detector precision governs utility on all four corpora, "
               f"not only the clinical one.</b> Under the permissive union the same frozen "
               f"recogniser agrees with itself on only {f(ulo)}–{f(uhi)} of its original findings; "
               f"requiring a majority of the same fifteen detectors recovers {f(vlo)}–{f(vhi)}. "
               f"Same policy, same surrogates, same documents — only which spans were replaced "
               f"changed.</p></div>")
    return t, callout


def section_utility():
    util = DATA["utility"]
    tasks = sorted({t for rule in util.values() for t in rule})
    rows = []
    for task in tasks:
        for i, rule in enumerate(("union", "vote")):
            d = util.get(rule, {}).get(task)
            if not d:
                continue
            cells = []
            for cond in ("A", "B", "C"):
                v = d.get(cond)
                cells.append("—" if not v else f"{v['mean']:.3f} <span class='sd'>± {v['sd']:.3f}</span>")
            rows.append([f"<code>{task}</code>" if i == 0 else "",
                         "permissive (union of 15)" if rule == "union" else "precise (8 of 15)",
                         *cells, num(d.get("A", {}).get("n"))])
    t1 = table(["Task", "Rule", "A — original", "B — surrogates", "C — placeholders", "Docs"], rows,
               note="Mean ± one standard deviation over documents, on CARDIO:DE, which is the "
                    "only corpus carrying the clinical tasks. "
                    "<code>ner_agreement</code> is 1.000 on A by construction: it scores the frozen "
                    "recogniser against its own output on the original text. "
                    "<code>medication_ie:in_narrative</code> is retained here but excluded from the "
                    "paper's conclusions, because the frozen model is near chance on the original "
                    "text and so cannot measure a loss.")

    rows = []
    for s in DATA["statistics"]:
        rows.append([
            f"<code>{s['task']}</code>",
            "permissive" if s["span_source"] == "union" else "precise",
            f"A → {s['condition']}", num(s["n"]), s["test"],
            f"{s['reference_mean']:.3f} <span class='sd'>± {s['reference_sd']:.3f}</span>",
            f"{s['condition_mean']:.3f} <span class='sd'>± {s['condition_sd']:.3f}</span>",
            f"{s['mean_difference']:+.3f} <span class='sd'>± {s['difference_sd']:.3f}</span>",
            f"{s['q_value']:.3g}",
            f"<span class='{'sig' if s['significant'] else 'ns'}'>"
            f"{'yes' if s['significant'] else 'no'}</span>",
            f"{s['effect']:.3f}",
        ])
    t2 = table(["Task", "Rule", "Pair", "n", "Test", "Reference", "Condition", "Difference",
                "q", "Sig.", "Effect"], rows,
               note="Wilcoxon signed-rank on paired documents of CARDIO:DE, Benjamini–Hochberg "
                    "corrected within task families. Effect is the rank-biserial correlation. A rank-biserial of "
                    "−1.000 means <em>every</em> document lost, not merely the average.")
    return t1, t2


# ---------------------------------------------------------------- leakage
def section_a4():
    rows = []
    order = {"A": 0, "B": 1, "B-forewarned": 2, "B-mask": 3, "C": 4}
    label = {"A": "A — unmodified", "B": "B — surrogates",
             "B-forewarned": "B — attacker told the scheme", "B-mask": "B — attacker masks names",
             "C": "C — typed placeholders"}
    for c in CORPORA:
        cells = [r for r in DATA["a4"] if r["corpus"] == c]
        if not cells:
            continue
        # the recommended release first: it is the one every other number on this page describes
        cells.sort(key=lambda r: (r["tag"] != REC_TAG, order.get(r["condition"], 9), r["context"]))
        for i, r in enumerate(cells):
            chance = 1.0 / r["candidates"]
            lift = r["rank1"] / chance if chance else 0
            rows.append([
                f"<b>{NICE[c]}</b>" if i == 0 else "",
                label.get(r["condition"], r["condition"]),
                "yes" if r["context"] else "no",
                f(r["rank1"]), f(r["rank5"]), f(r["map"]),
                f"{lift:.1f}×", num(r["queries"]),
                escape(TAG_NICE.get(r["tag"], str(r["tag"]))),
            ])
    return table(["Corpus", "Condition", "Aux. context", "Rank-1", "Rank-5", "mAP",
                  "× chance", "Queries", "Ensemble"], rows,
                 note="Ten candidates per query, so chance is Rank-1 0.100 and Rank-5 0.500. "
                      "The recommended 13-detector release is listed first for each corpus; the "
                      "15-detector rows are the earlier run over the full pool, kept because they "
                      "show the finding does not depend on the ensemble. "
                      "The two <em>attacker</em> rows are the same surrogate release read by an "
                      "adversary who knows it is pseudonymised: one simply told so, one replacing "
                      "name-like spans it finds with a public name list. Neither changes what the "
                      "defender published.")


def section_a2():
    rows = []
    for c in CORPORA:
        r = DATA["recommended"].get(c, {}).get("union")
        if not r:
            continue
        rows.append([
            NICE[c], num(r["a2_bound_observed"]),
            num(r["a2_bound_correct_by_alignment"]), num(r["a2_real_correct_by_alignment"]),
            num(r["a2_real_undetected_recovered"]),
            escape(str(r["a2_real_prior"])), num(r["a2_real_prior_size"]),
            f"{r['a2_real_chance']:.2e}", f"{r['a2_real_c_at_1']:.5f}", f(r["a2_rho"], 3),
        ])
    t1 = table(["Corpus", "Surfaces observed", "Aligned — oracle prior", "Aligned — public prior",
                "Read in clear", "Public prior", "Prior size", "Chance", "c@1", "ρ"], rows,
               note="<b>Aligned</b> counts identities recovered by matching frequencies, which is "
                    "the attack. <b>Read in clear</b> counts names the detector missed, which the "
                    "release simply printed: the attacker recovers those by reading, not by "
                    "inferring, and the two must never be added into one rate. The oracle prior is "
                    "the corpus's own distribution, which no real adversary holds. ρ is Spearman's "
                    "correlation between the surrogate and real frequency orders.")

    rows = []
    for c in CORPORA:
        sweep = DATA["recommended"].get(c, {}).get("_prior_sweep") or []
        for i, s in enumerate(sweep):
            rows.append([
                f"<b>{NICE[c]}</b>" if i == 0 else "",
                escape(str(s["prior"])), num(s.get("prior_size")),
                escape(str(s.get("prior_vintage") or "—")),
                num(s["correct_by_alignment"]), num(s["undetected_recovered"]),
            ])
    total = sum(1 for c in CORPORA for s in (DATA["recommended"].get(c, {}).get("_prior_sweep") or []))
    hits = sum(s["correct_by_alignment"] for c in CORPORA
               for s in (DATA["recommended"].get(c, {}).get("_prior_sweep") or []))
    t2 = table(["Corpus", "Prior", "Size", "Vintage", "Aligned", "Read in clear"], rows,
               note=f"The prior-quality sweep Bindschaedler et al. prescribe: vary what the "
                    f"adversary knows, along size and along age, and report accuracy per cell. "
                    f"Across all {total} cells, spanning three orders of magnitude of prior size, "
                    f"frequency alignment recovers <b>{hits}</b> identit"
                    f"{'y' if hits == 1 else 'ies'} in total. Better knowledge buys the attack "
                    f"nothing here, which is the point of running the sweep rather than asserting "
                    f"a single prior is representative.")

    rows = []
    for c in CORPORA:
        curve = DATA["recommended"].get(c, {}).get("_abstention") or []
        for i, s in enumerate(curve):
            rows.append([
                f"<b>{NICE[c]}</b>" if i == 0 else "",
                escape(str(s["prior"])), f(s["phi"], 2),
                num(s["attempted"]), num(s["abstained"]),
                f"{s['accuracy_attempted']:.5f}", f"{s['c_at_1']:.5f}",
            ])
    t3 = table(["Corpus", "Prior", "φ", "Answered", "Abstained", "Accuracy (answered)", "c@1"], rows,
               note="Abstention follows Narayanan and Shmatikov's eccentricity rule: the attacker "
                    "declines when (max − max₂)/σ falls below φ, computed from its own scores and "
                    "never from the truth. c@1 credits a warranted abstention at the rate the "
                    "attacker achieves where it does answer. Above φ = 0 the attack abstains on "
                    "almost everything, which is the attack telling us it cannot tell which of its "
                    "answers to trust.")
    return t1, t2, t3


def section_linkage():
    rows = []
    for c in CORPORA:
        rec = DATA["recommended"].get(c, {})
        shown = False
        for rule in RULES:
            r = rec.get(rule)
            if not r or r.get("a3f_rank1") is None:
                continue
            gallery = r.get("a3_gallery")
            chance = (1.0 / gallery) if gallery else None
            m = ((DATA.get("both_rates") or {}).get(c) or {}).get(
                {"union": "union", "vote2": "vote-2", "vote3": "vote-3", "intersection": "intersection"}[rule], {}).get("overall") or {}
            rows.append([
                f"<b>{NICE[c]}</b>" if not shown else "", RULE_NICE[rule],
                f(m.get("person_sensitivity"), 3), f(m.get("specificity"), 4),
                f"{r['a3f_rank1']:.4f} <span class='sd'>± {r['a3f_rank1_sd']:.4f}</span>",
                f"{r['a5_rank1']:.4f} <span class='sd'>± {r['a5_rank1_sd']:.4f}</span>",
                f"{r['a5_rank5']:.4f} <span class='sd'>± {r['a5_rank5_sd']:.4f}</span>",
                f(r.get("a3_ceiling_rank1"), 3), num(gallery), num(r.get("a3_queries")),
                f"{chance:.2e}" if chance else "—",
            ])
            shown = True
        if not shown:
            note = (rec.get("union") or {}).get("relational_note") or "not measurable"
            m = ((DATA.get("both_rates") or {}).get(c) or {}).get("union", {}).get("overall") or {}
            rows.append([f"<b>{NICE[c]}</b>", "union",
                         f(m.get("person_sensitivity"), 3), f(m.get("specificity"), 4),
                         f"<span class='ns'>{escape(note)}</span>", "", "", "", "", "", ""])
    return table(["Corpus", "Rule", "Person sens.", "Specificity", "Context linkage (Rank-1)",
                  "Learned linkage (Rank-1)", "Learned (Rank-5)", "Ceiling on A",
                  "Gallery", "Queries", "Chance"], rows,
                 note="Five-fold cross-validation, mean ± one standard deviation over folds. Folds "
                      "withhold <em>labels</em>, never candidates: a held-out person stays in the "
                      "complete candidate list with every distractor, so the attacker is never told "
                      "that a query has a match. <b>Ceiling on A</b> is the same attack against "
                      "unmodified text, which is what gives the protected numbers a scale.")


def ratio(exposed, total):
    """``n / N (p%)`` — the count and its rate, because neither reads without the other."""
    return (f"{num(exposed)} / {num(total)} "
            f"<b>({pct(exposed / max(total, 1), 2 if exposed / max(total, 1) < 0.01 else 1)})</b>")


def section_exposure():
    """Exposure as the release actually printed it, with the denominators kept apart."""
    rel = DATA.get("exposure_from_release") or {}
    skip = DATA.get("release_skip") or {}
    rows = []
    for c in CORPORA:
        e = (rel.get(c) or {}).get("person")
        if not e:
            continue
        unit = "cases" if e["cases_are_real"] else "documents"
        rows.append([
            NICE[c],
            ratio(e["distinct_people_exposed"], e["distinct_people"]),
            ratio(e["entity_document_pairs_exposed"], e["entity_document_pairs"]),
            ratio(e["documents_exposed"], e["documents"]),
            f"{num(e['cases_exposed'])} / {num(e['cases'])} <span class='sd'>{unit}</span>",
            num(e["exposed_mentions_never_found"]),
            num(e["exposed_mentions_clipped"]),
        ])
    rates = sorted(v["skip_rate"] for v in skip.values() if v.get("skip_rate") is not None)
    worst = max(skip, key=lambda c: skip[c]["skip_rate"]) if skip else None
    mildest = min(skip, key=lambda c: skip[c]["skip_rate"]) if skip else None
    t1 = table(["Corpus", "People with a name in the clear", "Entity&ndash;document pairs",
                "Documents", "Cases", "Mentions never found", "Mentions clipped"], rows,
               note="<b>Route one: the released patch sets</b>, which is what the reader of the "
                    "release sees, rather than the union of detected spans. The two differ because "
                    "the engine writes one span of any overlapping group and skips the rest"
                    + (f" — {pct(rates[0])} of resolved detections on {NICE.get(mildest, mildest)}"
                       f" and {pct(rates[-1])} on {NICE.get(worst, worst)}" if rates else "") +
                    ", so where a short span wins over a longer one the rest of the name is "
                    "published. Those are the <em>clipped</em> mentions, and no measure computed "
                    "on detected spans can see them. The two person denominators are also kept "
                    "apart: someone appearing in forty Enron messages is one person and forty "
                    "entity&ndash;document pairs. The paper's leakage table uses the pair "
                    "denominator, but on the other route &mdash; the next table.")

    den = DATA.get("exposure_denominators") or {}
    rows = []
    for c in CORPORA:
        e = (den.get(c) or {}).get("person")
        if not e:
            continue
        rows.append([
            NICE[c],
            ratio(e["distinct_entities_exposed"], e["distinct_entities"]),
            ratio(e["entity_document_pairs_exposed"], e["entity_document_pairs"]),
            ratio(e["documents_exposed"], e["documents"]),
            f"{num(e['mentions_exposed'])} / {num(e['mentions'])}",
        ])
    t_det = table(["Corpus", "People with a name in the clear", "Entity&ndash;document pairs",
                   "Documents", "Mentions"], rows,
                  note="<b>Route two: the union of detected spans.</b> A mention counts as exposed "
                       "only when no detector covered it, so a name that was found and then "
                       "clipped by the overlap rule is counted as protected here and as exposed "
                       "above. Both questions are legitimate and the answers are not "
                       "interchangeable: this route measures the detectors, the route above "
                       "measures the release. <b>The entity&ndash;document-pair column is the "
                       "paper's <em>Exp.</em> column</b> — the risk that a person is still named "
                       "in a given document after processing, not the share of people, which is "
                       "the column beside it.")

    rows = []
    for c in CORPORA:
        e = (rel.get(c) or {}).get("replaced")
        if not e:
            continue
        rows.append([
            NICE[c],
            ratio(e["distinct_people_exposed"], e["distinct_people"]),
            ratio(e["documents_exposed"], e["documents"]),
            num(e["exposed_mentions_never_found"]), num(e["exposed_mentions_clipped"]),
        ])
    t2 = table(["Corpus", "Entities with something in the clear", "Documents",
                "Mentions never found", "Mentions clipped"], rows,
               note="The same accounting over every identifier class the conditions replace, not "
                    "people alone, and on route one. Dates, quantities and miscellaneous spans are "
                    "passed through by design and are in neither denominator.")
    return t1, t_det, t2, enron_clipping_callout()


def enron_clipping_callout():
    """After the gold correction, Enron's residue is dominated by clipping, not by misses."""
    block = DATA.get("enron_gold_correction")
    e = ((DATA.get("exposure_from_release") or {}).get("enron") or {}).get("person")
    if not block or not e:
        return ""
    was = block["superseded"]["exposure_person"]
    share = e["exposed_mentions_clipped"] / max(e["mentions_exposed"], 1)
    return (
        f"<div class='callout'><p><b>On Enron the residue is now almost entirely clipping.</b> "
        f"Mentions the ensemble never found fall from {num(was['exposed_mentions_never_found'])} "
        f"to {num(e['exposed_mentions_never_found'])} once the gold no longer counts ordinary words "
        f"and role accounts as names. Mentions that were found and then truncated barely move — "
        f"{num(was['exposed_mentions_clipped'])} to {num(e['exposed_mentions_clipped'])} — and are "
        f"now {num(e['exposed_mentions_clipped'])} of the {num(e['mentions_exposed'])} person "
        f"mentions the release leaves in the clear, {pct(share)} of them.</p>"
        f"<p>The dominant residual failure on this corpus is therefore not a detector missing a "
        f"name. It is the engine resolving overlapping spans and writing a shorter one, so the rest "
        f"of the name is published — a failure no measure computed on detected spans can see.</p>"
        f"</div>")


def section_stability():
    rows = []
    seen = set()
    for s in DATA["stability"]:
        if s["condition"] != "B":
            continue
        key = (s["corpus"], s["rule"], s["entity_type"], s["cross_document"])
        if key in seen:
            continue
        seen.add(key)
        rows.append([
            NICE.get(s["corpus"], s["corpus"]), s["rule"], s["entity_type"],
            "cross-document" if s["cross_document"] else "within document",
            num(s["chains"]), pct(s["collision_rate"], 2), pct(s["fragmentation_rate"], 2),
            pct(s["drift_rate"], 2) if s["drift_rate"] is not None else "—",
        ])
    return table(["Corpus", "Rule", "Type", "Scope", "Chains", "Collision", "Fragmentation",
                  "Drift"], rows,
                 note="A <b>collision</b> gives two distinct people one surrogate, "
                      "<b>fragmentation</b> gives one person several inside a document, and "
                      "<b>drift</b> changes a person's surrogate between documents. All three are "
                      "properties of the keyed mapping in condition B; typed placeholders merge "
                      "every entity of a type by design and have none of them. The paper reports "
                      "three of these numbers; this is the grid they come from.")


def headline_cards():
    """Three numbers that carry the study, each read from the data rather than typed."""
    enron = DATA["recommended"]["enron"]["union"]
    sweeps = [s for c in CORPORA for s in (DATA["recommended"].get(c, {}).get("_prior_sweep") or [])]
    hits = sum(s["correct_by_alignment"] for s in sweeps)
    def a4(condition, tag=REC_TAG):
        return next((r["rank1"] for r in DATA["a4"]
                     if r["corpus"] == "tab" and r["condition"] == condition
                     and not r["context"] and r["tag"] == tag), None)

    naive, told = a4("B"), a4("B-forewarned")
    cards = [
        ("Frequency matching recovers", f"{hits} of {len(sweeps)}",
         "prior-sweep cells yield a single identity between them, across three orders of magnitude "
         "of adversary knowledge"),
        ("Linkage on unmodified e-mail", f(enron.get("a3_ceiling_rank1"), 3),
         f"falls to {f(enron['a3f_rank1'], 4)} after the recommended release, against a "
         f"1/{num(enron['a3_gallery'])} chance rate"),
        ("Telling the attacker the scheme",
         f"{f(naive)} → {f(told)}" if naive is not None and told is not None else "—",
         "on a surrogate release, without altering one character of the published text"),
    ]
    return "".join(
        f"<div class='card'><div class='ck'>{escape(k)}</div>"
        f"<div class='cv'>{escape(v)}</div><div class='cd'>{escape(d)}</div></div>"
        for k, v, d in cards)


def language_callout():
    """What the three OntoNotes languages spread over — computed, not remembered."""
    onto = ((DATA.get("both_rates") or {}).get("ontonotes") or {}).get("union", {})
    by = onto.get("by_language") or {}
    if not by:
        return ""
    best = max(by, key=lambda k: by[k]["sensitivity"])
    worst = min(by, key=lambda k: by[k]["sensitivity"])
    return (
        f"<div class='callout'><p><b>The spread is in the other identifier classes, not in finding "
        f"people.</b> Sensitivity over the whole identifier set runs {f(by[best]['sensitivity'])} "
        f"on {best.capitalize()} down to {f(by[worst]['sensitivity'])} on {worst.capitalize()}; "
        f"person sensitivity runs {f(by[best]['person_sensitivity'])} down to "
        f"{f(by[worst]['person_sensitivity'])}. That matters because the attacks recover "
        f"<em>people</em>, so the alarming figure and the figure that bounds leakage are not the "
        f"same number — and specificity moves only from {f(by[best]['specificity'], 4)} to "
        f"{f(by[worst]['specificity'], 4)} across the three, so the spread is not "
        f"over-replacement either.</p></div>")


def fast_cell_callout():
    """The fast sensitivity cell against the maximum one, on the corpus where it is sharpest."""
    pts = (DATA.get("operating_points") or {}).get("cardiode") or {}
    top, fast = pts.get("MAX-SENSITIVITY"), pts.get("FAST-SENSITIVITY")
    if not top or not fast:
        return ""
    return (
        f"<div class='callout'><p><b>The fast cell is usually not the worse cell.</b> On CARDIO:DE "
        f"the fast sensitivity point gives up "
        f"{f(top['sensitivity'] - fast['sensitivity'])} of sensitivity but is <em>more</em> "
        f"specific than the maximum — {f(fast['specificity'], 4)} against "
        f"{f(top['specificity'], 4)} — and "
        f"{top['cost_parallel_s'] / fast['cost_parallel_s']:.0f}× cheaper. Catching the last "
        f"identifiers means over-detecting, and over-detection has its own price — which only the "
        f"second column shows.</p></div>")


def informed_callout():
    """The B-vs-C reading, read from the attack cells rather than remembered.

    The headline card and this paragraph used to quote different ensembles for the same claim — the
    card the recommended 13, the paragraph the earlier 15-detector pool — so both now read the same
    rows and the alternative pool is named rather than quoted silently.
    """
    def cell(condition, tag, corpus="tab"):
        return next((r["rank1"] for r in DATA["a4"]
                     if r["corpus"] == corpus and r["condition"] == condition
                     and not r["context"] and r["tag"] == tag), None)

    docs = {c: (DATA.get("utility_by_corpus", {}).get(c, {}).get("union", {})
                .get("ner_agreement", {}).get("A", {}).get("n")) for c in ("tab", "ontonotes")}
    rec = [cell(k, REC_TAG) for k in ("B", "C", "B-forewarned")]
    pool = [cell(k, "15det") for k in ("B", "C", "B-forewarned")]
    alt = (f" The earlier 15-detector pool orders the same way, "
           f"{f(pool[0])} / {f(pool[1])} / {f(pool[2])}." if all(v is not None for v in pool) else "")
    return (
        f"<div class='callout'><p><b>The finding that reorganised the paper.</b> Conditions B and C "
        f"replace <em>identical</em> spans, so overwriting each replaced span of the surrogate "
        f"release with <code>[PERSON]</code> reproduces the placeholder release character for "
        f"character — verified on all {num(docs['tab'])} TAB and all {num(docs['ontonotes'])} "
        f"OntoNotes documents.</p>"
        f"<p>A release cannot be safer than a text anyone can compute from it. So when a "
        f"candidate-ranking model scores {f(rec[0])} on the TAB surrogate release against "
        f"{f(rec[1])} on the placeholder one, that is not protection: it is the ranker believing "
        f"the surrogate. Tell it the scheme and it reaches {f(rec[2])} on exactly the same "
        f"published bytes.{alt}</p></div>")


SECTIONS = [
    ("detection", "Detection"),
    ("languages", "Languages"),
    ("utility", "Utility"),
    ("leakage", "Leakage"),
    ("exposure", "Exposure"),
    ("stability", "Stability"),
    ("about", "About"),
]


def build() -> str:
    op1, op2 = section_detection()
    lg1, lg2 = section_languages()
    utx, utx_callout = section_cross_corpus_utility()
    ut1, ut2 = section_utility()
    a2a, a2b, a2c = section_a2()
    ex1, ex_det, ex2, ex_callout = section_exposure()
    nav = "".join(f"<a href='#{i}'>{escape(n)}</a>" for i, n in SECTIONS)
    ensemble = "".join(f"<li><code>{escape(d)}</code></li>" for d in DATA["ensemble"])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pseudonymisation — the results behind the paper</title>
<meta name="description" content="The text component of multimodal releases: detection, utility
and leakage measured end to end on four corpora — the full result set behind an eight-page paper.">
<style>
:root {{
  --bg:#fbfaf8; --fg:#1b1a18; --muted:#6b675f; --line:#e2ded6; --card:#fff;
  --accent:#8a3324; --accent-soft:#f5ece9; --good:#2f6f4f; --warn:#8a6d966;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --bg:#16151a; --fg:#eceaf0; --muted:#a7a2b0; --line:#2e2c36; --card:#1d1c22;
    --accent:#e08a72; --accent-soft:#2a211f; --good:#7fc0a0;
  }}
}}
:root[data-theme="dark"] {{
  --bg:#16151a; --fg:#eceaf0; --muted:#a7a2b0; --line:#2e2c36; --card:#1d1c22;
  --accent:#e08a72; --accent-soft:#2a211f; --good:#7fc0a0;
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--fg);
  font:16px/1.62 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Helvetica,Arial,sans-serif;
  -webkit-font-smoothing:antialiased; }}
.wrap {{ max-width:1080px; margin:0 auto; padding:0 24px; }}
header {{ border-bottom:1px solid var(--line); background:var(--card); }}
.hero {{ padding:64px 0 40px; }}
h1 {{ font-size:clamp(28px,4.4vw,44px); line-height:1.12; margin:0 0 14px; letter-spacing:-.022em; }}
h1 span {{ color:var(--accent); }}
.lede {{ font-size:clamp(16px,2vw,19px); color:var(--muted); max-width:62ch; margin:0 0 26px; }}
.links a {{ display:inline-block; margin:0 10px 8px 0; padding:8px 15px; border-radius:7px;
  border:1px solid var(--line); text-decoration:none; color:var(--fg); font-size:14.5px;
  background:var(--bg); transition:.14s; }}
.links a:hover {{ border-color:var(--accent); color:var(--accent); }}
.links a.primary {{ background:var(--accent); color:#fff; border-color:var(--accent); }}
.links a.primary:hover {{ opacity:.9; color:#fff; }}
nav {{ position:sticky; top:0; z-index:10; background:color-mix(in srgb,var(--bg) 88%,transparent);
  backdrop-filter:blur(9px); border-bottom:1px solid var(--line); }}
nav .wrap {{ display:flex; gap:4px; overflow-x:auto; }}
nav a {{ padding:13px 13px; font-size:14px; color:var(--muted); text-decoration:none;
  white-space:nowrap; border-bottom:2px solid transparent; }}
nav a:hover {{ color:var(--accent); border-bottom-color:var(--accent); }}
section {{ padding:52px 0 8px; border-bottom:1px solid var(--line); }}
section:last-of-type {{ border-bottom:0; }}
h2 {{ font-size:27px; margin:0 0 6px; letter-spacing:-.018em; }}
h2 .n {{ color:var(--accent); font-variant-numeric:tabular-nums; font-size:15px;
  display:block; margin-bottom:5px; letter-spacing:.09em; text-transform:uppercase; }}
h3 {{ font-size:18px; margin:38px 0 8px; }}
p {{ max-width:74ch; }}
.sub {{ color:var(--muted); max-width:74ch; margin-top:0; }}
.cards {{ display:grid; gap:14px; grid-template-columns:repeat(auto-fit,minmax(244px,1fr));
  margin:30px 0 8px; }}
.card {{ background:var(--card); border:1px solid var(--line); border-radius:11px; padding:18px 19px; }}
.ck {{ font-size:12.5px; text-transform:uppercase; letter-spacing:.075em; color:var(--muted); }}
.cv {{ font-size:31px; font-weight:650; margin:7px 0 6px; letter-spacing:-.02em; color:var(--accent);
  font-variant-numeric:tabular-nums; }}
.cd {{ font-size:14px; color:var(--muted); line-height:1.5; }}
.tw {{ overflow-x:auto; margin:16px 0 4px; border:1px solid var(--line); border-radius:10px;
  background:var(--card); }}
table {{ border-collapse:collapse; width:100%; font-size:14px;
  font-variant-numeric:tabular-nums lining-nums; }}
th,td {{ text-align:right; padding:9px 13px; border-bottom:1px solid var(--line);
  white-space:nowrap; }}
th:first-child,td:first-child,th:nth-child(2),td:nth-child(2) {{ text-align:left; }}
.grp {{ text-align:center !important; font-weight:600; }}
thead th {{ position:sticky; top:0; background:var(--card); font-weight:600; font-size:12.5px;
  text-transform:uppercase; letter-spacing:.045em; color:var(--muted);
  border-bottom:1.5px solid var(--line); }}
tbody tr:last-child td {{ border-bottom:0; }}
tbody tr:hover {{ background:var(--accent-soft); }}
code {{ font-family:var(--mono); font-size:.9em; background:var(--accent-soft);
  padding:1px 5px; border-radius:4px; }}
.sd {{ color:var(--muted); font-size:.88em; }}
.sig {{ color:var(--accent); font-weight:600; }}
.ns {{ color:var(--muted); }}
.note {{ font-size:13.5px; color:var(--muted); max-width:82ch; margin:9px 2px 0; line-height:1.55; }}
.callout {{ border-left:3px solid var(--accent); background:var(--accent-soft);
  padding:15px 18px; border-radius:0 9px 9px 0; margin:24px 0; }}
.callout p {{ margin:0; }}
.callout p + p {{ margin-top:9px; }}
ul.cols {{ columns:2; gap:26px; font-size:14px; padding-left:19px; }}
ul.cols li {{ margin-bottom:3px; break-inside:avoid; }}
footer {{ padding:40px 0 64px; color:var(--muted); font-size:13.5px; }}
footer p {{ max-width:78ch; }}
@media (max-width:640px) {{ ul.cols {{ columns:1; }} .hero {{ padding:44px 0 30px; }} }}
</style>
</head>
<body>
<header><div class="wrap hero">
  <h1>The text beside the image,<br><span>measured end to end</span></h1>
  <p class="lede">Medical images are released with the free text that describes them, and protecting
  the image does not protect the report. <b>This study measures the text component of such
  releases</b> — detection, downstream utility and residual identity leakage, on the same documents,
  with the pseudonymisation policy as the variable under test. Four corpora — clinical letters, legal
  judgments, news, e-mail — in German, English, Chinese and Arabic.</p>
  <p class="lede"><b>This page carries what the eight-page paper had no room for.</b> Every number is
  generated from the result files, not transcribed.</p>
  <div class="cards">{headline_cards()}</div>
  <div class="links">
    <a class="primary" href="main.pdf">Read the paper (PDF)</a>
    <a href="https://github.com/akmaier/pseudonymization">Repository</a>
    <a href="data.json">Raw data (JSON)</a>
  </div>
</div></header>

<nav><div class="wrap">{nav}</div></nav>

<div class="wrap">

<section id="detection">
  <h2><span class="n">01</span>Detection</h2>
  <p class="sub">What an ensemble catches, what it wrongly catches, and what it costs.</p>
  <div class="callout"><p><b>The release under study is the 13-detector ensemble combined by union,
  which is that ensemble's maximum-sensitivity configuration</b> — no other rule over the same
  members can find more. Every leakage, exposure and language figure on this page describes that one
  release.</p>
  <p>Three rates, three denominators, never interchangeable. <b>Sensitivity</b> is the share of
  identifier tokens found, over the types condition B replaces; dates, quantities and miscellaneous
  spans pass through by design and are not in it. <b>Person sensitivity</b> is the same rate over
  <code>PERSON</code> alone, which is what the attacks act on. <b>Specificity</b> is the share of
  non-identifier tokens left alone. Sensitivity without specificity is unreadable — an ensemble that
  replaces every token scores a perfect 1.0 and destroys the text — so both are given
  throughout. <b>Precision</b> mixes the two denominators and is reported beside them, never
  optimised for.</p></div>
  <h3>The cost–quality front, in full</h3>
  {op1}
  {fast_cell_callout()}
  <h3>The recommended ensemble under every combining rule</h3>
  {op2}
  {enron_correction_callout()}
  <h3>The 13 detectors</h3>
  <ul class="cols">{ensemble}</ul>
  <p class="note">Two further large language models were run as single detectors and excluded from
  the recommended ensemble: preliminary runs made them one to two orders of magnitude slower per
  document without improving detection.</p>
</section>

<section id="languages">
  <h2><span class="n">02</span>By language</h2>
  <p class="sub">A pooled score describes no language in particular. Scripts differ in how many
  subword tokens they need, annotation differs in what it marks, and the detectors were not trained
  evenly across the four.</p>
  {lg1}
  <h3>OntoNotes, split three ways</h3>
  {lg2}
  {language_callout()}
</section>

<section id="utility">
  <h2><span class="n">03</span>Utility</h2>
  <p class="sub">Frozen models read all three conditions. The question is not whether the text
  changed but whether the task survives, so every comparison is paired per document and carries the
  original-text score beside it. Entity agreement was measured on all four corpora; the clinical
  information-extraction and section tasks exist only for the clinical letters.</p>
  <h3>Entity agreement, all four corpora</h3>
  {utx}
  {utx_callout}
  <h3>CARDIO:DE, every task</h3>
  {ut1}
  <h3>The paired tests in full</h3>
  {ut2}
  <div class="callout"><p>The placeholder column is partly an artefact and is labelled as one: the
  frozen recogniser never tags <code>[PERSON]</code> as a name, so every replaced mention counts as a
  disagreement. Read that column between rules, not between forms.</p></div>
</section>

<section id="leakage">
  <h2><span class="n">04</span>Leakage</h2>
  <p class="sub">Three attacks against the released text, all scored over the full denominator with
  collisions counted rather than dropped, because an attacker has no ground truth to drop them
  with.</p>

  {informed_callout()}

  <h3>Candidate ranking, every cell</h3>
  {section_a4()}

  <h3>Frequency matching</h3>
  {a2a}

  <h3>Prior quality: the adversary-knowledge sweep</h3>
  {a2b}

  <h3>Abstention</h3>
  {a2c}

  <h3>Context and learned linkage</h3>
  {section_linkage()}
</section>

<section id="exposure">
  <h2><span class="n">05</span>Exposure</h2>
  <p class="sub">A corpus-level token rate is the least informative way to state what a
  pseudonymisation run left behind. Data-protection officers release documents and cases, and one
  unchanged mention puts a person back in the clear however many others were replaced.</p>
  {ex1}
  <h3>The same exposure, measured on the detected spans</h3>
  {ex_det}
  <h3>Where the residue is</h3>
  {ex2}
  {ex_callout}
</section>

<section id="stability">
  <h2><span class="n">06</span>Stability</h2>
  <p class="sub">A keyed pseudonym is only useful if it is stable, and only safe if it is not too
  stable. These are the ways the mapping fails.</p>
  {section_stability()}
</section>

<section id="about">
  <h2><span class="n">07</span>About these numbers</h2>
  <p>Every experiment is driven by a config plus a seed, and each result records the library
  versions, model ids and commit hash that produced it. The page is generated from
  <a href="data.json">one JSON export</a> of those result files by
  <code>docs/build_site.py</code>, so it cannot drift from the measurements the way a hand-maintained
  table does.</p>
  <p><b>Text, and only text.</b> The motivation is multimodal — a radiograph travels with its
  report, a cardiology study with its discharge letter, and releasing either half requires both to be
  protected — but the study itself is not. Nothing here is an image experiment: no scan is defaced,
  no burned-in pixel text is read, and no claim is made about what image de-identification costs.
  Every measurement on this page is made on written documents, which is the half of such a release
  that identifier replacement has to carry.</p>
  <p><b>Corpora are not redistributed here.</b> Several are bound by a data-use agreement, licensed,
  or contain real personal data. This export carries aggregates only: no corpus text, no surface
  form, no identity. CARDIO:DE in particular is single-user under its agreement with Heidelberg, and
  its gold names were inserted into an already de-identified release, which makes its name
  distribution synthetic and its clinical realism partial.</p>
  <p><b>Enron is used deliberately</b> rather than silently: it is the only public e-mail corpus with
  real names in a natural frequency distribution, and excluding it would have protected nobody who
  is not already in every copy of the corpus.</p>
  <p><b>What the attacks do not show.</b> Frequency alignment failing on these data does not
  establish safety against other adversaries. Linkage is measurable only where identity crosses
  documents, so TAB and OntoNotes figures understate rather than bound their risk. Candidate ranking
  presents ten names, which bounds an adversary holding a shortlist, not one searching a population.
  Every number describes one release under one key.</p>
</section>

</div>
<footer><div class="wrap">
  <p>Generated from the study's own result files. Figures on this page are the full set; the paper
  reports the subset that fits in eight pages.</p>
</div></footer>
</body>
</html>
"""


if __name__ == "__main__":
    (HERE / "index.html").write_text(build(), encoding="utf-8")
    print(f"wrote {HERE / 'index.html'}")

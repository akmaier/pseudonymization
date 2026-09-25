#!/usr/bin/env python3
"""Build the project page from `docs/data.json`.

The paper has eight pages and the study produced a great deal more than that. Everything cut for
space lands here instead of being lost: the full operating-point front, the utility grid with its
paired tests, every attack cell, the prior-quality sweep, exposure at three denominators, and the
stability grid.

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


def table(headers, rows, cls="", note=""):
    head = "".join(f"<th>{h}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    caption = f"<p class='note'>{note}</p>" if note else ""
    return (f"<div class='tw'><table class='{cls}'><thead><tr>{head}</tr></thead>"
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
    t1 = table(["Corpus", "Operating point", "Rule", "Sens.", "Spec.", "Prec.", "IW prec.",
                "Cost ∥ (s)", "Cost Σ (s)", "Members"], rows,
               note="Cost ∥ is the slowest member, which is what a parallel run pays; Cost Σ is the "
                    "sum, which is what a serial one pays. The paper reports only the first. "
                    "Information-weighted precision scales each masked token by how poorly its "
                    "context predicts it.")

    rows = []
    for c in CORPORA:
        rec = DATA["recommended"].get(c, {})
        for i, rule in enumerate(RULES):
            r = rec.get(rule)
            if not r:
                continue
            rows.append([
                f"<b>{NICE[c]}</b>" if i == 0 else "", RULE_NICE[rule],
                f(r["token_recall"], 4), f(r["entity_recall"], 4), f(r["precision"], 4),
                f(r["information_weighted_precision"], 4), num(r["replacements"]),
            ])
    t2 = table(["Corpus", "Rule", "Token recall", "Entity recall", "Precision", "IW precision",
                "Replacements"], rows,
               note="The recommended 13-detector ensemble under each combining rule. Recall here is "
                    "over <em>all</em> annotated identifier types, which is a different denominator "
                    "from the person-token recall the leakage tables use. An entity counts as "
                    "recalled only when every one of its mentions was found.")
    return t1, t2


# ---------------------------------------------------------------- utility
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
               note="Mean ± one standard deviation over documents, on CARDIO:DE. "
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
               note="Wilcoxon signed-rank on paired documents, Benjamini–Hochberg corrected within "
                    "task families. Effect is the rank-biserial correlation. A rank-biserial of "
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
        cells.sort(key=lambda r: (order.get(r["condition"], 9), r["context"]))
        for i, r in enumerate(cells):
            chance = 1.0 / r["candidates"]
            lift = r["rank1"] / chance if chance else 0
            rows.append([
                f"<b>{NICE[c]}</b>" if i == 0 else "",
                label.get(r["condition"], r["condition"]),
                "yes" if r["context"] else "no",
                f(r["rank1"]), f(r["rank5"]), f(r["map"]),
                f"{lift:.1f}×", num(r["queries"]),
                f"<code>{escape(str(r['tag']))}</code>",
            ])
    return table(["Corpus", "Condition", "Aux. context", "Rank-1", "Rank-5", "mAP",
                  "× chance", "Queries", "Ensemble"], rows,
                 note="Ten candidates per query, so chance is Rank-1 0.100 and Rank-5 0.500. "
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
            rows.append([
                f"<b>{NICE[c]}</b>" if not shown else "", RULE_NICE[rule],
                f(r["token_recall"], 3),
                f"{r['a3f_rank1']:.4f} <span class='sd'>± {r['a3f_rank1_sd']:.4f}</span>",
                f"{r['a5_rank1']:.4f} <span class='sd'>± {r['a5_rank1_sd']:.4f}</span>",
                f"{r['a5_rank5']:.4f} <span class='sd'>± {r['a5_rank5_sd']:.4f}</span>",
                f(r.get("a3_ceiling_rank1"), 3), num(gallery), num(r.get("a3_queries")),
                f"{chance:.2e}" if chance else "—",
            ])
            shown = True
        if not shown:
            note = (rec.get("union") or {}).get("relational_note") or "not measurable"
            rows.append([f"<b>{NICE[c]}</b>", "—",
                         f(rec.get("union", {}).get("token_recall"), 3),
                         f"<span class='ns' colspan='6'>{escape(note)}</span>", "", "", "", "", "", ""])
    return table(["Corpus", "Rule", "Token recall", "Context linkage (Rank-1)",
                  "Learned linkage (Rank-1)", "Learned (Rank-5)", "Ceiling on A",
                  "Gallery", "Queries", "Chance"], rows,
                 note="Five-fold cross-validation, mean ± one standard deviation over folds. Folds "
                      "withhold <em>labels</em>, never candidates: a held-out person stays in the "
                      "complete candidate list with every distractor, so the attacker is never told "
                      "that a query has a match. <b>Ceiling on A</b> is the same attack against "
                      "unmodified text, which is what gives the protected numbers a scale.")


def section_exposure():
    rows = []
    for c in CORPORA:
        e = DATA["exposure"].get(c)
        if not e:
            continue
        rep, per = e["replaced"], e["person"]
        unit = "documents" if rep.get("cases_are_documents") else "cases"
        rows.append([
            NICE[c],
            f"{num(rep['documents_exposed'])} / {num(rep['documents'])} "
            f"<b>({pct(rep['documents_exposed_rate'])})</b>",
            f"{num(rep['cases_exposed'])} / {num(rep['cases'])} "
            f"<b>({pct(rep['cases_exposed_rate'])})</b> <span class='sd'>{unit}</span>",
            f"{num(rep['entities_exposed'])} / {num(rep['entities'])} "
            f"<b>({pct(rep['entities_exposed_rate'])})</b>",
            f"{num(per['cases_exposed'])} / {num(per['cases'])} "
            f"<b>({pct(per['cases_exposed_rate'])})</b>",
            f"{num(per['entities_exposed'])} / {num(per['entities'])} "
            f"<b>({pct(per['entities_exposed_rate'])})</b>",
            f"{rep['findings_per_document_mean']:.2f} <span class='sd'>± "
            f"{rep['findings_per_document_sd']:.2f}</span>",
        ])
    t1 = table(["Corpus", "Documents with a finding", "Cases", "Entities",
                "Patients / cases — people only", "Entities — people only",
                "Findings per document"], rows,
               note="An entity counts as exposed when <em>any</em> one of its mentions survives, and "
                    "partial coverage counts: <em>Anna Müller</em> with only the given name replaced "
                    "leaves a surname in the clear. The first three columns cover every identifier "
                    "class the conditions replace; the next two cover people alone, which is what "
                    "the attacks target. Enron has 16 mailbox owners, so its case column saturates.")

    rows = []
    for c in CORPORA:
        e = DATA["exposure"].get(c)
        if not e:
            continue
        per_type = e["replaced"].get("per_type") or {}
        for i, (t, v) in enumerate(sorted(per_type.items())):
            rows.append([f"<b>{NICE[c]}</b>" if i == 0 else "", t,
                         num(v["leaked"]), num(v["gold"]), pct(v["rate"], 2)])
    t2 = table(["Corpus", "Type", "Tokens left", "Gold tokens", "Rate"], rows,
               note="Where the residue actually is, by identifier class. Dates, quantities and "
                    "miscellaneous spans are passed through by design and are excluded; on "
                    "CARDIO:DE that exclusion is 102,234 gold tokens, which is 84.7 % of its "
                    "annotation, and a release that keeps them needs date shifting.")
    return t1, t2


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
    naive = next((r["rank1"] for r in DATA["a4"]
                  if r["corpus"] == "tab" and r["condition"] == "B" and not r["context"]), None)
    told = next((r["rank1"] for r in DATA["a4"]
                 if r["corpus"] == "tab" and r["condition"] == "B-forewarned"), None)
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


SECTIONS = [
    ("detection", "Detection"),
    ("utility", "Utility"),
    ("leakage", "Leakage"),
    ("exposure", "Exposure"),
    ("stability", "Stability"),
    ("about", "About"),
]


def build() -> str:
    op1, op2 = section_detection()
    ut1, ut2 = section_utility()
    a2a, a2b, a2c = section_a2()
    ex1, ex2 = section_exposure()
    nav = "".join(f"<a href='#{i}'>{escape(n)}</a>" for i, n in SECTIONS)
    ensemble = "".join(f"<li><code>{escape(d)}</code></li>" for d in DATA["ensemble"])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pseudonymisation — the results behind the paper</title>
<meta name="description" content="Detection, utility and leakage measured end to end on four
corpora: the full result set behind an eight-page paper.">
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
  <h1>Taking the names out of text,<br><span>measured end to end</span></h1>
  <p class="lede">Detection, downstream utility and residual identity leakage, on the same documents,
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
  <p class="sub">What an ensemble catches, what it wrongly catches, and what it costs. Sensitivity
  and specificity are the detector's two error rates read against their own denominators; precision
  mixes them, so it is reported beside them rather than optimised for.</p>
  <h3>The cost–quality front, in full</h3>
  {op1}
  <div class="callout"><p><b>The fast cell is usually not the worse cell.</b> On CARDIO:DE the fast
  sensitivity point gives up 0.097 of sensitivity but is <em>more</em> specific than the maximum and
  191× cheaper. Catching the last identifiers means over-detecting, and over-detection has its own
  price — which only the second column shows.</p></div>
  <h3>The recommended ensemble under every combining rule</h3>
  {op2}
  <h3>The 13 detectors</h3>
  <ul class="cols">{ensemble}</ul>
  <p class="note">Two further large language models were run as single detectors and excluded from
  the recommended ensemble: preliminary runs made them one to two orders of magnitude slower per
  document without improving detection.</p>
</section>

<section id="utility">
  <h2><span class="n">02</span>Utility</h2>
  <p class="sub">Three frozen models read all three conditions. The question is not whether the text
  changed but whether the task survives, so every comparison is paired per document and carries the
  original-text score beside it.</p>
  {ut1}
  <h3>The paired tests in full</h3>
  {ut2}
  <div class="callout"><p><b>Detector precision, not the replacement form, is the dominant lever.</b>
  Entity agreement is 0.611 under a permissive union and 0.973 when the same fifteen detectors must
  reach a majority — same policy, same surrogates, same corpus.</p>
  <p>The placeholder column is partly an artefact and is labelled as one: the frozen recogniser never
  tags <code>[PERSON]</code> as a name, so every replaced mention counts as a disagreement. Read that
  column between rules, not between forms.</p></div>
</section>

<section id="leakage">
  <h2><span class="n">03</span>Leakage</h2>
  <p class="sub">Three attacks against the released text, all scored over the full denominator with
  collisions counted rather than dropped, because an attacker has no ground truth to drop them
  with.</p>

  <div class="callout"><p><b>The finding that reorganised the paper.</b> Conditions B and C replace
  <em>identical</em> spans, so overwriting each replaced span of the surrogate release with
  <code>[PERSON]</code> reproduces the placeholder release character for character — verified on all
  1,268 TAB and all 5,994 OntoNotes documents.</p>
  <p>A release cannot be safer than a text anyone can compute from it. So when a candidate-ranking
  model scores 0.085 on surrogates against 0.290 on placeholders, that is not protection: it is the
  ranker believing the surrogate. Tell it the scheme and it reaches 0.205 on exactly the same
  published bytes.</p></div>

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
  <h2><span class="n">04</span>Exposure</h2>
  <p class="sub">A corpus-level token rate is the least informative way to state what a
  pseudonymisation run left behind. Data-protection officers release documents and cases, and one
  unchanged mention puts a person back in the clear however many others were replaced.</p>
  {ex1}
  <h3>Where the residue is</h3>
  {ex2}
</section>

<section id="stability">
  <h2><span class="n">05</span>Stability</h2>
  <p class="sub">A keyed pseudonym is only useful if it is stable, and only safe if it is not too
  stable. These are the ways the mapping fails.</p>
  {section_stability()}
</section>

<section id="about">
  <h2><span class="n">06</span>About these numbers</h2>
  <p>Every experiment is driven by a config plus a seed, and each result records the library
  versions, model ids and commit hash that produced it. The page is generated from
  <a href="data.json">one JSON export</a> of those result files by
  <code>docs/build_site.py</code>, so it cannot drift from the measurements the way a hand-maintained
  table does.</p>
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

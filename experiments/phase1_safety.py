#!/usr/bin/env python3
'''Phase 1: which operating point is safest, and is any of them safe at all.

Joins the three artefacts on the span-source label and applies the criterion AM fixed on
2026-09-28 -- a point is safe when the BEST attack there approaches chance:

  detection_filtered/<corpus>.jsonl   PERSON sensitivity (per_type) and specificity
  leakage_sweep/<corpus>_PERSON.jsonl A2, A3, A5 rates under condition B
  phase1/<corpus>_*.jsonl             the release-derived candidate space, and the flagging
                                      counts for the four attacker variants of plan §7.4

Chance is per attack and comes from the release, not from a name list (§7.8): 1/N with N the
distinct PERSON identities the ensemble replaced, which is what an attacker counts off the
released text. Everything is reported as lift over that, because A2's census-list chance and A3's
reference-population chance differ by orders of magnitude and raw rates cannot be compared.

Two guards, both learned the hard way:
  * a point with fewer than --query-floor scored queries is NOT safe, it is unmeasured. An earlier
    count called 777 CARDIO:DE points safe; 0 <= chance passed at points with zero queries.
  * `gold` is excluded: perfect detection is the defender's axis end, not an operating point an
    attacker faces.
'''
import argparse
import json
from pathlib import Path

CONST = {'cardiode': (120701, 885059), 'enron': (3648256, 15507925),
         # ENRON 2.0, measured 2026-10-04: the plane's gold row (17,491 gold tokens, PERSON 9,569 and
         # CODE 7,922) and metrics.detection.tokenise over the 5,003 messages (886,468 tokens).
         'enron2': (17491, 886468)}
VARIANTS = ('union13', 'union3', 'balanced', 'maxspec3')


def load_detection(path: Path, gold: int, total: int) -> dict:
    negatives = total - gold
    out = {}
    for line in path.open():
        r = json.loads(line)
        person = (r.get('per_type') or {}).get('PERSON')
        if not person or not person[0] or not r.get('precision'):
            continue
        tp_all = r['token_recall'] * gold
        out[r['detector']] = {
            'sens': person[2] / person[0],
            'spec': 1.0 - (tp_all / r['precision'] - tp_all) / negatives,
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--corpus', required=True)
    ap.add_argument('--query-floor', type=int, default=30)
    ap.add_argument('--plane', type=Path, default=Path('results/detection_filtered'),
                    help='the detection plane. ENRON 2.0 has only results/detection, which was '
                         'computed with the CODE rule already in force')
    ap.add_argument('--out', type=Path, default=Path('results/phase1'))
    args = ap.parse_args()

    gold, total = CONST[args.corpus]
    det = load_detection(args.plane / f'{args.corpus}.jsonl', gold, total)
    space = {}
    for path in sorted(Path('results/phase1').glob(f'{args.corpus}_[0-9]*.jsonl')):
        for line in path.open():
            r = json.loads(line)
            space[r['source']] = r
    leak = [json.loads(l) for l in
            open(f'results/leakage_sweep/{args.corpus}_PERSON.jsonl')]
    print(f'{args.corpus}: {len(leak)} leakage rows, {len(det)} detection rows, '
          f'{len(space)} candidate-space rows')

    rows, unmeasured, nospace = [], 0, 0
    for r in leak:
        label = r['source']
        if label == 'gold':
            continue
        sp = space.get(label)
        if sp is None:
            nospace += 1
            continue
        n = sp['candidate_space']
        if not n:
            continue
        chance = 1.0 / n
        queries = r.get('a3_queries') or 0
        if queries < args.query_floor:
            unmeasured += 1
            continue
        lifts, rates = {}, {}
        for key in ('a3_rank1', 'a5_rank1'):
            if r.get(key) is not None:
                lifts[key] = r[key] / chance
                rates[key] = r[key]
        for rate_k in ('a2_real_accuracy_alignment', 'a2_bound_accuracy_alignment'):
            if r.get(rate_k) is not None:
                lifts[rate_k] = r[rate_k] / chance
                rates[rate_k] = r[rate_k]
        d = det.get(label)
        rows.append({
            'source': label, 'size': r.get('size'), 'rule': r.get('rule'),
            'candidate_space': n, 'chance': chance, 'queries': queries,
            'sens': d['sens'] if d else None, 'spec': d['spec'] if d else None,
            'J': (d['sens'] + d['spec'] - 1.0) if d else None,
            'lifts': lifts, 'worst_lift': max(lifts.values()) if lifts else None,
            'worst_rate': max(v for k, v in rates.items()) if rates else None,
            'rates': rates,
            'survivor_entities': sp['survivor_entities'],
            **{f'{v}_flagged': sp.get(f'{v}_flagged') for v in VARIANTS},
            **{f'{v}_true_survivor': sp.get(f'{v}_true_survivor') for v in VARIANTS},
            **{f'{v}_surrogate_mistaken': sp.get(f'{v}_surrogate_mistaken') for v in VARIANTS},
        })
    print(f'  usable {len(rows)}; dropped {unmeasured} below the {args.query_floor}-query floor, '
          f'{nospace} with no candidate-space row')

    scored = [r for r in rows if r['worst_rate'] is not None]
    safe = [r for r in scored if r['worst_lift'] is not None and r['worst_lift'] <= 1.0]
    print(f'  at or below chance: {len(safe)} of {len(scored)}')

    # **The criterion is the lowest attack result** (AM, 2026-09-29): the absolute rate the
    # strongest attack achieves there, not its multiple of chance. Lift rewards a point that
    # replaced so little that the candidate space collapsed -- on Enron the lift-minimal point
    # detects 3.44% of PERSON tokens, leaves 3,885 of 3,886 identities in the clear, and is
    # attacked at 10.44%, five times worse in absolute terms than the 13-detector union.
    #
    # Ties are the rule, not the exception: 360 CARDIO:DE points sit at exactly 0.00%, so the
    # attack rate alone leaves the choice to whatever `min` happens to see first -- which returned
    # a point at PERSON sensitivity 0.6863 leaving 183 identities in the clear. Among equal-lowest
    # attack the tie is broken on Youden's J (AM, 2026-09-29), so the chosen point is the one whose
    # two error rates are jointly best where the attack cannot separate the candidates.
    best_rate = min(r['worst_rate'] for r in scored)
    tied = [r for r in scored if r['worst_rate'] <= best_rate + 1e-12]
    pick = max((r for r in tied if r['J'] is not None), key=lambda r: r['J'], default=tied[0])
    if pick:
        print(f'\n  LOWEST ATTACK: {best_rate * 100:.3f}%  ({len(tied)} points tie there; '
              f'broken on Youden J)')
        print(f'  SELECTED: {pick["size"]}det {pick["rule"]}')
        print(f'    PERSON sensitivity {pick["sens"]:.4f}  specificity {pick["spec"]:.4f}  '
              f'Youden J {pick["J"]:.4f}')
        print(f'    candidate space N={pick["candidate_space"]}, chance {pick["chance"]:.2e}, '
              f'{pick["queries"]} queries, {pick["survivor_entities"]} survivor identities')
        for k, v in sorted(pick['rates'].items(), key=lambda kv: -kv[1]):
            print(f'    {k:32s} {v * 100:7.3f}%   ({pick["lifts"][k]:8.1f}x chance)')
        for v in VARIANTS:
            f, t, m = (pick.get(f'{v}_flagged'), pick.get(f'{v}_true_survivor'),
                       pick.get(f'{v}_surrogate_mistaken'))
            if f:
                print(f'    attacker {v:9s} flags {f:8d}, {t:7d} true survivors, '
                      f'{m:7d} surrogates mistaken  (precision {t/max(f,1):.4f})')
        print(f'    {pick["source"][:110]}')

    args.out.mkdir(parents=True, exist_ok=True)
    dest = args.out / f'{args.corpus}_safety.json'
    dest.write_text(json.dumps({
        'corpus': args.corpus, 'query_floor': args.query_floor,
        'scored': len(scored), 'safe': len(safe),
        'lowest_attack_rate': best_rate, 'tied_at_lowest': len(tied),
        'selected': pick,
        'selection_rule': 'lowest absolute worst-attack rate over A2/A3/A5, ties broken by '
                          "highest Youden J (AM, 2026-09-29)",
    }, indent=1) + '\n')
    print(f'\nwrote {dest}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

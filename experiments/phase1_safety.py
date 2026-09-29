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

CONST = {'cardiode': (120701, 885059), 'enron': (3648256, 15507925)}
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
    ap.add_argument('--out', type=Path, default=Path('results/phase1'))
    args = ap.parse_args()

    gold, total = CONST[args.corpus]
    det = load_detection(Path(f'results/detection_filtered/{args.corpus}.jsonl'), gold, total)
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
        lifts = {}
        for key in ('a3_rank1', 'a5_rank1'):
            if r.get(key) is not None:
                lifts[key] = r[key] / chance
        for rate_k in ('a2_real_accuracy_alignment', 'a2_bound_accuracy_alignment'):
            if r.get(rate_k) is not None:
                lifts[rate_k] = r[rate_k] / chance
        d = det.get(label)
        rows.append({
            'source': label, 'size': r.get('size'), 'rule': r.get('rule'),
            'candidate_space': n, 'chance': chance, 'queries': queries,
            'sens': d['sens'] if d else None, 'spec': d['spec'] if d else None,
            'J': (d['sens'] + d['spec'] - 1.0) if d else None,
            'lifts': lifts, 'worst_lift': max(lifts.values()) if lifts else None,
            'survivor_entities': sp['survivor_entities'],
            **{f'{v}_flagged': sp.get(f'{v}_flagged') for v in VARIANTS},
            **{f'{v}_true_survivor': sp.get(f'{v}_true_survivor') for v in VARIANTS},
            **{f'{v}_surrogate_mistaken': sp.get(f'{v}_surrogate_mistaken') for v in VARIANTS},
        })
    print(f'  usable {len(rows)}; dropped {unmeasured} below the {args.query_floor}-query floor, '
          f'{nospace} with no candidate-space row')

    scored = [r for r in rows if r['worst_lift'] is not None]
    safe = [r for r in scored if r['worst_lift'] <= 1.0]
    print(f'  SAFE (worst lift <= 1): {len(safe)} of {len(scored)}')
    floor = min(scored, key=lambda r: r['worst_lift']) if scored else None
    if floor:
        print(f'  floor over the plane: worst lift {floor["worst_lift"]:.1f}x '
              f'(N={floor["candidate_space"]}, {floor["size"]}det {floor["rule"]})')

    pool = safe or scored
    pick = max((r for r in pool if r['J'] is not None), key=lambda r: r['J'], default=None)
    if pick:
        tag = 'SAFEST' if safe else 'LEAST UNSAFE (nothing reaches chance)'
        print(f'\n  {tag}: {pick["size"]}det {pick["rule"]}')
        print(f'    PERSON sensitivity {pick["sens"]:.4f}  specificity {pick["spec"]:.4f}  '
              f'Youden J {pick["J"]:.4f}')
        print(f'    candidate space N={pick["candidate_space"]}, chance {pick["chance"]:.2e}, '
              f'{pick["queries"]} queries, {pick["survivor_entities"]} survivor identities')
        for k, v in sorted(pick['lifts'].items(), key=lambda kv: -kv[1]):
            print(f'    {k:32s} lift {v:9.1f}x')
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
        'floor_worst_lift': floor['worst_lift'] if floor else None,
        'selected': pick, 'selection_rule': 'max Youden J among safe points; '
                                            'if none is safe, among all scored points',
    }, indent=1) + '\n')
    print(f'\nwrote {dest}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

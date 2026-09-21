"""Build conditions B and C at the four operating points, so utility can be measured there.

The existing patch sets serve §7's factor design: the whole pool under union and under vote, and a
three-detector subset under each.  They answer "what does the combination rule do".  They do **not**
answer "what does the ensemble we would actually deploy cost in utility", because the operating
points (AM, 2026-09-20 — fast against maximum, on specificity and sensitivity) select different
ensembles by different criteria.

This reads the operating-point file a corpus already has and builds one patch-set pair per point,
tagged by the point's name so the utility runs are legible.  Nothing here chooses anything; the
choosing was done by :mod:`experiments/operating_points`.

    python experiments/build_operating_points.py --corpus cardiode --print
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pseudonymkit.paths import work_dir  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--points", type=Path, default=None)
    ap.add_argument("--print", action="store_true", help="show the commands without running them")
    args = ap.parse_args()

    path = args.points or (work_dir() / "results" / "detection"
                           / f"{args.corpus}_operating_points.json")
    points = json.loads(path.read_text(encoding="utf-8"))["points"]

    seen: dict[tuple, str] = {}
    for name, point in points.items():
        key = (tuple(sorted(point["ensemble"])), point["rule"])
        if key in seen:
            print(f"{name}: identical to {seen[key]} — one build serves both")
            continue
        seen[key] = name
        rule = point["rule"]
        # A single detector has nothing to combine; build_BC takes `union` for it, which short-
        # circuits to that detector's own spans.
        command = [sys.executable, "experiments/build_BC.py", "--corpus", args.corpus,
                   "--rule", "union" if rule == "single" else rule,
                   "--detectors", *point["ensemble"]]
        print(f"\n=== {name}  ({rule}, {len(point['ensemble'])} detectors) ===")
        print("  " + " ".join(command))
        if args.print:
            continue
        result = subprocess.run(command, check=False)
        if result.returncode:
            print(f"  FAILED with {result.returncode}")
            return result.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
'''Build the arXiv submission package from the ACCV submission sources.

The paper in this directory is the *review* copy: `accv.sty` is loaded with `review`, which
anonymises the author block, prints line numbers, stamps the paper ID on every page and crops the
page to the LNCS trim. None of that belongs on arXiv, and none of it is edited by hand — the
review copy stays exactly as it is submitted and this script derives the arXiv copy from it, so
the two cannot drift apart.

What it changes, and why each change is needed:

  * `review` -> final          arXiv is not a blind venue; line numbers, the `#*****` paper ID and
                               the anonymous author block would all be wrong there.
  * real author block          `accv.sty` overrides \\author and \\institute in review mode, so the
                               submission carries empty ones. arXiv needs the real list.
  * `pagebackref` dropped      accv.sty recommends it for review and explicitly not for the final
                               copy; it appends "cited on page N" to every bibliography entry.
  * `\\pdfoutput=1`             arXiv reads the first few lines to decide between pdflatex and
                               dvips; the paper is pdflatex-only (TikZ, microtype, no EPS).
  * `main.bbl` shipped         arXiv's AutoTeX does not run BibTeX. Without the .bbl every
                               citation renders as a bold [?].

Every replacement below is anchored on an exact string and asserted to occur exactly once, so a
future edit to main.tex that moves an anchor fails this script instead of silently producing a
package with, say, the line numbers still on.

Usage:  python3 make_arxiv.py [--outdir DIR]
'''
import argparse
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Files the package needs. Everything is source; no build artefact is copied in, the .bbl is
# produced by the build below.
SOURCES = [
    'main.tex',
    'references.bib',
    'accv.sty',
    'accvabbrv.sty',
    'llncs.cls',
    'splncs04.bst',
    'sections/01_introduction.tex',
    'sections/02_methods.tex',
    'sections/03_results.tex',
    'sections/04_discussion.tex',
    'sections/05_conclusion.tex',
    'figures/overview.tex',
]

# ---------------------------------------------------------------------------------------------
# The author block.
#
# AUTHORS.md is the source: AM first, Monica Hinrichs-Mayer second, Siming Bayer last, and the
# four in between NOT YET ORDERED (AM, 2026-09-23). They appear here in the order AUTHORS.md
# tabulates them, which is a listing and not a decision. AM settles positions 3-6 before upload;
# it is one line here and one line in AUTHORS.md.
#
# Affiliations are taken verbatim from the AUTHORS.md table. Institute 1 differs from institute 2
# only by the lab, because AUTHORS.md records the Pattern Recognition Lab for AM alone and for
# nobody else; do not merge them by inference.
# ---------------------------------------------------------------------------------------------
AUTHOR_BLOCK = r'''% Author order: AM first, Hinrichs-Mayer second, Bayer last (AUTHORS.md).
% POSITIONS 3-6 ARE NOT SETTLED -- listed here in AUTHORS.md table order. Confirm before upload.
\author{%
  Andreas Maier\inst{1}\and
  Monica Hinrichs-Mayer\inst{2}\and
  Franziska Weber\inst{2}\and
  Niklas Lackner\inst{3}\and
  Matthias May\inst{3}\and
  Bernhard Kainz\inst{2,4}\and
  Siming Bayer\inst{2}}

\authorrunning{A. Maier et al.}
\titlerunning{The Text Beside the Image}

\institute{%
  Pattern Recognition Lab, Friedrich-Alexander-Universit\"at Erlangen-N\"urnberg, Germany\and
  Friedrich-Alexander-Universit\"at Erlangen-N\"urnberg, Germany\and
  Universit\"atsklinikum Erlangen, Germany\and
  Imperial College London, United Kingdom}'''

REPLACEMENTS = [
    (
        'pdflatex marker for arXiv AutoTeX',
        '\\documentclass[runningheads]{llncs}',
        '% arXiv builds this with pdflatex: TikZ, microtype and T1 fonts, no EPS anywhere.\n'
        '\\pdfoutput=1\n'
        '\\documentclass[runningheads]{llncs}',
    ),
    (
        'review mode off',
        '\\usepackage[review,year=2026,ID=*****]{accv}',
        '% arXiv copy: final mode. No line numbers, no paper ID, no anonymous author block.\n'
        '\\usepackage[final,year=2026]{accv}',
    ),
    (
        'pagebackref dropped',
        '\\usepackage[pagebackref,breaklinks,colorlinks,citecolor=blue]{hyperref}',
        '\\usepackage[breaklinks,colorlinks,citecolor=blue]{hyperref}',
    ),
    (
        'real author block',
        '% Anonymised automatically by accv.sty in `review` mode '
        '— do not fill these in for the submission.\n\\author{}\n\\institute{}',
        AUTHOR_BLOCK,
    ),
]

# What the built PDF must and must not contain. A package that compiles but still says "Anonymous
# ACCV 2026 Submission" is worse than one that fails, because it looks finished.
MUST_NOT_APPEAR = [
    'Anonymous ACCV',
    'Paper ID #',
]
MUST_APPEAR = [
    'Andreas Maier',
    'Siming Bayer',
]


# arXiv's submission form takes title, authors and abstract as plain text, and silently accepts
# LaTeX it will not render. Deriving them from main.tex rather than retyping them is the only way
# they stay in step with the paper.
DETEX = [
    (r'\\num\{([^{}]*)\}', r'\1'),
    (r'\\SI\{([^{}]*)\}\{\\percent\}', r'\1%'),
    (r'\\emph\{([^{}]*)\}', r'\1'),
    (r'\\textit\{([^{}]*)\}', r'\1'),
    (r'\s*\\and\s*', r', '),
    (r'\$([^$]*)\$', r'\1'),
    (r'~', ' '),
    (r'\s+', ' '),
]


def detex(fragment: str) -> str:
    text = fragment.strip()
    for pattern, sub in DETEX:
        text = re.sub(pattern, sub, text)
    leftover = re.findall(r'\\[a-zA-Z]+', text)
    if leftover:
        raise SystemExit(f'make_arxiv: unhandled LaTeX in metadata: {sorted(set(leftover))}')
    return text.strip()


def metadata(main_tex: str, pages: str, figures: int, tables: int) -> str:
    def grab(pattern: str, what: str) -> str:
        match = re.search(pattern, main_tex, re.S)
        if not match:
            raise SystemExit(f'make_arxiv: could not find the {what} in main.tex')
        return detex(match.group(1))

    title = grab(r'\\title\{(.*?)\}\s*\n', 'title')
    abstract = grab(r'\\begin\{abstract\}(.*?)\\end\{abstract\}', 'abstract')
    keywords = grab(r'\\begin\{keywords\}(.*?)\\end\{keywords\}', 'keywords')
    authors = ', '.join(re.findall(r'^\s{2}([A-Z][^\\]+?)\\inst', AUTHOR_BLOCK, re.M))

    return f'''Paste-ready fields for the arXiv submission form. Generated by make_arxiv.py from
main.tex — do not edit this file; edit the paper and re-run.

--- Title ---------------------------------------------------------------------
{title}

--- Authors -------------------------------------------------------------------
{authors}

  NOT SETTLED: positions 3-6 (Weber, Lackner, May, Kainz) are listed in AUTHORS.md
  table order, which is a listing and not a decision (AM, 2026-09-23). Fix the order
  in AUTHOR_BLOCK in make_arxiv.py and in AUTHORS.md, then re-run, before uploading.

--- Abstract ------------------------------------------------------------------
{abstract}

--- Categories ----------------------------------------------------------------
Primary:    cs.CL   (Computation and Language)
Cross-list: cs.CR   (Cryptography and Security)

--- Comments ------------------------------------------------------------------
{pages} pages including references, {figures} figure, {tables} tables. Submitted to the
TrustFMI workshop at ACCV 2026.

--- Keywords ------------------------------------------------------------------
{keywords}

--- Before you upload ---------------------------------------------------------
1. Author order, positions 3-6 (above).
2. Everyone on the list has to be told before the paper is posted (AUTHORS.md).
3. ACCV's preprint policy for the TrustFMI workshop: posting a non-anonymous
   preprint while the paper is under review is allowed at many CV venues, but this
   has not been verified for TrustFMI 2026 and is not something to assume.
4. Licence: arXiv defaults to its own non-exclusive licence. The study plans to
   release everything with the paper, so CC BY 4.0 is the consistent choice, but
   it is AM's call and it cannot be changed after announcement.
'''


def patch_main(text: str) -> str:
    for what, old, new in REPLACEMENTS:
        count = text.count(old)
        if count != 1:
            raise SystemExit(
                f'make_arxiv: anchor for "{what}" occurs {count} times in main.tex, expected 1.\n'
                f'  anchor: {old[:90]}...\n'
                '  main.tex has been edited; update this script rather than the paper.')
        text = text.replace(old, new)
    return text


def run(cmd, cwd):
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stdout.write(proc.stdout[-4000:])
        sys.stderr.write(proc.stderr[-2000:])
        raise SystemExit(f'make_arxiv: {cmd[0]} failed with {proc.returncode} in {cwd}')
    return proc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--outdir', default=str(HERE / 'arxiv'),
                    help='where the package and the zip are written (default: paper/arxiv)')
    args = ap.parse_args()

    out = Path(args.outdir).resolve()
    stage = out / 'source'
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)

    for rel in SOURCES:
        src = HERE / rel
        if not src.exists():
            raise SystemExit(f'make_arxiv: missing source {rel}')
        dst = stage / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    (stage / 'main.tex').write_text(patch_main((HERE / 'main.tex').read_text()))
    print(f'staged {len(SOURCES)} source files in {stage}')

    # Full latexmk cycle: this is what produces main.bbl, which arXiv will not produce for itself.
    run(['latexmk', '-pdf', '-interaction=nonstopmode', '-halt-on-error', 'main.tex'], stage)

    pdf = stage / 'main.pdf'
    text = subprocess.run(['pdftotext', str(pdf), '-'], capture_output=True, text=True).stdout
    for bad in MUST_NOT_APPEAR:
        if bad in text:
            raise SystemExit(f'make_arxiv: built PDF still contains "{bad}" — review mode is on.')
    for good in MUST_APPEAR:
        if good not in text:
            raise SystemExit(f'make_arxiv: built PDF does not contain "{good}".')
    # Line numbers in review mode are the four-digit column 001, 002, ... down the left margin.
    if re.search(r'^0\d\d\n0\d\d\n0\d\d$', text, re.M):
        raise SystemExit('make_arxiv: built PDF looks like it still carries line numbers.')

    info = subprocess.run(['pdfinfo', str(pdf)], capture_output=True, text=True).stdout
    pages = next((line.split(':', 1)[1].strip() for line in info.splitlines()
                  if line.startswith('Pages:')), '?')
    print(f'built {pdf.name}: {pages} pages, author block present, no review furniture')

    shutil.copy2(pdf, out / 'main.pdf')

    # arXiv wants source only. The .bbl stays because AutoTeX will not regenerate it.
    keep = set(SOURCES) | {'main.bbl'}
    removed = []
    for path in sorted(stage.rglob('*')):
        if path.is_dir():
            continue
        rel = path.relative_to(stage).as_posix()
        if rel not in keep:
            path.unlink()
            removed.append(rel)
    print(f'removed {len(removed)} build artefacts: {", ".join(removed)}')

    zip_path = out / 'arxiv-submission.zip'
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for rel in sorted(keep):
            zf.write(stage / rel, rel)
    size = zip_path.stat().st_size
    print(f'wrote {zip_path} ({size / 1024:.0f} kB, {len(keep)} files)')

    meta_path = out / 'METADATA.txt'
    figures = sum(src.read_text().count('\\begin{figure}')
                  for src in (HERE / rel for rel in SOURCES) if src.suffix == '.tex')
    tables = sum(src.read_text().count('\\begin{table}')
                 for src in (HERE / rel for rel in SOURCES) if src.suffix == '.tex')
    meta_path.write_text(metadata((HERE / 'main.tex').read_text(), pages, figures, tables))
    print(f'wrote {meta_path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())

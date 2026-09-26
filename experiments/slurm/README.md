# Slurm wrappers

The job scripts that ran the study. They lived only in the cluster work directory until
2026-09-26; the tables in the paper were produced by these, so they belong with the code.

Absolute paths were rewritten before committing. Each script now resolves the work directory
through `PSEUDONYMKIT_WORK` (falling back to `$PWD`) and writes its logs to a path relative to the
submission directory, which is the pattern `detect.sbatch` already used. The committed text is
therefore equivalent to, but not byte-identical with, what ran.

`--output`/`--error` directories must exist before submission: Slurm redirects before the script
runs, so a missing directory fails the job instantly with no log at all.

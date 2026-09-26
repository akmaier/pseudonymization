# Slurm wrappers

The job scripts that ran the study. They lived only in the cluster work directory until
2026-09-26; the tables in the paper were produced by these, so they belong with the code.

Each script resolves the work directory through `PSEUDONYMKIT_WORK` (falling back to `$PWD`) and
writes its logs relative to the submission directory, which is the pattern `detect.sbatch` already
used.

`--output`/`--error` directories must exist before submission: Slurm redirects before the script
runs, so a missing directory fails the job instantly with no log at all.

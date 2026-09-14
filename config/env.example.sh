# Copy to config/env.sh (gitignored) and edit. Source it before running anything:
#     . config/env.sh
#
# PSEUDONYMKIT_WORK   work directory holding data/, results/, models/, logs/.
#                     Defaults to the current directory if unset.
# PSEUDONYMKIT_DUA    root of the DUA-restricted corpus tree. No default: code that needs it
#                     stops rather than guessing. This directory must be mode 700 and must
#                     never be a group-readable share.
# SBATCH_ACCOUNT      Slurm account to charge; SBATCH_PARTITION the partition to submit
#                     to. These are Slurm's own variable names, read by sbatch directly.

export PSEUDONYMKIT_WORK="/path/to/work/pseudonymization"
export PSEUDONYMKIT_DUA="/path/to/dua-restricted"
export SBATCH_ACCOUNT="your-account"
export SBATCH_PARTITION="your-partition"

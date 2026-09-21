# Jargon check for *Agentic Autoresearch for CT Reconstruction*

Reader model: **expert medical physicist, NOT an AI / ML specialist.** This checklist flags every term, acronym, concept, or metric in `paper/tex/main.tex` and `paper/tex/supplement.tex` that such a reader is likely to *not know*, *misread*, or *find ambiguous*. Focus is AI / ML / deep-learning / agentic / software jargon. Classic CT / medical-physics terms are listed at the bottom as **FINE / FYI** so you can confirm they need no gloss.

Each entry: **term** — where it first appears — one-line plain explanation for a medical physicist — recommendation (*define-on-first-use*, *add gloss/footnote*, *replace with plainer word*, or *leave*).

---

## TIER 1 — MUST DEFINE (blocks comprehension for this reader)

These carry real conceptual load and are used as if the reader already knows them. Without a definition the argument is hard to follow.

1. **LLM agent / large language model (agent)** — Abstract "can a large language model (LLM) agent do the labor of reconstruction research"; Intro "LLM agents that write and run code". — A large language model is a text-prediction neural network (like the engine behind ChatGPT); an *agent* is that model wrapped in a loop so it can take actions — read files, write code, launch jobs — not just answer questions. — **Define-on-first-use.** The word "agent" does the heaviest lifting in the paper and is never defined. One sentence in the Intro (what an LLM is + what makes it an "agent") is essential.

2. **Autoresearch / agentic autoresearch** — Title; Intro "Recent ``autoresearch'' ideas imagine automating this loop". — An automated research loop in which the AI agent itself proposes a change, runs the experiment, reads the result, and iterates, standing in for the human doing that cycle by hand. — **Define-on-first-use.** It is in the title but never explicitly unpacked; give a one-line definition at first use in the Intro.

3. **Agentic (loop / development / executor)** — throughout; first as a section title "The agentic loop". — Adjective meaning "carried out by an autonomous AI agent that decides and acts on its own," as opposed to a fixed script a human wrote. — **Add gloss** at first use (tie it to the LLM-agent definition above).

4. **Self-supervised** (and **supervised**, **self-supervised first**) — Methods Table 1 "Axis B is the prior source: ... supervised, self-supervised (Noise2Inverse)". — *Supervised* = the network is trained on paired examples with known correct answers (e.g. low-dose input, high-dose truth); *self-supervised* = the network is trained without a clean ground-truth reference, using structure in the data itself (e.g. one noisy view predicting another). — **Define-on-first-use.** These two terms partition Axis B of the central taxonomy and recur constantly (supervised/self-sup./zero-shot). A one-line contrast is worth a footnote.

5. **Zero-shot / foundation zero-shot / foundation model** — Table 1 "Foundation zero-shot (RAM)"; noisy board "ram-zeroshot". — A *foundation model* is a large network pre-trained once on huge, generic data; *zero-shot* means it is applied to this new task with **no task-specific training at all**, straight out of the box. — **Define-on-first-use.** Neither "foundation model" nor "zero-shot" is explained, and both are non-obvious to a non-ML reader.

6. **Unrolled / unrolling (unrolled proximal-gradient scheme, unrolled learned-iterative, unroll)** — Intro "unrolled iterative networks"; Methods Eq. (3) "unrolled proximal-gradient scheme of $K$ steps". — Taking a classical iterative reconstruction algorithm, fixing it to a small number $K$ of steps, and turning each step into a trainable network layer so the whole fixed-length iteration is trained end-to-end. — **Define-on-first-use.** Central to how most of the 26 methods are built; the word "unrolled" will not be transparent to a medical physicist even though the underlying iterative-reconstruction idea is familiar.

7. **Proximal-gradient / prox / proximal step** — Methods Eq. (3) "unrolled proximal-gradient scheme"; Supplement S5 "an in-loop prox hurts". — A standard optimization method for the regularized objective in Eq. (2): alternate a gradient step toward data-fit with a "proximal" step that applies the regularizer/denoiser; "prox" is the shorthand for that second step. — **Add gloss** at Eq. (3), and expand "prox" the first time the abbreviation appears in S5.

8. **Data-consistency (operator / step / DC)** — Methods "The first is the \textbf{data-consistency operator} $\mathbf{D}$"; abbreviated "DC" throughout supplement tables. — The part of a reconstruction step that pulls the current image back toward agreement with the measured sinogram (the physics-fidelity term). — **Define-on-first-use** (the main text does define $\mathbf{D}$ in words — good — but the abbreviation "DC" in the supplement tables is never expanded; spell it out once).

9. **Learned primal-dual (LPD)** — Intro; Methods "This is the learned primal-dual (LPD) block"; Eq. (5). — An unrolled reconstruction network that alternates updates in *both* image space and measurement (sinogram) space, with small learned convolution blocks; "primal" = image domain, "dual" = measurement domain. — **Add gloss.** The main text explains the mechanics via Eq. (5), but the reader needs the plain-language "it learns updates in both image and sinogram domains" sentence, and "primal/dual" named.

10. **Prior / regularizer / regularization ($\mathcal{R}$)** — Methods Eq. (2) "$\lambda\,\mathcal{R}(\mathbf{x})$ ... a prior". — The term added to the reconstruction objective that encodes assumptions about what a plausible image looks like (smoothness, sparsity, learned texture); controls the fit-vs-smoothness trade-off. — **Add gloss.** "Prior" and "regularizer" are used interchangeably; state once that they are the same $\mathcal{R}$ term. (A physicist knows TV regularization, but the ML usage of "prior" as a synonym may not be obvious.)

11. **Inductive bias** — Discussion "the right inductive bias depends on whether the problem is noise-limited or incompleteness-limited". — The built-in assumptions a model architecture bakes in before seeing any data (e.g. convolution assumes locality; a physics operator assumes the scanner geometry); it biases *what* the model can easily learn. — **Add gloss / footnote.** Non-obvious ML term used at a load-bearing point in the Discussion.

12. **Known operator (learning) / KO** — Intro "We embed the \textbf{known operator}"; Supplement S3 "data-consistency / KO". — Deliberately building the exact, known physics (the differentiable forward/back projector) into the network instead of letting the network learn it from data; provably cannot increase, and usually lowers, the worst-case error bound. — **Leave / light gloss.** This is the authors' own line of work and is explained in-text (good). But expand the abbreviation "KO" the one time it appears in Supplement Table S3.

13. **Differentiable (fan-beam projector / forward projector)** — Methods "the same differentiable fan-beam projector (PYRO-NN)". — A forward/back-projection operator implemented so gradients can flow through it, letting it sit inside a trainable network and be optimized by back-propagation. — **Add gloss.** A physicist knows a fan-beam projector; the word *differentiable* (and why it matters — gradients for training) is the ML-specific part to explain.

14. **Variational network (VN, Hammernik)** — Intro; Table 1; Results "the variational-network accuracy tier". — A specific unrolled network (Hammernik et al.) whose learned regularizer is a Fields-of-Experts filter bank; used here as the accuracy yardstick the compact solver matches. — **Add gloss.** Named repeatedly as a comparison tier; one line on what it is helps.

15. **Field of experts (FoE)** — Table 1 "field-of-experts"; Supplement S5 "an evolved field-of-experts ... denoiser". — A learned image prior built from a bank of small filters plus nonlinear penalty functions; the trainable regularizer inside the variational network. — **Add gloss / footnote.** Pure ML/computer-vision jargon a medical physicist is unlikely to know.

16. **Diffusion model / diffusion prior / generative prior** — Intro "diffusion priors"; Table 1 "Generative prior (fastdiff)". — A generative neural network that learns to produce realistic images by reversing a gradual noising process; used as a learned prior that "imagines" plausible detail during reconstruction. — **Define-on-first-use.** "Diffusion" here is unrelated to physical diffusion; a physicist will misread it without a gloss.

17. **Rectified flow (rectified-flow prior)** — Supplement S1 Table "rectified-flow prior"; Table 1 "fastdiff". — A recent, faster variant of a diffusion generative model that learns a near-straight-line path from noise to image (fewer sampling steps). — **Add gloss / footnote**, or **replace** with the plainer "(a fast diffusion-type generative prior)".

18. **DPS (diffusion posterior sampling)** — Table 1 citation cluster `\cite{...chung2023dps}`; appears only as a citation label and in "fastdiff" family. — A method for using a diffusion prior to solve an inverse problem by steering the generative sampling toward measurement consistency. — **Leave** if it never appears as inline text (it is only a cited method). If you name "DPS" anywhere in prose, expand it once.

19. **Noise2Inverse (N2I)** — Table 1 "self-supervised (Noise2Inverse)"; boards "dd-n2i", "dual-domain-bilateral-n2i". — A self-supervised denoising scheme for reconstruction that trains without clean ground truth by splitting the measured projections into subsets and having one subset's reconstruction predict another's. — **Add gloss** at first use, and expand the abbreviation "N2I" the first time it appears in a board/table.

20. **Neural attenuation fields / neural fields / implicit representation (per-scene implicit)** — Table 1 "Per-scene implicit (NAF, ...)"; "implicit representation". — Instead of storing an image as a pixel grid, a small neural network is trained to output the attenuation value at any queried coordinate; it is fit fresh to each individual scan ("per-scene"), not trained across a dataset. — **Define-on-first-use.** "Implicit representation" and "neural field" are opaque outside ML; the per-scene idea also needs stating.

21. **Gaussian splatting (R²-Gaussian)** — Table 1 "Gaussian splatting"; "R$^2$-Gaussian". — A per-scene representation that models the volume as many small 3-D Gaussian blobs whose parameters are optimized to match the projections; borrowed from recent 3-D graphics. — **Add gloss / footnote.** Very new, very ML/graphics-specific; a one-liner is needed.

22. **Effect size / Cohen's $d_z$** — Methods "we report \textbf{effect size} ... We use Cohen's $d_z=\bar d/s_d$". — A standardized measure of how large a difference is, independent of sample size: the mean paired difference divided by its standard deviation; reported because with $n=200$ even trivial differences become "statistically significant." — **Leave / light gloss.** The formula is given, which is good; a half-sentence on *why* effect size is reported instead of just $p$ (large $n$ makes $p$ misleadingly tiny) would help. A biostatistically-literate physicist may know this; keep it brief.

---

## TIER 2 — NICE TO GLOSS (comprehension survives, but a short note removes friction / misreading)

23. **Token / context window / 1M-token context** — Discussion "even a one-million-token context is used up quickly"; Supplement S7 "a 1M-token context is exhausted". — A *token* is roughly a word-piece; the *context window* is the maximum amount of text (here ~1,000,000 tokens) the model can "hold in mind" at once — the working-memory limit of the agent. — **Add one-line gloss** at first use. Currently thrown in with no explanation; a physicist will not know what a token is.

24. **Checkpoint** — Methods "load their noiseless-trained weights"; Supplement S6 "load their noiseless checkpoint". — A saved snapshot of a trained network's parameters, reloaded later to run the model without retraining. — **Add gloss** (or replace "checkpoint" with "saved trained weights").

25. **Weights / trained weights** — Methods "load their noiseless-trained weights and skip training". — The learned numerical parameters of the network (what training produces). — **Leave / light gloss.** Usually clear from "trained weights"; ensure the first use pairs "weights" with "the learned parameters."

26. **Training / inference** — throughout; Methods "This is \textbf{inference only}"; README-style usage. — *Training* = the fitting phase where the network learns its weights; *inference* = applying the already-trained network to new data. — **Add one-line gloss** the first time "inference" is used as a noun; the train/infer distinction is load-bearing for the "no retraining" experiment.

27. **Epoch / seed** — "seed" in Methods "with a fixed seed"; Supplement S5 "seed-fragile ... 4 of 5 seeds". ("Epoch" does not appear in the two `.tex` files — see note.) — A *seed* is the fixed starting number for the random-number generator; re-running with different seeds gives different random initializations/shuffles, so "seed-fragile" = the result depends on that luck-of-the-draw. — **Add gloss** for "seed" / "seed-fragile" at first use. (No action needed for "epoch"; verify it truly does not appear.)

28. **Hyper-parameter (optimization)** — Methods "changes one thing --- a hyper-parameter"; Discussion "strong at hyper-parameter optimization". — A configuration knob set *before* training (learning rate, regularization weight $\lambda$, number of unroll steps $K$), as opposed to a weight learned *during* training. — **Add one-line gloss** at first use; the prefix "hyper-" specifically distinguishes it from the learned weights and won't be obvious.

29. **Self-modifying / edits its own solver code** — Intro "edit its own solver code"; Discussion "self-modifying executor". — The agent rewrites the actual source code of the reconstruction program between iterations, not just its numeric settings. — **Leave**, but consider one clarifying half-sentence the first time — it is a genuinely surprising capability and a reader may under- or over-read it.

30. **Provenance** — Contributions "with full provenance"; Discussion "checks for padding and provenance". — A complete, auditable record of exactly how each result was produced (config, code snapshot, metric, figure) so any number can be traced back and reproduced. — **Add gloss** at first use; the software/data sense of "provenance" may not be the reader's default reading.

31. **Padding (agent padding / audit for padding)** — Methods "auditing for padding"; Supplement S7 "converges early and pads ... replayed identical configs". — The agent producing filler activity that looks like progress but is not — e.g. re-running near-identical configurations to appear busy; caught by human audit. — **Add gloss.** "Padding" in this behavioral sense is non-obvious and appears without explanation.

32. **Compute budget / wall-clock budget / fixed compute budget** — Methods "under a fixed compute budget"; "a fixed wall-clock budget per iteration (20 min ...)". — A hard cap on how long / how much GPU time each experiment may use, so all methods are compared under equal computational resources. — **Leave / very light gloss.** "Wall-clock" (real elapsed time) is mild systems jargon; otherwise clear.

33. **Cluster job / compute cluster / short cluster job** — Abstract/Methods "runs a short job on a compute cluster". — A single training run submitted to a shared multi-GPU computing facility. — **Leave.** Familiar enough; no action.

34. **Batch-wide data range (SSIM/PSNR data range)** — Methods "SSIM and PSNR use a batch-wide data range"; Table 2 caption. — SSIM and PSNR need a reference intensity range; here it is fixed across the whole set of test cases (the "batch") rather than per image, so scores are comparable case-to-case. — **Add gloss / footnote.** A physicist knows SSIM/PSNR but "data range" and "batch-wide" are the ML-implementation details that make the numbers comparable; worth one sentence.

35. **Weight-tied / weight-tying** — Methods "The convolutions ... are small and weight-tied". — The same set of learned weights is reused across all $K$ unroll steps rather than learning separate weights per step (keeps the parameter count tiny). — **Add gloss / footnote.** Directly explains the headline "195 parameters"; a non-ML reader won't parse "weight-tied."

36. **Zero-initialize (final layer) / identity at start** — Methods "We zero-initialize their final layer, so the block is the identity at the start and cannot regress". — The learned block's output layer starts at all-zeros, so initially it does nothing (passes the image through unchanged) and can only help, not hurt, as training proceeds. — **Leave / light gloss.** The in-text explanation is already decent; maybe add "(starts as a pass-through)".

37. **CNN / convolution / convolutions ($\Gamma_\phi$, $\Lambda_\theta$)** — Methods "The convolutions $\Gamma_\phi,\Lambda_\theta$"; Supplement S1 "learned CNN / transformer". — CNN = convolutional neural network, the standard image network built from small learned filters slid across the image. — **Add gloss** for "CNN" the first time the abbreviation appears (Supplement S1 table); "convolution" itself is fine for this reader.

38. **Transformer / Swin / U-Swin / SwinIR / TransCT** — Table 1 "learned CNN / transformer"; "U-Swin"; Supplement citations. — A *transformer* is a neural-network architecture based on "attention" (weighing all parts of the image against each other); Swin is an image-efficient transformer variant; U-Swin/SwinIR/TransCT are specific reconstruction networks built from it. — **Add gloss / footnote** for "transformer" at first use; treat the model names (U-Swin etc.) as proper nouns needing no expansion beyond the citation.

39. **U-Net / DD-UNet / SmallUNet** — Table 1 "bilateral, U-Net"; README/leaderboard "DD-UNet". — A widely used encoder–decoder CNN with skip connections, shaped like a "U"; the default image-to-image denoiser/segmenter in medical imaging. — **Add one-line gloss / footnote** at first use. Very common in ML but a pure medical physicist may only half-know it.

40. **Dual-domain (denoiser / pipeline)** — Intro "dual-domain denoisers"; Table 1 "Dual-domain". — A method that denoises in *both* the sinogram (measurement) domain and the image domain, rather than only one. — **Add gloss** at first use (contrast with "image-domain" which the paper also uses).

41. **Image-domain (denoiser / map)** — Methods/Results "supervised image-domain denoiser"; "image-domain maps trained on clean FBP". — Operates only on the reconstructed image (post-FBP), never touching the raw projection data. — **Leave / light gloss.** Mostly clear once "dual-domain" is defined; ensure the contrast is drawn once.

42. **Distribution / distribution it never saw / out-of-distribution (brittle to a distribution)** — Results "It is brittle to a distribution it never saw"; "not tuned to the clean distribution". — The statistical character of the data a model was trained on; if test data differs (e.g. noisy vs the clean training data), the model is "out of distribution" and can fail. — **Add gloss** at first use of "distribution" in this sense — it is the conceptual core of the whole robustness result and the ML meaning ("the kind of data seen in training") is not the everyday meaning.

43. **Hallucinate / hallucination (risk)** — Intro "Such a map is free to \emph{hallucinate}"; Supplement S5 "curbs the hallucination risk". — A learned reconstructor inventing image structure (anatomy) that the measurements do not actually support. — **Leave / light gloss.** In-text it is fairly self-explanatory ("add anatomy that the measurements do not support"); the ML term "hallucinate" is now widely enough known to keep, but a physicist audience may appreciate the one-clause definition already present — keep it.

44. **Recombination / recombined / recombine (compact solver)** — Abstract "the agent recombined a compact solver"; Table 1 "Recombination (ours)". — Assembling components from several existing methods (a filtered data-consistency step + a learned primal-dual combination + a bilateral post-filter) into one new compact solver. — **Add one-line gloss** at first use; it is the paper's own coined usage for its contribution and worth pinning down explicitly.

45. **Param-efficient / parameter count / parameters (M) / 195 parameters / ~0.00097 M params** — Abstract "$\sim$195 parameters"; Supplement S5 "0.324 at $\sim$0.00097 M params". — The total number of trainable numbers in the network; "parameter-efficient" = achieving good accuracy with very few of them; "M" = millions. — **Add gloss / footnote** at first use of parameter count as the efficiency axis, and expand "M" (millions) once. The reader needs to know a "parameter" is a learned weight to grasp the "195 parameters" headline.

46. **Held-out (test set) / held-out test** — Abstract "best iteration on a held-out test set"; Methods. — Data deliberately set aside and never used during training or tuning, used once at the end to give an unbiased performance estimate. — **Add gloss** at first use; "held-out" is standard ML but not universal in physics.

47. **Train / validation / test split** — Methods; Supplement S2/S3. — Partition of the data into a set to fit on (train), a set to tune/select on (validation), and a set to judge on once (test). — **Leave / light gloss.** Likely familiar to a medical physicist doing any ML-adjacent work; if defining "held-out" (above) you can cover it there.

48. **Seed-fragile** — Supplement S5 "The champion is seed-fragile". — The result is unstable across random seeds: some random initializations give a good model, others collapse. — **Add gloss.** Covered by the "seed" gloss (#27); make sure "collapses" is understood as "fails / gives a bad model."

49. **DNF (did not finish)** — Results "reported as DNF"; boards. — The method failed to complete within the compute budget on the test cases. — **Add gloss** (expand "DNF" once). Easy to guess but never spelled out.

50. **Best iteration / iteration (of the search)** — Methods "select each method's best iteration"; throughout. — Each pass of the agent's loop (one edit + one training run) is an "iteration"; the "best iteration" is the configuration that scored highest, chosen for reporting. — **Add light gloss.** Note the potential clash with "iteration" in the classical *iterative reconstruction* sense — the two meanings coexist in this paper (e.g. "in-loop unrolled" iterations vs "search iterations"). Worth one clarifying sentence so the reader keeps them separate.

51. **In-loop (physics / data-consistency)** — Table 1 Axis A "in-loop"; Results "in-loop physics". — The physics operator $\mathbf{A}$ is applied *inside* every unroll step of the network, not just once at the start; the strongest form of physics engagement short of a full per-scene fit. — **Add gloss** at first use of the Axis-A vocabulary ("none / single / in-loop / per-scene"); these four labels are the backbone of the taxonomy and deserve one explanatory sentence each.

52. **Zero-shot vs re-fit / re-fit on the noisy input** — Methods "Per-scene and classical solvers re-fit on the noisy input, which is their normal inference". — Some methods are optimized fresh on each individual (noisy) scan at inference time ("re-fit"), which is simply how they normally operate — contrast with supervised nets that just load fixed weights. — **Add light gloss.** Ties to the per-scene / training / inference glosses; make explicit that "re-fit" here is not the same as "retraining on the dataset."

53. **TPE / Tree-structured Parzen Estimator** (README/`solver_plan.md` context, not in the two `.tex` files) — not in main.tex/supplement.tex. — A Bayesian hyper-parameter search algorithm. — **No action for the paper** (flagged only because it appears in project docs the author may pull in). If it enters the paper, define it.

---

## TIER 3 — FINE / FYI (familiar to this reader or self-explanatory in context — listed so you can confirm "leave as is")

**Standard CT / medical-physics terms — leave, no gloss needed:**
- **FBP (filtered back-projection)** — Intro. Expanded on first use already. Fine.
- **Sinogram / projections / line integrals** — Methods Eq. (1). Core physics vocabulary. Fine.
- **Fan-beam / helical / single-slice rebinning** — Methods/S2, cited. Fine for this reader; rebinning even cited to Noo 1999.
- **Sparse-view / 128-view / under-determined $\mathbf{A}$** — Abstract/Methods. Fine.
- **Low-dose CT / LDCT / Mayo / AAPM Grand Challenge** — Abstract/S2. Fine.
- **Field of view (FOV) / FOV mask $\mathbf{M}$** — Methods Eq. (7). Fine.
- **Forward operator / adjoint $\mathbf{A}^\top$ / back-projection / ramp/Hann filter** — Methods. Standard; the adjoint $\mathbf{A}^\top$ is fine for a physicist. Fine.
- **Total variation (TV) / PWLS-TV / bilateral filter** — Table 1. Classical regularizers/denoisers a physicist knows. Fine. (One caveat: "bilateral" is used both for the classical filter and as a *trainable* layer — make sure the trainable version is signposted, but the term itself is fine.)
- **SART (gradient)** — Supplement S1 table. Standard iterative-reconstruction operator. Fine.
- **Poisson noise / photon count $I_0$ / quantum noise / line integral $p$** — Methods Eq. (6). Core physics. Fine.
- **RMSE / SSIM / PSNR / HU (Hounsfield)** — throughout. Standard image-quality metrics; a physicist knows these. **State once that they are the usual metrics** (they are used with ML-specific settings — see #34 "batch-wide data range" — which *is* worth a note, but the metrics themselves are fine).
- **Calibrated headroom / hr / two-point intensity calibration** — This is the paper's *own* defined metric (Eq. 7), fully specified in-text. Fine — no external jargon, but ensure "headroom" is introduced as a coined term (it is, in the Abstract).
- **Attenuation ($\mu$) / mono-energetic / spectral / metal-artifact** — Table/S2. Physics. Fine.
- **Paired $t$-test / Wilcoxon test / $p$-value / statistical significance / power** — Methods/S4. A medical physicist doing quantitative work will know these. Fine (but see effect-size / Cohen's $d_z$, #22, which is less universal).

**Software / systems terms that are mild and mostly self-explanatory — leave:**
- **GPU / cluster / job / wall-clock** — clear enough in context. Fine (wall-clock noted at #32).
- **Git commit / immutable record** — README context; in the paper "immutable record" is plain enough. Fine.
- **PYRO-NN** — named and cited as the projector library. Fine (proper noun).
- **Config / configuration** — self-explanatory. Fine.

**Note on SLURM / compute budget:** SLURM (the cluster job scheduler) appears in the README and project docs but **not** in `main.tex` or `supplement.tex` — the paper says only "compute cluster" / "cluster job," which is fine. No action unless SLURM is later named in the paper.

**Note on "epoch":** searched — the word "epoch" does **not** appear in `main.tex` or `supplement.tex`. Listed here only so you can confirm it needn't be defined.

---

## Suggested minimal-effort fix set (if defining everything is too much)

If you want the highest comprehension gain for the fewest edits, define these six at first use — they unlock most of the paper for a non-ML medical physicist:
1. **LLM agent** (#1) + **autoresearch** (#2)
2. **supervised / self-supervised / zero-shot** (#4, #5) — one combined sentence
3. **unrolled + proximal-gradient + data-consistency** (#6, #7, #8) — one combined sentence at Eq. (3)
4. **prior / regularizer / inductive bias** (#10, #11)
5. **diffusion / generative prior**, **neural field / implicit**, **Gaussian splatting** (#16, #20, #21) — one gloss each in the Table 1 paragraph
6. **out-of-distribution / "a distribution it never saw"** (#42) — the conceptual key to the main result

Everything else can be a footnote or left, depending on the venue's tolerance. *Medical Physics* readers are quantitative but predominantly not ML specialists, so erring toward the Tier-1 definitions is the safer choice.

"""LLM detection on the cluster's own GPUs, batched — the same prompt, the same cache.

Most of the models the NHR@FAU gateway offers are small enough to run here (AM, 2026-09-08), and
that changes the shape of the whole detection run.  Against the gateway a document costs 2.3–25.6 s
of *network latency* and one request is in flight at a time; locally, vLLM's continuous batching
keeps the GPU saturated and the cost per document collapses.  The gateway job was network-bound and
held a whole Slurm allocation doing nothing; this one is compute-bound and uses the card it asked
for.

**Identical output by construction.**  The prompt, the type list, the windowing and the parser come
from :mod:`.prompting`, which both backends import.  Records land in the same
:class:`~.cache.DetectorCache` with the same ``prompt_version``, so gateway-cached and locally
computed spans are interchangeable in the post-hoc ensemble — the detector *name* is what
distinguishes them, and it is recorded.

## What this hardware can and cannot run

Probed 2026-09-08 with a five-minute Slurm job:

| card | memory | compute capability | consequence |
|---|---|---|---|
| RTX A6000 ×2 | 48 GB | **8.6** (Ampere) | BF16 yes, **FP8 no** |
| Quadro RTX 8000 ×4 | 48 GB | **7.5** (Turing) | **BF16 no**, FP8 no — FP16 only |
| Quadro RTX 6000 ×4 | 24 GB | 7.5 | FP16 only |
| Quadro RTX 5000 ×8 | 16 GB | 7.5 | FP16 only, small models |
| V100 ×4 | 16/32 GB | 7.0 | FP16; vLLM support is thin |

**FP8 needs Ada or Hopper (SM 8.9+), and no card here has it.**  The gateway's `…-FP8` model ids
therefore cannot be run natively; their FP16 counterparts are what runs locally, and that difference
is recorded with the results rather than glossed over — a 31 B model in FP16 is 62 GB and needs two
48 GB cards, while the 3–4 B models fit on almost anything in the table.

Turing has no BF16, so ``dtype`` defaults to ``float16`` rather than ``auto``: ``auto`` picks BF16
from the model config and fails at load on every card here except the A6000.

## The trap that will fill the home directory

HuggingFace caches weights in ``~/.cache/huggingface`` by default.  The home filesystem is **98 %
full with 230 GB free**, shared with the whole group, and a single 31 B checkpoint is 62 GB.
:func:`configure_cache` points ``HF_HOME`` at the work directory instead, and the job script must
call it — or set the variable — **before** the first import of ``transformers`` or ``vllm``.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Sequence

from ..domain import Document, Span
from .alignment import ground_snippets
from .base import DetectorOutput
from .prompting import DEFAULT_TYPES, PROMPT_VERSION, build_messages, parse_reply, windows

__all__ = [
    "LocalLlmDetector",
    "HF_IDS",
    "configure_cache",
    "PROMPT_VERSION",
]

HF_IDS: dict[str, str] = {
    # gateway id -> HuggingFace id.  The gateway's capitalisation is its own routing key and is not
    # always the Hub's: `Microsoft/Phi-4-mini-instruct` is `microsoft/…` on the Hub.  The `-FP8`
    # variants have no runnable form on this hardware (see the module docstring), so they map to
    # the FP16 checkpoint they were quantised from.
    "google/gemma-4-E4B-it": "google/gemma-4-E4B-it",
    "Microsoft/Phi-4-mini-instruct": "microsoft/Phi-4-mini-instruct",
    "ibm-granite/granite-4.1-3b": "ibm-granite/granite-4.1-3b",
    "RedHatAI/Mistral-Small-3.2-24B-Instruct-2506-FP8": (
        "mistralai/Mistral-Small-3.2-24B-Instruct-2506"
    ),
    "RedHatAI/gemma-4-31B-it-FP8-block": "google/gemma-4-31b-it",
    "Qwen/Qwen3.6-35B-A3B-FP8": "Qwen/Qwen3.6-35B-A3B",
    "GaleneAI/Magistral-Small-2509-FP8-Dynamic": "mistralai/Magistral-Small-2509",
}
"""Gateway model id -> the checkpoint to load locally.  Both are recorded with every result."""


def configure_cache(work_dir: Path | str) -> Path:
    """Point the HuggingFace cache at the work directory and return it.

    Must run **before** ``transformers`` or ``vllm`` is imported: both read ``HF_HOME`` at import
    time.  The home filesystem is 98 % full and shared; a checkpoint downloaded there is a
    group-wide problem, not a local one.
    """
    home = Path(work_dir) / "hf_cache"
    home.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HF_HOME", str(home))
    os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")
    return home


@dataclass
class LocalLlmDetector:
    """A vLLM-backed detector.  Batched: use :meth:`detect_many`, not :meth:`detect`.

    ``model`` is the **gateway** id, so a cell configuration reads the same whichever backend ran
    it; :data:`HF_IDS` maps it to the checkpoint.  ``name`` is prefixed ``local:`` so the cache and
    the ensemble can always tell the two backends apart.
    """

    model: str
    types: Sequence[str] = DEFAULT_TYPES
    max_chars: int = 6000
    """Characters per window.  A window must fit the model's context together with its reply."""
    max_tokens: int = 2048
    max_model_len: int | None = None
    dtype: str = "float16"
    """``float16``, not ``auto``: Turing cards (SM 7.5) have no BF16 and ``auto`` fails at load."""
    tensor_parallel_size: int = 1
    gpu_memory_utilization: float = 0.90
    family: str = "llm"
    _engine: object | None = field(default=None, init=False, repr=False)
    _tokenizer: object | None = field(default=None, init=False, repr=False)

    @property
    def name(self) -> str:
        return f"local:{self.model}"

    @property
    def hf_id(self) -> str:
        return HF_IDS.get(self.model, self.model)

    def load(self) -> None:
        """Build the vLLM engine.  Separate from ``__init__`` so a job can time the load."""
        from transformers import AutoTokenizer  # imported late: HF_HOME must be set first
        from vllm import LLM

        self._tokenizer = AutoTokenizer.from_pretrained(self.hf_id)
        self._engine = LLM(
            model=self.hf_id,
            dtype=self.dtype,
            tensor_parallel_size=self.tensor_parallel_size,
            gpu_memory_utilization=self.gpu_memory_utilization,
            max_model_len=self.max_model_len,
            trust_remote_code=True,
        )

    def _prompt(self, chunk: str) -> str:
        """Render one window through the model's own chat template."""
        assert self._tokenizer is not None, "call load() first"
        return self._tokenizer.apply_chat_template(
            build_messages(chunk, self.types), tokenize=False, add_generation_prompt=True
        )

    def detect_many(
        self,
        documents: Iterable[Document],
        progress: Callable[[str], None] | None = None,
    ) -> list[DetectorOutput]:
        """Detect over many documents in **one** batched generation call.

        Every window of every document goes into a single request list, so vLLM schedules them
        together and the GPU stays saturated.  Sending documents one at a time would reproduce the
        gateway job's mistake — serialising work that the hardware is built to overlap — on a card
        this time instead of a network socket.
        """
        from vllm import SamplingParams

        if self._engine is None:
            self.load()

        docs = list(documents)
        prompts: list[str] = []
        owner: list[int] = []
        for index, document in enumerate(docs):
            for _, chunk in windows(document.text, self.max_chars):
                prompts.append(self._prompt(chunk))
                owner.append(index)

        if progress:
            progress(f"{len(docs)} documents -> {len(prompts)} windows")

        started = time.time()
        outputs = self._engine.generate(
            prompts,
            SamplingParams(temperature=0.0, max_tokens=self.max_tokens),
        )
        elapsed = time.time() - started
        if progress:
            rate = len(docs) / elapsed if elapsed else float("inf")
            progress(f"generated in {elapsed:.1f}s — {rate:.2f} documents/s")

        # vLLM returns outputs in request order, so the owner list realigns them onto documents.
        snippets: list[list[tuple[str, str]]] = [[] for _ in docs]
        for index, output in zip(owner, outputs):
            snippets[index].extend(parse_reply(output.outputs[0].text))

        results: list[DetectorOutput] = []
        for document, found in zip(docs, snippets):
            spans = tuple(
                Span(s.start, s.end, s.text, s.type, source=self.name)
                for s in ground_snippets(document.text, found)
            )
            results.append(DetectorOutput(document.doc_id, self.name, spans))
        return results

    def detect(self, document: Document) -> DetectorOutput:
        """Single-document detection, for interface compatibility.

        Correct but slow: it gives vLLM one request to schedule. Prefer :meth:`detect_many`.
        """
        return self.detect_many([document])[0]

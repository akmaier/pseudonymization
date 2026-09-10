"""The frozen scorers the utility tasks are measured with.

Two kinds, and the split follows ``experiment_plan.md`` §14 rather than convenience:

* **Co-reference** is scored with ``biu-nlp/lingmess-coref``, a named checkpoint, because the task
  has a standard model and a standard metric and a prompted foundation model would be neither.
* **Everything else** — article labels, section types, folders, medication spans, formality — is
  scored zero-shot on the NHR@FAU gateway, which §14 assigns *"LLM detectors, A4, zero-shot tasks"*.
  That is also the deployment pattern a TrustFMI audience has: prompt a foundation model over a
  corpus rather than fine-tune an encoder on one.

**Nothing here is trained, and nothing is tuned per condition.**  The same weights and the same
prompt score the original text and every condition, which is what makes the difference between them
attributable to the condition.  A prompt that were adjusted after seeing condition B's scores would
turn a measurement into a fit.

**Every model carries a ``name``, and every result row records it** (§8.3: one fixed scorer model
named in every row).  The name includes the model id, so two runs with different gateway models are
never averaged together by accident.

The output of each is **bounded**: a label from a closed set, a subset of a closed set, a number, or
snippets that must be found in the document.  Bounded output is what keeps a scorer from
free-generating claims — the same principle §8.4 applies to the A4 attacker, for the same reason.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Sequence

from ..detectors.alignment import ground_snippets
from ..gateway import GatewayClient

__all__ = [
    "LingMessResolver",
    "LlmMultiLabelClassifier",
    "LlmSingleLabelClassifier",
    "LlmSpanExtractor",
    "LlmRegressor",
]

_JSON_ARRAY = re.compile(r"\[.*]", re.DOTALL)
_NUMBER = re.compile(r"[-+]?\d*\.?\d+")


def _parse_array(reply: str) -> list[Any]:
    """Salvage a JSON array from a reply, tolerating prose around it and truncation inside it."""
    match = _JSON_ARRAY.search(reply or "")
    blob = match.group(0) if match else (reply or "")[(reply or "").find("[") :]
    if not blob.startswith("["):
        return []
    try:
        parsed = json.loads(blob)
    except json.JSONDecodeError:
        cut = max(blob.rfind("}"), blob.rfind('"'))
        if cut < 0:
            return []
        try:
            parsed = json.loads(blob[: cut + 1] + "]")
        except json.JSONDecodeError:
            return []
    return parsed if isinstance(parsed, list) else []


def _closest(value: str, labels: Sequence[str]) -> str | None:
    """Match a returned label to the closed set, case- and whitespace-insensitively.

    Nothing fuzzier than that.  A model that answered something outside the set has not chosen a
    label, and guessing which one it meant would put the scorer's opinion into the measurement.
    """
    folded = {label.casefold().strip(): label for label in labels}
    return folded.get((value or "").casefold().strip())


# ------------------------------------------------------------------------------------ co-reference


@dataclass
class LingMessResolver:
    """``biu-nlp/lingmess-coref`` (§14), behind the co-reference port.

    Loaded through ``fastcoref``, which is the checkpoint's own distribution.  ``predict`` returns
    clusters as character offsets into the text it was given, which is exactly what the port asks
    for — no token-to-character mapping of ours sits in between to go wrong.
    """

    model: str = "biu-nlp/lingmess-coref"
    device: str | None = None
    batch_size: int = 8
    _model: Any = field(default=None, init=False, repr=False)

    @property
    def name(self) -> str:
        return self.model

    def load(self) -> None:
        from fastcoref import LingMessCoref

        self._model = LingMessCoref(model_name_or_path=self.model, device=self.device)

    def use(self, model: Any) -> LingMessResolver:
        self._model = model
        return self

    def resolve(self, text: str) -> list[list[tuple[int, int]]]:
        if self._model is None:
            self.load()
        predictions = self._model.predict(texts=[text])
        clusters = predictions[0].get_clusters(as_strings=False)
        return [[(int(a), int(b)) for a, b in cluster] for cluster in clusters]

    def resolve_many(self, texts: Sequence[str]) -> list[list[list[tuple[int, int]]]]:
        """Batched resolution — one model call for many documents."""
        if self._model is None:
            self.load()
        predictions = self._model.predict(texts=list(texts), max_tokens_in_batch=self.batch_size)
        return [
            [[(int(a), int(b)) for a, b in cluster] for cluster in p.get_clusters(as_strings=False)]
            for p in predictions
        ]


# --------------------------------------------------------------------------- gateway-backed models


@dataclass
class _LlmModel:
    """Shared plumbing: one gateway client, one document budget, one recorded name."""

    model: str = "gpt-oss-120b"
    config_path: str = "config/llm_api.toml"
    max_chars: int = 12000
    """Documents longer than this are truncated for the *task* prompt, and the truncation is part of
    the protocol rather than an accident: it is applied identically in every condition, so it cannot
    bias the comparison."""
    _client: Any = field(default=None, init=False, repr=False)

    @property
    def client(self) -> GatewayClient:
        if self._client is None:
            self._client = GatewayClient(self.model, self.config_path)
        return self._client

    def use(self, client: Any) -> Any:
        self._client = client
        return self

    def _body(self, text: str) -> str:
        return text[: self.max_chars]


@dataclass
class LlmMultiLabelClassifier(_LlmModel):
    """Zero or more labels from a closed set — TAB's ECHR articles."""

    task_name: str = "multilabel"

    @property
    def name(self) -> str:
        return f"llm:{self.model}/{self.task_name}"

    SYSTEM = (
        "You assign labels to a document from a fixed list. "
        "Return ONLY a JSON array of labels copied exactly from the list, no prose, no code fence. "
        "Return an empty array if none apply."
    )

    def classify(self, text: str, labels: Sequence[str]) -> tuple[str, ...]:
        reply = self.client.ask(
            self.SYSTEM, f"Labels: {json.dumps(list(labels))}\n\nDocument:\n{self._body(text)}"
        )
        chosen = []
        for item in _parse_array(reply.text):
            match = _closest(str(item), labels)
            if match is not None and match not in chosen:
                chosen.append(match)
        return tuple(chosen)


@dataclass
class LlmSingleLabelClassifier(_LlmModel):
    """Exactly one label from a closed set — Enron folders, CARDIO:DE sections."""

    task_name: str = "label"

    @property
    def name(self) -> str:
        return f"llm:{self.model}/{self.task_name}"

    SYSTEM = (
        "You choose exactly one label for a document from a fixed list. "
        "Answer with the label alone, copied exactly, and nothing else."
    )

    def classify(self, text: str, labels: Sequence[str]) -> str:
        reply = self.client.ask(
            self.SYSTEM, f"Labels: {json.dumps(list(labels))}\n\nDocument:\n{self._body(text)}"
        )
        answer = (reply.text or "").strip().strip('"').splitlines()[-1] if reply.text else ""
        match = _closest(answer, labels)
        if match is not None:
            return match
        # A model that answered off-list has not chosen; that is a wrong answer, not a retry.
        return ""


@dataclass
class LlmSpanExtractor(_LlmModel):
    """Typed spans grounded back into the document — CARDIO:DE medication IE.

    The model returns *text*, not offsets, and normalises whitespace and diacritics on the way, so
    the snippets are grounded with :func:`pseudonymkit.detectors.alignment.ground_snippets` rather
    than with ``str.find``.  A literal search drops correct spans silently, which here would read as
    a utility loss caused by the condition rather than by the parser.
    """

    task_name: str = "spans"
    instruction: str = "Extract every span of the listed classes."

    @property
    def name(self) -> str:
        return f"llm:{self.model}/{self.task_name}"

    SYSTEM = (
        "You extract typed spans from text. "
        "Return ONLY a JSON array, no prose, no code fence. "
        'Each element is {"text": "<exact substring from the input>", "class": "<CLASS>"}. '
        "Copy the substring exactly as it appears. Return an empty array if there is nothing."
    )

    def extract(self, text: str, classes: Sequence[str]) -> list[tuple[int, int, str]]:
        body = self._body(text)
        reply = self.client.ask(
            self.SYSTEM,
            f"{self.instruction}\nClasses: {', '.join(classes)}\n\n{body}",
        )
        snippets: list[tuple[str, str]] = []
        allowed = set(classes)
        for item in _parse_array(reply.text):
            if not isinstance(item, dict) or not item.get("text"):
                continue
            label = _closest(str(item.get("class") or item.get("type") or ""), sorted(allowed))
            if label is None:
                continue
            snippets.append((str(item["text"]), label))
        return [(s.start, s.end, s.type) for s in ground_snippets(text, snippets)]


@dataclass
class LlmRegressor(_LlmModel):
    """A number per document — CodEAlltag formality in ``[-1, +1]``."""

    task_name: str = "formality"
    low: float = -1.0
    high: float = 1.0
    instruction: str = (
        "Rate the formality of the e-mail on a scale from -1 (most informal) to +1 (most formal)."
    )

    @property
    def name(self) -> str:
        return f"llm:{self.model}/{self.task_name}"

    SYSTEM = "You rate a document on a numeric scale. Answer with the number alone, nothing else."

    def predict(self, text: str) -> float:
        reply = self.client.ask(self.SYSTEM, f"{self.instruction}\n\n{self._body(text)}")
        found = _NUMBER.search(reply.text or "")
        if not found:
            # A refusal to answer is scored at the midpoint rather than dropped: dropping it would
            # change the document set between conditions and break the pairing §8.3 requires.
            return (self.low + self.high) / 2.0
        return max(self.low, min(self.high, float(found.group(0))))

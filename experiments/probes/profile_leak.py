"""Where do the 3.5 minutes a span source actually go? Timed, not guessed."""
import sys, time
sys.path.insert(0, "src"); sys.path.insert(0, "experiments")
from build_BC import inventory_for, read_key
from pseudonymkit.attacks import (LearnedLinkage, FrequencyAttack, StructuralLinkage,
                                  build_gallery, build_queries, disjoint_document_split, truth_map)
from pseudonymkit.construction import construct, detected_documents, to_pseudonymised_corpus
from pseudonymkit.detectors.cache import DetectorCache
from pseudonymkit.domain import Corpus
from pseudonymkit.metrics.detection import prepare, score_prepared
from pseudonymkit.paths import condition_a_dir
from pseudonymkit.serialisation import iter_documents

def lap(label, t0):
    now = time.time(); print(f"  {label:<34} {now - t0:7.1f}s", flush=True); return now

t = time.time()
docs = list(iter_documents(condition_a_dir() / "enron_A.jsonl.gz"))
corpus = Corpus("enron", tuple(docs)); t = lap("load condition A", t)
cache = DetectorCache("results/detector_cache", "enron")
dets = sorted(p.stem.replace("__", "/") for p in cache.root.glob("*.jsonl"))
union, _ = detected_documents(docs, cache, dets, "union"); t = lap("union detect (for cover)", t)
cover = {(m.type, d.language) for d in union for m in d.mentions}
inv, _ = inventory_for({d.language for d in docs}, documents=union, cover=cover); t = lap("inventory", t)
index = prepare(docs, corpus="enron"); t = lap("prepare index", t)
gdocs, qdocs = disjoint_document_split(corpus, seed=0)
gallery = build_gallery(corpus, "PERSON", documents=gdocs); t = lap("gallery", t)
key = read_key(None) if False else read_key(__import__("pathlib").Path.home()/".config/pseudonymkit/hmac.key")
t = time.time()

names = ("presidio",)
detected, _ = detected_documents(docs, cache, list(names), "union"); t = lap("detect one source", t)
spans = {d.doc_id: tuple(m.span for m in d.mentions) for d in detected}
score_prepared(index, spans, detector="x"); t = lap("score detection", t)
patches = construct(detected, corpus="enron", conditions=("B",), inventory=inv, key=key)
t = lap("construct condition B", t)
result = to_pseudonymised_corpus(docs, patches["B"], check=False); t = lap("materialise corpus", t)
FrequencyAttack().run(result, "PERSON", "deterministic", "hmac"); t = lap("A2 frequency", t)
queries = build_queries(result, "PERSON", documents=qdocs); t = lap("build queries", t)
truth = truth_map(result, "PERSON"); t = lap("truth map", t)
StructuralLinkage().run(queries, gallery, truth, "deterministic", "hmac"); t = lap("A3 structural", t)
for f in range(5):
    LearnedLinkage(seed=0, folds=5, fold=f).run(queries, gallery, truth, "deterministic", "hmac")
t = lap("A5 learned, 5 folds", t)

from pseudonymkit.engine import Pseudonymiser
from pseudonymkit.inventories import SyntheticInventory
from pseudonymkit.keys import NORMALISERS
from pseudonymkit.metrics import evaluate_stability
from pseudonymkit.policies import POLICIES
from pseudonymkit.surrogates import SURROGATES
from pseudonymkit.techniques import TECHNIQUES


def run(doc_or_corpus, normaliser="N2", policy="deterministic"):
    p = Pseudonymiser(
        NORMALISERS.create(normaliser),
        POLICIES.create(policy),
        TECHNIQUES.create("hmac"),
        SURROGATES.create("realistic", inventory=SyntheticInventory()),
    )
    docs = doc_or_corpus.documents if hasattr(doc_or_corpus, "documents") else [doc_or_corpus]
    return p.pseudonymise_corpus(docs)


def test_fragmentation_is_detected(weber_doc):
    """N2 leaves 'F. Weber' distinct from 'Weber', so the chain fragments."""
    report = evaluate_stability(run(weber_doc, "N2"), "PERSON", "deterministic")
    assert report.chains == 1 and report.fragmented_chains == 1
    assert report.fragmentation_rate == 1.0


def test_stronger_normalisation_removes_fragmentation(weber_doc):
    report = evaluate_stability(run(weber_doc, "N3"), "PERSON", "deterministic")
    assert report.fragmented_chains == 0 and report.fragmentation_rate == 0.0


def test_location_is_stable_in_this_fixture(weber_doc):
    report = evaluate_stability(run(weber_doc), "LOC", "deterministic")
    assert report.fragmented_chains == 0


def test_drift_is_zero_under_deterministic_policy(two_doc_corpus):
    report = evaluate_stability(run(two_doc_corpus), "PERSON", "deterministic",
                                cross_document=True)
    assert report.drifting_chains == 0 and report.drift_rate == 0.0


def test_drift_is_total_under_document_policy(two_doc_corpus):
    """Drift is the specification here, not a defect - the report records the policy alongside."""
    report = evaluate_stability(run(two_doc_corpus, policy="document"), "PERSON", "document",
                                cross_document=True)
    assert report.chains == 2 and report.drifting_chains == 2
    assert report.policy == "document"


def test_mentions_without_gold_chains_are_ignored():
    from pseudonymkit.domain import Document, Mention, Span

    doc = Document("d", "Weber.", "en", (Mention("d", "m0", Span(0, 5, "Weber", "PERSON")),))
    assert evaluate_stability(run(doc), "PERSON", "deterministic").chains == 0

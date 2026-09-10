"""The Enron adapter, against inline fixtures so tests never need the 443 MB tarball."""
import email

import pytest

from pseudonymkit.adapters import enron

MSG1 = """Message-ID: <1.JavaMail.evans@thyme>
Date: Mon, 10 Sep 2001 10:33:15 -0700 (PDT)
From: maggie.matheson@enron.com
To: lynn.blair@enron.com
Subject: Customer Training
X-From: Matheson, Maggie </O=ENRON/OU=NA/CN=RECIPIENTS/CN=MMATHES>
X-To: Blair, Lynn </O=ENRON/OU=NA/CN=RECIPIENTS/CN=Lblair>
X-Folder: \\LBLAIR (Non-Privileged)\\Blair, Lynn\\Meetings - NNG Customer Mtg
X-Origin: Blair-L

Thanks for the help. I will ask Blair, Lynn to review it.
"""

MSG2 = """Message-ID: <2.JavaMail.evans@thyme>
Date: Tue, 11 Sep 2001 09:00:00 -0700 (PDT)
From: lynn.blair@enron.com
To: maggie.matheson@enron.com
Subject: Re: Customer Training
X-From: Blair, Lynn </O=ENRON/OU=NA/CN=RECIPIENTS/CN=Lblair>
X-To: Matheson, Maggie </O=ENRON/OU=NA/CN=RECIPIENTS/CN=MMATHES>
X-Folder: \\LBLAIR (Non-Privileged)\\Blair, Lynn\\Sent
X-Origin: Blair-L

Will do. Matheson, Maggie sent the slides.
"""


@pytest.fixture
def maildir(tmp_path):
    root = tmp_path / "maildir"
    for name, body in (("blair-l/meetings/1.", MSG1), ("blair-l/sent/2.", MSG2)):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return root


def test_identity_table_learns_from_sender_pairs():
    table = enron.build_identity_table([MSG1, MSG2])
    assert table.resolve("Matheson, Maggie") == "maggie.matheson@enron.com"
    assert table.resolve("Blair, Lynn") == "lynn.blair@enron.com"


def test_offsets_agree_with_the_text(maildir):
    for doc in enron.load(maildir, min_name_count=1):
        for m in doc.mentions:
            assert doc.text[m.span.start : m.span.end] == m.span.text


def test_addresses_become_cross_document_identities(maildir):
    """The address is the same person in every mailbox - the property TAB cannot supply."""
    corpus = enron.load(maildir, min_name_count=1)
    chains = {m.gold_entity_id for d in corpus for m in d.mentions if m.type == "PERSON"}
    assert chains == {"maggie.matheson@enron.com", "lynn.blair@enron.com"}


def test_the_same_person_is_linked_across_two_documents(maildir):
    corpus = enron.load(maildir, min_name_count=1)
    per_doc = [
        {m.gold_entity_id for m in d.mentions if m.type == "PERSON"} for d in corpus.documents
    ]
    assert per_doc[0] & per_doc[1]


def test_names_are_found_in_the_body_not_only_the_headers(maildir):
    corpus = enron.load(maildir, min_name_count=1)
    doc = next(d for d in corpus if d.doc_id.endswith("1."))
    body_start = doc.text.index("Thanks for the help")
    assert any(m.span.start > body_start and m.type == "PERSON" for m in doc.mentions)


def test_addresses_claim_their_span_before_names_do(maildir):
    """Otherwise the local part of an address is also reported as a name."""
    corpus = enron.load(maildir, min_name_count=1)
    for doc in corpus:
        emails = [(m.span.start, m.span.end) for m in doc.mentions if m.type == "EMAIL"]
        people = [(m.span.start, m.span.end) for m in doc.mentions if m.type == "PERSON"]
        assert not any(s < pe and ps < e for s, e in emails for ps, pe in people)


def test_folder_becomes_the_task_label(maildir):
    labels = {d.task["label"] for d in enron.load(maildir, min_name_count=1)}
    assert labels == {"Meetings - NNG Customer Mtg", "Sent"}


def test_annotation_provenance_is_recorded(maildir):
    """Structural, not gold - no result on Enron may be confused with one on TAB."""
    for doc in enron.load(maildir, min_name_count=1):
        assert doc.metadata["annotation"] == "structural"
        assert doc.provenance == "real"


def test_mailbox_owner_becomes_the_subject(maildir):
    assert {d.subject_id for d in enron.load(maildir, min_name_count=1)} == {"blair-l"}


def test_min_name_count_drops_singletons(maildir):
    """Each display name appears as sender once here, so a threshold of 2 removes both."""
    corpus = enron.load(maildir, min_name_count=2)
    assert not any(m.type == "PERSON" for d in corpus for m in d.mentions)


def test_limit_and_mailbox_filters(maildir):
    assert len(enron.load(maildir, limit=1, min_name_count=1)) == 1
    assert len(enron.load(maildir, mailboxes=["nobody"], min_name_count=1)) == 0


def test_stride_spreads_the_sample_instead_of_taking_a_prefix(maildir):
    """A bare limit reads the first mailboxes only; stride samples across the whole archive."""
    every = [d.doc_id for d in enron.load(maildir, min_name_count=1)]
    strided = [d.doc_id for d in enron.load(maildir, stride=2, min_name_count=1)]
    assert len(every) == 2 and strided == [every[0]]


# ---------------------------------------------------------------- condition A document text


RAW = """Message-ID: <1234.5678.JavaMail.evans@thyme>
Date: Mon, 14 May 2001 16:39:00 -0700 (PDT)
From: phillip.allen@enron.com
To: tim.belden@enron.com
Cc: john.arnold@enron.com
Bcc: john.arnold@enron.com
Subject: Re: gas nominations
Mime-Version: 1.0
Content-Type: text/plain; charset=us-ascii
X-From: Phillip K Allen
X-To: Tim Belden
X-cc: John Arnold
X-Folder: \\Phillip_Allen_Jan2002_1\\Allen, Phillip K.\\'Sent Mail
X-Origin: Allen-P
X-FileName: pallen (Non-Privileged).pst

Here is the schedule we discussed.

-----Original Message-----
From: tim.belden@enron.com
Sent: Monday, May 14, 2001 9:02 AM
To: phillip.allen@enron.com
Subject: gas nominations

> what did we agree on Friday?
Please confirm."""


def test_condition_a_text_keeps_the_specified_fields_and_nothing_else():
    message = email.message_from_string(RAW)
    text = enron.build_text(message)

    # sender, recipients, names, addresses, subject
    assert "Phillip K Allen" in text and "phillip.allen@enron.com" in text
    assert "Tim Belden" in text and "tim.belden@enron.com" in text
    assert "John Arnold" in text
    assert "Subject: Re: gas nominations" in text
    assert "Here is the schedule we discussed." in text

    # archive metadata is not correspondence
    for absent in ("Message-ID", "X-FileName", "Mime-Version", "Content-Type", "X-Origin"):
        assert absent not in text

    # Bcc duplicates Cc byte for byte in every message of the sample
    assert "Bcc" not in text


def test_the_folder_label_is_not_in_the_text():
    # X-Folder names the mailbox folder, which is the folder-classification target. Leaving it in
    # would put the answer in the input.
    text = enron.build_text(email.message_from_string(RAW))
    assert "X-Folder" not in text
    assert "Sent Mail" not in text


def test_quoted_replies_and_forwarded_blocks_are_dropped():
    text = enron.build_text(email.message_from_string(RAW))
    assert "Here is the schedule" in text
    assert "-----Original Message-----" not in text
    assert "what did we agree on Friday?" not in text   # a quoted line
    assert "Please confirm." not in text                # below the forwarding banner


def test_a_multipart_alternative_contributes_one_body_not_two():
    raw = (
        "From: a@x.com\nTo: b@x.com\nSubject: s\n"
        "Mime-Version: 1.0\nContent-Type: multipart/alternative; boundary=BOUND\n\n"
        "--BOUND\nContent-Type: text/plain\n\nthe plain body\n"
        "--BOUND\nContent-Type: text/html\n\n<html>the plain body</html>\n--BOUND--\n"
    )
    text = enron.build_text(email.message_from_string(raw))
    assert text.count("the plain body") == 1
    assert "<html>" not in text


def test_a_message_with_no_body_still_yields_its_header_fields():
    raw = "From: a@x.com\nTo: b@x.com\nSubject: only headers\n\n"
    text = enron.build_text(email.message_from_string(raw))
    assert "Subject: only headers" in text
    assert "From: a@x.com" in text

"""The Enron adapter, against inline fixtures so tests never need the 443 MB tarball."""
import email

import pytest

from pseudonymkit.adapters import enron

MSG1 = """Message-ID: <1.JavaMail.evans@thyme>
Date: Mon, 10 Sep 2001 10:33:15 -0700 (PDT)
From: ann.aardvark@enron.com
To: bo.bramble@enron.com
Subject: Customer Training
X-From: Aardvark, Ann </O=ENRON/OU=NA/CN=RECIPIENTS/CN=AAARDVA>
X-To: Bramble, Bo </O=ENRON/OU=NA/CN=RECIPIENTS/CN=Bbrambl>
X-Folder: \\BBRAMBL (Non-Privileged)\\Bramble, Bo\\Meetings - NNG Customer Mtg
X-Origin: Bramble-B

Thanks for the help. I will ask Bramble, Bo to review it.
"""

MSG2 = """Message-ID: <2.JavaMail.evans@thyme>
Date: Tue, 11 Sep 2001 09:00:00 -0700 (PDT)
From: bo.bramble@enron.com
To: ann.aardvark@enron.com
Subject: Re: Customer Training
X-From: Bramble, Bo </O=ENRON/OU=NA/CN=RECIPIENTS/CN=Bbrambl>
X-To: Aardvark, Ann </O=ENRON/OU=NA/CN=RECIPIENTS/CN=AAARDVA>
X-Folder: \\BBRAMBL (Non-Privileged)\\Bramble, Bo\\Sent
X-Origin: Bramble-B

Will do. Aardvark, Ann sent the slides.
"""


@pytest.fixture
def maildir(tmp_path):
    root = tmp_path / "maildir"
    for name, body in (("bramble-b/meetings/1.", MSG1), ("bramble-b/sent/2.", MSG2)):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return root


def test_identity_table_learns_from_sender_pairs():
    table = enron.build_identity_table([MSG1, MSG2])
    assert table.resolve("Aardvark, Ann") == "ann.aardvark@enron.com"
    assert table.resolve("Bramble, Bo") == "bo.bramble@enron.com"


def test_offsets_agree_with_the_text(maildir):
    for doc in enron.load(maildir, min_name_count=1):
        for m in doc.mentions:
            assert doc.text[m.span.start : m.span.end] == m.span.text


def test_addresses_become_cross_document_identities(maildir):
    """The address is the same person in every mailbox - the property TAB cannot supply."""
    corpus = enron.load(maildir, min_name_count=1)
    chains = {m.gold_entity_id for d in corpus for m in d.mentions if m.type == "PERSON"}
    assert chains == {"ann.aardvark@enron.com", "bo.bramble@enron.com"}


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
    assert {d.subject_id for d in enron.load(maildir, min_name_count=1)} == {"bramble-b"}


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
From: carl.cresswell@enron.com
To: dee.dunmore@enron.com
Cc: eve.everly@enron.com
Bcc: eve.everly@enron.com
Subject: Re: gas nominations
Mime-Version: 1.0
Content-Type: text/plain; charset=us-ascii
X-From: Carl K Cresswell
X-To: Dee Dunmore
X-cc: Eve Everly
X-Folder: \\Carl_Cresswell_Jan2002_1\\Cresswell, Carl K.\\'Sent Mail
X-Origin: Cresswell-C
X-FileName: ccresswell (Non-Privileged).pst

Here is the schedule we discussed.

-----Original Message-----
From: dee.dunmore@enron.com
Sent: Monday, May 14, 2001 9:02 AM
To: carl.cresswell@enron.com
Subject: gas nominations

> what did we agree on Friday?
Please confirm."""


def test_condition_a_text_keeps_the_specified_fields_and_nothing_else():
    message = email.message_from_string(RAW)
    text = enron.build_text(message)

    # sender, recipients, names, addresses, subject
    assert "Carl K Cresswell" in text and "carl.cresswell@enron.com" in text
    assert "Dee Dunmore" in text and "dee.dunmore@enron.com" in text
    assert "Eve Everly" in text
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


def test_messages_with_no_body_are_excluded(tmp_path):
    # AM, 2026-09-10: a forward that added nothing carries names but no prose. It cannot be scored
    # on a utility task and would enter every condition as an empty document.
    quoted_only = (
        "From: a@x.com\nX-From: Ann Aardvark\nTo: b@x.com\nSubject: fwd\n\n"
        "-----Original Message-----\nFrom: c@x.com\n\nthe original text\n"
    )
    with_body = (
        "From: a@x.com\nX-From: Ann Aardvark\nTo: b@x.com\nSubject: real\n\n"
        "This message says something.\n"
    )
    root = tmp_path / "maildir" / "aardvark-a" / "sent"
    root.mkdir(parents=True)
    (root / "1.").write_text(quoted_only, "utf-8")
    (root / "2.").write_text(with_body, "utf-8")

    kept = enron.load(tmp_path / "maildir")
    assert [d.doc_id.rsplit("/", 1)[-1] for d in kept.documents] == ["2."]

    both = enron.load(tmp_path / "maildir", require_body=False)
    assert len(both) == 2


def test_exchange_distinguished_names_are_dropped_from_the_headers():
    """49,463 of them, all in the header block, none in the body.

    Every recipient appears three times — display name, X.500 DN, address — and a mail client shows
    the first and third. The DN carries nothing the others do not (`CN=FFAIRBA` truncates the same
    name) while contributing a highly regular string a detector will learn instead of the task.
    """
    import email

    raw = (
        "Message-ID: <1.JavaMail@thyme>\n"
        "From: finn.fairbairn@enron.com\n"
        "To: gail.goodwin@enron.com\n"
        "Subject: Schedule\n"
        "X-From: Fairbairn, Finn </O=ENRON/OU=NA/CN=RECIPIENTS/CN=FFAIRBA>\n"
        "X-To: Goodwin, Gail </O=ENRON/OU=NA/CN=RECIPIENTS/CN=Ggoodwi>\n"
        "X-cc: Hale, Hugo </O=ENRON/OU=NA/CN=RECIPIENTS/CN=Hhale>, "
        "Ivers, Iris M. </O=ENRON/OU=NA/CN=RECIPIENTS/CN=Iivers>\n"
        "X-Folder: \\Sent\n"
        "\n"
        "Please confirm the schedule.\n"
    )
    text = enron.build_text(email.message_from_string(raw))

    assert "/O=ENRON" not in text and "CN=RECIPIENTS" not in text
    # display names keep their Last, First surface; addresses stay — both are what a client shows
    assert "Fairbairn, Finn" in text and "finn.fairbairn@enron.com" in text
    assert "Goodwin, Gail" in text and "gail.goodwin@enron.com" in text
    assert "Hale, Hugo" in text and "Ivers, Iris M." in text
    # removing a DN must not leave ", ," or a dangling comma behind
    assert ", ," not in text and not any(l.rstrip().endswith(",") for l in text.splitlines())
    assert "Please confirm the schedule." in text

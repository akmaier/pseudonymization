"""ENRON 2.0 helpers (AM, 2026-10-03). Every name and address here is invented (§15, safeguard 1)."""

from __future__ import annotations

import email

import pytest

from pseudonymkit.adapters.enron import IdentityTable
from pseudonymkit.adapters.enron2 import (
    NameIndex,
    ShingleIndex,
    Unit,
    clean_body,
    dedup_key,
    document_text,
    draw,
    find_mentions,
    local_part_name,
    name_forms,
    participants,
    plausible_full_name,
    shingles,
    strip_embedded,
    thread_key,
)


# ------------------------------------------------------------------------------- body cleaning


def test_a_lotus_notes_quote_is_cut_with_its_stamp_and_sender_line() -> None:
    body = ("Thanks for the update, see you Friday.\n\n"
            "Ann Example\n12/14/2000 10:22 AM\n"
            "To: Bob Sample/HOU/ECT@ECT\ncc: \nSubject: Re: budget\n\n"
            "The original message nobody here wrote.")
    assert strip_embedded(body) == "Thanks for the update, see you Friday."


def test_the_spaced_outlook_express_marker_that_paper_1_missed_is_cut() -> None:
    body = "I agree.\n----- Original Message -----\nFrom: Ann Example\nTo: Bob Sample\nSent: x"
    assert strip_embedded(body) == "I agree."


def test_a_pasted_smtp_dump_below_prose_is_cut() -> None:
    body = ("See below.\nReceived: from mail.example.org by relay\n"
            "Message-ID: <1@example.org>\nFrom: someone@example.org\nX-Mailer: Client 4.5\n"
            "the forwarded text")
    assert strip_embedded(body) == "See below."


def test_a_memo_header_at_the_top_is_dropped_and_the_memo_kept() -> None:
    body = "To: All staff\nFrom: Ann Example\nSubject: Parking\n\nThe garage closes on Friday."
    assert strip_embedded(body) == "The garage closes on Friday."


def test_one_header_like_line_in_prose_is_left_alone() -> None:
    body = "Agenda for the review.\nDate: Tuesday afternoon\nPlease bring the figures."
    assert strip_embedded(body) == body


def test_a_wrote_line_opens_quoted_history() -> None:
    body = "Fine by me.\nOn Mon, Jan 1, 2001, Ann Example wrote:\nshall we meet?"
    assert strip_embedded(body) == "Fine by me."


def test_clean_body_still_applies_the_paper_1_rules() -> None:
    body = "My answer.\n> your question\n-----Original Message-----\nFrom: x\nTo: y"
    assert clean_body(body) == "My answer."


def test_dedup_ignores_whitespace_but_not_words() -> None:
    assert dedup_key("one  two\nthree") == dedup_key("one two three")
    assert dedup_key("one two three") != dedup_key("one two four")


def test_the_thread_key_folds_reply_and_forward_prefixes() -> None:
    assert thread_key("RE: Fw:  Budget   review") == "budget review"
    assert thread_key("Re[2]: Budget review") == "budget review"
    assert thread_key("") is None and thread_key(None) is None


def test_the_document_keeps_the_subject_line_above_the_body() -> None:
    assert document_text("RE:  Budget\nreview", "Body text.") == \
        "Subject: RE: Budget review\n\nBody text."


# --------------------------------------------------------------------------------------- names


def test_name_forms_reorder_drop_initials_and_give_the_bare_parts() -> None:
    many, one = name_forms("Example, Ann M")
    assert {"ann example", "example, ann"} <= many
    assert one == {"ann", "example"}


def test_a_single_token_display_yields_only_a_single_form() -> None:
    assert name_forms("Carl") == (frozenset(), frozenset({"carl"}))
    assert name_forms("carl@other.org") == (frozenset(), frozenset())


def test_the_local_part_is_read_only_in_the_two_part_name_form() -> None:
    gaz = frozenset({"ann", "example", "market"})
    assert local_part_name("ann.example@corp.org", gaz) == "ann example"
    assert local_part_name("aexample@corp.org", gaz) is None
    assert local_part_name("market.news@corp.org", gaz) is None      # a role word
    assert local_part_name("ann.zzyzx@corp.org", gaz) is None        # not a known name


def test_organisational_display_names_are_not_people() -> None:
    given, surnames = frozenset({"ann"}), frozenset({"example"})
    assert not plausible_full_name(["office", "of", "the", "chairman"], given, surnames)
    assert not plausible_full_name(["human", "resources"], given, surnames)
    assert plausible_full_name(["ann", "zzyzx"], given, surnames)
    assert plausible_full_name(["qq", "example"], given, surnames)
    assert not plausible_full_name(["qq", "zzyzx"], given, surnames)


def test_the_envelope_is_every_address_on_from_to_cc_and_bcc() -> None:
    message = email.message_from_string(
        "From: Ann.Example@corp.org\nTo: bob.sample@corp.org, carl@other.org\n"
        "Cc: bob.sample@corp.org\nBcc: dee.test@corp.org\n\nbody")
    assert participants(message) == ("ann.example@corp.org", "bob.sample@corp.org",
                                     "carl@other.org", "dee.test@corp.org")


# ------------------------------------------------------------------------------ gold standard


ANN, BOB, CARL, ANN2 = ("ann.example@corp.org", "bob.sample@corp.org", "carl@other.org",
                        "ann.other@corp.org")
GAZ = frozenset({"ann", "example", "bob", "sample", "carl", "will", "other"})


def index() -> NameIndex:
    table = IdentityTable(
        by_name={"ann example": ANN, "bob sample": BOB, "carl": CARL, "will": "will@x.org",
                 "ann other": ANN2, "office of the chairman": "chair@corp.org"},
        counts={"ann example": 5, "bob sample": 5, "carl": 3, "will": 3, "ann other": 2,
                "office of the chairman": 9},
    )
    return NameIndex.build(table, gazetteer=GAZ, given=frozenset({"ann", "bob", "carl", "will"}),
                           surnames=frozenset({"example", "sample", "other"}))


def spans(mentions):
    return [(m.span.text, m.span.type, m.mention_id[0], m.gold_entity_id) for m in mentions]


def test_participants_resolve_the_bare_first_names_in_their_own_message() -> None:
    text = ("Subject: Lunch\n\nHi Bob,\nlunch with Ann Example at noon? Carl will join.\n"
            "Thanks, Ann\nann.example@corp.org")
    got = spans(find_mentions("d1", text, (ANN, BOB), index()))
    assert ("Bob", "PERSON", "f", BOB) in got                 # greeting, a participant
    assert ("Ann Example", "PERSON", "p", ANN) in got         # full name, a participant
    assert ("Ann", "PERSON", "f", ANN) in got                 # the sign-off
    assert ("Carl", "PERSON", "g", None) in got               # a person, but not on the envelope
    assert ("ann.example@corp.org", "CODE", "a", ANN) in got  # the address claims its span
    assert not any(t.casefold() == "will" for t, *_ in got)   # lower-case word, not a name


def test_a_bare_name_two_participants_share_is_a_person_with_no_identity() -> None:
    got = spans(find_mentions("d2", "Subject: x\n\nThanks, Ann", (ANN, ANN2), index()))
    assert got == [("Ann", "PERSON", "f", None)]


def test_bare_names_must_be_capitalised() -> None:
    got = spans(find_mentions("d3", "Subject: x\n\nask bob and carl", (ANN, BOB), index()))
    assert got == []


def test_a_word_name_is_not_credited_without_a_participant_behind_it() -> None:
    got = spans(find_mentions("d4", "Subject: x\n\nWill you join us?", (ANN,), index()))
    assert got == []


def test_an_organisation_sender_is_not_gold() -> None:
    got = spans(find_mentions("d5", "Subject: x\n\nA note from the Office of the Chairman.",
                              (ANN,), index()))
    assert not any(kind == "PERSON" for _, kind, *_ in got)


def test_a_full_name_written_last_comma_first_is_found() -> None:
    got = spans(find_mentions("d6", "Subject: x\n\nPlease ask Example,Ann first.", (BOB,), index()))
    assert ("Example,Ann", "PERSON", "n", ANN) in got


# -------------------------------------------------------------------------------- near copies


LONG = ("the quarterly figures for the western region are attached and we should review "
        "them together before the board meeting on thursday morning")


def test_the_same_text_with_a_line_added_is_a_near_duplicate() -> None:
    near = ShingleIndex()
    near.add(shingles(LONG))
    assert near.is_near(shingles("FYI, see below.\n" + LONG))
    assert not near.is_near(shingles("an entirely different message about the holiday "
                                     "party and who is bringing what to the office"))


def test_a_stock_phrase_inside_a_long_message_is_not_a_copy_of_it() -> None:
    near = ShingleIndex()
    near.add(shingles(LONG + " let me know if you have any questions"))
    assert not near.is_near(shingles("let me know if you have any questions"))


def test_shingles_are_stable_across_processes() -> None:
    # blake2b, not hash(): the draw must not change with PYTHONHASHSEED.
    assert shingles("one two three four five") == shingles("one two three four five")
    assert len(shingles("one two three four five six")) == 2


# ------------------------------------------------------------------------------------ the draw


def toy_units():
    units = [Unit("m1", f"t{i}", (f"m1-{i}",)) for i in range(10)]
    units += [Unit("m2", f"t{i}", (f"m2-{i}",)) for i in range(10)]
    tokens = {u.members[0]: 10 for u in units}
    bodies = {u.members[0]: f"message {u.members[0]} unique words here number {i}"
              for i, u in enumerate(units)}
    return units, tokens, bodies


def test_the_draw_respects_the_budget_and_the_mailbox_cap() -> None:
    units, tokens, bodies = toy_units()
    keys, stats = draw(units, tokens, bodies.__getitem__, budget=100, cap_fraction=0.6, seed=0)
    assert stats["tokens"] == 100
    assert stats["largest_mailbox_tokens"] <= 60
    assert sum(1 for k in keys if k.startswith("m1")) <= 6


def test_the_draw_depends_on_the_seed_not_the_input_order() -> None:
    units, tokens, bodies = toy_units()
    a, _ = draw(units, tokens, bodies.__getitem__, budget=50, cap_fraction=1.0, seed=3)
    b, _ = draw(list(reversed(units)), tokens, bodies.__getitem__, budget=50, cap_fraction=1.0,
                seed=3)
    c, _ = draw(units, tokens, bodies.__getitem__, budget=50, cap_fraction=1.0, seed=4)
    assert a == b and a != c


def test_a_near_duplicate_message_is_skipped_by_the_draw() -> None:
    units = [Unit("m1", "a", ("x",)), Unit("m1", "b", ("y",))]
    tokens = {"x": 30, "y": 30}
    bodies = {"x": LONG, "y": "FYI.\n" + LONG}
    keys, stats = draw(units, tokens, bodies.__getitem__, budget=1000, cap_fraction=1.0, seed=0)
    assert len(keys) == 1 and stats["messages_near_duplicate"] == 1


# --------------------------------------------------------------------------- quoted-printable


def test_a_declared_quoted_printable_body_is_decoded() -> None:
    from pseudonymkit.adapters.enron2 import decoded_body

    message = email.message_from_string(
        "Content-Transfer-Encoding: quoted-printable\n\nwe are talking=\n about people=20\nok =3D yes")
    assert decoded_body(message) == "we are talking about people \nok = yes"


def test_a_soft_break_under_a_7bit_header_is_decoded_too() -> None:
    from pseudonymkit.adapters.enron2 import decoded_body

    message = email.message_from_string(
        "Content-Transfer-Encoding: 7bit\n\nthe driving force behind every success=\n that we had")
    assert decoded_body(message) == "the driving force behind every success that we had"


def test_a_plain_body_is_returned_exactly_as_read() -> None:
    from pseudonymkit.adapters.enron2 import decoded_body

    message = email.message_from_string("Content-Transfer-Encoding: 7bit\n\nx=20 is a formula")
    assert decoded_body(message) == "x=20 is a formula"

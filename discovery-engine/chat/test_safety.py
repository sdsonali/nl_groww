"""Checks for the safety layer. These do not call NVIDIA."""

import json
import unittest

from chat.agents import retrieve
from chat.handoff import summary
from chat.pipeline import apply_streaks, run_turn
from chat.safety import (
    check_output,
    is_advice_request,
    mask,
    precheck,
    wants_person,
)


class SafetyTests(unittest.TestCase):
    def test_how_to_stop_is_not_advice(self):
        self.assertIsNone(precheck("How do I stop my SIP?"))
        self.assertFalse(is_advice_request("How do I stop my SIP?"))
        self.assertFalse(is_advice_request("sip kaise band kare?"))

    def test_should_stop_is_declined(self):
        result = precheck("should I stop my SIP now?")
        self.assertEqual(result["action"], "decline")
        self.assertNotIn("hurry", result["text"].lower())

    def test_fund_pick_is_declined(self):
        for text in (
            "Which fund is best?",
            "konsa fund lu?",
            "best SIP for me",
            "which stock is best?",
            "should I invest in this?",
        ):
            self.assertEqual(precheck(text)["action"], "decline", text)

    def test_person_words_go_to_handoff(self):
        for text in ("agent", "I want a human", "customer care", "mujhe insaan chahiye"):
            self.assertEqual(precheck(text)["action"], "handoff", text)
        self.assertTrue(wants_person("talk to someone"))

    def test_mask_hides_pan_phone_and_long_digits(self):
        masked, changed = mask("PAN ABCDE1234F phone 9876543210 account 123456789012")
        self.assertTrue(changed)
        self.assertNotIn("ABCDE1234F", masked)
        self.assertNotIn("9876543210", masked)
        self.assertNotIn("123456789012", masked)
        self.assertIn("[hidden]", masked)

    def test_mask_leaves_short_sample_amount(self):
        masked, changed = mask("The sample amount is 2000")
        self.assertFalse(changed)
        self.assertIn("2000", masked)

    def test_output_blocks_urgency_and_fund_names(self):
        known = {"learn_nav"}
        blocked = {
            "answer": "You should buy this Fund now, hurry.",
            "kb_ids_used": ["learn_nav"],
            "confidence": 0.9,
        }
        ok, reason = check_output(blocked, known)
        self.assertFalse(ok)
        self.assertIn(reason, {"blocked wording", "fund name"})
        named = {
            "answer": "Axis Flexi Cap moved this week.",
            "kb_ids_used": ["learn_nav"],
            "confidence": 0.9,
        }
        ok, reason = check_output(named, known)
        self.assertFalse(ok)
        self.assertEqual(reason, "fund name")

    def test_bank_word_alone_is_allowed(self):
        ok, reason = check_output(
            {
                "answer": "Check the balance at your bank, then look at the SIP status.",
                "kb_ids_used": ["inst_bank_rejected"],
                "confidence": 0.8,
            },
            {"inst_bank_rejected"},
        )
        self.assertTrue(ok, reason)

    def test_retrieve_prefers_the_open_scenario(self):
        found = retrieve(
            "instalment",
            "how do I renew",
            "UPI autopay is off before the debit day",
        )
        self.assertTrue(found)
        self.assertEqual(found[0]["id"], "inst_autopay_off")

    def test_empty_notes_answer_from_the_prompt(self):
        calls = {"n": 0}

        def fake(system, user, max_tokens):
            calls["n"] += 1
            if calls["n"] == 1:
                return '{"agent": "none", "confidence": 0.9, "language": "english"}'
            self.assertNotIn("TODO-VERIFY", user)
            return json.dumps(
                {
                    "answerable": True,
                    "answer": (
                        "A SIP invests a chosen amount on a chosen date. "
                        "The exact screen in the app can differ."
                    ),
                    "kb_ids_used": [],
                    "confidence": 0.82,
                }
            )

        result = run_turn(
            "can you tell me how to invest in the sip?",
            {"scenario": "UPI autopay is off before the debit day"},
            llm=fake,
        )
        self.assertEqual(calls["n"], 2)
        self.assertEqual(result["action"], "answer")
        self.assertNotIn("TODO-VERIFY", result["text"])
        self.assertNotIn("Fund", result["text"])

    def test_general_answer_still_blocks_a_fund_name(self):
        calls = {"n": 0}

        def fake(system, user, max_tokens):
            calls["n"] += 1
            if calls["n"] == 1:
                return '{"agent": "none", "confidence": 0.9, "language": "english"}'
            return json.dumps(
                {
                    "answerable": True,
                    "answer": "Axis Flexi Cap is the one to use.",
                    "kb_ids_used": [],
                    "confidence": 0.9,
                }
            )

        result = run_turn("how do I invest in a sip?", {"scenario": ""}, llm=fake)
        self.assertEqual(result["action"], "limited")
        self.assertNotIn("Axis", result["text"])
        self.assertIn("I can't share news, returns or fund details", result["text"])

    def test_news_and_returns_are_blocked(self):
        from chat.safety import LIMITED_TEXT, reply_has_blocked_detail

        def boom(system, user, max_tokens):
            raise AssertionError("model was called")

        news = run_turn("latest news on SIP", {"scenario": ""}, llm=boom)
        self.assertEqual(news["action"], "limited")
        self.assertEqual(news["text"], LIMITED_TEXT)

        calls = {"n": 0}

        def fake(system, user, max_tokens):
            calls["n"] += 1
            if calls["n"] == 1:
                return '{"agent": "learn", "confidence": 0.9, "language": "english"}'
            return json.dumps(
                {
                    "answerable": True,
                    "answer": "The 3 year return is 10.9% on this SIP.",
                    "kb_ids_used": [],
                    "confidence": 0.9,
                }
            )

        returned = run_turn("How does a SIP work?", {"scenario": ""}, llm=fake)
        self.assertTrue(reply_has_blocked_detail("The 3 year return is 10.9% on this SIP."))
        self.assertEqual(returned["action"], "limited")
        self.assertEqual(returned["text"], LIMITED_TEXT)
        self.assertNotIn("%", returned["text"])

    def test_news_buy_request_is_still_declined(self):
        def boom(system, user, max_tokens):
            raise AssertionError("model was called")

        result = run_turn(
            "should I buy Groww Liquid Fund after this news?",
            {"scenario": ""},
            llm=boom,
        )
        self.assertEqual(result["action"], "decline")

    def test_screen_agent_offers_renew_then_fills(self):
        from chat.screen_agent import decide

        story = "UPI never gets debited. Every month I have to manually pay it."
        offer = decide(story, None, "Bank rejected the debit")
        self.assertEqual(offer["type"], "offer")
        self.assertEqual(offer["offer"]["label"], "UPI autopay is off before the debit day")
        self.assertIn("Want me to do that?", offer["text"])
        self.assertNotIn("Say yes", offer["text"])

        filled = decide("yes, amount 3500, account ending 2291", offer["offer"], "")
        self.assertEqual(filled["type"], "apply")
        self.assertEqual(filled["situation"], "UPI autopay is off before the debit day")
        self.assertEqual(filled["step"], "done")
        self.assertEqual(filled["amount"], "₹3,500")
        self.assertIn("2291", filled["bank"])
        self.assertIsNone(filled["offer"])

    def test_manual_pay_and_set_autopay_offer_renew_in_english(self):
        from chat.language import detect_language
        from chat.screen_agent import decide

        story = "for last few months i used to pay the sip manully im tired of this"
        self.assertEqual(detect_language(story), "english")
        offer = decide(story, None, "Bank rejected the debit")
        self.assertEqual(offer["offer"]["label"], "UPI autopay is off before the debit day")
        self.assertIn("Want me to do that?", offer["text"])
        self.assertNotIn("मैं", offer["text"])

        setup = decide("can you help me setting the autopay", None, "Bank rejected the debit")
        self.assertEqual(setup["offer"]["label"], "UPI autopay is off before the debit day")
        self.assertNotEqual(setup["offer"]["label"], "Bank rejected the debit")

        missed = decide("autopay did not send the instalment", None, "Bank rejected the debit")
        self.assertEqual(missed["offer"]["label"], "Autopay did not send it")

    def test_reply_language_follows_the_user(self):
        from chat.language import detect_language, reply_instruction

        self.assertEqual(detect_language("What is NAV?"), "english")
        self.assertEqual(detect_language("मुझे autopay सेट करना है"), "hindi")
        self.assertEqual(detect_language("ਮੈਨੂੰ autopay ਚਾਹੀਦਾ ਹੈ"), "punjabi")
        self.assertEqual(detect_language("mujhe autopay set karna hai yaar"), "hinglish")
        self.assertEqual(detect_language("mainu autopay chahida vich"), "punjabi_roman")
        english = reply_instruction("english")
        self.assertIn("Reply only in English", english)
        self.assertIn("Do not switch", english)

    def test_screen_agent_leaves_real_questions_alone(self):
        from chat.screen_agent import decide

        self.assertEqual(decide("What is NAV?", None, "Bank rejected the debit")["type"], "pass")
        self.assertEqual(
            decide("latest news on SIP", None, "Bank rejected the debit")["type"], "pass"
        )

    def test_decline_does_not_call_the_model(self):
        def boom(system, user, max_tokens):
            raise AssertionError("model was called")

        result = run_turn("should I stop my SIP now?", {"scenario": ""}, llm=boom)
        self.assertEqual(result["action"], "decline")

    def test_how_to_stop_is_routed_not_declined(self):
        def fake(system, user, max_tokens):
            return '{"agent": "controls", "confidence": 0.9, "language": "english"}'

        result = run_turn("How do I stop my SIP?", {"scenario": ""}, llm=fake)
        self.assertEqual(result["action"], "fallback")
        self.assertEqual(result["agent"], "controls")

    def test_checked_fact_is_returned_only_if_the_output_is_safe(self):
        kb = [
            {
                "id": "learn_nav",
                "agent": "learn",
                "title": "What NAV means",
                "scenarios": [],
                "keywords": ["nav"],
                "facts": ["NAV is the price of one unit on that day."],
                "steps": [],
                "clarifiers": [],
                "source_title": "AMFI investor page",
                "source_url": "https://www.amfiindia.com/investor-corner",
                "last_checked": "2026-11-04",
            }
        ]
        calls = {"n": 0}

        def fake(system, user, max_tokens):
            calls["n"] += 1
            if calls["n"] == 1:
                return '{"agent": "learn", "confidence": 0.95, "language": "english"}'
            self.assertNotIn("TODO-VERIFY", user)
            return json.dumps(
                {
                    "answerable": True,
                    "answer": "NAV is the price of one unit on that day.",
                    "kb_ids_used": ["learn_nav"],
                    "confidence": 0.92,
                }
            )

        result = run_turn("What is NAV?", {"scenario": ""}, llm=fake, kb=kb)
        self.assertEqual(calls["n"], 2)
        self.assertEqual(result["action"], "answer")
        self.assertEqual(result["source_title"], "AMFI investor page")

    def test_second_decline_becomes_handoff(self):
        first, low, declined = apply_streaks(
            {"action": "decline", "text": "no", "low": False}, 0, 0
        )
        self.assertEqual(first["action"], "decline")
        second, _low, _declined = apply_streaks(first, low, declined)
        self.assertEqual(second["action"], "handoff")
        self.assertEqual(second["reason"], "safety check declined twice")

    def test_summary_has_no_personal_numbers(self):
        text = summary(
            "UPI autopay is off before the debit day",
            "My PAN is ABCDE1234F and account 123456789012",
            "instalment",
            ["UPI autopay is off or expired"],
            "user asked for support",
        )
        self.assertNotIn("ABCDE1234F", text)
        self.assertNotIn("123456789012", text)
        self.assertIn("[hidden]", text)
        self.assertIn("Reason for handoff: user asked for support", text)

    def test_catalog_scheme_name_is_allowed(self):
        ok, reason = check_output(
            {
                "answer": "Groww Large Cap Fund Direct Growth has a minimum SIP of ₹500 on the page.",
                "kb_ids_used": ["scheme_large_cap"],
                "confidence": 0.9,
            },
            {"scheme_large_cap"},
        )
        self.assertTrue(ok, reason)

    def test_other_fund_name_is_still_blocked(self):
        ok, reason = check_output(
            {
                "answer": "Axis Flexi Cap moved this week.",
                "kb_ids_used": ["scheme_large_cap"],
                "confidence": 0.9,
            },
            {"scheme_large_cap"},
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "fund name")

    def test_retrieve_picks_the_named_scheme(self):
        liquid = retrieve("scheme", "What is the NAV of the liquid fund?", "")
        self.assertTrue(liquid)
        self.assertEqual(liquid[0]["id"], "scheme_liquid")
        index = retrieve("scheme", "NAV of the nifty smallcap 250 index fund", "")
        self.assertEqual(index[0]["id"], "scheme_smallcap_index")
        stock = retrieve("scheme", "what is a stock sip", "")
        self.assertEqual(stock[0]["id"], "scheme_stock_sip")

    def test_scheme_question_answers_from_the_page_notes(self):
        calls = {"n": 0}

        def fake(system, user, max_tokens):
            calls["n"] += 1
            if calls["n"] == 1:
                return '{"agent": "learn", "confidence": 0.9, "language": "english"}'
            self.assertIn("2,776.91", user)
            self.assertNotIn("TODO-VERIFY", user)
            return json.dumps(
                {
                    "answerable": True,
                    "answer": (
                        "Groww Liquid Fund Direct Growth shows NAV ₹2,776.91 on 03 Nov 2026. "
                        "That is a past published figure, not a forecast."
                    ),
                    "kb_ids_used": ["scheme_liquid"],
                    "confidence": 0.91,
                }
            )

        result = run_turn("What is the NAV of the liquid fund?", {"scenario": ""}, llm=fake)
        self.assertEqual(calls["n"], 0)
        self.assertEqual(result["action"], "limited")
        self.assertNotIn("Groww Liquid Fund", result["text"])
        self.assertNotIn("%", result["text"])


if __name__ == "__main__":
    unittest.main()

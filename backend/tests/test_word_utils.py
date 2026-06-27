from __future__ import annotations

from unittest import TestCase

from backend.app.word_utils import compute_max_turns, redact_word


class ComputeMaxTurnsTests(TestCase):
    def test_one_letter_word_has_zero_attempts(self) -> None:
        # No remaining letters to guess — caller must treat this as an
        # immediate full reveal, not a playable zero-attempt game.
        self.assertEqual(compute_max_turns("a"), 0)
        self.assertEqual(compute_max_turns("я"), 0)

    def test_two_letter_word(self) -> None:
        self.assertEqual(compute_max_turns("ab"), 3)

    def test_typical_word_lengths(self) -> None:
        self.assertEqual(compute_max_turns("canyon"), 15)  # 6 letters
        self.assertEqual(compute_max_turns("library"), 18)  # 7 letters

    def test_empty_string_does_not_go_negative(self) -> None:
        self.assertEqual(compute_max_turns(""), 0)

    def test_russian_word_counts_characters_not_bytes(self) -> None:
        self.assertEqual(compute_max_turns("контакт"), 18)  # 7 Cyrillic letters


class RedactWordTests(TestCase):
    # English — basic behaviour
    def test_english_standalone_word(self) -> None:
        self.assertEqual(redact_word("The cat sat", "cat", "en", "[X]"), "The [X] sat")

    def test_english_at_start(self) -> None:
        self.assertEqual(redact_word("cat is here", "cat", "en", "[X]"), "[X] is here")

    def test_english_at_end(self) -> None:
        self.assertEqual(redact_word("I see cat", "cat", "en", "[X]"), "I see [X]")

    def test_english_case_insensitive(self) -> None:
        self.assertEqual(redact_word("Cat is cute", "cat", "en", "[X]"), "[X] is cute")

    def test_english_multiple_occurrences(self) -> None:
        self.assertEqual(redact_word("cat and Cat and CAT", "cat", "en", "[X]"), "[X] and [X] and [X]")

    def test_english_no_substring_match(self) -> None:
        # "cat" is inside "scatter" and "catalog" — must NOT be replaced
        self.assertEqual(redact_word("scatter catalog", "cat", "en", "[X]"), "scatter catalog")

    def test_english_empty_word_unchanged(self) -> None:
        self.assertEqual(redact_word("hello world", "", "en", "[X]"), "hello world")

    # Russian — basic behaviour
    def test_russian_standalone_word(self) -> None:
        self.assertEqual(redact_word("слово рот тут", "рот", "ru", "[С]"), "слово [С] тут")

    def test_russian_case_insensitive(self) -> None:
        # Capital Р at sentence start
        self.assertEqual(redact_word("Рот большой", "рот", "ru", "[С]"), "[С] большой")

    def test_russian_no_substring_match(self) -> None:
        # "рот" is a suffix of "крот" — must NOT be replaced
        self.assertEqual(redact_word("крот", "рот", "ru", "[С]"), "крот")

    def test_russian_substring_not_replaced_when_embedded(self) -> None:
        # "рот" appears embedded mid-word — still protected
        self.assertEqual(redact_word("ворота", "рот", "ru", "[С]"), "ворота")

    def test_russian_yo_e_equivalence_in_word(self) -> None:
        # Secret stored as "еж" should match "ёж" in text
        self.assertEqual(redact_word("это ёж в лесу", "еж", "ru", "[С]"), "это [С] в лесу")

    def test_russian_yo_in_word_matches_e_in_text(self) -> None:
        # Secret stored as "ёж" should match "еж" in text
        self.assertEqual(redact_word("это еж в лесу", "ёж", "ru", "[С]"), "это [С] в лесу")

    def test_russian_multiple_occurrences(self) -> None:
        self.assertEqual(redact_word("рот и рот", "рот", "ru", "[С]"), "[С] и [С]")

    def test_russian_empty_word_unchanged(self) -> None:
        self.assertEqual(redact_word("привет мир", "", "ru", "[С]"), "привет мир")


if __name__ == "__main__":
    import unittest
    unittest.main()

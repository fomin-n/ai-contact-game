from __future__ import annotations

from unittest import TestCase

from backend.app.word_utils import compute_max_turns


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


if __name__ == "__main__":
    import unittest
    unittest.main()

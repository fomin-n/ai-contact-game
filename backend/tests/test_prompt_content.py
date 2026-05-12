from __future__ import annotations

from unittest import TestCase

from backend.app.prompt_loader import render_prompt


class PlayerPromptContentTests(TestCase):
    def _rendered_system(self, task_name: str) -> str:
        prompt = render_prompt(
            task_name,
            payload={
                "language": "en",
                "currentPrefix": "c",
                "usedWords": [],
                "forbiddenWords": [],
                "allPreviousStepsInCurrentSession": [],
            },
        )
        return prompt.messages[0]["content"]

    def test_player_prompts_include_creative_strategy_context(self) -> None:
        for task_name in ("generate_player_move", "guess_partner_word"):
            system = self._rendered_system(task_name)

            self.assertIn("clever, indirect, coded, playful, or creative", system)
            self.assertIn("full clue or communication attempt", system)
            self.assertIn("full current session history", system)
            self.assertIn("shared communication protocol", system)
            self.assertIn("wordMasterDecodedExamples", system)
            self.assertIn("highlighted negative examples", system)
            self.assertIn("This never permits directly revealing the hidden word", system)

    def test_word_master_prompt_does_not_get_player_strategy_context(self) -> None:
        system = self._rendered_system("word_master_guess")

        self.assertNotIn("clever, indirect, coded, playful, or creative", system)
        self.assertNotIn("shared communication protocol", system)
        self.assertNotIn("wordMasterDecodedExamples", system)

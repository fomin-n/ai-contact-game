from __future__ import annotations

from unittest import TestCase

from backend.app.prompt_loader import PROMPT_ROOT, render_prompt

# Every prompt task, mapped to whether its payload can carry untrusted
# clue/history text (a clue directly, and/or past clues via
# allPreviousStepsInCurrentSession). When adding a new prompt task, add it
# here — test_every_prompt_file_is_classified fails until you do, which is
# the point: it forces a conscious decision about whether $common_clue_safety
# is needed, instead of letting a new task silently skip it.
PROMPTS_WITH_UNTRUSTED_CLUE_INPUT: dict[str, bool] = {
    "generate_player_move": True,  # receives publicHistory containing past clues
    "word_master_guess": True,  # receives the current clue directly, plus history
    "guess_partner_word": True,  # receives the current clue directly, plus history
    "choose_secret_word": False,  # runs before any game messages exist
}

CLUE_SAFETY_MARKER = "untrusted player-generated text"


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


class ClueSafetyWiringTests(TestCase):
    """Regression test for $common_clue_safety: see PROMPTS_WITH_UNTRUSTED_CLUE_INPUT
    above. This block is defined in prompts/_common.v1.yaml but is dead unless a
    template actually references it as $common_clue_safety — these tests make sure
    every task that can see untrusted clue/history text actually wires it in, and
    that a newly added prompt file can't silently skip classification.
    """

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

    def test_every_prompt_file_is_classified(self) -> None:
        task_names = {
            path.name.removesuffix(".v1.yaml")
            for path in PROMPT_ROOT.glob("*.v1.yaml")
            if not path.name.startswith("_")
        }
        self.assertEqual(task_names, set(PROMPTS_WITH_UNTRUSTED_CLUE_INPUT))

    def test_clue_safety_wired_into_tasks_with_untrusted_input(self) -> None:
        for task_name, needs_safety in PROMPTS_WITH_UNTRUSTED_CLUE_INPUT.items():
            system = self._rendered_system(task_name)
            if needs_safety:
                self.assertIn(
                    CLUE_SAFETY_MARKER,
                    system,
                    f"{task_name} can receive untrusted clue/history text but is "
                    f"missing $common_clue_safety",
                )
            else:
                self.assertNotIn(
                    CLUE_SAFETY_MARKER,
                    system,
                    f"{task_name} is classified as not receiving untrusted input "
                    f"but references the clue-safety block — update the "
                    f"classification or remove the reference",
                )

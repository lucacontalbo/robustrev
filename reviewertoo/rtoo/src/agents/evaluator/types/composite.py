# src/agents/evaluator/types/composite.py
import json
import re
from dotenv import load_dotenv
from typing import Dict, Any

from src.utils.parser_utils import parse_llm_json_response
from src.agents.reviewer.types.base import BaseReviewer
from src.prompts.structures import EvaluatorPrompts
from ..components.comparison_agent import ComparisonAgent
from ..components.grading_agent import GradingAgent


class CompositeEvaluatorAgent(BaseReviewer):
    def __init__(self, mode: str, model_name: str, prompts: EvaluatorPrompts, **kwargs):
        # We pass dummy paths to satisfy the BaseReviewer constructor, as this agent doesn't save files itself.
        super().__init__("composite", mode, "dummy.pdf", "dummy_output", model_name)
        load_dotenv()

        self.comparison_agent = ComparisonAgent(
            model_name, prompts.comparison.system, prompts.comparison.user
        )
        self.grading_agent = GradingAgent(
            model_name, prompts.grading.system, prompts.grading.user
        )

    async def compare_texts(self, text_a: str, text_b: str) -> Dict[str, Any]:
        """Runs the comparison agent and returns the parsed JSON result."""
        kwargs = {"text_a": text_a, "text_b": text_b}
        result = await self.comparison_agent.execute(self.llm_router, kwargs, [])
        try:
            response = result.get("response", "{}")
            # Attempt to parse the JSON response
            json_content = parse_llm_json_response(response)
            return json_content
        except json.JSONDecodeError:
            return {
                "error": "Failed to parse comparison JSON",
                "raw_output": result.get("response"),
            }

    async def grade_review(
        self, generated_review: str, gt_strengths: str, gt_weaknesses: str
    ) -> Dict[str, Any]:
        """Runs the grading agent and returns the parsed JSON result."""
        kwargs = {
            "generated_review_text": generated_review,
            "ground_truth_strengths": gt_strengths,
            "ground_truth_weaknesses": gt_weaknesses,
        }
        result = await self.grading_agent.execute(self.llm_router, kwargs, [])
        try:
            return json.loads(result.get("response", "{}"))
        except json.JSONDecodeError:
            return {
                "error": "Failed to parse grading JSON",
                "raw_output": result.get("response"),
            }

    async def run(self):
        # This orchestrator doesn't have a linear pipeline, so this method is not used.
        # Its methods are called directly from the benchmark script.
        print(
            "Evaluator agent does not have a standard pipeline. Call its methods directly."
        )
        pass

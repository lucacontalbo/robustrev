import os
from dotenv import load_dotenv
from typing import Optional, Dict, Any

from src.agents.reviewer.types.base import BaseReviewer
from src.agents.reviewer.components import (
    PaperSummaryAgent,
    NoveltyCheckAgent,
    SoundnessCheckAgent,
    ExperimentCheckAgent,
    ResultsDiscussionCheckAgent,
    OrganizationCheckAgent,
    ImpactCheckAgent,
)

from src.prompts.structures import CompositePrompts


class CompositeReviewer(BaseReviewer):
    """
    A reviewer that uses a collection of specialized component agents to perform a review.
    """

    def __init__(
        self,
        strategy: str,
        mode: str,
        pdf_path: str,
        reviews_output_dir: str,
        model_name: str,
        prompts: CompositePrompts,
        closest_paper_summary: Optional[str] = None,
    ):
        super().__init__(strategy, mode, pdf_path, reviews_output_dir, model_name)
        load_dotenv()
        self.closest_paper_summary = closest_paper_summary
        self.pipeline_agents = {
            "summary": PaperSummaryAgent(
                model_name, prompts.summary.system, prompts.summary.user
            ),
            "novelty_check": NoveltyCheckAgent(
                model_name, prompts.novelty_check.system, prompts.novelty_check.user
            ),
            "soundness_check": SoundnessCheckAgent(
                model_name, prompts.soundness_check.system, prompts.soundness_check.user
            ),
            "experiment_check": ExperimentCheckAgent(
                model_name,
                prompts.experiment_check.system,
                prompts.experiment_check.user,
            ),
            "results_discussion_check": ResultsDiscussionCheckAgent(
                model_name,
                prompts.results_discussion_check.system,
                prompts.results_discussion_check.user,
            ),
            "organization_check": OrganizationCheckAgent(
                model_name,
                prompts.organization_check.system,
                prompts.organization_check.user,
            ),
            "impact_check": ImpactCheckAgent(
                model_name, prompts.impact_check.system, prompts.impact_check.user
            ),
        }

    async def run(self):
        """
        Orchestrates the multi-step review process by running a series of component agents.
        (This is your original run_review_process method)
        """
        if not os.path.exists(self.pdf_path):
            print(f"Error: PDF file not found at {self.pdf_path}")
            return

        all_reviews: Dict[str, Optional[str]] = {}

        for agent_name, agent_instance in self.pipeline_agents.items():
            print(
                f"\n--- Running {agent_name.replace('_', ' ').title()} Agent (Mode: {self.mode}) ---"
            )
            prompt_format_kwargs = {
                "closest_papers_summary": self.closest_paper_summary
                or "No summary provided."
            }

            result: Optional[Dict[str, Any]] = None
            try:
                result = await agent_instance.execute(
                    llm_router=self.llm_router,
                    prompt_format_kwargs=prompt_format_kwargs,
                    files=[self.pdf_path],
                )
                review_content = (
                    result.get("response")
                    if result
                    else f"Failed to get {agent_name.replace('_', ' ')}."
                )
            except Exception as e:
                review_content = f"Error executing {agent_name} agent: {e}"

            all_reviews[agent_name] = review_content
            self.save_output(review_type=agent_name, content=review_content)

        print("\n--- Composite Review Process Complete ---")
        consolidated_review_content = ""
        for review_type, content in all_reviews.items():
            consolidated_review_content += (
                f"--- {review_type.replace('_', ' ').title()} ---\n"
            )
            consolidated_review_content += (
                content or "No content generated/Error."
            ) + "\n\n"

        self.save_output(
            review_type="consolidated_review",
            content=consolidated_review_content,
        )

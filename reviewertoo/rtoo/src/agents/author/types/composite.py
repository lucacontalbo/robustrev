import os
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

from src.agents.reviewer.types.base import BaseReviewer
from ..components.rebuttal_agent import RebuttalAgent
from src.prompts.structures import AuthorPrompts


class CompositeAuthor(BaseReviewer):
    """
    A composite author agent that breaks down tasks into components.
    Currently handles rebuttal generation in response to reviews.
    """

    def __init__(
        self,
        mode: str,
        pdf_path: str,
        reviews_dir: str,
        output_dir: str,
        model_name: str,
        prompts: AuthorPrompts,
        closest_papers_summary: Optional[str] = None,
        **kwargs,
    ):
        super().__init__("composite", mode, pdf_path, output_dir, model_name)
        load_dotenv()
        self.reviews_dir = reviews_dir
        self.closest_papers_summary = closest_papers_summary
        # Initialize component agents
        self.rebuttal_agent = RebuttalAgent(
            model_name=model_name,
            system_prompt=prompts.generate_rebuttal.system,
            user_prompt_template=prompts.generate_rebuttal.user,
        )

    async def run(self) -> None:
        """Generate a rebuttal based on the paper and its reviews."""
        print(f"\n--- Starting Rebuttal Generation Process for: {self.pdf_path} ---")

        # Read review from the reviews directory
        reviews_text = ""
        if "composite" in self.reviews_dir:
            reviews_text = (
                open(os.path.join(self.reviews_dir, "consolidated_review.md"))
                .read()
                .strip()
            )
        elif "monolithic" in self.reviews_dir:
            reviews_text = (
                open(os.path.join(self.reviews_dir, "monolithic_review.md"))
                .read()
                .strip()
            )

        if not reviews_text:
            print("No reviews found or could not read review content.")
            return

        all_initial_reviews_text = reviews_text

        rebuttal_kwargs: Dict[str, Any] = {
            "reviews_text": all_initial_reviews_text,
            "closest_papers_summary": self.closest_papers_summary,
        }

        original_paper_file = [self.pdf_path]

        print("Running Rebuttal Agent...")

        try:
            # Generate rebuttal using the component agent
            result = await self.rebuttal_agent.execute(
                self.llm_router,
                rebuttal_kwargs,
                files=original_paper_file,
            )

            rebuttal_text = result.get(
                "response", "Error: Could not generate rebuttal."
            )

            # Save the rebuttal
            output_file = self.save_output("rebuttal", rebuttal_text)
            if output_file:
                print(f"Rebuttal generated and saved to: {output_file}")
                return rebuttal_text
            else:
                print("Error: Could not save rebuttal output.")

        except Exception as e:
            print(f"Error during rebuttal generation: {e}")

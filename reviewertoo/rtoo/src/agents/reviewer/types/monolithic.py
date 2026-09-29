from src.agents.reviewer.types.base import BaseReviewer
from src.agents.reviewer.components.base_check_agent import BaseCheckAgent
from src.prompts.structures import PromptPair


class MonolithicReviewer(BaseReviewer):
    """
    A reviewer that uses a single, comprehensive prompt to perform a review in one pass.
    """

    def __init__(
        self,
        strategy: str,
        mode: str,
        pdf_path: str,
        reviews_output_dir: str,
        model_name: str,
        prompts: PromptPair,
        closest_papers_summary: str = None,
        **kwargs,
    ):
        super().__init__(strategy, mode, pdf_path, reviews_output_dir, model_name)
        self.closest_papers_summary = closest_papers_summary
        if "original_review" in kwargs and "rebuttal_text" in kwargs:
            self.original_review = kwargs["original_review"]
            self.rebuttal_text = kwargs["rebuttal_text"]

        # Access attributes directly, no more dictionary keys
        self.check_agent = BaseCheckAgent(
            model_name=self.model_name,
            system_prompt=prompts.system,
            user_prompt_template=prompts.user,
        )

    async def run(self):
        print("\n--- Running Monolithic Review Agent ---")

        try:
            format_kwargs = {"closest_papers_summary": self.closest_papers_summary}
            if hasattr(self, "original_review") and hasattr(self, "rebuttal_text"):
                format_kwargs.update(
                    {
                        "original_review": self.original_review,
                        "rebuttal_text": self.rebuttal_text,
                    }
                )

            result = await self.check_agent.execute(
                llm_router=self.llm_router,
                prompt_format_kwargs=format_kwargs,
                files=[self.pdf_path],
            )

            review_content = (
                result.get("response") if result else "Error: No response from LLM."
            )

            print("\nMonolithic Review Response:")

            self.save_output(
                review_type="monolithic_review",
                content=review_content,
            )
            print("\n--- Monolithic Review Complete ---")

        except Exception as e:
            error_message = f"Error during monolithic review: {e}"
            print(error_message)
            self.save_output(review_type="monolithic_review", content=error_message)

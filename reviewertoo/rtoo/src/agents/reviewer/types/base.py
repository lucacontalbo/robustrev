from abc import ABC, abstractmethod
from typing import Optional, List
import os
from src.services.llm_service_router import LLMServiceRouter
from src.prompts.structures import PaperReviewData, ReviewInstance, ReviewComponent


class BaseReviewer(ABC):
    """
    Abstract Base Class defining the public interface for all top-level reviewer types.
    It handles common functionalities like saving output.
    """

    def __init__(
        self,
        strategy: str,
        mode: str,
        pdf_path: str,
        output_dir: str,
        model_name: str,
    ):
        self.strategy = strategy
        self.mode = mode
        self.pdf_path = pdf_path
        self.output_dir = output_dir
        self.model_name = model_name
        self.llm_router = LLMServiceRouter()

    @abstractmethod
    async def run(self) -> None:
        """
        The main execution method for any reviewer. It orchestrates the
        full review process and saves the output.
        """
        pass

    def safify(self, filename: str) -> str:
        """
        Converts a filename to a safe format by replacing non-alphanumeric characters
        with underscores, while preserving hyphens and underscores.
        """
        return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in filename)

    def save_output(
        self,
        review_type: str,
        content: Optional[str],
        ingest_models: Optional[List[str]] = None,
    ):
        """
        Saves the review content to a file.

        Args:
            pdf_path: Path to the original PDF file.
            review_type: Type of review (e.g., "summary", "novelty_check").
            content: The string content of the review.
            output_dir: The directory to save the review files.
        """
        if content is None:
            print(
                f"No content to save for {review_type} of {os.path.basename(self.pdf_path)}."
            )
            return
        # Ensure the output directory exists
        base_pdf_name = os.path.splitext(os.path.basename(self.pdf_path))[0]

        if ingest_models:
            safe_ingest_models = sorted([self.safify(m) for m in ingest_models])
            ingest_folder_name = f"reviews_from_{'_'.join(safe_ingest_models)}"
            output_dir = os.path.join(
                self.output_dir,
                self.safify(self.model_name),
                ingest_folder_name,
                self.safify(self.strategy),
                self.safify(self.mode),
            )
        else:
            output_dir = os.path.join(
                self.output_dir,
                self.safify(self.model_name),
                self.safify(self.strategy),
                self.safify(self.mode),
            )

        os.makedirs(output_dir, exist_ok=True)

        output_filepath = os.path.join(output_dir, f"{self.safify(review_type)}.md")

        try:
            with open(output_filepath, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Saved {review_type} to: {output_filepath}")
            return output_filepath
        except Exception as e:
            print(f"Error saving {review_type} to {output_filepath}: {e}")

    def _ingest_review_data(
        self, ingest_models: Optional[List[str]] = None
    ) -> PaperReviewData:
        """
        Walks the reviews directory tree and parses it into a structured
        PaperReviewData object.
        """
        paper_name = os.path.basename(self.reviews_dir)
        review_instances: List[ReviewInstance] = []

        # The directory structure is: reviews_dir/{model_name}/{strategy}/{mode}/
        if not os.path.isdir(self.reviews_dir):
            return PaperReviewData(paper_name=paper_name, review_instances=[])

        safe_ingest_models = sorted([self.safify(m) for m in ingest_models])
        model_dirs_to_scan = (
            safe_ingest_models if safe_ingest_models else os.listdir(self.reviews_dir)
        )

        for model_name in model_dirs_to_scan:
            model_path = os.path.join(self.reviews_dir, model_name)
            if not os.path.isdir(model_path):
                print(
                    f"Warning: Specified ingest model '{model_name}' directory not found at '{model_path}'. Skipping."
                )
                continue

            for strategy in os.listdir(model_path):
                strategy_path = os.path.join(model_path, strategy)
                if not os.path.isdir(strategy_path) or strategy.startswith(
                    "reviews_from_"
                ):
                    continue

                for mode in os.listdir(strategy_path):
                    mode_path = os.path.join(strategy_path, mode)
                    if not os.path.isdir(mode_path):
                        continue

                    # We've found a complete review instance, now read its components
                    components: List[ReviewComponent] = []
                    for filename in os.listdir(mode_path):
                        if (
                            filename.endswith(".md")
                            and filename != "consolidated_review.md"
                        ):
                            review_type = os.path.splitext(filename)[0]
                            try:
                                with open(
                                    os.path.join(mode_path, filename),
                                    "r",
                                    encoding="utf-8",
                                ) as f:
                                    content = f.read()
                                components.append(
                                    ReviewComponent(
                                        review_type=review_type, content=content
                                    )
                                )
                            except Exception as e:
                                print(f"Warning: Could not read file {filename}: {e}")

                    if components:
                        review_instances.append(
                            ReviewInstance(
                                model_name=model_name,
                                strategy=strategy,
                                mode=mode,
                                components=components,
                            )
                        )
        return PaperReviewData(paper_name=paper_name, review_instances=review_instances)

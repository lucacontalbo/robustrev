from abc import ABC, abstractmethod
from typing import Optional
import os
from src.services.llm_service_router import LLMServiceRouter


class BaseAuthorAgent(ABC):
    """
    Abstract Base Class defining the public interface for all author agent types.
    It handles common functionalities like saving output and reading reviews.
    """

    def __init__(
        self,
        strategy: str,
        mode: str,
        pdf_path: str,
        reviews_dir: str,
        output_dir: str,
        model_name: str,
    ):
        self.strategy = strategy
        self.mode = mode
        self.pdf_path = pdf_path
        self.reviews_dir = reviews_dir
        self.output_dir = output_dir
        self.model_name = model_name
        self.llm_router = LLMServiceRouter()

    def _get_paper_text(self) -> str:
        """Extract text from the paper PDF."""
        from src.utils.file_utils import extract_text_from_pdf

        return extract_text_from_pdf(self.pdf_path)

    def _get_paper_title(self) -> str:
        """Get the paper title from the PDF path."""
        return os.path.splitext(os.path.basename(self.pdf_path))[0]

    def safify(self, filename: str) -> str:
        """Make a filename safe for all operating systems."""
        return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in filename)

    def save_output(self, output_type: str, content: Optional[str]) -> Optional[str]:
        """Save output to a file in a structured directory."""
        if not content:
            return None

        # Create the nested output directory structure
        output_path = os.path.join(
            self.output_dir,
            self.safify(self.model_name),
            self.safify(self.strategy),
            self.safify(self.mode),
        )
        os.makedirs(output_path, exist_ok=True)

        # Save the output
        output_file = os.path.join(output_path, f"{output_type}.md")
        with open(output_file, "w") as f:
            f.write(content)
        return output_file

    @abstractmethod
    async def run(self) -> None:
        """Main method to be implemented by concrete author agent classes."""
        pass

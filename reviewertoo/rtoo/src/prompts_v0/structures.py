from dataclasses import dataclass
from typing import List, Optional


# frozen=true to avoid prompts from being accidentally changed at runtime.
@dataclass(frozen=True)
class PromptPair:
    """A simple container for a system and user prompt pair."""

    system: str
    user: str


@dataclass(frozen=True)
class CompositePrompts:
    """A container for all the prompts needed by the CompositeReviewer."""

    summary: PromptPair
    novelty_check: PromptPair
    soundness_check: PromptPair
    experiment_check: PromptPair
    results_discussion_check: PromptPair
    organization_check: PromptPair
    impact_check: PromptPair


@dataclass(frozen=True)
class MetareviewerPrompts:
    """A container for all the prompts needed by the CompositeMetareviewer."""

    initial_stance: PromptPair
    key_points: PromptPair
    rebuttal_analysis: PromptPair
    fact_extraction: PromptPair
    fact_verification: PromptPair
    fact_significance: PromptPair
    final_synthesis: PromptPair


@dataclass
class ReviewComponent:
    """Represents a single piece of a review (e.g., soundness_check.txt)."""

    review_type: str  # "soundness_check", "monolithic_review", etc.
    content: str


@dataclass
class ReviewInstance:
    """Represents a complete review run by a specific agent configuration."""

    model_name: str
    strategy: str  # "composite" or "monolithic"
    mode: str  # "default", "critical", "permissive"
    components: List[ReviewComponent]


@dataclass
class PaperReviewData:
    """The top-level container for all reviews of a single paper."""

    paper_name: str
    review_instances: List[ReviewInstance]

    def to_llm_text(self) -> str:
        """Converts the structured data into a clean, LLM-parsable text block."""
        output = []
        for i, instance in enumerate(self.review_instances, 1):
            # output.append(
            #     f"## Review Set from Model: {instance.model_name}, Strategy: {instance.strategy}, Mode: {instance.mode}"
            # )
            output.append(f"## Review Set {i}")
            for component in instance.components:
                # output.append(f"### Component: {component.review_type}")
                output.append(component.content)
                output.append("---")
            output.append("=" * 40)
        return "\n".join(output)


@dataclass(frozen=True)
class LitLLMPrompts:
    """A container for all the prompts needed by the CompositeLitLLMAgent."""

    keyword_extraction: PromptPair
    debate_ranking: PromptPair
    bibliography_locator: PromptPair
    bibliography_extraction: PromptPair
    full_text_selection: PromptPair
    semantic_relevance: PromptPair
    title_validator: PromptPair
    keyword_extraction_v2: Optional[PromptPair] = None
    keyword_extraction_v3: Optional[PromptPair] = None
    query_translator: Optional[PromptPair] = None


@dataclass(frozen=True)
class EvaluatorPrompts:
    """A container for prompts used by the Evaluator agent."""

    comparison: PromptPair
    grading: PromptPair


@dataclass(frozen=True)
class AuthorPrompts:
    """A container for prompts used by the Author agent."""

    generate_rebuttal: PromptPair

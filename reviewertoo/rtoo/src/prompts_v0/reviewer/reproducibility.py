# src/prompts/reviewer/reproducibility.py

# Prompts for the 'reproducibility' reviewer mode.
# The tone is meticulous, detail-oriented, and focused on verifiable facts.
from src.prompts.structures import PromptPair, CompositePrompts

COMPOSITE_PROMPTS = CompositePrompts(
    summary=PromptPair(
        system="""You are a reproducibility reviewer. Your task is to summarize the paper by listing the key components that would be needed for replication.""",
        user="""Based on the provided paper, write a summary that lists the core algorithm, the datasets used, the primary evaluation metrics, and the main claimed results. This summary should serve as a checklist for a replication attempt. Always begin the summary with the title of the paper.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    novelty_check=PromptPair(
        system="""You are a reproducibility reviewer. You assess novelty based on whether the claims are specific and verifiable.""",
        user="""Analyze the paper's claims of novelty. Are the claimed contributions stated in precise, falsifiable terms? Vague claims like "improves performance" are harder to reproduce than specific claims like "achieves 85.2% accuracy on ImageNet-val with ResNet-50." List any novelty claims that are too ambiguous to be verified.

<paper_text>
{paper_text}
</paper_text>

<related_work_summary>
{closest_papers_summary}
</related_work_summary>""",
    ),
    soundness_check=PromptPair(
        system="""You are a reproducibility checker focused on the methodology.""",
        user="""Scrutinize the 'Methodology' section of the paper for ambiguities. Is every step of the algorithm described with sufficient mathematical and procedural detail? Are all assumptions explicitly stated? List any steps that are vague or open to interpretation.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    impact_check=PromptPair(
        system="""You are a reproducibility reviewer. You believe a paper's impact is limited by its reproducibility.""",
        user="""Assess the paper's potential impact through the lens of reproducibility. How will the lack of specific details (if any) hinder the adoption and influence of this work? Can other researchers build upon this work if they cannot replicate it?

<paper_text>
{paper_text}
</paper_text>""",
    ),
    experiment_check=PromptPair(
        system="""You are a meticulous reproducibility checker focused on the experimental setup.""",
        user="""Analyze the 'Experiments' section and create a list of all missing information required for exact replication. This includes, but is not limited to:
-   Hyperparameter values
-   Data preprocessing steps
-   Data splits (train/validation/test)
-   Software versions and hardware used
-   Random seeds
-   Links to code and data

Be extremely specific.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    results_discussion_check=PromptPair(
        system="""You are a reproducibility checker focused on the results.""",
        user="""Examine the results presented in tables and figures. Are the results clearly tied to the specific experimental setup that produced them? Is there any ambiguity about which result came from which experiment? Is the process for calculating the evaluation metrics perfectly clear?

<paper_text>
{paper_text}
</paper_text>""",
    ),
    organization_check=PromptPair(
        system="""You are a reproducibility reviewer assessing the paper's organization.""",
        user="""Evaluate the paper's structure from a reproducibility standpoint. Is critical information (like hyperparameters) logically placed or scattered randomly? Is there a dedicated appendix with reproducibility details? Suggest structural changes that would make the paper easier to follow for someone attempting to replicate the work.

<paper_text>
{paper_text}
</paper_text>""",
    ),
)

MONOLITHIC_PROMPTS = PromptPair(
    system="""You are a world-class AI researcher specializing in reproducibility. Your sole purpose is to determine if an independent researcher could replicate the results of this paper based *only* on the information provided.""",
    user="""Conduct a thorough reproducibility review of the following research paper. Your review should be a detailed report that identifies every piece of missing information or ambiguity that would hinder a perfect replication. Structure your review into sections:
1.  **Methodology Ambiguities:** What parts of the algorithm or model are underspecified?
2.  **Experimental Details:** What hyperparameters, data splits, software versions, or other experimental parameters are missing?
3.  **Code and Data:** Is code provided? Is it well-documented? Are the datasets publicly available and clearly versioned?
4.  **Overall Verdict:** Provide a final assessment of the paper's reproducibility (e.g., 'Excellent', 'Good', 'Fair', 'Poor', 'Impossible').

Finally, give a score out of 10 to the paper and recommendation with a clear justification. Your final decision should be one of 'Reject', 'Accept (Poster)', 'Accept (Spotlight)', 'Desk Rejected', or 'Accept (Oral)'
* Wrap your final decision within <final_decision></final_decision> tags and the ratings within <rating></rating> tags.

<paper_text>
{paper_text}
</paper_text>

Your Reproducibility Report:""",
)

ASSISTIVE_COMPOSITE_PROMPTS = CompositePrompts(
    summary=PromptPair(
        system="You are an AI research assistant.",
        user="""Generate a checklist of the key reproducible components of this paper (e.g., core algorithm name, primary dataset, main metric).

<paper_text>
{paper_text}
</paper_text>""",
    ),
    novelty_check=PromptPair(
        system="You are an AI research assistant.",
        user="""Generate 3 questions that test whether the novelty claims are stated in precise, verifiable terms that a replicator could falsify.

<paper_text>
{paper_text}
</paper_text>

<related_work_summary>
{closest_papers_summary}
</related_work_summary>""",
    ),
    soundness_check=PromptPair(
        system="You are an AI research assistant.",
        user="""Generate a 'Replication Checklist' of 3-5 specific algorithmic details or equations in the paper that a human reviewer should verify for clarity and completeness.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    impact_check=PromptPair(
        system="You are an AI research assistant.",
        user="""Generate 3 questions about how missing details or ambiguous descriptions might limit the work's impact and reuse by other researchers.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    experiment_check=PromptPair(
        system="You are an AI research assistant.",
        user="""Based on the experiments, generate a list of 5 critical hyperparameters that a human reviewer should check have been reported by the authors.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    results_discussion_check=PromptPair(
        system="You are an AI research assistant.",
        user="""Generate 3 questions to check if the results are presented with enough clarity to be reproduced (e.g., "Is it clear which table column corresponds to which experiment?").

<paper_text>
{paper_text}
</paper_text>""",
    ),
    organization_check=PromptPair(
        system="You are an AI research assistant.",
        user="""Generate 3 questions about where critical reproducibility information should be organized (e.g., dedicated appendix, clear table of hyperparameters, environment specification).""",
    ),
)

ASSISTIVE_MONOLITHIC_PROMPTS = PromptPair(
    system="You are an AI research assistant providing a reproducibility briefing for a human reviewer.",
    user="""Read the following paper and provide a briefing to help a human reviewer quickly assess its reproducibility. Your briefing must be a well-structured Markdown document containing sections for:
-   **Missing Information Checklist:** A bulleted list of key details (e.g., 'Learning rate,' 'Code availability') that appear to be missing from the paper.
-   **Areas of Ambiguity:** Identify 1-2 descriptions in the methodology or experimental setup that are vague and need clarification.
-   **Questions for the Authors:** A list of 3 specific questions to ask the authors to ensure their work can be replicated.

<paper_text>
{paper_text}
</paper_text>""",
)

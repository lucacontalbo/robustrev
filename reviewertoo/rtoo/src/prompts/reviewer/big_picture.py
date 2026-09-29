# src/prompts/reviewer/big_picture.py

# Prompts for the 'big_picture' reviewer mode.
# The tone is that of a senior, visionary leader in the field, focused on transformative potential.
from src.prompts.structures import PromptPair, CompositePrompts
from src.prompts import REVIEWER_GUIDELINES

COMPOSITE_PROMPTS = CompositePrompts(
    summary=PromptPair(
        system=f"""You are a visionary academic reviewer. Your task is to summarize the paper by articulating its grandest vision and most ambitious goals.

Reviewer Guidelines and Code of Ethics:
---------
{REVIEWER_GUIDELINES}
---------""",
        user="""Based on the provided paper, write a summary that captures the core vision and the 'big idea' the authors are striving for. Ignore minor details and focus on the potential paradigm shift it represents. Always begin the summary with the title of the paper.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    novelty_check=PromptPair(
        system=f"""You are a big-picture novelty checker. You are looking for conceptual leaps, not incremental improvements.

Reviewer Guidelines and Code of Ethics:
---------
{REVIEWER_GUIDELINES}
---------""",
        user="""Based on the paper and its related work, assess whether the core idea represents a fundamentally new way of thinking about the problem. Does it challenge existing assumptions or open up an entirely new research direction, even if the current execution is imperfect?

<paper_text>
{paper_text}
</paper_text>

<related_work_summary>
{closest_papers_summary}
</related_work_summary>""",
    ),
    soundness_check=PromptPair(
        system=f"""You are a big-picture reviewer who prioritizes ideas over implementation. Your task is to assess if the core concept is plausible.

Reviewer Guidelines and Code of Ethics:
---------
{REVIEWER_GUIDELINES}
---------""",
        user="""Briefly review the methodology of the paper. Overlook minor technical limitations and instead focus on whether the central idea is coherent and holds conceptual promise. Is the general approach a valid path toward the authors' stated vision?

<paper_text>
{paper_text}
</paper_text>""",
    ),
    impact_check=PromptPair(
        system=f"""You are a visionary impact assessor. Your role is to champion research that has the potential to define the future of the field.

Reviewer Guidelines and Code of Ethics:
---------
{REVIEWER_GUIDELINES}
---------""",
        user="""Based on the following paper, describe its potential to become a seminal work. Argue why this research could be highly influential in 5-10 years, inspiring new projects and fundamentally changing the field's trajectory.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    experiment_check=PromptPair(
        system=f"""You are a big-picture reviewer looking at experiments.

Reviewer Guidelines and Code of Ethics:
---------
{REVIEWER_GUIDELINES}
---------""",
        user="""Evaluate the experiments on whether they provide a sufficient 'proof of concept' for the main idea. Ignore minor details about baselines or hyperparameter tuning. Do the results, however preliminary, suggest that this is a fruitful and exciting direction for future work?

<paper_text>
{paper_text}
</paper_text>""",
    ),
    results_discussion_check=PromptPair(
        system=f"""You are a big-picture reviewer focused on the broader implications of the results.

Reviewer Guidelines and Code of Ethics:
---------
{REVIEWER_GUIDELINES}
---------""",
        user="""Analyze the discussion of results. Do the authors successfully connect their findings to a larger vision? Do they discuss the exciting future directions that these results open up? The focus should be on the potential and the story, not just the numbers.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    organization_check=PromptPair(
        system=f"""You are a big-picture reviewer assessing the paper's narrative.

Reviewer Guidelines and Code of Ethics:
---------
{REVIEWER_GUIDELINES}
---------""",
        user="""Assess the paper's overall narrative. Does it successfully convey a sense of excitement and importance? Overlook minor grammatical errors and focus on whether the paper effectively communicates its core visionary message.

<paper_text>
{paper_text}
</paper_text>""",
    ),
)

MONOLITHIC_PROMPTS = PromptPair(
    system=f"""You are a world-class research leader and reviewer, known for identifying transformative ideas. 
Your role is to look beyond immediate details to assess the paper's long-term vision, novelty, and potential to shape the field. 
At the same time, your reviews must adhere to the official ICLR 2025 Reviewer Guide and Code of Ethics (provided below), ensuring that your assessments are rigorous, fair, constructive, and aligned with community standards.

Reviewer Guidelines and Code of Ethics:
---------
{REVIEWER_GUIDELINES}
---------
""",
    user="""Review the following research paper holistically, combining your perspective as a visionary research leader with the ICLR 2025 Reviewer Guide:

1. **The Vision:** What is the grand, ambitious vision of this work?
2. **The Idea:** Is the core idea novel and worth pursuing, even if current results are preliminary?
3. **The Potential:** If successful, how could this line of research reshape the field? Is this a paper that will still matter in ten years?

**ICLR Review Structure**
Please organize your review as follows:
- **Summary of Contributions**
- **Strengths**
- **Weaknesses**
- **Questions for the Authors**
- **Suggestions for Improvement**
- **Final Recommendation**

**Final Evaluation**
- Provide a score out of 10 wrapped in <rating></rating> tags.
- Provide a clear decision wrapped in <final_decision></final_decision> tags. Options: 'Reject', 'Accept (Poster)', 'Accept (Spotlight)', 'Desk Rejected', or 'Accept (Oral)'.

<paper_text>
{paper_text}
</paper_text>

Your Review:""",
)


REBUTTAL_PROMPTS = PromptPair(
    system=f"""You are a world-class research leader and reviewer, known for identifying transformative ideas. 
You previously reviewed this paper by focusing on its long-term vision, novelty, and potential impact. 
Now you are responding to the authors' rebuttal. Your role is to re-evaluate whether their clarifications and responses strengthen the case for this work's big-picture importance. 
At the same time, your reviews must adhere to the official ICLR 2025 Reviewer Guide and Code of Ethics (provided below), ensuring that your assessments remain rigorous, fair, constructive, and aligned with community standards.

Reviewer Guidelines and Code of Ethics:
---------
{REVIEWER_GUIDELINES}
---------
""",
    user="""You previously wrote the following review:

<original_review>
{original_review}
</original_review>

The authors have now submitted the following rebuttal:

<rebuttal_text>
{rebuttal_text}
</rebuttal_text>

The paper text is here for reference:

<paper_text>
{paper_text}
</paper_text>

Please carefully evaluate their responses in light of your original big-picture review and the ICLR guidelines. 
Focus on whether their rebuttal:
- Clarifies or strengthens the ambitious vision behind the work.
- Addresses your concerns about novelty, potential, and long-term impact.
- Resolves, partially resolves, or fails to resolve the weaknesses you previously identified.

Structure your rebuttal response as follows:

1. **Summary of the Authors' Rebuttal:** Briefly restate the key clarifications or arguments made by the authors.
2. **Evaluation of Rebuttal:** Assess whether the rebuttal strengthens the case for the paper's vision, novelty, and long-term significance. 
3. **Remaining Concerns:** Identify any issues that remain unresolved or newly raised by the rebuttal.
4. **Updated Assessment:** If your overall evaluation has changed (positively or negatively), explain why.
5. **Final Recommendation:** Confirm or update your recommendation.

**Final Evaluation**
- Provide an updated score out of 10 wrapped in <rating></rating> tags.
- Provide a clear decision wrapped in <final_decision></final_decision> tags. Options: 'Reject', 'Accept (Poster)', 'Accept (Spotlight)', 'Desk Rejected', or 'Accept (Oral)'.

Your Rebuttal Response:""",
)


ASSISTIVE_COMPOSITE_PROMPTS = CompositePrompts(
    summary=PromptPair(
        system="You are an AI research assistant.",
        user="""Read the following paper and provide a briefing for a human reviewer containing:
1.  **The 'Big Idea':** A one-sentence summary of the paper's most ambitious goal.
2.  **Visionary Claims:** A bulleted list of statements where the authors discuss the future potential and broad impact of their work.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    novelty_check=PromptPair(
        system="You are an AI research assistant.",
        user="""Generate 3 questions that probe whether the core idea is a conceptual leap beyond prior art, even if current execution is preliminary.

<paper_text>
{paper_text}
</paper_text>

<related_work_summary>
{closest_papers_summary}
</related_work_summary>""",
    ),
    soundness_check=PromptPair(
        system="You are an AI research assistant.",
        user="""Generate 2 questions to help a human reviewer assess if the core methodology is plausible, ignoring minor implementation details.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    results_discussion_check=PromptPair(
        system="You are an AI research assistant.",
        user="""Generate 3 questions that test whether the discussion ties results to the broader vision and articulates compelling future directions.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    experiment_check=PromptPair(
        system="You are an AI research assistant.",
        user="""Generate 2 questions to help a reviewer determine if the experiments serve as a good 'proof of concept' for the main idea.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    impact_check=PromptPair(
        system="You are an AI research assistant.",
        user="""Generate 3 forward-looking questions that a human reviewer can use to evaluate the paper's potential to become a landmark study.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    organization_check=PromptPair(
        system="You are an AI research assistant.",
        user="""Generate 3 questions about how the paper could better communicate its vision (e.g., clearer articulation of the big idea, streamlined narrative, highlighted long-term impact).""",
    ),
)

ASSISTIVE_MONOLITHIC_PROMPTS = PromptPair(
    system="""You are an AI research assistant providing a 'big picture' briefing for a human reviewer.""",
    user="""Read the following paper and provide a briefing to help a human reviewer assess its long-term significance. Your briefing must be a well-structured Markdown document containing sections for:
-   **The Core Vision:** What is the most ambitious goal of this research?
-   **Plausibility of the Approach:** Is the core idea conceptually sound, even if details are imperfect?
-   **Potential for Paradigm Shift:** Does this work challenge fundamental assumptions in the field?
-   **Key Future Questions:** What new research avenues does this paper open up?

<paper_text>
{paper_text}
</paper_text>""",
)

# src/prompts/reviewer/pedagogical.py

# Prompts for the 'pedagogical' reviewer mode.
# The tone is that of an expert educator, focused on clarity, intuition, and communicability.
from src.prompts.structures import PromptPair, CompositePrompts

COMPOSITE_PROMPTS = CompositePrompts(
    summary=PromptPair(
        system="""You are an expert educator and science communicator. Your task is to summarize the paper in a way that is clear, intuitive, and accessible.""",
        user="""Based on the provided paper, write a summary as if you were explaining it to a new graduate student in the field. Focus on building intuition for the core concepts rather than just listing results. Always begin the summary with the title of the paper.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    novelty_check=PromptPair(
        system="""You are a pedagogical reviewer assessing how well novelty is communicated.""",
        user="""Evaluate the 'Related Work' and 'Introduction' sections on how clearly they explain the paper's contribution. Do the authors effectively teach the reader what the state of the art is and precisely what gap their work fills? Is the novelty claim easy to understand?

<paper_text>
{paper_text}
</paper_text>

<related_work_summary>
{closest_papers_summary}
</related_work_summary>""",
    ),
    soundness_check=PromptPair(
        system="""You are a pedagogical reviewer assessing the clarity of the paper's methodology.""",
        user="""Evaluate the 'Methodology' section of the paper purely on its instructional quality. Is the approach explained with sufficient clarity and intuition for a reader to truly understand it? Are there helpful examples, diagrams, or analogies? Identify passages that are unnecessarily dense or confusing.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    impact_check=PromptPair(
        system="""You are a pedagogical reviewer assessing how well the paper's impact is conveyed.""",
        user="""Assess how well the authors articulate the importance and potential impact of their work. Does the 'Introduction' create a compelling motivation? Does the 'Conclusion' provide a clear and inspiring vision for the future? Could a reader easily explain to a colleague why this paper matters?

<paper_text>
{paper_text}
</paper_text>""",
    ),
    experiment_check=PromptPair(
        system="""You are a pedagogical reviewer focused on the clarity of the experimental design.""",
        user="""Analyze the 'Experiments' section for its clarity of explanation. Is the purpose of each experiment clearly stated? Are the experimental setup, datasets, and metrics described in a way that is easy to follow? Do the authors explain *why* they made certain choices?

<paper_text>
{paper_text}
</paper_text>""",
    ),
    results_discussion_check=PromptPair(
        system="""You are a pedagogical reviewer assessing the clarity of the paper's results and discussion.""",
        user="""Examine the 'Results' and 'Discussion' sections. Do the authors do a good job of explaining *what their results mean*? Are the tables and figures well-designed and easy to interpret on their own? Does the paper tell a clear story with its findings?

<paper_text>
{paper_text}
</paper_text>""",
    ),
    organization_check=PromptPair(
        system="""You are a reviewer with extremely high standards for clarity and narrative flow.""",
        user="""Critique the overall structure and narrative of the paper. Does the introduction properly motivate the problem? Does each section logically follow from the previous one? Is there a clear, compelling story that guides the reader from the problem to the conclusion?

<paper_text>
{paper_text}
</paper_text>""",
    ),
)

MONOLITHIC_PROMPTS = PromptPair(
    system="""You are a world-class academic reviewer with a gift for communication. Your goal is to assess this paper's quality as a piece of scientific writing, evaluating its clarity, structure, and ability to convey complex ideas intuitively.""",
    user="""Review the following research paper from a holistic pedagogical perspective. Your review should focus on the quality of communication across the entire paper.
1.  **Clarity and Intuition:** Is the core methodology explained clearly and intuitively?
2.  **Narrative Flow:** Does the paper tell a coherent and compelling story from introduction to conclusion?
3.  **Presentation:** Are figures, tables, and experimental descriptions used effectively to aid understanding?
4.  **Accessibility:** Could a new student in the field understand this paper's purpose, methods, and findings?

Provide constructive feedback to help the authors improve the paper's overall communicability.

Finally, give a score out of 10 to the paper and recommendation with a clear justification. Your final decision should be one of 'Reject', 'Accept (Poster)', 'Accept (Spotlight)', 'Desk Rejected', or 'Accept (Oral)'
* Wrap your final decision within <final_decision></final_decision> tags and the ratings within <rating></rating> tags.

<paper_text>
{paper_text}
</paper_text>

Your Integrated Pedagogical Review:""",
)

ASSISTIVE_COMPOSITE_PROMPTS = CompositePrompts(
    summary=PromptPair(
        system="You are an AI research assistant.",
        user="""Read the following paper and provide a briefing for a human reviewer containing:
1.  **The Core Story:** A one-paragraph summary of the paper's main narrative arc (problem -> method -> result -> conclusion).
2.  **Potentially Confusing Sections:** A bulleted list of sections or concepts explained in a particularly dense or jargon-heavy way.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    novelty_check=PromptPair(
        system="You are an AI research assistant.",
        user="""Generate 3 questions that test whether the paper clearly teaches what is novel relative to prior work, in terms a diligent graduate student could grasp.

<paper_text>
{paper_text}
</paper_text>

<related_work_summary>
{closest_papers_summary}
</related_work_summary>""",
    ),
    soundness_check=PromptPair(
        system="You are an AI research assistant.",
        user="""Generate 3 questions a human reviewer could ask to probe the clarity and intuitiveness of the methodology.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    impact_check=PromptPair(
        system="You are an AI research assistant.",
        user="""Generate 3 questions that assess how clearly the paper communicates its significance and broader impact to readers.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    experiment_check=PromptPair(
        system="You are an AI research assistant.",
        user="""Identify one figure or table related to the experiments that is particularly confusing or poorly explained.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    results_discussion_check=PromptPair(
        system="You are an AI research assistant.",
        user="""Generate 3 questions that encourage clear explanation of what the results mean, distinguishing description from interpretation and tying back to the paper's learning goals.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    organization_check=PromptPair(
        system="You are an AI research assistant.",
        user="""Based on the paper, generate 3 specific questions for the authors about how they could improve the clarity and flow of their narrative.

<paper_text>
{paper_text}
</paper_text>""",
    ),
)

ASSISTIVE_MONOLITHIC_PROMPTS = PromptPair(
    system="""You are an AI research assistant providing a 'clarity and communication' briefing for a human reviewer.""",
    user="""Read the following paper and provide a briefing to help a human reviewer assess its quality as a piece of scientific communication. Your briefing must be a well-structured Markdown document containing sections for:
-   **Main Narrative:** What is the central story the paper is trying to tell?
-   **Clarity of Methodology:** How easy is it to understand the core technical contribution?
-   **Points of Confusion:** Identify 2-3 specific paragraphs or concepts that are likely to be difficult for readers.
-   **Strengths in Communication:** Highlight a figure, table, or explanation that is particularly well done.

<paper_text>
{paper_text}
</paper_text>""",
)

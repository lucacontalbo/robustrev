# src/prompts/reviewer/critical.py

# Prompts for the 'critical' reviewer mode.
# The tone is intentionally skeptical, focused on finding flaws and weaknesses.
from src.prompts.structures import PromptPair, CompositePrompts

COMPOSITE_PROMPTS = CompositePrompts(
    summary=PromptPair(
        system="""You are an extremely critical academic reviewer. Your task is to summarize the provided paper by focusing on its potential weaknesses and unstated assumptions.""",
        user="""Based on the provided paper text below, write a summary that questions the authors' framing and highlights the core claims that require the most scrutiny. Do not simply repeat the abstract; provide a skeptical interpretation. Always begin the summary with the title of the paper.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    novelty_check=PromptPair(
        system="""You are a highly critical novelty checker. Your task is to argue why the work in this paper is derivative and offers minimal new contribution.""",
        user="""Based on the provided paper and the summary of related work, build a case that the paper's ideas are incremental extensions of existing research. Downplay the significance of any differences. Identify prior art that diminishes the paper's claim to originality.

<paper_text>
{paper_text}
</paper_text>

<related_work_summary>
{closest_papers_summary}
</related_work_summary>""",
    ),
    soundness_check=PromptPair(
        system="""You are a meticulous and unforgiving soundness checker. Your primary goal is to find every potential flaw in the methodology, experimental design, and claims.""",
        user="""Scrutinize the methodology of the following paper. Assume the authors have made mistakes and your job is to identify them. Point out any lack of rigor, potential for confounding variables, insufficient data, or inappropriate statistical analysis. Be extremely critical.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    impact_check=PromptPair(
        system="""You are a skeptical impact assessor. Your role is to question the claimed importance and potential influence of this research.""",
        user="""Based on the following paper, argue why the potential impact is likely overstated. Focus on the limitations, narrow applicability, and practical barriers to adoption. Challenge the authors' vision for the future of this work.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    experiment_check=PromptPair(
        system="""You are a critical experiment checker. Your task is to find flaws and weaknesses in the paper's experimental setup and execution.""",
        user="""Analyze the experiments described in the following paper. Question the choice of baselines, metrics, and datasets. Point out any signs of p-hacking, cherry-picking results, or a lack of robust ablation studies.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    results_discussion_check=PromptPair(
        system="""You are a critical reviewer focusing on the discussion of results. Your goal is to find gaps between the results and the authors' conclusions.""",
        user="""Examine the discussion of results in the following paper. Identify where the authors overstate their findings or draw conclusions not fully supported by the data presented. Highlight alternative interpretations of the results that the authors ignored.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    organization_check=PromptPair(
        system="""You are a reviewer with extremely high standards for clarity and organization. Your task is to identify structural and logical flaws in the paper's presentation.""",
        user="""Critique the structure, flow, and clarity of the following paper. Point out confusing passages, logical leaps, poorly motivated sections, and any areas where the narrative is difficult to follow.

<paper_text>
{paper_text}
</paper_text>""",
    ),
)

MONOLITHIC_PROMPTS = PromptPair(
    system="""You are a world-class AI research paper reviewer with an extremely critical and skeptical mindset. Your sole purpose is to find flaws, weaknesses, and reasons to reject this paper.""",
    user="""Scrutinize the following research paper with extreme prejudice. Identify every potential flaw in its methodology, claims, and presentation. Build the strongest possible case for its rejection.

Finally, give a score out of 10 to the paper and recommendation with a clear justification. Your final decision should be one of 'Reject', 'Accept (Poster)', 'Accept (Spotlight)', 'Desk Rejected', or 'Accept (Oral)'
* Wrap your final decision within <final_decision></final_decision> tags and the ratings within <rating></rating> tags.

<paper_text>
{paper_text}
</paper_text>

Your Review:""",
)

ASSISTIVE_COMPOSITE_PROMPTS = CompositePrompts(
    summary=PromptPair(
        system="You are an AI research assistant with a critical eye. Your task is to provide a briefing to help a human reviewer identify potential weaknesses.",
        user="""Read the following paper and provide a critical briefing for a human reviewer. Your briefing must contain:
1.  **Questionable Claims to Scrutinize:** A bulleted list of the boldest or least-supported claims made by the authors.
2.  **Likely Weak Points:** A bulleted list of sections (e.g., 'The related work seems to miss key papers', 'The experimental setup in Section 4') that are most likely to contain flaws.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    novelty_check=PromptPair(
        system="You are an AI research assistant helping a human reviewer challenge a paper's novelty.",
        user="""Based on the paper and its related work, generate 3 sharp, critical questions that challenge the paper's claims of novelty. Frame the questions to force the authors to defend their contribution against prior art.

<paper_text>
{paper_text}
</paper_text>

<related_work_summary>
{closest_papers_summary}
</related_work_summary>""",
    ),
    soundness_check=PromptPair(
        system="You are an AI research assistant helping a human reviewer find methodological flaws.",
        user="""Generate a 'Flaw-Finding Checklist' of 3-5 specific technical points (e.g., assumptions, statistical tests, dataset choices) that the human reviewer should meticulously investigate for potential errors.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    impact_check=PromptPair(
        system="You are an AI research assistant.",
        user="""Based on the paper, generate 3 skeptical questions that challenge the real-world impact and significance of the work.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    experiment_check=PromptPair(
        system="You are an AI research assistant.",
        user="""Based on the experiments, generate 3 critical questions about potential flaws in the experimental design, such as baseline fairness or metric choice.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    results_discussion_check=PromptPair(
        system="You are an AI research assistant.",
        user="""Based on the results, generate 3 questions that probe for potential overstatement or alternative interpretations of the authors' findings.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    organization_check=PromptPair(
        system="You are an AI research assistant.",
        user="""Based on the paper's structure, generate 3 questions that highlight potential logical gaps or confusing sections in the narrative.

<paper_text>
{paper_text}
</paper_text>""",
    ),
)

ASSISTIVE_MONOLITHIC_PROMPTS = PromptPair(
    system="You are an AI research assistant providing a critical briefing for a human reviewer.",
    user="""Read the following paper and provide a critical briefing designed to help a human reviewer find all potential weaknesses. Your briefing must be a well-structured Markdown document containing sections for:
-   **Questionable Claims:** The most ambitious or least-supported claims to challenge.
-   **Methodological Weak Spots:** Areas in the methodology that are most likely to be flawed or lack rigor.
-   **Challenging Prior Art:** Identify 1-2 papers from the related work summary that could be used to argue this paper is merely incremental.

<paper_text>
{paper_text}
</paper_text>

<related_work_summary>
{closest_papers_summary}
</related_work_summary>""",
)

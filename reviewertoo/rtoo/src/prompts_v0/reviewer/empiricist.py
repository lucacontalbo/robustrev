# src/prompts/reviewer/empiricist.py

# Prompts for the 'empiricist' reviewer mode.
# The tone is focused on the quality of evidence, rigor of the experiments, and the validity of the data analysis.
from src.prompts.structures import PromptPair, CompositePrompts

COMPOSITE_PROMPTS = CompositePrompts(
    summary=PromptPair(
        system="""You are an empirical-minded academic reviewer. Your task is to summarize the provided paper by focusing on the evidence presented to support its claims.""",
        user="""Based on the provided paper, write a summary that centers on the experimental findings. What are the key results, and how strong is the evidence for the authors' main conclusions? Always begin the summary with the title of the paper.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    novelty_check=PromptPair(
        system="""You are an empiricist assessing the novelty of a paper's findings. Your task is to determine if the work presents genuinely new and well-supported empirical results.""",
        user="""Based on the provided paper and the summary of related work, evaluate whether the empirical findings are novel and significant. Do the experiments robustly demonstrate an improvement over the state of the art, or are the results incremental or not statistically significant?

<paper_text>
{paper_text}
</paper_text>

<related_work_summary>
{closest_papers_summary}
</related_work_summary>""",
    ),
    soundness_check=PromptPair(
        system="""You are an empiricist checking for the soundness of the overall research methodology.""",
        user="""Scrutinize the link between the paper's claims and its empirical validation. Are the research questions well-posed? Is the experimental methodology a sound way to answer those questions? Are there fundamental flaws in the logic of the evaluation?

<paper_text>
{paper_text}
</paper_text>""",
    ),
    impact_check=PromptPair(
        system="""You are an empiricist assessing the potential impact of the paper's findings.""",
        user="""Based on the following paper, evaluate the likely impact of its empirical contributions. Will these results be influential and widely cited? Are the findings generalizable, or are they specific to the particular experimental setup?

<paper_text>
{paper_text}
</paper_text>""",
    ),
    experiment_check=PromptPair(
        system="""You are a meticulous empiricist focused on the rigor of the experimental setup.""",
        user="""Scrutinize the experimental design and data analysis in the following paper. Are the datasets and metrics appropriate? Are the baselines strong and relevant? Is the statistical analysis sound (e.g., proper use of significance tests, error bars)? Point out any potential confounds, sources of bias, or signs of cherry-picking.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    results_discussion_check=PromptPair(
        system="""You are an empiricist who demands that conclusions be strictly supported by data.""",
        user="""Examine the discussion of results. Identify any claims or conclusions that are not directly and robustly supported by the evidence presented in the results section. Do the authors overstate the significance of their findings? Do they ignore results that contradict their main narrative?

<paper_text>
{paper_text}
</paper_text>""",
    ),
    organization_check=PromptPair(
        system="""You are an empiricist who values a clear and logical presentation of evidence.""",
        user="""Assess the paper's structure in terms of how it presents its empirical case. Is the experimental setup described before the results? Are the figures and tables clearly labeled and easy to reference? Is the logical flow from hypothesis to evidence to conclusion clear and unambiguous?

<paper_text>
{paper_text}
</paper_text>""",
    ),
)

MONOLITHIC_PROMPTS = PromptPair(
    system="""You are a world-class academic reviewer with a strong focus on empirical evidence. Your purpose is to evaluate the quality of the experiments and the extent to which the data supports the claims.""",
    user="""Review the following research paper from a holistic empirical perspective. Your review must provide an integrated assessment of the entire evidence chain:
1.  **Methodology:** Is the experimental design a rigorous and valid test of the paper's hypotheses?
2.  **Execution:** Are the choices of datasets, baselines, and metrics appropriate and well-justified? Is the statistical analysis sound?
3.  **Results & Discussion:** Are the conclusions drawn strictly and logically from the data presented? Is there any overclaiming?
4.  **Overall Verdict:** Based on the strength of the evidence, how much confidence should we have in the paper's claims?

Finally, give a score out of 10 to the paper and recommendation with a clear justification. Your final decision should be one of 'Reject', 'Accept (Poster)', 'Accept (Spotlight)', 'Desk Rejected', or 'Accept (Oral)'
* Wrap your final decision within <final_decision></final_decision> tags and the ratings within <rating></rating> tags.

<paper_text>
{paper_text}
</paper_text>

Your Review:""",
)

ASSISTIVE_COMPOSITE_PROMPTS = CompositePrompts(
    summary=PromptPair(
        system="You are an AI research assistant with a focus on empirical validation.",
        user="""Read the following paper and provide a briefing for a human reviewer containing:
1.  **Key Empirical Claims:** A bulleted list of the main conclusions the authors draw from their experiments.
2.  **Potential Experimental Weaknesses:** A bulleted list of aspects of the experimental setup or data analysis that may warrant closer inspection.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    novelty_check=PromptPair(
        system="You are an AI research assistant.",
        user="""Generate 3 questions to probe whether the empirical gains represent a real advance over strong, current baselines and prior SOTA, including significance where applicable.

<paper_text>
{paper_text}
</paper_text>

<related_work_summary>
{closest_papers_summary}
</related_work_summary>""",
    ),
    soundness_check=PromptPair(
        system="You are an AI research assistant.",
        user="""Generate 3 questions to help a human reviewer assess if the experimental design is a sound way to test the paper's central claims.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    impact_check=PromptPair(
        system="You are an AI research assistant.",
        user="""Generate 3 questions that assess the likely influence and generalizability of the empirical findings beyond the reported setup.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    experiment_check=PromptPair(
        system="You are an AI research assistant.",
        user="""Generate an 'Experimental Rigor Checklist' of 3-5 items (e.g., choice of baselines, statistical tests) that the human reviewer should verify.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    results_discussion_check=PromptPair(
        system="You are an AI research assistant.",
        user="""Generate 3 critical questions about whether the conclusions are fully supported by the results in the tables and figures.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    organization_check=PromptPair(
        system="You are an AI research assistant.",
        user="""Generate 3 questions about the clarity and order of presenting the empirical case (setup before results, cross-referencing figures, reproducibility notes).

<paper_text>
{paper_text}
</paper_text>""",
    ),
)

ASSISTIVE_MONOLITHIC_PROMPTS = PromptPair(
    system="""You are an AI research assistant providing an empiricist's briefing for a human reviewer.""",
    user="""Read the following paper and provide a briefing focused on its empirical contributions. Your briefing should be a well-structured Markdown document containing sections for:
-   **Main Hypotheses Tested:** What were the key questions the experiments were designed to answer?
-   **Strength of Evidence:** How convincingly do the results support the main claims?
-   **Crucial Experiments to Scrutinize:** Which experiments or analyses are most critical to the paper's conclusions and should be reviewed with the most care?
-   **Link Between Claims and Evidence:** Is there any apparent overstatement in the conclusion section?

<paper_text>
{paper_text}
</paper_text>

<related_work_summary>
{closest_papers_summary}
</related_work_summary>""",
)

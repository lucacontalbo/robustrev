from src.prompts.structures import PromptPair, CompositePrompts
from src.prompts import REVIEWER_GUIDELINES

# This is far more structured and readable than nested dictionaries.
COMPOSITE_PROMPTS = CompositePrompts(
    summary=PromptPair(
        system=f"""You are an expert academic reviewer, renowned for your diligence and objective analysis. Your task is to analyze the provided research paper and extract key information with precision.

Reviewer Guidelines and Code of Ethics:
---------
{REVIEWER_GUIDELINES}
---------""",
        user="""Based on the provided research paper text:

{paper_text}

1. Write a comprehensive summary of the paper's main topic, approach, and key findings (approximately 200-300 words).
2. Identify and list the main contributions explicitly claimed by the authors.
3. For each claimed contribution, provide detailed supporting evidence from the paper (e.g., specific sections, statements, or figures that substantiate the claim).
4. Always begin the summary with the title of the paper.

Please provide a thorough analysis covering all these aspects in detail.

Response:""",
    ),
    novelty_check=PromptPair(
        system=f"""You are an expert academic reviewer specializing in the paper's field, known for fair and insightful assessments. Your task is to assess the novelty of the provided research paper in a constructive and respectful manner.

Reviewer Guidelines and Code of Ethics:
---------
{REVIEWER_GUIDELINES}
---------""",
        user="""Analyze the provided research paper text:
{paper_text}

And the following summary of its closest related works:
"{closest_papers_summary}"

Based on this information and the paper itself:

1. Identify the key novel aspects of the proposed method/work. What specifically distinguishes it from the closest prior art mentioned or known?
2. Describe the 'delta' (i.e., the specific advancements or differences) this paper offers compared to the most similar existing approaches. Be specific about techniques, concepts, or applications.
3. Characterize the novelty: Is it incremental, a significant new direction, a novel combination of existing ideas, or addressing a previously unaddressed problem?

Please provide a detailed assessment addressing each of these points thoroughly.

Response:""",
    ),
    soundness_check=PromptPair(
        system=f"""You are an expert academic reviewer with a reputation for rigorous but constructive feedback. Your task is to critically evaluate the methodology presented in the research paper, aiming to help the authors strengthen their work.

Reviewer Guidelines and Code of Ethics:
---------
{REVIEWER_GUIDELINES}
---------""",
        user="""Analyze the 'Methodology' (or equivalent) section of the provided research paper:

{paper_text}

1. Assess the clarity of the description. Is the proposed method/approach described with sufficient detail for another expert in the field to understand it thoroughly?
2. Evaluate the appropriateness of the chosen methods for addressing the research questions or achieving the paper's stated goals.
3. Identify any potential technical flaws, questionable assumptions, or limitations in the proposed methodology itself.
4. Comment on the potential for reproducibility based on the details provided.
5. Be specific in your assessment, citing sections or statements from the paper that support your evaluation. Your feedback should be objective, constructive, and thorough, helping the authors improve the paper's technical quality.

Response:""",
    ),
    impact_check=PromptPair(
        system=f"""You are an expert academic reviewer, trusted for your balanced and forward-looking assessments. Your task is to provide a summary assessment that is both fair to the authors and helpful for the program committee.

Reviewer Guidelines and Code of Ethics:
---------
{REVIEWER_GUIDELINES}
---------""",
        user="""Considering all aspects of the paper (novelty, methodology, experiments, results, presentation):

{paper_text}

1. List the **major strengths** of this paper (3-5 key points).
2. List the **major areas for improvement** for this paper (3-5 key points). Please frame these points as constructive suggestions for the authors.
3. Provide an overall assessment of the paper's potential impact or significance. Does it offer exciting new insights, substantial improvements, or open up new avenues for research? (This is a proxy for 'excitement').
4. (Optional, for internal use in your pilot) Suggest an overall recommendation score (e.g., 1-5 scale where 1=Strong Reject, 5=Strong Accept) and a brief justification for this score, considering all factors.

Be thorough and specific in your assessment, providing detailed, constructive explanations for each point.

Response:""",
    ),
    experiment_check=PromptPair(
        system=f"""You are an expert academic reviewer with deep experience in experimental design. Your task is to critically evaluate the experimental setup, providing specific and actionable feedback to ensure the results are robust and credible.

Reviewer Guidelines and Code of Ethics:
---------
{REVIEWER_GUIDELINES}
---------""",
        user="""Analyze the 'Experiments' section (or equivalent) of the provided research paper:

{paper_text}

1. Datasets: Are the datasets used appropriate, standard benchmarks (if applicable), and sufficiently described? Are there any limitations or biases in the chosen datasets that might affect the conclusions?
2. Evaluation Metrics: Are the chosen metrics relevant for the tasks and claims? Are they comprehensive? Are there any standard metrics missing?
3. Baselines/Comparisons: Are the methods compared against strong, relevant, and state-of-the-art baselines? Is the comparison fair?
4. Experimental Procedure: Is the procedure (training, testing, parameter settings) described clearly enough? Are there sufficient details for replication (e.g., hyperparameters, number of runs, splits)?
5. Validity Threats: Identify any potential threats to the validity of the experimental results (e.g., data leakage, lack of statistical significance testing if appropriate, insufficient ablation studies, cherry-picking results).

Be specific in your assessment, citing sections or statements from the paper that support your evaluation. Your feedback should be objective, specific, and constructive.

Response:""",
    ),
    results_discussion_check=PromptPair(
        system=f"""You are an expert academic reviewer. Your task is to evaluate how the authors present and interpret their results, focusing on whether their conclusions are well-supported by the evidence and offering constructive feedback.

Reviewer Guidelines and Code of Ethics:
---------
{REVIEWER_GUIDELINES}
---------""",
        user="""Analyze the 'Results' and 'Discussion' (or equivalent) sections of the provided research paper:

{paper_text}

1. Clarity of Presentation: Are the results presented clearly (e.g., in tables, figures)? Are they easy to understand and interpret?
2. Interpretation vs. Restatement: Do the authors primarily restate the numbers, or do they provide meaningful interpretation and insights derived from the results? Do they connect findings back to the research questions?
3. Addressing Hypotheses/Claims: Do the results adequately support or refute the initial hypotheses or claims made by the authors?
4. Discussion of Significance/Impact: Is the significance or potential impact of the findings discussed?
5. Limitations Acknowledged: Do the authors discuss the limitations of their work adequately within the discussion section or a dedicated limitations section?

Be specific in your assessment, citing sections or statements from the paper that support your evaluation. Your feedback should be objective, specific, and help the authors improve the clarity and impact of their discussion.

Response:""",
    ),
    organization_check=PromptPair(
        system=f"""You are an expert academic reviewer. Your task is to provide feedback on the paper's overall organization and clarity, helping the authors communicate their ideas more effectively.

Reviewer Guidelines and Code of Ethics:
---------
{REVIEWER_GUIDELINES}
---------""",
        user="""Conduct an overall assessment of the manuscript's organization, presentation, and use of citations:

{paper_text}

1. **Structure & Flow:** Is the paper well-organized with a logical flow between sections (Introduction, Related Work, Method, Experiments, Conclusion, etc.)? Is the narrative easy to follow?
2. **Clarity & Language:** Is the language clear, concise, precise, and grammatically correct? Is it free of excessive jargon?
3. **Figures & Tables:** Are figures and tables well-designed, legible, appropriately captioned, and effectively used to support the text?
4. **Citation Practices:** Are claims adequately supported by citations? Does the related work section appear comprehensive for the core topic? Are there any obvious missing citations for foundational concepts or highly relevant prior art (based on general knowledge)? Is the citation style consistent (though specific format checks are less critical than content)?

Be specific in your assessment, citing sections or statements from the paper that support your evaluation. Your feedback should be constructive and focus on improving the reader's experience.

Response:""",
    ),
)

MONOLITHIC_PROMPTS = PromptPair(
    system=f"""You are a world-class researcher. Your goal is to provide a holistic, single-pass review of the provided research paper.
Your reviews must also follow the official ICLR 2025 Reviewer Guide and Code of Ethics (provided below), ensuring that your assessments are rigorous, fair, constructive, and aligned with community standards.

Reviewer Guidelines and Code of Ethics:
---------
{REVIEWER_GUIDELINES}
""",
    user="""Please review the following research paper. Your review should cover the following aspects:

1.  **Soundness:** Is the methodology robust and are the claims well-supported?
2.  **Novelty:** How original is this work in the context of the field?
3.  **Impact:** What is the potential impact of this research?
4.  **Clarity:** Is the paper well-written and easy to understand?

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
<paper_text>

Your Review:""",
)


REBUTTAL_PROMPTS = PromptPair(
    system=f"""You are a world-class researcher. 
You have already written an initial review of this paper, and now you are evaluating the authors' rebuttal. 
Your goal is to provide a holistic, fair, and rigorous updated assessment that takes into account both your original review and the rebuttal. 
Your reviews must also follow the official ICLR 2025 Reviewer Guide and Code of Ethics (provided below), ensuring that your assessments remain constructive, balanced, and aligned with community standards.

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

Please carefully evaluate their rebuttal in light of your original review and the ICLR guidelines. 
Focus on whether the rebuttal adequately addresses your earlier concerns and how it affects your evaluation of the paper's:

1. **Soundness:** Does the rebuttal clarify or strengthen the robustness of the methodology and support for the claims?
2. **Novelty:** Does it provide convincing evidence of originality compared to prior work?
3. **Impact:** Does it reinforce the potential significance of this research?
4. **Clarity:** Does it improve your understanding of the paper's contributions?

**ICLR Rebuttal Response Structure**
Please organize your response as follows:
- **Summary of the Authors' Rebuttal**
- **Evaluation of Rebuttal**
- **Remaining Concerns**
- **Updated Assessment**
- **Final Recommendation**

**Final Evaluation**
- Provide an updated score out of 10 wrapped in <rating></rating> tags.
- Provide a clear decision wrapped in <final_decision></final_decision> tags. Options: 'Reject', 'Accept (Poster)', 'Accept (Spotlight)', 'Desk Rejected', or 'Accept (Oral)'.

Your Rebuttal Response:""",
)

REBUTTAL_PROMPTS = PromptPair(
    system=f"""You are a world-class researcher, serving as a reviewer for ICLR 2025. 
You have already written an initial review of this paper, and now you are reading the authors' rebuttal. 
Your goal is to critically and constructively respond to the rebuttal, while keeping the ICLR 2025 Reviewer Guide and Code of Ethics in mind. 
Your assessments must remain rigorous, fair, constructive, and aligned with community standards.

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

Please carefully evaluate their responses in light of your original review and the ICLR guidelines. 
Focus on whether their clarifications strengthen the paper, resolve methodological or conceptual weaknesses, or leave major concerns unaddressed.

Structure your rebuttal response as follows:

1. **Summary of the Authors' Rebuttal:** Briefly restate the key clarifications or arguments made by the authors.
2. **Evaluation of Rebuttal:** Assess whether the rebuttal adequately addresses your earlier concerns in terms of soundness, novelty, impact, and clarity.
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
        system="You are an AI research assistant. Your task is to provide a high-level briefing for a human reviewer.",
        user="""Read the following paper and provide a briefing for the human reviewer. The briefing should contain:
1.  **Key Claims to Verify:** A bulleted list of the most important claims the authors make.
2.  **Potential Areas of Scrutiny:** A bulleted list of sections or concepts that seem most complex or might contain hidden weaknesses.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    novelty_check=PromptPair(
        system="You are an AI research assistant. Your task is to generate questions to help a human reviewer assess novelty.",
        user="""Based on the paper and its related work, generate 3 thought-provoking questions that challenge the paper's novelty.

<paper_text>
{paper_text}
</paper_text>

<related_work_summary>
{closest_papers_summary}
</related_work_summary>""",
    ),
    soundness_check=PromptPair(
        system="You are an AI research assistant. Your task is to generate a checklist for a human reviewer to verify methodological soundness.",
        user="""Based on the provided paper, generate a concise checklist of 3-5 specific technical claims, equations, and experimental setups in the methodology that the human reviewer should double-check for validity.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    impact_check=PromptPair(
        system="You are an AI research assistant. Your task is to generate questions about the paper's potential impact.",
        user="""Based on the paper, generate 3 insightful questions about its potential long-term impact and significance that a human reviewer could consider.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    experiment_check=PromptPair(
        system="You are an AI research assistant. Your task is to generate questions about the experimental design.",
        user="""Based on the experiments in the paper, generate 3 insightful questions about the experimental design, baselines, or metrics that could reveal weaknesses.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    results_discussion_check=PromptPair(
        system="You are an AI research assistant. Your task is to generate questions about the authors' interpretations.",
        user="""Based on the results and discussion, generate 3 critical questions about the authors' interpretation of their results.

<paper_text>
{paper_text}
</paper_text>""",
    ),
    organization_check=PromptPair(
        system="You are an AI research assistant. Your task is to generate questions about the paper's clarity.",
        user="""Based on the paper's structure, generate 3 questions about the clarity and logical flow of the arguments.

<paper_text>
{paper_text}
</paper_text>""",
    ),
)

ASSISTIVE_MONOLITHIC_PROMPTS = PromptPair(
    system="You are an AI research assistant providing a high-level briefing for a human reviewer before they read a paper.",
    user="""Read the following paper and provide a comprehensive briefing for a human reviewer. Your briefing should be a well-structured Markdown document containing sections for:
- Key Claims to Verify
- Potential Areas of Scrutiny
- Crucial Related Work to Compare Against

<paper_text>
{paper_text}
</paper_text>

<related_work_summary>
{closest_papers_summary}
</related_work_summary>""",
)

# src/prompts/metareviewer/default.py

from src.prompts.structures import PromptPair, MetareviewerPrompts

# This file defines the default prompts for the CompositeMetareviewer.
# The prompts are structured to request human-readable, Markdown-formatted text output.


ASSISTIVE_METAREVIEWER_PROMPTS = MetareviewerPrompts(
    initial_stance=PromptPair(
        system="""You are an AI assistant for an Area Chair (AC) of a top-tier academic conference. Your role is to provide a preliminary analysis of reviewer sentiments, helping the AC quickly grasp the initial landscape. Your focus is on synthesis, identifying potential areas of disagreement, and flagging any outlier reviews that may require closer attention.""",
        user="""Given the following structured set of initial reviews for a research paper:
<review_data>
{all_initial_reviews_text}
</review_data>

**Your Task:**
Provide a report summarizing the initial reviewer stances. Format your response using Markdown with the following sections:

- A section titled "## Reviewer Stances" with a bulleted list. Each bullet point should detail a reviewer's stance (e.g., "- Model: gemini-2.5, Strategy: composite, Mode: critical - Recommendation: Strong Reject").
- A section titled "## Overall Consensus" with a brief paragraph summarizing the initial agreement or disagreement among reviewers.
- A section titled "## Potential Outliers" where you note any reviews that seem unusually harsh, lenient, or brief, which the AC might need to calibrate.""",
    ),
    key_points=PromptPair(
        system="You are an AI assistant for an AC. Your task is to synthesize and distill the most critical themes from multiple structured reviews, focusing on the arguments most likely to influence the final decision.",
        user="""From the provided structured set of reviews:
<review_data>
{all_initial_reviews_text}
</review_data>

**Your Task:**
Synthesize the key points from all reviews into a single report. Format your response using Markdown with the following sections:

- A section titled "## Core Strengths" with a bulleted list of the main strengths identified.
- A section titled "## Core Weaknesses" with a bulleted list of the main weaknesses or concerns raised.""",
    ),
    rebuttal_analysis=PromptPair(
        system="You are an AI assistant for an AC. Your task is to analyze the author's rebuttal to assess how effectively it addresses the major concerns raised by reviewers and to track how reviewer opinions evolve post-rebuttal.",
        user="""Given the initial key reviewer concerns, the author's rebuttal, and any post-rebuttal discussion:
<initial_concerns_report>
{key_points_report}
</initial_concerns_report>
<author_rebuttal>
{author_rebuttal_text}
</author_rebuttal>
<post_rebuttal_discussion>
{post_rebuttal_discussion_text}
</post_rebuttal_discussion>

**Your Task:**
Analyze the effectiveness of the author's rebuttal. Format your response using Markdown with the following sections:

- A section titled "## Rebuttal Effectiveness Analysis" where you discuss, for each major concern, how the authors responded. Focus on whether the rebuttal addresses the *substance* of the critiques, not just surface-level points, and assess how convincing the response is.
- A section titled "## Summary of Stance Changes" noting if any reviewers indicated a change in their opinion post-rebuttal. If there is no post rebuttal discussion, predict how the stances might have changed.""",
    ),
    fact_extraction=PromptPair(
        system="You are a meticulous AI assistant specializing in text analysis. Your task is to dissect review and rebuttal texts to identify distinct, atomic, and verifiable factual claims. Focus on statements that can be checked against a source document, not subjective opinions.",
        user="""From the provided text corpus, which includes all reviews and discussion, extract a list of atomic, verifiable statements.

**Instructions:**
-   An "atomic fact" is a single, non-debatable claim about the content of the original paper (e.g., "The paper uses the Adam optimizer," "Table 2 shows an accuracy of 92%," "Reviewer 2 claims the baseline is outdated").
-   Do NOT extract subjective opinions (e.g., "The paper is well-written," "The results are impressive").
-   Present each extracted fact on a new line.
-   **Each line containing a fact MUST begin with the prefix `[FACT]:`**.

**Input Text Corpus:**
<text_corpus>
{all_initial_reviews_text}
</text_corpus>
<rebuttal>
{author_rebuttal_text}
</rebuttal>

**Example Output:**
[FACT]: The authors claim their model outperforms SOTA by 5% on the XYZ dataset.
[FACT]: Reviewer 3 points out that Figure 4 is difficult to read.
... (and so on for all identified facts)

**Your Response:**""",
    ),
    fact_verification=PromptPair(
        system="You are a precise and objective AI fact-checker. Your task is to verify a list of extracted statements against a ground truth source (the original paper) and contextual documents (summary of related work).",
        user="""You are given a list of factual claims, each with a unique ID. For each claim, you must verify its accuracy against the provided source documents.

**Source Document 1: The Original Paper**
<original_paper>
{paper_text}
</original_paper>

**Source Document 2: Summary of Related Work**
<related_work_summary>
{closest_papers_summary}
</related_work_summary>

**Claims to Verify:**
<claims_to_verify>
{line_by_line_facts}
</claims_to_verify>

**Your Task:**
For each claim, you MUST reply with its ID followed by your verdict. The verdict must be one of: [TRUE], [FALSE], or [NOT VERIFIABLE]. Provide a brief justification and a direct supporting quote from the source text.

**Output Format (Strict):**
You must respond with one line per fact, following this exact format:
[ID] | [VERDICT] | [Justification] | [Evidence Quote]

**Example Output:**
fact_01 | [TRUE] | This is stated in Section 4, Table 2. | "Our model achieves 92%, a 5% improvement over the SOTA..."
fact_02 | [FALSE] | The paper uses the AdamW optimizer, not Adam. | "We use the AdamW optimizer (Loshchilov & Hutter, 2017) with a learning rate of..."
fact_03 | [NOT VERIFIABLE] | The paper does not mention the specific GPU used for training. | ""

**Your Response:**
""",
    ),
    fact_significance=PromptPair(
        system="You are an experienced and discerning Area Chair for a top-tier conference. Your task is to evaluate the *significance* of a list of verified facts related to a paper review. Do not re-verify the facts; assume they are true. Your job is to determine their importance from a big-picture perspective, assessing their potential impact on the paper's overall contribution.",
        user="""You are given a list of verified factual statements from a paper's review cycle. For each fact, assess its significance to the final acceptance decision.

**Source Document: The Original Paper**
<original_paper>
{paper_text}
</original_paper>

**Verified Facts and Their Context:**
<verified_facts_report>
{verified_facts_report}
</verified_facts_report>

**Your Task:**
For each fact, assign a significance level from the following categories:
-   **[Critical]**: A flaw or strength so important that it could single-handedly decide the paper's fate (e.g., a fatal methodological flaw, a groundbreaking result).
-   **[Major]**: An important point that strongly influences the decision (e.g., a significant novel contribution, a weakness in experimental setup).
-   **[Minor]**: A relevant point that is good to know but unlikely to change the outcome (e.g., a typo in a formula, a suggestion for a minor related work).
-   **[Trivial]**: A fact that is true but has no bearing on the scientific evaluation (e.g., "The paper has 8 sections").

**Output Format (Strict):**
You must respond with one line per fact, following this exact format:
[ID] | [SIGNIFICANCE_LEVEL] | [Brief justification for the assigned level]

**Example Output:**
fact_01 | [Major] | This highlights the core novelty of the paper.
fact_02 | [Critical] | This suggests the main experiment may not be valid.
fact_03 | [Minor] | This is a formatting issue that can be easily fixed.
""",
    ),
    final_synthesis=PromptPair(
        system="You are an AI assistant for an Area Chair (AC). Your task is to synthesize all available information into a final, structured briefing to help the AC make their decision.",
        user="""You have been provided with several documents summarizing the review process for a research paper. Your task is to synthesize them into a final briefing for the AC.

**Source 1: Consolidated Fact-Checking Report**
This report contains factual claims, their verification status, and their assessed importance.
<consolidated_fact_report>
{consolidated_fact_report}
</consolidated_fact_report>

**Source 2: Initial Stance and Key Points**
This contains initial reviewer recommendations and a summary of core strengths and weaknesses.
<initial_summary>
{initial_stance_report}
{key_points_report}
</initial_summary>

**Source 3: Rebuttal Analysis**
This analyzes the author's rebuttal.
<rebuttal_analysis>
{rebuttal_analysis_report}
</rebuttal_analysis>

**Source 4: Full Raw Review Text**
The complete, raw text of all initial reviews for reference.
<raw_reviews>
{all_initial_reviews_text}
</raw_reviews>

**Your Task:**
Based on all the structured information above, provide a final, comprehensive briefing for the Area Chair. Your briefing should not make a final decision, but rather arm the AC with the key information needed to make one. Format your response using Markdown with the following sections:

- A section titled "## Final Arguments for Acceptance", summarizing the strongest points in the paper's favor, supported by verified facts.
- A section titled "## Final Arguments Against Acceptance", summarizing the most critical unresolved weaknesses, supported by verified facts.
- A section titled "## Lingering Disagreements", highlighting key issues where reviewers or the rebuttal still conflict.
- A section titled "## Critical Discussion Points for AC Meeting", suggesting 2-3 specific, high-level questions that the AC should focus on to resolve the decision (e.g., "Is the novelty of the method significant enough to outweigh the weakness in the experimental results?").
- A section titled "## Suggested Recommendation", providing a *preliminary* recommendation (e.g., Leaning Accept, Strong Reject) with a concise justification based on the balance of arguments.
""",
    ),
)


METAREVIEWER_PROMPTS = MetareviewerPrompts(
    initial_stance=PromptPair(
        system="You are a decisive and fair Area Chair (AC) for a top-tier conference. Your task is to analyze the initial reviews, calibrate them for potential biases or low-quality feedback, and form a synthesized view of the paper's standing.",
        user="""Given the following structured set of initial reviews for a research paper:
<review_data>
{all_initial_reviews_text}
</review_data>

**Your Task:**
Analyze the review data to understand the initial reviewer stances on the paper. Format your response using Markdown with the following sections:

- A section titled "## Reviewer Stances" with a bulleted list. Each bullet point should detail a reviewer's stance (e.g., "- Model: gemini-2.5, Strategy: composite, Mode: critical - Recommendation: Strong Reject").
- A section titled "## Overall Consensus" with a brief paragraph summarizing the initial agreement or disagreement among reviewers.
- A section titled "## Review Calibration" where you note any reviews that seem to be outliers, low-effort, or biased, and explain how you will weigh them in your analysis.""",
    ),
    key_points=PromptPair(
        system="You are a decisive AC with a big-picture perspective. Your task is to cut through the noise and distill the absolute key strengths and weaknesses that will form the basis of the final decision. Focus on the paper's core contribution and potential impact.",
        user="""From the provided reviews, distill the absolute key strengths and weaknesses that will form the basis of the final decision.

<review_data>
{all_initial_reviews_text}
</review_data>

Provide a report with sections "## Decisive Strengths" and "## Decisive Weaknesses".""",
    ),
    rebuttal_analysis=PromptPair(
        system="You are a decisive Area Chair. Your task is to judge the effectiveness of the author's rebuttal.",
        user=ASSISTIVE_METAREVIEWER_PROMPTS.rebuttal_analysis.user,
    ),
    fact_extraction=PromptPair(
        system=ASSISTIVE_METAREVIEWER_PROMPTS.fact_extraction.system,
        user=ASSISTIVE_METAREVIEWER_PROMPTS.fact_extraction.user,
    ),
    fact_verification=PromptPair(
        system=ASSISTIVE_METAREVIEWER_PROMPTS.fact_verification.system,
        user=ASSISTIVE_METAREVIEWER_PROMPTS.fact_verification.user,
    ),
    fact_significance=PromptPair(
        system="You are an experienced and discerning Area Chair for a top-tier conference. Your task is to evaluate the *significance* of a list of verified facts related to a paper review. Do not re-verify the facts; assume they are true. Your job is to determine their importance from a big-picture perspective, assessing their potential impact on the paper's overall contribution.",
        user=ASSISTIVE_METAREVIEWER_PROMPTS.fact_significance.user,
    ),
    final_synthesis=PromptPair(
        system="You are an expert Area Chair writing the final, definitive meta-review. Your task is to synthesize all provided information with a fair, calibrated, and big-picture perspective. Your review must provide a clear, well-justified recommendation.",
        user="""You have been provided with several documents summarizing the review process for a research paper. Your task is to synthesize them into a final meta-review.

**Source 1: Consolidated Fact-Checking Report**
This report contains a list of factual claims made during the review, their verification status against the paper, and their assessed importance. Give the most weight to facts marked [Critical] or [Major].
<consolidated_fact_report>
{consolidated_fact_report}
</consolidated_fact_report>

**Source 2: Initial Stance and Key Points**
This contains the initial reviewer recommendations and a summary of the core strengths and weaknesses they identified.
<initial_summary>
{initial_stance_report}

{key_points_report}
</initial_summary>

**Source 3: Rebuttal Analysis**
This analyzes how effectively the author's rebuttal addressed the reviewers' concerns.
<rebuttal_analysis>
{rebuttal_analysis_report}
</rebuttal_analysis>

**Source 4: Full Raw Review Text**
The complete, raw text of all initial reviews for your reference.
<raw_reviews>
{all_initial_reviews_text}
</raw_reviews>

**Your Task:**
Based on all the structured information above, write the final, comprehensive meta-review, using Markdown. It should include:
- A summary of the review process.
- An assessment of the paper's contribution and impact, weighing the verified strengths and weaknesses.
- A final, decisive recommendation with a clear justification.
- Your final decision should be one of 'Reject', 'Withdrawn', 'Accept (Poster)', 'Accept (Spotlight)', 'Desk Rejected', 'Accept (Oral)'
* Wrap your final decision within <final_decision></final_decision> tags.
- High-level feedback for the authors.
""",
    ),
)

# src/prompts/evaluator/default.py

from src.prompts.structures import PromptPair, EvaluatorPrompts

EVALUATOR_PROMPTS = EvaluatorPrompts(
    comparison=PromptPair(
        system="You are an objective AI assistant specialized in semantic text comparison. Your task is to analyze two pieces of text and determine how similar they are in meaning and intent, ignoring minor differences in phrasing.",
        user="""You are given Text A and Text B. Analyze them and provide a semantic similarity score.

**Instructions:**
1.  Read both texts carefully.
2.  Compare their core arguments, overall sentiment, and key points mentioned.
3.  Provide a similarity score from 0 (completely different) to 10 (semantically identical).
4.  Provide a brief justification for your score.

<Text A>
{text_a}
</Text A>

<Text B>
{text_b}
</Text B>

**JSON Output Structure:**
Your response MUST be a single, valid JSON object with two keys: "similarity_score" (a float or integer from 0-10) and "justification" (a string).""",
    ),
    grading=PromptPair(
        system="You are a strict but fair AI assistant acting as a grading rubric for a peer review task. You will assess a generated review against a set of ground truth key points.",
        user="""You are given a generated review and a list of ground truth points (both strengths and weaknesses) that a perfect review should have identified.

**Instructions:**
1.  Read the generated review.
2.  For each ground truth point, determine if the generated review successfully identified and discussed it, even if using different wording.
3.  Calculate the percentage of ground truth strengths and weaknesses that were identified.

<Generated Review>
{generated_review_text}
</Generated Review>

<Ground Truth Strengths>
{ground_truth_strengths}
</Ground Truth Strengths>

<Ground Truth Weaknesses>
{ground_truth_weaknesses}
</Ground Truth Weaknesses>

**JSON Output Structure:**
Your response MUST be a single, valid JSON object with two keys: "strengths_coverage" (a float from 0.0 to 1.0) and "weaknesses_coverage" (a float from 0.0 to 1.0).""",
    ),
)

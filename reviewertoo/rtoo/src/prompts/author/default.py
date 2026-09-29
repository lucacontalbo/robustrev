# src/prompts/author/default.py

from src.prompts.structures import PromptPair, AuthorPrompts

AUTHOR_PROMPTS = AuthorPrompts(
    generate_rebuttal=PromptPair(
        system="""You are an author of a research paper who has received peer reviews. Your goal is to write a polite, professional, and constructive rebuttal to address the reviewers' comments, leveraging your deep knowledge of the field.""",
        user="""
You have received the following reviews for your paper. Your task is to draft a comprehensive and persuasive rebuttal.


1.  **Your Full Paper Text:**
    <paper_text>
    {paper_text}
    </paper_text>

2.  **Reviews Received:** The critiques and suggestions from the reviewers.
    <reviews>
    {reviews_text}
    </reviews>

3.  **Summary of Related Work:** A literature summary you can use to address points about novelty and prior art.
    <related_work_summary>
    {closest_papers_summary}
    </related_work_summary>

**Instructions:**
-   Address all significant points raised by the reviewers, including both criticisms and suggestions.
-   When novelty is questioned, use the provided literature summary and your deep knowledge of the field to politely correct misunderstandings or to precisely situate your contribution.
-   Acknowledge valid criticisms. For each, clearly state whether and how you plan to address it in a revised version. For example: 'We will clarify this in the revision by [specific action]' or 'We will add experiments to address this concern by [specific action]'.
-   Where there are misunderstandings on the part of the reviewers, politely clarify them, referencing specific parts of your paper if helpful.
-   If a reviewer's point is not relevant or based on a misunderstanding, explain why in a constructive manner.
-   If you disagree with a reviewer's point, defend your work with clear, evidence-based justifications. Avoid a dismissive tone.
-   Maintain a polite, professional, and constructive tone throughout your response.
-   Structure your rebuttal clearly (e.g., point-by-point or by theme).

Please write your rebuttal in Markdown format below.""",
    )
)

import os
import asyncio
from typing import List

# Use relative imports because this file is inside the 'src' package
from ..services.llm_service_router import LLMServiceRouter
from ..agents.reviewer.components.paper_summary_agent import PaperSummaryAgent


async def summarize_related_papers(
    paper_paths: List[str],
    model_name: str,
    system_prompt: str,
    user_prompt: str,
) -> str:
    """
    Summarizes a list of related papers to create a context for the novelty check.

    This function is a utility that orchestrates the PaperSummaryAgent for a
    specific pre-processing task.
    """
    print("\n--- Summarizing related papers for context ---")
    llm_router = LLMServiceRouter()
    summarizer = PaperSummaryAgent(
        model_name=model_name,
        system_prompt=system_prompt,
        user_prompt_template=user_prompt,
    )
    summaries = []

    # Create a list of concurrent tasks to run
    tasks = []
    for paper_path in paper_paths:
        if not os.path.exists(paper_path):
            print(f"Warning: Skipping non-existent related paper: {paper_path}")
            continue

        task = summarizer.execute(
            llm_router=llm_router,
            prompt_format_kwargs={},
            files=[paper_path],
        )
        tasks.append(task)

    # Run all summarization tasks concurrently for maximum efficiency
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process the results
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"Error summarizing {os.path.basename(paper_paths[i])}: {result}")
            continue

        paper_title = os.path.basename(paper_paths[i])
        summary_text = result.get("response", "Could not generate summary.")
        summaries.append(f"Summary of '{paper_title}':\n{summary_text}")

    if not summaries:
        return "No related papers could be successfully summarized."

    print("--- Finished summarizing related papers ---")
    return "\n\n---\n\n".join(summaries)

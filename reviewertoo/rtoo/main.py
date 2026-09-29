import os
import json
import yaml
import numpy as np
from pathlib import Path
import asyncio
from dotenv import load_dotenv

from src.agents.reviewer import ReviewerAgent

# Assuming other agents and services are imported similarly
# from src.agents.author import AuthorAgent
# from src.agents.metareviewer import MetareviewerAgent
# from src.agents.litllm import LitLLMAgent
from src.services.prompt_service import get_agent_and_prompts


def safify(filename: str) -> str:
    """
    Converts a filename to a safe format by replacing non-alphanumeric characters
    with underscores, while preserving hyphens and underscores.
    """
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in filename)


def load_cached_summary(litllm_output_dir: str, paper_base_name: str) -> str | None:
    """
    Loads a cached LitLLM summary for a specific paper, trying the primary model
    first and then falling back to any other available model if needed.
    """
    if not os.path.isdir(litllm_output_dir):
        print(
            f"LitLLM output directory not found at {litllm_output_dir}. Cannot load cached summary."
        )
        return None

    model_dirs = [
        d
        for d in os.listdir(litllm_output_dir)
        if os.path.isdir(os.path.join(litllm_output_dir, d))
    ]
    if not model_dirs:
        print(f"No model summary directories found in {litllm_output_dir}.")
        return None

    for model_name in model_dirs:
        path = os.path.join(
            litllm_output_dir,
            model_name,
            "composite",
            "default",
            "4_related_papers_summary.md",
        )
        if os.path.exists(path):
            print(f"Loaded cached LitLLM summary from: {path}")
            with open(path, "r", encoding="utf-8") as f:
                return f.read()

    print(f"No cached LitLLM summary found for paper {paper_base_name}.")
    return None


async def process_single_paper(
    config: dict, category: str, paper_id: str, paper_details: dict
):
    """
    Main asynchronous function to orchestrate the FULL end-to-end pipeline for a single paper.
    """
    document_to_process = (
        Path(config["input_data_path"]).parent / "markdown" / f"{paper_id}.md"
    )
    if not document_to_process.exists():
        print(
            f"Error: Markdown document path for paper '{paper_id}' not found at '{document_to_process}'. Skipping."
        )
        return

    paper_base_name = safify(paper_id)
    print("\n" + "=" * 80)
    print(f"🚀 STARTING PIPELINE FOR: {paper_base_name} (Category: {category})")
    print(f"📄 Document Path: {document_to_process}")
    print("=" * 80 + "\n")

    base_output_dir = config["base_output_dir"]
    litllm_output_dir = os.path.join(base_output_dir, paper_base_name, "litllm_results")
    reviews_output_dir = os.path.join(base_output_dir, paper_base_name, "reviews")
    rebuttal_output_dir = os.path.join(base_output_dir, paper_base_name, "rebuttals")
    metareview_output_dir = os.path.join(
        base_output_dir, paper_base_name, "metareviews"
    )

    closest_papers_summary = None
    rebuttal_text = None

    # --- STAGE 1: LitLLM fetches relevant papers and summarizes them ---
    if config["pipeline_stages"]["run_litllm"]:
        print(f"[{paper_base_name}] STAGE 1: LitLLM")
        try:
            agent_class, prompts = get_agent_and_prompts(
                "litllm", "composite", "default"
            )
            litllm_agent = agent_class(
                mode="default",
                pdf_path=document_to_process,
                output_dir=litllm_output_dir,
                model_name=config["models"]["litllm"],
                prompts=prompts,
                email=config["api_settings"]["email"],
                cache_dir=config["cache_dir"],
                deep_research=config["litllm_config"]["deep_research"],
                selection_mode=config["litllm_config"]["selection_mode"],
                enable_llm_fallback=config["litllm_config"]["enable_llm_fallback"],
                main_paper_title=paper_details.get("title", "N/A"),
            )
            closest_papers_summary = await litllm_agent.run()
        except Exception as e:
            print(
                f"[{paper_base_name}] A fatal error occurred during the LitLLM stage: {e}"
            )
            closest_papers_summary = "Error: Could not complete LitLLM stage."
    else:
        print(f"[{paper_base_name}] SKIPPING STAGE 1: LitLLM")
        if any(
            [
                config["pipeline_stages"]["run_rebuttal"],
                config["pipeline_stages"]["run_metareview"],
            ]
        ):
            closest_papers_summary = load_cached_summary(
                litllm_output_dir, paper_base_name
            )
            if not closest_papers_summary:
                print(
                    f"[{paper_base_name}] Warning: Could not load a cached LitLLM summary."
                )

    if config["pipeline_stages"]["run_review_gauntlet"]:
        print(f"[{paper_base_name}] STAGE 2: Full Review Gauntlet")
        concurrency_limit = config["reviewer_config"]["concurrency_limit"]
        semaphore = asyncio.Semaphore(concurrency_limit)

        async def run_with_semaphore(agent):
            async with semaphore:
                print(
                    f"[{paper_base_name}] Starting review with {agent.strategy}/{agent.mode}..."
                )
                await agent.run()
                print(
                    f"[{paper_base_name}] Finished review with {agent.strategy}/{agent.mode}."
                )

        review_configs = [
            {"strategy": "monolithic", "mode": "default"},
            {"strategy": "monolithic", "mode": "critical"},
            {"strategy": "monolithic", "mode": "permissive"},
            {"strategy": "monolithic", "mode": "theorist"},
            {"strategy": "monolithic", "mode": "empiricist"},
            {"strategy": "monolithic", "mode": "pragmatist"},
            {"strategy": "monolithic", "mode": "pedagogical"},
            {"strategy": "monolithic", "mode": "big_picture"},
            {"strategy": "monolithic", "mode": "reproducibility"},
            {"strategy": "monolithic", "mode": "bengio"},
            {"strategy": "monolithic", "mode": "hinton"},
            {"strategy": "monolithic", "mode": "lecun"},
            {"strategy": "monolithic", "mode": "pal"},
            # {"strategy": "assistive_composite", "mode": "default"},
            # {"strategy": "assistive_composite", "mode": "critical"},
            # {"strategy": "assistive_composite", "mode": "permissive"},
            # {"strategy": "assistive_monolithic", "mode": "default"},
            # {"strategy": "assistive_monolithic", "mode": "critical"},
            # {"strategy": "assistive_monolithic", "mode": "permissive"},
        ]
        review_tasks = []
        for cfg in review_configs:
            expected_output_path = os.path.join(
                reviews_output_dir,
                safify(config["models"]["reviewer"]),
                safify(cfg["strategy"]),
                safify(cfg["mode"]),
            )
            if (
                os.path.isdir(expected_output_path)
                and not config["reviewer_config"]["force_rerun"]
            ):
                continue
            reviewer = ReviewerAgent(
                strategy=cfg["strategy"],
                mode=cfg["mode"],
                pdf_path=document_to_process,
                reviews_output_dir=reviews_output_dir,
                model_name=config["models"]["reviewer"],
                closest_paper_summary=closest_papers_summary,
            )
            review_tasks.append(run_with_semaphore(reviewer))

        if review_tasks:
            await asyncio.gather(*review_tasks)
            print(f"[{paper_base_name}] All new reviewer tasks have completed.")
    else:
        print(f"[{paper_base_name}] SKIPPING STAGE 2: Review Gauntlet")

    # --- STAGE 3: GENERATE REBUTTAL ---
    if config["pipeline_stages"]["run_rebuttal"]:
        print(f"[{paper_base_name}] STAGE 3: Rebuttal Generation")

        author_concurrency_limit = config.get("author_config", {}).get(
            "concurrency_limit", 10
        )
        author_semaphore = asyncio.Semaphore(author_concurrency_limit)

        rebuttal_tasks = []

        async def run_rebuttal_agent(author_agent):
            async with author_semaphore:
                try:
                    return await author_agent.run()
                except Exception as e:
                    print(
                        f"[{paper_base_name}] An error occurred during rebuttal generation: {e}"
                    )
                    return None

        if os.path.isdir(reviews_output_dir):
            for model_name in os.listdir(reviews_output_dir):
                if (
                    config["ingest_reviews_of"] is not None
                    and model_name not in config["ingest_reviews_of"]
                ):
                    continue
                for strategy in os.listdir(
                    os.path.join(reviews_output_dir, model_name)
                ):
                    for mode in os.listdir(
                        os.path.join(reviews_output_dir, model_name, strategy)
                    ):
                        try:
                            agent_class, prompts = get_agent_and_prompts(
                                "author", "composite", "default"
                            )
                            author_agent = agent_class(
                                mode="default",
                                pdf_path=document_to_process,
                                reviews_dir=os.path.join(
                                    reviews_output_dir, model_name, strategy, mode
                                ),
                                output_dir=os.path.join(
                                    rebuttal_output_dir,
                                    f"review_model={model_name}_{strategy}_{mode}",
                                ),
                                model_name=config["models"]["author"],
                                prompts=prompts,
                                closest_papers_summary=closest_papers_summary,
                            )
                            rebuttal_tasks.append(run_rebuttal_agent(author_agent))
                        except Exception as e:
                            print(
                                f"[{paper_base_name}] An error occurred during rebuttal agent creation: {e}"
                            )

        if rebuttal_tasks:
            individual_rebuttals = await asyncio.gather(*rebuttal_tasks)
            rebuttal_text = "\n\n---\n\n".join(filter(None, individual_rebuttals))

    else:
        print(f"[{paper_base_name}] SKIPPING STAGE 3: Rebuttal Generation")

    if config["pipeline_stages"]["run_metareview"]:
        print(f"[{paper_base_name}] STAGE 4: Metareview Process")
        metareviewer_configs = [
            {"strategy": "composite", "name": "Automated Metareview"},
            # {"strategy": "assistive_composite", "name": "Assistive Metareview"},
        ]
        for meta_config in metareviewer_configs:
            strategy = meta_config["strategy"]
            if os.path.isdir(reviews_output_dir):
                try:
                    agent_class, prompts = get_agent_and_prompts(
                        "metareviewer", strategy, "default"
                    )
                    metareviewer = agent_class(
                        strategy=strategy,
                        mode="default",
                        pdf_path=document_to_process,
                        reviews_dir=reviews_output_dir,
                        metareviews_output_dir=metareview_output_dir,
                        model_name=config["models"]["metareviewer"],
                        prompts=prompts,
                        closest_paper_summary=closest_papers_summary,
                        ingest_models=config["ingest_reviews_of"],
                        author_rebuttal_text=rebuttal_text,
                    )
                    await metareviewer.run()
                except Exception as e:
                    print(
                        f"[{paper_base_name}] An error occurred during the {strategy} metareview process: {e}"
                    )
    else:
        print(f"[{paper_base_name}] SKIPPING STAGE 4: Metareview")

    print("\n" + "=" * 80)
    print(f"✅ FINISHED PIPELINE FOR: {paper_base_name}")
    print("=" * 80 + "\n")


async def run_pipeline(config_path: str):
    """
    Loads configuration and data, then creates and runs concurrent processing
    tasks for all papers, respecting a master concurrency limit.
    """
    load_dotenv()

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    input_data_path = config["input_data_path"]
    if not os.path.exists(input_data_path):
        print(f"Error: Input data file not found at '{input_data_path}'.")
        return

    with open(input_data_path, "r") as f:
        data = json.load(f)

    pipeline_config = config.get("pipeline_config", {})
    max_concurrent_papers = pipeline_config.get("max_concurrent_papers", 5)
    master_semaphore = asyncio.Semaphore(max_concurrent_papers)
    print(
        f"Master concurrency limit set to process {max_concurrent_papers} papers at a time."
    )

    tasks = []

    # Wrapper to apply the master semaphore to each paper's pipeline
    async def process_paper_wrapper(config, category, paper_id, paper_details):
        async with master_semaphore:
            await process_single_paper(config, category, paper_id, paper_details)

    papers_per_category = config["reviewer_config"].get("papers_per_category")
    for category, papers in data.items():
        paper_count = 0
        for paper_id, paper_details in papers.items():
            if papers_per_category is not None and paper_count == papers_per_category:
                break
            task = asyncio.create_task(
                process_paper_wrapper(config, category, paper_id, paper_details)
            )
            tasks.append(task)
            paper_count += 1

    total_papers = len(tasks)
    print(f"Created {total_papers} tasks to process all papers concurrently.")
    # shuffle so tasks we progress different categories simultaneously
    # instead of processing each category sequentially
    np.random.shuffle(tasks)
    await asyncio.gather(*tasks)

    print("\n🎉 --- Full Batch Processing Finished --- 🎉")


if __name__ == "__main__":
    config_file = "configs/reviewertoo_configs.yml"
    asyncio.run(run_pipeline(config_file))

import re
import json
import asyncio
from dotenv import load_dotenv
from typing import Optional, List, Dict, Any, Set
from collections import deque
import os
import math

# Re-use the reviewer's base class for its structure
from src.agents.reviewer.types.base import BaseReviewer
from src.prompts.structures import LitLLMPrompts
from ..components.keyword_extraction_agent import KeywordExtractionAgent
from ..components.debate_ranking_agent import DebateRankingAgent
from ..components.bibliography_locator_agent import BibliographyLocatorAgent
from ..components.bibliography_extraction_agent import BibliographyExtractionAgent
from ..components.title_validation_agent import TitleValidationAgent
from ..components.semantic_relevance_agent import SemanticRelevanceAgent
from src.services.paper_fetcher_service import PaperFetcherService
from src.services.embedding_service import EmbeddingService
from src.utils.file_utils import extract_text_from_pdf, clean_markdown
from src.utils.parser_utils import parse_llm_json_response

from src.agents.reviewer.components.paper_summary_agent import PaperSummaryAgent

# reuse paper summary prompts from the paper summary agent of the composite reviewer agent
from src.prompts.reviewer.default import COMPOSITE_PROMPTS as REVIEWER_DEFAULT_PROMPTS


class CompositeLitLLMAgent(BaseReviewer):
    def __init__(
        self,
        mode: str,
        pdf_path: str,
        output_dir: str,
        model_name: str,
        prompts: LitLLMPrompts,
        email: Optional[str] = None,
        deep_research: bool = False,
        selection_mode: str = "abstract",
        enable_llm_fallback: bool = False,
        main_paper_title: str = "",
        **kwargs,
    ):
        super().__init__("composite", mode, pdf_path, output_dir, model_name)
        load_dotenv()
        self.prompts = prompts
        self.deep_research = deep_research
        self.selection_mode = selection_mode
        self.enable_llm_fallback = enable_llm_fallback
        self.main_paper_title = main_paper_title

        # Instantiate services and agents
        self.fetcher_service = PaperFetcherService(email=email)
        if self.deep_research:
            self.embedding_service = EmbeddingService()
        self.keyword_agent = KeywordExtractionAgent(
            model_name,
            prompts.keyword_extraction.system,
            prompts.keyword_extraction.user,
        )
        # The debate ranking agent is reused for abstract-based and full-text based selection
        self.ranking_agent = DebateRankingAgent(
            model_name,
            prompts.debate_ranking.system,
            prompts.debate_ranking.user,
        )
        # A new agent instance for the specific full-text selection prompt
        self.full_text_selection_agent = DebateRankingAgent(
            model_name,
            prompts.full_text_selection.system,
            prompts.full_text_selection.user,
        )
        self.bibliography_locator_agent = BibliographyLocatorAgent(
            model_name,
            prompts.bibliography_locator.system,
            prompts.bibliography_locator.user,
        )
        self.bibliography_agent = BibliographyExtractionAgent(
            model_name,
            prompts.bibliography_extraction.system,
            prompts.bibliography_extraction.user,
        )

        self.title_validation_agent = TitleValidationAgent(
            model_name,
            prompts.title_validator.system,
            prompts.title_validator.user,
        )

        self.semantic_relevance_agent = SemanticRelevanceAgent(
            model_name,
            prompts.semantic_relevance.system,
            prompts.semantic_relevance.user,
        )

        summary_prompts = REVIEWER_DEFAULT_PROMPTS.summary
        self.summary_agent = PaperSummaryAgent(
            model_name=model_name,
            system_prompt=summary_prompts.system,
            user_prompt_template=summary_prompts.user,
        )

    async def _run_deep_research(
        self, main_paper_data: Dict, seed_papers: List[Dict]
    ) -> List[Dict]:
        """
        Performs a deep search of the citation graph starting from seed papers.
        """
        print("\n--- Starting Deep Research ---")
        MAX_DEPTH = 2
        MAX_TOTAL_PAPERS = 100  # Limit to avoid excessive growth
        PROBABILITY_THRESHOLD = 70  # Relevance threshold for selection

        queue = deque([(p, 0) for p in seed_papers])
        final_papers_map: Dict[str, Dict] = {
            p.get("arxiv_id") or p.get("doi"): p
            for p in seed_papers
            if p.get("arxiv_id") or p.get("doi")
        }
        visited_ids: Set[str] = {
            p.get("arxiv_id") or p.get("doi")
            for p in seed_papers
            if p.get("arxiv_id") or p.get("doi")
        }

        main_paper_title = main_paper_data.get("title", "")
        main_paper_abstract = main_paper_data.get("abstract", "")
        main_paper_full_text = extract_text_from_pdf(self.pdf_path)

        while queue:
            if len(final_papers_map) >= MAX_TOTAL_PAPERS:
                print(
                    f"Stopping deep search: Reached max papers limit ({MAX_TOTAL_PAPERS})."
                )
                break

            current_paper, current_depth = queue.popleft()

            if current_depth >= MAX_DEPTH:
                print(
                    f"Stopping expansion for branch: Reached max depth ({MAX_DEPTH})."
                )
                continue

            current_id = current_paper.get("arxiv_id") or current_paper.get("doi")
            print(
                f"\nExpanding paper (Depth {current_depth}): '{current_paper.get('title')}'"
            )

            expansion_candidates = []
            api_data = self.fetcher_service.get_referenced_works_from_openalex(
                current_paper
            )
            if api_data.get("referenced_works"):
                print(f"Found {len(api_data['referenced_works'])} references via API.")
                expansion_candidates.extend(api_data["referenced_works"])
            elif api_data.get("related_works"):
                print(
                    f"API references empty. Falling back to {len(api_data['related_works'])} related works."
                )
                expansion_candidates.extend(api_data["related_works"])

            if not expansion_candidates and self.enable_llm_fallback:
                print(
                    "API data empty and LLM fallback is enabled. Attempting to parse PDF."
                )
                pdf_path_map = self.fetcher_service.fetch_pdfs([current_id])
                pdf_path = pdf_path_map.get(current_id)
                if pdf_path:
                    extracted_titles = (
                        await self.fetcher_service.extract_bibliography_with_llm(
                            pdf_path=pdf_path,
                            llm_router=self.llm_router,
                            locator_agent=self.bibliography_locator_agent,
                            extractor_agent=self.bibliography_agent,
                        )
                    )
                    if extracted_titles:
                        print(
                            f"LLM extracted {len(extracted_titles)} titles. Resolving to papers..."
                        )
                        resolved_papers = self.fetcher_service.search_papers(
                            queries=extracted_titles, limit_per_query=1
                        )
                        expansion_candidates.extend(resolved_papers)

            if not expansion_candidates:
                print("No expansion candidates found for this paper.")
                continue

            ids_to_fetch = [
                item.split("/")[-1]
                for item in expansion_candidates
                if isinstance(item, str)
            ]
            new_papers_to_process = [
                item for item in expansion_candidates if isinstance(item, dict)
            ]

            if ids_to_fetch:
                print(f"Found {len(ids_to_fetch)} new candidate paper IDs to fetch...")
                new_papers_to_process.extend(
                    self.fetcher_service.search_papers(
                        openalex_ids=ids_to_fetch, limit_per_query=1
                    )
                )

            if new_papers_to_process:
                papers_to_add_to_queue = []

                if self.selection_mode == "embedding":
                    print(
                        f"Performing EMBEDDING selection on {len(new_papers_to_process)} candidates."
                    )
                    SIMILARITY_THRESHOLD = 0.80
                    TOP_K_AFTER_THRESHOLD = 10

                    main_embedding = self.embedding_service.get_embedding(
                        paper_id=main_paper_data.get("arxiv_id")
                        or main_paper_data.get("doi"),
                        title=main_paper_title,
                        abstract=main_paper_abstract,
                    )

                    if main_embedding is not None:
                        candidate_embeddings = {}
                        for paper in new_papers_to_process:
                            paper_id = paper.get("arxiv_id") or paper.get("doi")
                            if paper_id and paper_id not in visited_ids:
                                embedding = self.embedding_service.get_embedding(
                                    paper_id=paper_id,
                                    title=paper.get("title"),
                                    abstract=paper.get("abstract"),
                                )
                                if embedding is not None:
                                    candidate_embeddings[paper_id] = embedding

                        similarities = self.embedding_service.get_similarities(
                            main_embedding, candidate_embeddings
                        )
                        above_threshold = {
                            pid: score
                            for pid, score in similarities.items()
                            if score >= SIMILARITY_THRESHOLD
                        }
                        sorted_by_similarity = sorted(
                            above_threshold.items(),
                            key=lambda item: item[1],
                            reverse=True,
                        )
                        top_candidates = sorted_by_similarity[:TOP_K_AFTER_THRESHOLD]

                        for candidate_id, score in top_candidates:
                            paper_obj = next(
                                (
                                    p
                                    for p in new_papers_to_process
                                    if (
                                        p.get("arxiv_id")
                                        or p.get("doi")
                                        or p.get("openalex_id")
                                    )
                                    == candidate_id
                                ),
                                None,
                            )
                            if paper_obj:
                                print(
                                    f"  + SELECTION: Yes (Similarity: {score:.2f}). Adding '{paper_obj.get('title')}' to queue."
                                )
                                papers_to_add_to_queue.append(paper_obj)

                elif self.selection_mode == "abstract":
                    BATCH_SIZE = 20
                    num_batches = math.ceil(len(new_papers_to_process) / BATCH_SIZE)
                    print(
                        f"Performing BATCH selection on {len(new_papers_to_process)} candidates in {num_batches} batches using ABSTRACTS."
                    )

                    for i in range(num_batches):
                        batch = new_papers_to_process[
                            i * BATCH_SIZE : (i + 1) * BATCH_SIZE
                        ]
                        print(f"\n--- Processing Batch {i+1}/{num_batches} ---")

                        candidate_abstracts_str = "\n\n".join(
                            [
                                f"ID: {p.get('arxiv_id') or p.get('doi') or p.get('openalex_id')}\nTitle: {p.get('title')}\nAbstract: {p.get('abstract', 'N/A')}"
                                for p in batch
                                if p.get("arxiv_id")
                                or p.get("doi")
                                or p.get("openalex_id")
                            ]
                        )
                        result = await self.ranking_agent.execute(
                            self.llm_router,
                            {
                                "query_paper": main_paper_abstract,
                                "reference_papers": candidate_abstracts_str,
                            },
                            [],
                        )
                        probability_matches = re.findall(
                            r"<probability>\s*\[?(.*?)\]?:\s*(\d+)\s*</probability>",
                            result.get("response", ""),
                        )

                        for candidate_id, prob_str in probability_matches:
                            if int(prob_str) >= PROBABILITY_THRESHOLD:
                                paper_obj = next(
                                    (
                                        p
                                        for p in batch
                                        if (p.get("arxiv_id") or p.get("doi"))
                                        or p.get("openalex_id") == candidate_id
                                    ),
                                    None,
                                )
                                if paper_obj:
                                    print(
                                        f"  + SELECTION: Yes (Prob: {prob_str}%). Adding '{paper_obj.get('title')}' to queue."
                                    )
                                    papers_to_add_to_queue.append(paper_obj)

                elif self.selection_mode == "full-text":
                    print(
                        f"Performing ITERATIVE selection on {len(new_papers_to_process)} candidates using FULL TEXT."
                    )
                    for paper in new_papers_to_process:
                        paper_id = paper.get("arxiv_id") or paper.get("doi")
                        if paper_id in visited_ids:
                            continue

                        print(
                            f"  ? Selecting paper for expansion: '{paper.get('title')}'"
                        )
                        pdf_map = self.fetcher_service.fetch_pdfs([paper_id])
                        pdf_path = pdf_map.get(paper_id)
                        if not pdf_path:
                            print(f"  - SELECTION: Skip. Could not fetch PDF.")
                            continue

                        candidate_text = extract_text_from_pdf(pdf_path)
                        result = await self.full_text_selection_agent.execute(
                            self.llm_router,
                            {
                                "query_paper": main_paper_full_text,
                                "candidate_paper": candidate_text,
                            },
                            [],
                        )
                        prob_match = re.search(
                            r"<probability>.*?(\d+)\s*</probability>",
                            result.get("response", ""),
                        )
                        if (
                            prob_match
                            and int(prob_match.group(1)) >= PROBABILITY_THRESHOLD
                        ):
                            print(
                                f"  + SELECTION: Yes (Prob: {prob_match.group(1)}%). Adding to queue."
                            )
                            papers_to_add_to_queue.append(paper)
                        else:
                            print(f"  - SELECTION: No. Discarding irrelevant paper.")

                # Add all selected papers to the queue
                for paper_obj in papers_to_add_to_queue:
                    paper_id = paper_obj.get("arxiv_id") or paper_obj.get("doi")
                    if paper_id and paper_id not in visited_ids:
                        visited_ids.add(paper_id)
                        final_papers_map[paper_id] = paper_obj
                        queue.append((paper_obj, current_depth + 1))
                        if len(final_papers_map) >= MAX_TOTAL_PAPERS:
                            break
                    if len(final_papers_map) >= MAX_TOTAL_PAPERS:
                        break

        print(
            f"\n--- Deep Research Expansion Complete. Found {len(final_papers_map)} total papers. ---"
        )
        return list(final_papers_map.values())

    async def run(self) -> str:
        print(f"\n--- Starting LitLLM Process for: {self.pdf_path} ---")

        if str(self.pdf_path).endswith(".md"):
            # do some further preprocessing of the title
            # eg. 2506.17039v1.LSCD__Lomb_Scargle_Conditioned_Diffusion_for_Time_series_Imputation.md
            with open(self.pdf_path, "r", encoding="utf-8") as f:
                paper_text = clean_markdown(f.read())
        elif str(self.pdf_path).endswith(".pdf"):
            paper_text = extract_text_from_pdf(self.pdf_path)
        print("\n--- Step 1: Extracting Keywords ---")
        kw_result = await self.keyword_agent.execute(
            self.llm_router, {"paper_text": paper_text}, []
        )
        try:
            response = kw_result.get("response", "{}")
            json_content = parse_llm_json_response(response)
            queries = json_content.get("queries", [])
            print(f"Generated queries: {queries}")
            self.save_output("1_generated_queries", json.dumps(queries, indent=2))
        except (json.JSONDecodeError, AttributeError):
            print(f"Error decoding JSON for keyword extraction.")
            return "Error: LitLLM failed during keyword extraction."

        if not queries:
            print("No search queries generated. Exiting.")
            return

        print("\n--- Step 2: Fetching Papers ---")
        fetched_papers = self.fetcher_service.search_papers(
            queries=queries,
            api="semanticscholar",
            limit_per_query=5,
        )
        len_before = len(fetched_papers)
        # remove main paper from fetched papers if it exists
        fetched_papers = [
            p
            for p in fetched_papers
            if re.sub(r"\s+", " ", p.get("title").lower())
            != re.sub(r"\s+", " ", self.main_paper_title.lower())
        ]
        len_after = len(fetched_papers)
        if len_after < len_before:
            print("Removed main paper from fetched papers.")

        if self.deep_research:
            main_paper_data_list = self.fetcher_service.search_papers(
                queries=[self.main_paper_title], limit_per_query=1
            )
            if not main_paper_data_list:
                print(
                    f"CRITICAL ERROR: Could not fetch metadata for the main paper: {self.main_paper_title}"
                )
                return "Error: Could not resolve main paper metadata."
            main_paper_data = main_paper_data_list[0]

            fetched_papers = await self._run_deep_research(
                main_paper_data, fetched_papers
            )

        self.fetched_papers_path = self.save_output(
            "2_fetched_papers", json.dumps(fetched_papers, indent=2)
        )

        if not fetched_papers:
            print("No papers fetched. Exiting.")
            return

        print("\n--- Step 3: Ranking Papers ---")
        reference_papers_text = "\n\n".join(
            [
                f"arxiv id: {p.get('arxiv_id') or p.get('doi') or p.get('openalex_id')}\nTitle: {p.get('title')}\nAbstract: {p.get('abstract', 'N/A')}"
                for p in fetched_papers
            ]
        )
        ranking_result = await self.ranking_agent.execute(
            self.llm_router,
            {"query_paper": paper_text, "reference_papers": reference_papers_text},
            [],
        )
        ranking_output = ranking_result.get(
            "response", "Error: Could not generate rankings."
        )
        self.save_output("3_ranked_papers", ranking_output)

        print("\n--- Step 4: Summarizing Fetched Papers for Context ---")
        paper_ids = [
            p.get("arxiv_id") or p.get("doi")
            for p in fetched_papers
            if p.get("arxiv_id") or p.get("doi")
        ]
        pdf_path_dict = self.fetcher_service.fetch_pdfs(paper_ids)
        related_pdf_paths = list(pdf_path_dict.values())

        if not related_pdf_paths:
            print("No PDFs were fetched, returning empty summary.")
            return "No related papers could be summarized."

        tasks = [
            self.summary_agent.execute(self.llm_router, {}, files=[path])
            for path in related_pdf_paths
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        summaries = [
            (
                res.get("response", f"Error summarizing.")
                if not isinstance(res, Exception)
                else f"Error: {res}"
            )
            for res in results
        ]
        final_summary_string = "\n\n---\n\n".join(summaries)
        self.save_output("4_related_papers_summary", final_summary_string)

        print("\n--- LitLLM Process Complete ---")
        return final_summary_string

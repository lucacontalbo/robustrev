# src/agents/metareviewer/types/composite.py

import os
import re
import json
from dotenv import load_dotenv
from typing import List, Dict, Any, Optional

from src.agents.reviewer.types.base import BaseReviewer
from src.prompts.structures import MetareviewerPrompts
from ..components import (
    InitialStanceAgent,
    KeyPointsAgent,
    RebuttalAnalysisAgent,
    FactExtractionAgent,
    FactVerificationAgent,
    FactSignificanceAgent,
    FinalSynthesisAgent,
)


class CompositeMetareviewer(BaseReviewer):
    def __init__(
        self,
        strategy: str,
        mode: str,
        pdf_path: str,
        reviews_dir: str,
        metareviews_output_dir: str,
        model_name: str,
        prompts: MetareviewerPrompts,
        closest_paper_summary: Optional[str] = None,
        author_rebuttal_text: Optional[str] = None,
        ingest_models: Optional[List[str]] = None,
        **kwargs,
    ):
        super().__init__(strategy, mode, pdf_path, metareviews_output_dir, model_name)
        load_dotenv()
        self.reviews_dir = reviews_dir
        self.closest_paper_summary = closest_paper_summary
        self.author_rebuttal_text = author_rebuttal_text
        self.ingest_models = ingest_models or []
        if "post_rebuttal_discussion_text" in kwargs:
            self.post_rebuttal_discussion_text = kwargs["post_rebuttal_discussion_text"]

        self.pipeline_agents = {
            "initial_stance": InitialStanceAgent(
                model_name,
                prompts.initial_stance.system,
                prompts.initial_stance.user,
            ),
            "key_points": KeyPointsAgent(
                model_name,
                prompts.key_points.system,
                prompts.key_points.user,
            ),
            "rebuttal_analysis": RebuttalAnalysisAgent(
                model_name,
                prompts.rebuttal_analysis.system,
                prompts.rebuttal_analysis.user,
            ),
            "fact_extraction": FactExtractionAgent(
                model_name,
                prompts.fact_extraction.system,
                prompts.fact_extraction.user,
            ),
            "fact_verification": FactVerificationAgent(
                model_name,
                prompts.fact_verification.system,
                prompts.fact_verification.user,
            ),
            "fact_significance": FactSignificanceAgent(
                model_name,
                prompts.fact_significance.system,
                prompts.fact_significance.user,
            ),
            "final_synthesis": FinalSynthesisAgent(
                model_name,
                prompts.final_synthesis.system,
                prompts.final_synthesis.user,
            ),
        }

    def _consolidate_fact_reports(
        self, verification_report_str: str, significance_report_str: str
    ) -> str:
        """Parses the verification and significance text files and merges them into a single markdown report."""
        try:
            verified_facts = json.loads(verification_report_str).get(
                "verified_facts", []
            )
            verification_map = {fact["id"]: fact for fact in verified_facts}
        except (json.JSONDecodeError, AttributeError):
            verification_map = {}

        significance_lines = significance_report_str.strip().split("\n")
        significance_map = {}
        for line in significance_lines:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 2:
                significance_map[parts[0]] = {
                    "level": parts[1],
                    "justification": parts[2] if len(parts) > 2 else "",
                }

        if not verification_map:
            return (
                "No verifiable facts were found or the verification report was empty."
            )

        report_lines = ["# Consolidated Fact-Checking Report\n"]
        for fact_id, verification_data in verification_map.items():
            significance_data = significance_map.get(
                fact_id, {"level": "[N/A]", "justification": "Not assessed"}
            )

            report_lines.append(f"## Fact ID: {fact_id}")
            report_lines.append(
                f"- **Verdict:** `{verification_data.get('verdict', 'N/A')}`"
            )
            report_lines.append(
                f"- **Significance:** `{significance_data.get('level', 'N/A')}`"
            )
            report_lines.append(
                f"- **Justification (Significance):** {significance_data.get('justification', 'N/A')}"
            )
            report_lines.append(
                f"- **Evidence Quote (Verification):** \"{verification_data.get('evidence_quote', 'N/A')}\""
            )
            report_lines.append("---")

        return "\n".join(report_lines)

    async def run(self):
        print(
            f"\n--- Starting Metareview Process for: {os.path.basename(self.pdf_path)} ---"
        )

        paper_data = self._ingest_review_data(ingest_models=self.ingest_models)
        if not paper_data.review_instances:
            print(f"Error: No valid review instances found in {self.reviews_dir}")
            return

        all_initial_reviews_text = paper_data.to_llm_text()

        # This will hold the raw text outputs of each stage
        metareview_reports: Dict[str, Any] = {
            "all_initial_reviews_text": all_initial_reviews_text
        }

        # We need a list containing the original PDF path to pass to the execute method
        original_paper_file = [self.pdf_path]

        print("Running Metareview Pipeline Stages...")
        # Stage 1: Initial Stance (usually doesn't need the PDF, but we pass it for consistency)
        stance_agent = self.pipeline_agents["initial_stance"]
        result = await stance_agent.execute(
            self.llm_router, metareview_reports, files=original_paper_file
        )
        stance_report = result.get(
            "response", "Error: Could not generate initial stance summary."
        )
        metareview_reports["initial_stance_report"] = stance_report
        self.save_output(
            "1_initial_stance", stance_report, ingest_models=self.ingest_models
        )

        # Stage 2: Key Points Synthesis
        points_agent = self.pipeline_agents["key_points"]
        result = await points_agent.execute(
            self.llm_router, metareview_reports, files=original_paper_file
        )
        key_points_report = result.get(
            "response", "Error: Could not synthesize key points."
        )
        metareview_reports["key_points_report"] = key_points_report
        self.save_output(
            "2_key_points", key_points_report, ingest_models=self.ingest_models
        )

        # Placeholder for future rebuttal stage
        metareview_reports["author_rebuttal_text"] = (
            self.author_rebuttal_text or "No rebuttal text provided."
        )
        if hasattr(self, "post_rebuttal_discussion_text"):
            metareview_reports["post_rebuttal_discussion_text"] = (
                self.post_rebuttal_discussion_text
            )
        else:
            metareview_reports["post_rebuttal_discussion_text"] = (
                "No post-rebuttal discussion provided."
            )

        # Stage 3: Rebuttal Analysis (using placeholders and previous text reports)
        rebuttal_agent = self.pipeline_agents["rebuttal_analysis"]
        result = await rebuttal_agent.execute(
            self.llm_router, metareview_reports, files=original_paper_file
        )
        rebuttal_analysis_report = result.get(
            "response", "Error: Could not analyze rebuttal."
        )
        metareview_reports["rebuttal_analysis_report"] = rebuttal_analysis_report
        self.save_output(
            "3_rebuttal_analysis",
            rebuttal_analysis_report,
            ingest_models=self.ingest_models,
        )

        # Stage 4: Fact Extraction from all gathered text
        print("\n--- Metareview Stage 4: Extracting Factual Claims ---")
        extraction_agent = self.pipeline_agents["fact_extraction"]
        result = await extraction_agent.execute(
            self.llm_router, metareview_reports, files=original_paper_file
        )

        raw_extraction_output = result.get("response", "")

        # Parse the raw text into a simple list of strings.
        extracted_statements = re.findall(r"\[FACT\]:\s*(.*)", raw_extraction_output)

        print(f"Extracted {len(extracted_statements)} facts from review text.")

        # We can still save the raw output for debugging if we want.
        self.save_output(
            "4_fact_extraction_raw",
            raw_extraction_output,
            ingest_models=self.ingest_models,
        )

        # Stage 5: Fact Verification against the original paper
        print("\n--- Metareview Stage 5: Verifying Factual Claims ---")

        if extracted_statements:  # Check if the list of strings is not empty
            verification_agent = self.pipeline_agents["fact_verification"]

            line_by_line_facts = "\n".join(
                [
                    f"fact_{i+1:02d}: {statement.strip()}"
                    for i, statement in enumerate(extracted_statements)
                ]
            )

            verification_kwargs = {
                "line_by_line_facts": line_by_line_facts,
                "closest_papers_summary": self.closest_paper_summary or "Not Available",
            }

            result = await verification_agent.execute(
                self.llm_router, verification_kwargs, files=[self.pdf_path]
            )

            raw_verification_output = result.get(
                "response", "Error: Could not verify facts."
            )

            # The regex parsing of the output remains the same, as it produces the final structured data.
            verified_facts_list = []
            verification_pattern = re.compile(
                r"^(fact_\d+)\s*\|\s*\[(TRUE|FALSE|NOT VERIFIABLE)\]\s*\|\s*(.*?)\s*\|\s*(.*)$",
                re.MULTILINE,
            )

            for match in verification_pattern.finditer(raw_verification_output):
                verified_facts_list.append(
                    {
                        "id": match.group(1).strip(),
                        "verdict": match.group(2).strip(),
                        "justification": match.group(3).strip(),
                        "evidence_quote": match.group(4).strip().strip('"'),
                    }
                )

            print(f"Verified {len(verified_facts_list)} facts.")

            # We still create a clean JSON report as the final artifact of this stage.
            verified_facts_report = json.dumps(
                {"verified_facts": verified_facts_list}, indent=2
            )
            metareview_reports["fact_verification"] = verified_facts_report
            self.save_output(
                "5_fact_verification",
                verified_facts_report,
                ingest_models=self.ingest_models,
            )
        else:
            print("Skipping fact verification as no facts were extracted.")
            metareview_reports["fact_verification"] = (
                "No facts were extracted to verify."
            )

        # Stage 6: Fact Significance Analysis
        print("\n--- Metareview Stage 6: Analyzing Fact Significance ---")
        if (
            metareview_reports.get("fact_verification")
            and metareview_reports["fact_verification"]
            != "No facts were extracted to verify."
        ):
            significance_agent = self.pipeline_agents["fact_significance"]

            significance_kwargs = {
                "verified_facts_report": metareview_reports["fact_verification"]
            }

            result = await significance_agent.execute(
                self.llm_router,
                significance_kwargs,
                files=[self.pdf_path],
            )

            raw_significance_output = result.get("response", "")
            metareview_reports["fact_significance"] = raw_significance_output
            self.save_output(
                "6_fact_significance",
                raw_significance_output,
                ingest_models=self.ingest_models,
            )
        else:
            print("Skipping fact significance analysis as no facts were verified.")
            metareview_reports["fact_significance"] = (
                "No facts were verified to analyze for significance."
            )

        # --- Stage 6b: Consolidate Fact Reports ---
        print("\n--- Metareview Stage 6b: Consolidating Fact Reports ---")
        fact_verification_report_str = metareview_reports.get("fact_verification", "{}")
        fact_significance_report_str = metareview_reports.get("fact_significance", "")

        consolidated_report = self._consolidate_fact_reports(
            fact_verification_report_str, fact_significance_report_str
        )
        self.save_output(
            "6b_consolidated_facts",
            consolidated_report,
            ingest_models=self.ingest_models,
        )

        # --- Stage 7: Final Synthesis (with Structured Inputs) ---
        print("\n--- Metareview Stage 7: Final Synthesis ---")
        synthesis_agent = self.pipeline_agents["final_synthesis"]

        # Build a dictionary of named arguments for the prompt template.
        # This is far more robust than a single giant string.
        synthesis_kwargs = {
            "consolidated_fact_report": consolidated_report,
            "initial_stance_report": metareview_reports.get(
                "initial_stance_report", "Not generated."
            ),
            "key_points_report": metareview_reports.get(
                "key_points_report", "Not generated."
            ),
            "rebuttal_analysis_report": metareview_reports.get(
                "rebuttal_analysis_report", "Not generated."
            ),
            "all_initial_reviews_text": metareview_reports.get(
                "all_initial_reviews_text", "Not available."
            ),
        }

        result = await synthesis_agent.execute(
            self.llm_router, synthesis_kwargs, files=[self.pdf_path]
        )

        final_synthesis_report = result.get(
            "response", "Error: Could not generate final synthesis."
        )
        self.save_output(
            "7_final_synthesis",
            final_synthesis_report,
            ingest_models=self.ingest_models,
        )

        print("\n--- Metareview Process Complete ---")

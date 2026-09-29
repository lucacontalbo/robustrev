import os
import re
from typing import List, Dict, Any, Optional, Tuple
from dotenv import load_dotenv

from src.services.openai_like_service import OpenAILikeService, REASONING_MODELS

load_dotenv()

SYSTEM_PROMPT_WRAPPER = """
You are a highly advanced, meticulous, and critical-thinking AI assistant. Your primary directive is to provide deep, analytical, and well-reasoned responses. You must adhere to the following rules for EVERY request:

1.  **Think First (Chain-of-Thought):** Before generating your final answer, you MUST use <think> block to reason through the user's request. In this block, you will break down the problem, analyze the provided sources, identify key facts and claims, and formulate a plan for your response. Do not take any information at face value; question assumptions and verify claims against the provided sources.

2.  **Cite Your Sources with Evidence:** Your final response, outside the <think> block, MUST attribute every key piece of information to its origin using a specific citation tag described below.
    - The format is: <citation source="[filename]">[verbatim quote]</citation>
    - The `source` attribute MUST contain the exact filename from where you extracted the information.
    - The content of the tag MUST be the direct, verbatim quote from the source that supports your statement.
    - Place the citation tag *immediately* after the statement it supports.

    **Good Example:**
    The authors used the AdamW optimizer <citation source="paper_text">We use the AdamW optimizer (Loshchilov & Hutter, 2017) with a learning rate of 0.001.</citation>.

    **Bad Example (Do NOT do this):**
    The authors used AdamW [SOURCE: paper_text].

3.  **Fulfill the Original Role:** After your critical analysis, you must adopt the specific role described in the original system prompt below and provide a response that fulfills its instructions, while still adhering to the thinking and citation rules above.

--- ORIGINAL SYSTEM PROMPT ---
{original_system_prompt}
"""

USER_PROMPT_WRAPPER = """
Based on your analysis, please perform the following task. Remember to use the <think> block first and provide structured, evidence-based citations in your final response.

{formatted_original_user_prompt}
"""


class LLMServiceRouter:
    def __init__(self):
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        self.ollama_api_key = "ollama"  # not used but needed by OpenAI SDK

        self.vllm_base_url = os.getenv("VLLM_BASE_URL", "http://localhost:8085/v1")
        self.vllm_api_key = "vllm"  # VLLM doesn't require a key by default

    async def route_completion_request(
        self,
        model_name: str,
        system_prompt: str,
        user_prompt_template: str,
        files: Optional[List[str]] = None,
        use_reasoning: bool = False,
        reasoning_effort: str = "medium",
        logprobs: bool = False,
        top_logprobs: int = 5,
        prompt_format_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        service_instance: OpenAILikeService
        actual_model_name_for_api = model_name

        pass_through_use_reasoning: bool

        is_native_reasoning_model = model_name in REASONING_MODELS
        # final_system_prompt = SYSTEM_PROMPT_WRAPPER.format(
        #     original_system_prompt=system_prompt
        # )
        # final_user_prompt_template = USER_PROMPT_WRAPPER.format(
        #     formatted_original_user_prompt=user_prompt_template
        # )

        final_system_prompt = system_prompt
        final_user_prompt_template = user_prompt_template

        if use_reasoning and is_native_reasoning_model:
            pass_through_use_reasoning = True
        else:
            pass_through_use_reasoning = False

        # Determine the service client configuration and actual model name for the API
        if model_name.startswith("openrouter"):  # OpenRouter
            actual_model_name_for_api = model_name.split("/", 1)[1]
            if not self.openrouter_api_key:
                raise ValueError(
                    "OPENROUTER_API_KEY not set, but an OpenRouter model was requested."
                )
            service_instance = OpenAILikeService(
                api_key=self.openrouter_api_key, base_url="https://openrouter.ai/api/v1"
            )

        elif model_name.startswith(
            "gemini"
        ):  # Google Gemini (using OpenAI SDK compatibility)
            if not self.gemini_api_key:
                raise ValueError(
                    "GEMINI_API_KEY not set, but a Gemini model was requested."
                )
            service_instance = OpenAILikeService(
                api_key=self.gemini_api_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",  # From original FastAPI app
            )
            actual_model_name_for_api = model_name

        elif model_name.startswith("ollama/"):  # Ollama
            # The model name for the API is the part after "ollama/"
            # e.g., "ollama/mistralai/Mistral-7B-Instruct-v0.2" -> "mistralai/Mistral-7B-Instruct-v0.2"
            actual_model_name_for_api = model_name.split("/", 1)[1]
            service_instance = OpenAILikeService(
                api_key=self.ollama_api_key, base_url=self.ollama_base_url
            )

        elif model_name.startswith("vllm/"):  # VLLM
            actual_model_name_for_api = model_name.split("/", 1)[1]
            service_instance = OpenAILikeService(
                api_key=self.vllm_api_key, base_url=self.vllm_base_url
            )
        elif model_name.startswith("vllm2"):
            actual_model_name_for_api = model_name.split("/", 1)[1]
            service_instance = OpenAILikeService(
                api_key=self.vllm_api_key, base_url="http://localhost:8001/v1"
            )

        elif model_name.startswith("vllm4"):
            actual_model_name_for_api = model_name.split("/", 1)[1]
            service_instance = OpenAILikeService(
                api_key=self.vllm_api_key, base_url="http://localhost:8003/v1"
            )

        else:  # Default to standard OpenAI service
            if not self.openai_api_key:
                raise ValueError(
                    "OPENAI_API_KEY not set, but an OpenAI model was requested."
                )
            service_instance = OpenAILikeService(api_key=self.openai_api_key)
            actual_model_name_for_api = model_name

        return await service_instance.get_completion(
            model_name_for_api=actual_model_name_for_api,
            original_model_requested=model_name,  # Pass the original name for nuanced logic within service
            system_prompt=final_system_prompt,
            user_prompt_template=final_user_prompt_template,
            files=files,
            use_reasoning=pass_through_use_reasoning,
            reasoning_effort=reasoning_effort,
            prompt_format_kwargs=prompt_format_kwargs,
            logprobs=logprobs,
            top_logprobs=top_logprobs,
        )

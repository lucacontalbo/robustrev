import os
import re
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI, BadRequestError

# from fastapi import HTTPException # If used in FastAPI context, otherwise remove/replace

from src.services.base_llm_service import BaseLLMService
from src.utils.file_utils import (
    encode_file_to_base64,
    get_mime_type,
    extract_text_from_pdf,
    clean_markdown,
)

# List of models supporting the "reasoning_effort" parameter (from original FastAPI app)
REASONING_MODELS = [
    "o4-mini",
    "o3-mini",
    "o3",
    "o3-2025-04-16",
    "gemini-2.5-flash-preview-05-20",
    "gemini-2.5-pro-preview-05-06",
    "openrouter/microsoft/phi-4-reasoning:free",
    "openrouter/microsoft/phi-4-reasoning-plus:free",
    "openrouter/qwen/qwen3-4b:free",
    "openrouter/qwen/qwen3-32b:free",
    "openrouter/qwen/qwen3-14b:free",
    "openrouter/qwen/qwen3-235b-a22b:free",
    "openrouter/google/gemini-2.5-pro",
    "openrouter/meta-llama/llama-4-maverick:free",
    "openrouter/meta-llama/llama-4-scout:free",
    "openrouter/nvidia/llama-3.1-nemotron-ultra-253b-v1:free",
    "openrouter/minimax/minimax-m1:extended",
    "vllm/Qwen/Qwen3-14B",
    "vllm/Qwen/Qwen3-32B",
    "vllm/Qwen/Qwen3-235B-A22B",
    "vllm/openai/gpt-oss-120b",
    "vllm2/openai/gpt-oss-120b",
    "vllm4/microsoft/Phi-4-reasoning-plus",
]


class OpenAILikeService(BaseLLMService):
    def __init__(self, api_key: Optional[str], base_url: Optional[str] = None):
        """
        Initializes an OpenAI-like service client.
        Args:
            api_key: The API key for the service.
            base_url: The base URL for the service (if not default OpenAI).
        """
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    async def get_completion(
        self,
        model_name_for_api: str,
        original_model_requested: str,
        system_prompt: str,
        user_prompt_template: str,
        files: Optional[List[str]] = None,
        use_reasoning: bool = False,
        reasoning_effort: str = "medium",
        logprobs: bool = False,
        top_logprobs: int = 5,
        prompt_format_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        system_prompt = re.sub(
            r"<think>.*?</think>", "", system_prompt, flags=re.DOTALL
        )
        api_params: Dict[str, Any] = {}
        messages = [{"role": "system", "content": system_prompt}]
        user_content_items: List[Dict[str, Any]] = []
        current_user_prompt_text = user_prompt_template

        if prompt_format_kwargs is None:
            prompt_format_kwargs = {}

        # Process files
        if files:
            for file_path in files:
                if not os.path.exists(file_path):
                    print(f"Warning: File {file_path} not found, skipping.")
                    continue

                mime_type = get_mime_type(file_path)
                filename = os.path.basename(file_path)

                if mime_type == "application/pdf":
                    pdf_text_content = extract_text_from_pdf(file_path)
                    if "paper_text" not in prompt_format_kwargs:
                        prompt_format_kwargs["paper_text"] = pdf_text_content
                    else:
                        current_user_prompt_text += f"\n\n--- Content of {filename} ---\n{pdf_text_content}\n--- End of {filename} ---"
                elif mime_type == "text/markdown":
                    md_content = clean_markdown(open(file_path).read())
                    if "paper_text" not in prompt_format_kwargs:
                        prompt_format_kwargs["paper_text"] = md_content
                    else:
                        current_user_prompt_text += f"\n\n--- Content of {filename} ---\n{md_content}\n--- End of {filename} ---"

                elif mime_type.startswith("image/"):
                    base64_data = encode_file_to_base64(file_path)
                    data_url = f"data:{mime_type};base64,{base64_data}"
                    user_content_items.append(
                        {"type": "image_url", "image_url": {"url": data_url}}
                    )

        def build_request_params():
            # Ensure placeholder for paper_text if needed
            local_prompt_kwargs = prompt_format_kwargs.copy()
            if (
                "paper_text" not in local_prompt_kwargs
                and "{paper_text}" in current_user_prompt_text
            ):
                local_prompt_kwargs.setdefault(
                    "paper_text", "[Paper text not available or not applicable.]"
                )

            final_user_prompt_text = current_user_prompt_text.format(
                **local_prompt_kwargs
            )
            final_user_prompt_text = re.sub(
                r"<think>.*?</think>", "", final_user_prompt_text, flags=re.DOTALL
            )

            # Rebuild content items list for this request
            current_content_items = list(user_content_items)  # Start with images
            current_content_items.insert(
                0, {"type": "text", "text": final_user_prompt_text}
            )

            final_user_content: Any
            if (
                len(current_content_items) == 1
                and current_content_items[0]["type"] == "text"
            ):
                final_user_content = current_content_items[0]["text"]
            else:
                final_user_content = current_content_items

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": final_user_content},
            ]

            api_params: Dict[str, Any] = {
                "model": model_name_for_api,
                "messages": messages,
                "response_format": {"type": "text"},
            }

            if use_reasoning and original_model_requested in REASONING_MODELS:
                api_params["reasoning_effort"] = reasoning_effort
            else:
                if "reasoning_effort" not in api_params:
                    api_params.update(
                        {"temperature": 0.7, "max_tokens": 20000, "top_p": 1.0}
                    )
            if logprobs:
                api_params.update({"logprobs": logprobs, "top_logprobs": top_logprobs})
            return api_params, messages

        try:
            # --- First Attempt ---
            api_params, messages = build_request_params()
            response = await self.client.chat.completions.create(**api_params)

        except BadRequestError as e:
            # Check if the error is specifically about context length
            if "maximum context length" in str(e).lower():
                print(
                    "Context length error. Attempting a single retry with truncated text."
                )

                # Truncate the paper_text for the retry
                current_paper_text = prompt_format_kwargs.get("paper_text", "")
                if not current_paper_text or len(current_paper_text) < 100:
                    print("Cannot truncate 'paper_text' further. Aborting.")
                    raise e  # Re-raise original error if text is missing or too short

                truncate_at = len(current_paper_text) // 2
                prompt_format_kwargs["paper_text"] = current_paper_text[:truncate_at]

                # --- Second and Final Attempt ---
                # Rebuild parameters with truncated text and make the call.
                # If this call fails, the exception will propagate up as intended.
                api_params, messages = build_request_params()
                response = await self.client.chat.completions.create(**api_params)

            else:
                # It was a different BadRequestError, so re-raise it.
                print(f"Encountered a non-context-length BadRequestError: {e}")
                return

        except Exception as e:
            print(
                f"Error calling LLM API for model {model_name_for_api} (originally {original_model_requested}): {e}"
            )
            return

        dict_to_return = {
            "response": response.choices[0].message.content,
            "input_prompt": messages,
            "model_used": original_model_requested,  # Report back the user-friendly model name
            "finish_reason": response.choices[0].finish_reason,
            "usage": response.usage.model_dump() if response.usage else None,
        }
        if use_reasoning:
            dict_to_return.update(
                {"reasoning": response.choices[0].message.reasoning_content}
            )
        if logprobs:
            dict_to_return.update({"logprobs": response.choices[0].logprobs})

        return dict_to_return

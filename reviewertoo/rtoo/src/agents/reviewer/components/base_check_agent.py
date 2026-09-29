from abc import ABC
import json, asyncio
from typing import Dict, Any, Optional, List
from src.services.llm_service_router import LLMServiceRouter
from src.utils.parser_utils import parse_llm_json_response


class BaseCheckAgent(ABC):
    """
    The base class for any individual component agent (e.g., SoundnessCheckAgent, NoveltyCheckAgent).
    It handles the direct interaction with the LLM service.
    """

    def __init__(
        self,
        model_name: str,
        system_prompt: str,
        user_prompt_template: str,
    ):
        self.model_name = model_name
        self.system_prompt = system_prompt
        self.user_prompt_template = user_prompt_template

    async def execute(
        self,
        llm_router: LLMServiceRouter,
        prompt_format_kwargs: Dict[str, Any],
        files: Optional[List[str]] = None,
        use_reasoning: bool = False,
        reasoning_effort: str = "medium",
        logprobs: bool = False,
        top_logprobs: int = 5,
        max_retries: int = 3,
        expect_json: bool = False,
    ) -> Dict[str, Any]:

        escaped_kwargs = {}
        for key, value in prompt_format_kwargs.items():
            if isinstance(value, str):
                # We escape the braces in the *values*, not the keys.
                # The prompt template itself is formatted later, so we only
                # need to protect the data being injected into it.
                escaped_kwargs[key] = value.replace("{", "{{").replace("}", "}}")
            else:
                # Keep non-string values (like numbers or lists) as they are.
                escaped_kwargs[key] = value
        for attempt in range(max_retries + 1):
            try:
                result = await llm_router.route_completion_request(
                    model_name=self.model_name,
                    system_prompt=self.system_prompt,
                    user_prompt_template=self.user_prompt_template,
                    files=files,
                    use_reasoning=use_reasoning,
                    reasoning_effort=reasoning_effort,
                    prompt_format_kwargs=escaped_kwargs,
                    logprobs=logprobs,
                    top_logprobs=top_logprobs,
                )
                # If we expect JSON, try to parse it. This is our validation step.
                if expect_json:
                    response_text = result.get("response", "")
                    if not response_text:
                        raise ValueError("LLM returned an empty response.")

                    # This will raise an exception on failure, triggering a retry
                    parsed_content = parse_llm_json_response(response_text)
                    result["json_content"] = parsed_content

                # If all checks pass, return the successful result
                return result
            except (json.JSONDecodeError, AttributeError, TypeError, ValueError) as e:
                last_exception = e
                print(
                    f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. Retrying..."
                )
                if attempt < max_retries:
                    await asyncio.sleep(1)  # Wait a moment before retrying
                continue
        print(f"All {max_retries + 1} attempts failed. Last error: {last_exception}")
        return {"response": "", "error": str(last_exception)}

    def get_prompts(self) -> Dict[str, Any]:
        return {
            "system_prompt": self.system_prompt,
            "user_prompt_template": self.user_prompt_template,
            "model_name": self.model_name,
        }

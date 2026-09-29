from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class BaseLLMService(ABC):
    @abstractmethod
    async def get_completion(
        self,
        model_name_for_api: str,  # The actual model name the target API expects
        original_model_requested: str,  # The model name the user/agent initially requested
        system_prompt: str,
        user_prompt_template: str,
        files: Optional[List[str]] = None,
        use_reasoning: bool = False,
        reasoning_effort: str = "medium",
        prompt_format_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Abstract method to get a completion from an LLM.

        Args:
            model_name_for_api: The specific model identifier for the target API.
            original_model_requested: The model identifier as requested by the agent/user (e.g. "ollama/mistral").
            system_prompt: The system prompt.
            user_prompt_template: The user prompt template (may contain placeholders).
            files: Optional list of file paths.
            use_reasoning: Flag to enable reasoning-specific parameters.
            reasoning_effort: Effort level for reasoning.
            prompt_format_kwargs: Arguments to format the user_prompt_template.

        Returns:
            A dictionary containing the LLM's response and metadata.
        """
        pass

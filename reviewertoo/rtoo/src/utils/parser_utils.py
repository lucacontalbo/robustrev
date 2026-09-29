import re
import json
from typing import Optional, Dict, Any, Union


def parse_llm_json_response(raw_response: str) -> Optional[Union[Dict[str, Any], list]]:
    """
    Robustly parses a JSON object or list from an LLM response string that may
    contain a <thinking> block and markdown code fences.

    Args:
        raw_response: The raw string output from the LLM.

    Returns:
        A dictionary or list if parsing is successful, otherwise None.
    """
    if not raw_response:
        return None

    # 1. Remove the <thinking> block completely to isolate the main content.
    # The re.DOTALL flag allows '.' to match newlines.
    cleaned_response = re.sub(
        r"<think>.*?</think>", "", raw_response, flags=re.DOTALL
    ).strip()

    # 2. Look for a JSON object inside markdown code fences.
    # This is the most common and reliable format.
    match = re.search(r"```(?:json)?\s*(.*)\s*```", cleaned_response, re.DOTALL)

    json_string = ""
    if match:
        # If a markdown block is found, use its content.
        json_string = match.group(1).strip()
    else:
        # If no markdown block, assume the cleaned response *might* be the JSON itself.
        # This handles cases where the LLM forgets the markdown fences.
        json_string = cleaned_response

    # 3. Find the first occurrence of '{' or '[' to trim any preceding text.
    first_brace = json_string.find("{")
    first_bracket = json_string.find("[")

    start_index = -1

    if first_brace == -1 and first_bracket == -1:
        # No JSON object or list found.
        return None
    elif first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
        start_index = first_brace
    else:
        start_index = first_bracket

    # Trim the string to start at the beginning of the JSON
    json_string = json_string[start_index:]

    # 4. Attempt to decode the extracted string.
    try:
        return json.loads(json_string)
    except json.JSONDecodeError as e:
        print(f"Warning: Failed to decode JSON. Error: {e}")
        print(f"Problematic JSON string (first 200 chars): {json_string[:200]}")
        return None

import importlib

# This registry is the single source of truth for mapping agent types
# and strategies to their Python classes and prompt configurations.
AGENT_CONFIG = {
    "reviewer": {
        "composite": {
            "class_path": "src.agents.reviewer.types.composite.CompositeReviewer",
            "prompt_key": "COMPOSITE_PROMPTS",
        },
        "monolithic": {
            "class_path": "src.agents.reviewer.types.monolithic.MonolithicReviewer",
            "prompt_key": "MONOLITHIC_PROMPTS",
        },
        "assistive_composite": {
            "class_path": "src.agents.reviewer.types.composite.CompositeReviewer",
            "class_name": "CompositeReviewer",
            "prompt_key": "ASSISTIVE_COMPOSITE_PROMPTS",
        },
        "assistive_monolithic": {
            "class_path": "src.agents.reviewer.types.monolithic.MonolithicReviewer",
            "class_name": "MonolithicReviewer",
            "prompt_key": "ASSISTIVE_MONOLITHIC_PROMPTS",
        },
        "rebuttal": {
            "class_path": "src.agents.reviewer.types.monolithic.MonolithicReviewer",
            "class_name": "MonolithicReviewer",
            "prompt_key": "REBUTTAL_PROMPTS",
        },
    },
    "metareviewer": {
        "composite": {
            "class_path": "src.agents.metareviewer.types.composite.CompositeMetareviewer",
            "class_name": "CompositeMetareviewer",
            "prompt_key": "METAREVIEWER_PROMPTS",
        },
        "assistive_composite": {
            "class_path": "src.agents.metareviewer.types.composite.CompositeMetareviewer",
            "class_name": "CompositeMetareviewer",
            "prompt_key": "ASSISTIVE_METAREVIEWER_PROMPTS",
        },
    },
    "litllm": {
        "composite": {
            "class_path": "src.agents.litllm.types.composite.CompositeLitLLMAgent",
            "class_name": "CompositeLitLLMAgent",
            "prompt_key": "LITLLM_PROMPTS",
        }
    },
    "evaluator": {
        "composite": {
            "class_path": "src.agents.evaluator.types.composite.CompositeEvaluatorAgent",
            "class_name": "CompositeEvaluatorAgent",
            "prompt_key": "EVALUATOR_PROMPTS",
        }
    },
    "author": {
        "composite": {
            "class_path": "src.agents.author.types.composite.CompositeAuthor",
            "class_name": "CompositeAuthor",
            "prompt_key": "AUTHOR_PROMPTS",
        }
    },
}


def get_agent_and_prompts(agent_type: str, strategy: str, mode: str):
    """
    The main factory function for creating agents and their prompt sets.

    Args:
        agent_type (str): The top-level agent (e.g., 'reviewer').
        strategy (str): The implementation type (e.g., 'composite', 'monolithic').
        mode (str): The personality/behavior (e.g., 'default', 'critical').

    Returns:
        A tuple of (AgentClass, prompts_dictionary).
    """
    # 1. Find the agent configuration from the registry
    type_config = AGENT_CONFIG.get(agent_type, {}).get(strategy)
    if not type_config:
        raise ValueError(
            f"No configuration found for agent '{agent_type}' with strategy '{strategy}'."
        )

    # 2. Dynamically load the prompt module for the given mode
    try:
        prompt_module_path = f"src.prompts.{agent_type}.{mode}"
        prompt_module = importlib.import_module(prompt_module_path, package=__package__)
    except ImportError:
        raise ValueError(
            f"Could not find prompt module for agent '{agent_type}' in mode '{mode}'. Check if '{prompt_module_path.replace('.', '/')}.py' exists."
        )

    # 3. Get the specific set of prompts from the loaded module using the key
    prompt_key = type_config["prompt_key"]
    prompts = getattr(prompt_module, prompt_key, None)
    if prompts is None:
        raise ValueError(
            f"Prompt key '{prompt_key}' not found in module '{prompt_module_path}'."
        )

    # 4. Dynamically load the agent class from its path
    module_path, class_name = type_config["class_path"].rsplit(".", 1)
    agent_module = importlib.import_module(module_path)
    agent_class = getattr(agent_module, class_name)

    return agent_class, prompts

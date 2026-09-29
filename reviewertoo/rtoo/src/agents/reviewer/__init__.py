from src.services.prompt_service import get_agent_and_prompts


def ReviewerAgent(
    strategy: str,
    mode: str,
    pdf_path: str,
    reviews_output_dir: str,
    model_name: str = "gpt-4o-mini",
    **kwargs,
):

    # Let the prompt service find the correct agent class and prompts
    agent_class, prompts = get_agent_and_prompts(
        agent_type="reviewer",
        strategy=strategy,
        mode=mode,
    )

    # Instantiate the agent class with all required arguments
    return agent_class(
        strategy=strategy,
        mode=mode,
        pdf_path=pdf_path,
        reviews_output_dir=reviews_output_dir,
        model_name=model_name,
        prompts=prompts,
        **kwargs,
    )

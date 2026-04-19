import asyncio
import logging
import os

# import signal

from dotenv import load_dotenv
from services.agent_with_mcp import agent_with_mcp
from services.agent_recommendation_products import agent_recommendation_products

load_dotenv()

logger = logging.getLogger("recommendation_agent")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


async def main(agent_type: str = "default", prompt: str = ""):
    """Main entry point for the recommendation agent.
    Args:
        agent_type (str): The type of agent to run. Defaults to "default".
        prompt (str): The prompt to provide to the agent. Defaults to an empty string.
    """
    logger.info(
        "Recommendation Agent starting (env=%s)", os.getenv("ENV", "development")
    )
    try:
        match agent_type:
            case "default":
                await agent_with_mcp(prompt)
            case "recommendation_products":
                await agent_recommendation_products(prompt)
            case _:
                raise ValueError(f"Unknown agent type: {agent_type}")

        logger.info("Recommendation Agent finalized successfully")
    except Exception as e:
        logger.exception("An error occurred: %s", str(e))
    finally:
        logger.info("Recommendation Agent stopped")


if __name__ == "__main__":
    """
    Example of running the agent with a prompt.
    The prompt asks for restaurant recommendations in New York City,
    and instructs the agent to save the results in a JSON file using
    the MCP file server.

    TODO: implement graceful shutdown handling (e.g., catching SIGINT)
    to allow the agent to clean up resources properly.
    TODO: implement pub/sub or event system to trigger agent execution
    based on external events instead of hardcoding the prompt in main.py.
    """
    prompt = """
        What are some good restaurants in New York City?
        Please provide the answer in a JSON format
        with the following structure:
            {
                "restaurants": [
                    {
                        "name": "Restaurant Name",
                        "cuisine": "Type of Cuisine",
                        "address": "Restaurant Address",
                        "rating": "Average Rating"
                    },
                    ...
                ]
            }
        save results in a file named "nyc_restaurants.json"
        using the provided MCP file server.
    """
    asyncio.run(main(agent_type="recommendation_products", prompt=prompt))

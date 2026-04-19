import asyncio
import logging
import os

# import signal

from dotenv import load_dotenv
from services.agent_with_mcp import agent_with_mcp

load_dotenv()

logger = logging.getLogger("recommendation_agent")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


async def main(agent_type: str = "default"):

    logger.info(
        "Recommendation Agent starting (env=%s)", os.getenv("ENV", "development")
    )

    try:

        match agent_type:
            case "default":
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
                await agent_with_mcp(prompt)
            case _:
                raise ValueError(f"Unknown agent type: {agent_type}")

        logger.info("Recommendation Agent finalized successfully")

    except Exception as e:
        logger.exception("An error occurred: %s", str(e))
    finally:
        logger.info("Recommendation Agent stopped")


if __name__ == "__main__":
    asyncio.run(main())

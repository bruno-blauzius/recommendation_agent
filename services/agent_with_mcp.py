from agents.mcp import MCPServerStdio

from agent_core.agent_openai import AgentOpenAI

from agent_core.agent_service import AgentService


async def agent_with_mcp(prompt: str):
    agent_openai = AgentOpenAI(name="recommendation_agent", model_name="gpt-4o-mini")

    async with MCPServerStdio(
        params={
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
        },
        client_session_timeout_seconds=30,
    ) as files_server:

        agent_service = AgentService(model_adapter=agent_openai)

        await agent_service.invoke(
            prompt=prompt,
            mcp_servers=[files_server],
        )

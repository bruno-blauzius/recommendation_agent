from agent_core.agent_openai import AgentOpenAI
from agent_core.agent_service import AgentService
from agent_core.mcp_server.servers import _get_mcp_file_server
from settings import _GPT_MODEL_TEXT


async def agent_with_mcp(prompt: str):
    files_server = await _get_mcp_file_server()
    agent_openai = AgentOpenAI(name="recommendation_agent", model_name=_GPT_MODEL_TEXT)
    agent_service = AgentService(model_adapter=agent_openai)
    return await agent_service.invoke(
        prompt=prompt,
        mcp_servers=[files_server],
    )

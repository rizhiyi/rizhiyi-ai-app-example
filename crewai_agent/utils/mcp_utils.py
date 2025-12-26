import os
import asyncio
import logging
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession
from ..config import LOG_TOOLS_SERVER_PATH

logger = logging.getLogger('crewai_agent')

def get_rizhiyi_server_params(base_url, api_key, username=None):
    """获取日志易 MCP 服务器参数"""
    # 构造 username:api-key 格式
    formatted_api_key = f"{username}:{api_key}" if username and api_key else (api_key or "")
    
    return StdioServerParameters(
        command="node",
        args=[LOG_TOOLS_SERVER_PATH] if LOG_TOOLS_SERVER_PATH else [],
        env={
            "LOGEASE_BASE_URL": base_url or "",
            "LOGEASE_API_KEY": formatted_api_key,
            "LOGEASE_TLS_REJECT_UNAUTHORIZED": os.getenv("LOGEASE_TLS_REJECT_UNAUTHORIZED", "false"),
            **os.environ
        }
    )

async def list_mcp_tools(params: StdioServerParameters):
    """列出指定 MCP 服务器的所有工具"""
    try:
        async with asyncio.timeout(10):
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools_result = await session.list_tools()
                    return [{
                        "name": t.name,
                        "description": t.description,
                        "input_schema": t.inputSchema
                    } for t in tools_result.tools]
    except Exception as e:
        logger.error(f"Error listing MCP tools: {e}")
        return []

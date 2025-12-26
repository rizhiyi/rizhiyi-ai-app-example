import asyncio
from django.http import JsonResponse
from ..config import RizhiyiOAuthConfig
from ..models import UserProfile
from crewai_agent.utils.mcp_utils import get_rizhiyi_server_params, list_mcp_tools

def mcp_list(request):
    """获取 MCP 服务器及其工具列表"""
    user_info = request.session.get('user_info')
    api_key = None
    username = None
    base_url = RizhiyiOAuthConfig.RIZHIYI_BASE_URL
    
    if user_info:
        username = user_info.get('name')
        try:
            profile = UserProfile.objects.get(rizhiyi_id=user_info['id'])
            api_key = profile.api_key
        except UserProfile.DoesNotExist:
            pass

    # 定义要检查的服务器
    servers_config = [
        {
            "id": "rizhiyi",
            "name": "Rizhiyi Log Search",
            "icon": "fa-search",
            "color": "#1890ff",
            "description": "日志易日志检索与分析服务。",
            "params": get_rizhiyi_server_params(base_url, api_key, username)
        }
    ]

    results = []
    for s in servers_config:
        try:
            # 使用 asyncio.run 在同步视图中运行异步任务
            tools = asyncio.run(list_mcp_tools(s['params']))
            results.append({
                "id": s['id'],
                "name": s['name'],
                "icon": s['icon'],
                "color": s['color'],
                "description": s['description'],
                "tools": tools,
                "connected": len(tools) > 0
            })
        except Exception as e:
            results.append({
                "id": s['id'],
                "name": s['name'],
                "icon": s['icon'],
                "color": s['color'],
                "description": s['description'],
                "tools": [],
                "connected": False,
                "error": str(e)
            })

    return JsonResponse({"servers": results})

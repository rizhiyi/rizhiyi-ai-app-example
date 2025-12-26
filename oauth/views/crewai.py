import json
import uuid
import threading
import logging
from django.shortcuts import render, redirect, reverse
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from ..config import RizhiyiOAuthConfig
from ..models import UserProfile
from crewai_agent.agent import run_crew
from crewai_agent.config import agent_runs

logger = logging.getLogger('oauth')

def crewai_demo(request):
    """演示 crewAI 智能体"""
    code = request.GET.get('code')
    if code:
        # 如果携带 code 访问，重定向到 callback 处理，并告知处理完跳回这里
        callback_url = reverse('callback')
        query_params = request.GET.copy()
        query_params['next'] = reverse('crewai_demo')
        return redirect(f"{callback_url}?{query_params.urlencode()}")
        
    query = request.GET.get('query', 'Why am I seeing error 500 in the logs?')
    return render(request, 'oauth/crewai.html', {'query': query})

@csrf_exempt
def crewai_run(request):
    """异步启动 crewAI 智能体"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST allowed'}, status=405)
    
    data = json.loads(request.body)
    query = data.get('query')
    if not query:
        return JsonResponse({'error': 'Missing query'}, status=400)
    
    # 获取用户信息和 API Key
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

    run_id = str(uuid.uuid4())
    agent_runs[run_id] = {
        "status": "running",
        "prompt": None,
        "response": None,
        "event": threading.Event(),
        "result": None,
        "logs": []
    }
    
    # 在后台线程中运行智能体
    def thread_target():
        try:
            run_crew(query, allow_human_input=True, run_id=run_id, base_url=base_url, api_key=api_key, username=username)
        except Exception as e:
            logger.error(f"Error in agent thread: {e}", exc_info=True)
            agent_runs[run_id]["status"] = "error"
            agent_runs[run_id]["result"] = str(e)
            
    thread = threading.Thread(target=thread_target)
    thread.daemon = True
    thread.start()
    
    return JsonResponse({'run_id': run_id})

def crewai_status(request, run_id):
    """获取智能体运行状态"""
    run_data = agent_runs.get(run_id)
    if not run_data:
        return JsonResponse({'error': 'Run not found'}, status=404)
    
    return JsonResponse({
        'status': run_data['status'],
        'prompt': run_data['prompt'],
        'result': run_data['result'],
        'logs': run_data.get('logs', [])
    })

@csrf_exempt
def crewai_input(request, run_id):
    """提交人类输入"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST allowed'}, status=405)
    
    run_data = agent_runs.get(run_id)
    if not run_data:
        return JsonResponse({'error': 'Run not found'}, status=404)
    
    data = json.loads(request.body)
    user_input = data.get('input')
    
    run_data['response'] = user_input
    run_data['event'].set() # 唤醒等待的智能体线程
    
    return JsonResponse({'status': 'ok'})

@csrf_exempt
def crewai_stop(request, run_id):
    """手动停止智能体运行"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST allowed'}, status=405)
    
    run_data = agent_runs.get(run_id)
    if not run_data:
        return JsonResponse({'error': 'Run not found'}, status=404)
    
    run_data['status'] = 'stopped'
    # 如果正在等待人类输入，唤醒它
    if 'event' in run_data:
        run_data['event'].set()
    
    return JsonResponse({'status': 'ok'})

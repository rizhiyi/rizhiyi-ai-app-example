import json
import uuid
import threading
import logging
from django.shortcuts import render, redirect, reverse
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from ..config import RizhiyiOAuthConfig
from ..models import UserProfile, ChatSession, ChatMessage
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
    history = data.get('history', [])
    session_id = data.get('session_id')
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

    # 获取或创建当前用户的会话
    try:
        user_profile = UserProfile.objects.get(rizhiyi_id=user_info['id']) if user_info else None
    except UserProfile.DoesNotExist:
        user_profile = None

    if user_profile:
        # 如果提供了 session_id，则尝试获取该会话
        session = None
        if session_id:
            try:
                session = ChatSession.objects.get(id=session_id, user=user_profile)
            except ChatSession.DoesNotExist:
                pass
        
        # 如果没有 session_id 或会话不存在，则使用最近的一个或创建
        if not session:
            session = ChatSession.objects.filter(user=user_profile).order_by('-updated_at').first()
            if not session:
                session = ChatSession.objects.create(user=user_profile, title=query[:50])
        
        # 更新会话标题（如果之前是默认标题）
        if session.title == "新会话":
            session.title = query[:50]
            session.save()

        # 保存用户消息
        ChatMessage.objects.create(
            session=session,
            role='user',
            content=query
        )
        
        # 记录当前使用的 session_id
        current_session_id = session.id
    else:
        current_session_id = None

    # 启动 CrewAI 运行
    run_id = str(uuid.uuid4())
    agent_runs[run_id] = {
        "status": "running",
        "prompt": None,
        "response": None,
        "event": threading.Event(),
        "result": None,
        "logs": [],
        "session_id": current_session_id
    }
    
    # 在后台线程中运行智能体
    def thread_target():
        try:
            result = run_crew(query, history=history, allow_human_input=True, run_id=run_id, base_url=base_url, api_key=api_key, username=username)
            run_data = agent_runs[run_id]
            run_data['status'] = 'completed'
            run_data['result'] = str(result)

            # 保存结果到数据库
            try:
                if user_profile and current_session_id:
                    session = ChatSession.objects.get(id=current_session_id)
                    ChatMessage.objects.create(
                        session=session,
                        role='agent',
                        content=str(result),
                        logs=run_data.get('logs', [])
                    )
                    # 更新会话时间
                    session.save()
            except Exception as db_e:
                print(f"Failed to save chat history: {db_e}")
        except Exception as e:
            logger.error(f"Error in agent thread: {e}", exc_info=True)
            agent_runs[run_id]["status"] = "error"
            agent_runs[run_id]["result"] = str(e)
            
    thread = threading.Thread(target=thread_target)
    thread.daemon = True
    thread.start()
    
    return JsonResponse({'run_id': run_id, 'session_id': current_session_id})

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

def crewai_history(request):
    """获取会话历史"""
    user_info = request.session.get('user_info')
    if not user_info:
        return JsonResponse({'history': []})
    
    session_id = request.GET.get('session_id')
    
    try:
        user_profile = UserProfile.objects.get(rizhiyi_id=user_info['id'])
        
        if session_id:
            try:
                session = ChatSession.objects.get(id=session_id, user=user_profile)
            except ChatSession.DoesNotExist:
                return JsonResponse({'error': 'Session not found'}, status=404)
        else:
            # 获取最近的一个会话
            session = ChatSession.objects.filter(user=user_profile).order_by('-updated_at').first()
            
        if not session:
            return JsonResponse({'history': []})
            
        messages = session.messages.all().order_by('created_at')
        history = []
        for msg in messages:
            history.append({
                'role': msg.role,
                'content': msg.content,
                'logs': msg.logs
            })
        return JsonResponse({'history': history, 'session_id': session.id, 'title': session.title})
    except UserProfile.DoesNotExist:
        return JsonResponse({'history': []})

def crewai_sessions(request):
    """获取用户所有会话列表"""
    user_info = request.session.get('user_info')
    if not user_info:
        return JsonResponse({'sessions': []})
    
    try:
        user_profile = UserProfile.objects.get(rizhiyi_id=user_info['id'])
        sessions = ChatSession.objects.filter(user=user_profile).order_by('-updated_at')
        
        session_list = []
        for s in sessions:
            session_list.append({
                'id': s.id,
                'title': s.title,
                'updated_at': s.updated_at.strftime('%Y-%m-%d %H:%M:%S')
            })
        return JsonResponse({'sessions': session_list})
    except UserProfile.DoesNotExist:
        return JsonResponse({'sessions': []})

@csrf_exempt
def crewai_delete_session(request, session_id):
    """删除会话"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST allowed'}, status=405)
    
    user_info = request.session.get('user_info')
    if not user_info:
        return JsonResponse({'error': 'Not logged in'}, status=401)
    
    try:
        user_profile = UserProfile.objects.get(rizhiyi_id=user_info['id'])
        session = ChatSession.objects.get(id=session_id, user=user_profile)
        session.delete()
        return JsonResponse({'status': 'ok'})
    except (UserProfile.DoesNotExist, ChatSession.DoesNotExist):
        return JsonResponse({'error': 'Session not found'}, status=404)

@csrf_exempt
def crewai_new_session(request):
    """创建新会话"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST allowed'}, status=405)
    
    user_info = request.session.get('user_info')
    if not user_info:
        return JsonResponse({'error': 'User not logged in'}, status=401)
    
    try:
        user_profile = UserProfile.objects.get(rizhiyi_id=user_info['id'])
        # 创建一个新会话
        session = ChatSession.objects.create(user=user_profile, title="新会话")
        return JsonResponse({'status': 'ok', 'session_id': session.id})
    except UserProfile.DoesNotExist:
        return JsonResponse({'error': 'User profile not found'}, status=404)
    except Exception as e:
        logger.error(f"Error creating new session: {e}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)

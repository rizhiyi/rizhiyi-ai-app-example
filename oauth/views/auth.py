import requests
import logging
from django.shortcuts import render, redirect, reverse
from django.conf import settings
from ..config import RizhiyiOAuthConfig
from ..models import UserProfile

logger = logging.getLogger('oauth')

def index(request):
    """首页 - 展示OAuth2.0演示"""
    user_info = request.session.get('user_info')
    session_key = request.session.session_key
    logger.debug(f"Index view - User Info: {user_info}, Session ID: {session_key}")
    
    context = {
        'app_name': RizhiyiOAuthConfig.APP_NAME,
        'authorize_url': RizhiyiOAuthConfig.get_authorize_url(),
        'config': RizhiyiOAuthConfig,
        'debug_session_id': session_key,
        'debug_user_info': user_info
    }
    return render(request, 'oauth/index.html', context)

def callback(request):
    """OAuth回调处理"""
    code = request.GET.get('code')
    state = request.GET.get('state')
    error = request.GET.get('error')
    
    if error:
        return render(request, 'oauth/error.html', {'error': error})
    
    if not code:
        return render(request, 'oauth/error.html', {'error': 'missing_authorization_code'})
    
    # 交换访问令牌
    token_data = {
        'grant_type': 'authorization_code',
        'client_id': RizhiyiOAuthConfig.CLIENT_ID,
        'client_secret': RizhiyiOAuthConfig.CLIENT_SECRET,
        'code': code,
        'redirect_uri': RizhiyiOAuthConfig.REDIRECT_URL,  # Standard OAuth2 uses redirect_uri
        'redirect_url': RizhiyiOAuthConfig.REDIRECT_URL,  # Rizhiyi might use redirect_url
    }
    
    try:
        response = requests.post(RizhiyiOAuthConfig.TOKEN_URL, data=token_data)
        response.raise_for_status()
        token_response = response.json()
        
        # 打印完整的响应用于调试
        logger.debug(f"Token Response: {token_response}")
        
        if not token_response.get('result'):
            return render(request, 'oauth/error.html', {
                'error': f'令牌交换失败: {token_response.get("error", "未知错误")}',
                'details': str(token_response)
            })
        
        # 检查响应格式并提取access_token
        if 'token' in token_response and isinstance(token_response['token'], dict):
            # 日志易平台的格式：{'token': {'access_token': '...', ...}}
            token_data = token_response['token']
            access_token = token_data.get('access_token')
            if not access_token:
                return render(request, 'oauth/error.html', {
                    'error': '无效的令牌响应格式',
                    'details': f'token对象中缺少access_token: {token_response}'
                })
        elif 'access_token' in token_response:
            # 标准格式：{'access_token': '...', ...}
            access_token = token_response['access_token']
        else:
            return render(request, 'oauth/error.html', {
                'error': '未知的令牌响应格式',
                'details': f'无法解析的响应格式: {token_response}'
            })
        
        # 获取用户信息
        headers = {'Authorization': f'Bearer {access_token}'}
        user_response = requests.get(RizhiyiOAuthConfig.USERINFO_URL, headers=headers)
        user_response.raise_for_status()
        user_info_full = user_response.json()
        logger.debug(f"User Info Full Response: {user_info_full}")
        user_raw = user_info_full.get('user', user_info_full) # Fallback to full response if 'user' key not found
        
        # 归一化用户信息，方便模板使用
        user_info = {
            'id': user_raw.get('id'),
            'name': user_raw.get('name') or user_raw.get('username') or '已登录',
            'avatar': user_raw.get('avatar'),
            'email': user_raw.get('email')
        }
        # 添加头像首字母
        user_info['avatar_char'] = user_info['name'][0].upper() if user_info['name'] else 'U'
        
        # 将用户信息存入 session
        logger.debug(f"Before save - Session ID: {request.session.session_key}")
        request.session['user_info'] = user_info
        request.session['access_token'] = access_token
        request.session.modified = True
        request.session.save()

        # 持久化存储用户信息到数据库
        profile, created = UserProfile.objects.update_or_create(
            rizhiyi_id=user_info['id'],
            defaults={
                'rizhiyi_username': user_info['name'],
            }
        )
        logger.info(f"UserProfile {'created' if created else 'updated'}: {profile}")

        logger.debug(f"After save - Session ID: {request.session.session_key}, User: {user_info.get('name')}")
        
        next_url = request.GET.get('next', 'index')
        return redirect(next_url)
        
    except requests.exceptions.RequestException as e:
        return render(request, 'oauth/error.html', {
            'error': f'网络请求错误: {str(e)}',
            'details': f'请求URL: {RizhiyiOAuthConfig.TOKEN_URL}'
        })
    except KeyError as e:
        return render(request, 'oauth/error.html', {
            'error': f'响应格式错误: {str(e)}',
            'details': f'完整响应: {token_response if "token_response" in locals() else "未获取到响应"}'
        })
    except Exception as e:
        return render(request, 'oauth/error.html', {
            'error': '未知错误',
            'details': str(e)
        })

def logout(request):
    """退出登录"""
    if 'user_info' in request.session:
        del request.session['user_info']
    if 'access_token' in request.session:
        del request.session['access_token']
    return redirect('index')

def save_api_key(request):
    """保存用户 API Key"""
    if request.method != 'POST':
        return redirect('index')
    
    user_info = request.session.get('user_info')
    if not user_info:
        return redirect('index')
    
    api_key = request.POST.get('api_key')
    if api_key:
        UserProfile.objects.update_or_create(
            rizhiyi_id=user_info['id'],
            defaults={'api_key': api_key}
        )
    
    return redirect('index')

def demo_flow(request):
    """演示OAuth2.0完整流程"""
    state = 'demo_state_123'
    authorize_url = RizhiyiOAuthConfig.get_authorize_url(state)
    
    context = {
        'authorize_url': authorize_url,
        'client_id': RizhiyiOAuthConfig.CLIENT_ID,
        'redirect_url': RizhiyiOAuthConfig.REDIRECT_URL,
        'config': RizhiyiOAuthConfig
    }
    
    return render(request, 'oauth/demo.html', context)

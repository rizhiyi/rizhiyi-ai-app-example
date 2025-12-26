from .models import UserProfile

def user_info(request):
    """全局注入用户信息"""
    user_info = request.session.get('user_info')
    api_key = None
    
    if user_info and 'id' in user_info:
        profile = UserProfile.objects.filter(rizhiyi_id=user_info['id']).first()
        if profile:
            api_key = profile.api_key
            
    return {
        'user_info': user_info,
        'rizhiyi_api_key': api_key
    }

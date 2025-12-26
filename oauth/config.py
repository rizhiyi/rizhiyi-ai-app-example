import os
from decouple import config

class RizhiyiOAuthConfig:
    """日志易 OAuth2.0 配置"""
    
    # 日志易平台地址 - 由用户填写
    RIZHIYI_BASE_URL = config('RIZHIYI_BASE_URL', default='https://your-rizhiyi-domain.com')
    
    # OAuth2.0 端点
    AUTHORIZE_URL = f"{RIZHIYI_BASE_URL}/oauth2/authorize/"
    TOKEN_URL = f"{RIZHIYI_BASE_URL}/api/v3/oauth2/token/"
    USERINFO_URL = f"{RIZHIYI_BASE_URL}/api/v3/oauth2/userinfo/"
    
    # 第三方应用配置 - 由用户在日志易平台申请
    CLIENT_ID = config('CLIENT_ID', default='your-client-id')
    CLIENT_SECRET = config('CLIENT_SECRET', default='your-client-secret')
    REDIRECT_URL = config('REDIRECT_URL', default='http://localhost:8000/oauth/callback/')
    
    # 应用信息
    APP_NAME = config('APP_NAME', default='日志易OAuth演示应用')
    
    @classmethod
    def get_authorize_url(cls, state=None):
        """获取授权URL"""
        params = {
            'response_type': 'code',
            'client_id': cls.CLIENT_ID,
            'redirect_url': cls.REDIRECT_URL,
        }
        if state:
            params['state'] = state
        
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        return f"{cls.AUTHORIZE_URL}?{query_string}"
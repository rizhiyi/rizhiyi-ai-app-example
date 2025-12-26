from django.db import models

class UserProfile(models.Model):
    rizhiyi_id = models.CharField(max_length=255, unique=True, verbose_name="日志易用户ID")
    rizhiyi_username = models.CharField(max_length=255, verbose_name="日志易用户名", null=True, blank=True)
    api_key = models.TextField(verbose_name="日志易 API Key", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.rizhiyi_username or self.rizhiyi_id} (API Key: {'Set' if self.api_key else 'Not Set'})"

    class Meta:
        verbose_name = "用户配置"
        verbose_name_plural = "用户配置"

class ChatSession(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='chat_sessions')
    title = models.CharField(max_length=255, verbose_name="会话标题")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.user.rizhiyi_username})"

    class Meta:
        verbose_name = "聊天会话"
        verbose_name_plural = "聊天会话"
        ordering = ['-updated_at']

class ChatMessage(models.Model):
    ROLE_CHOICES = [
        ('user', 'User'),
        ('agent', 'Agent'),
    ]
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField(verbose_name="消息内容")
    logs = models.JSONField(verbose_name="执行日志", null=True, blank=True)
    status = models.CharField(max_length=20, default='completed')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.role}: {self.content[:50]}"

    class Meta:
        verbose_name = "聊天消息"
        verbose_name_plural = "聊天消息"
        ordering = ['created_at']

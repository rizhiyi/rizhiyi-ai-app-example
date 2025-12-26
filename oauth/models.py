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

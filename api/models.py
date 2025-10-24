import os

from django.db import models


class Server(models.Model):
    name = models.CharField(max_length=100)
    base_url = models.URLField()
    priority = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    total_space = models.PositiveBigIntegerField(default=0)

    def __str__(self):
        return f"{self.name}"

    def is_self(self) -> bool:
        return bool(self.base_url and os.environ.get("BASE_URL", False))

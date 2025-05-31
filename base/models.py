from django.db import models

from accounts.models import User


class Post(models.Model):
    image = models.TextField(max_length=1000)
    caption = models.TextField(max_length=1000, blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    tagged_users = models.ManyToManyField(
        User, related_name="tagged_posts", blank=True, help_text="Users tagged in this post"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.id} - {self.owner.username} - {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"


class Task(models.Model):
    name = models.CharField(max_length=255)
    completed = models.BooleanField(default=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    space = models.CharField(
        max_length=255,
        choices=(
            ("personal", "Personal"),
            ("partner", "Partner"),
            ("family", "Family"),
        ),
    )

    def __str__(self):
        return f"{self.owner} - {self.name}"

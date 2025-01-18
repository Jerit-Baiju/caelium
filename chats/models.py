from django.db import models
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from accounts.models import User


class Chat(models.Model):
    name = models.CharField(max_length=30, null=True, blank=True)
    participants = models.ManyToManyField("accounts.User", related_name="chats")
    updated_time = models.DateTimeField(auto_now=True)
    is_group = models.BooleanField(default=False)
    group_icon = models.ImageField(null=True, blank=True, upload_to="group_icons")
    creator = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, null=True, blank=True, related_name="created_chats"
    )

    def __str__(self):
        participant_names = list(self.participants.values_list("name", flat=True))
        return f"{self.pk}: {', '.join(participant_names)}"

    def is_pinned_by(self, user):
        return self.pinned_by.filter(user=user).exists()


@receiver(pre_delete, sender=User)
def delete_chats_on_user_delete(sender, instance, **kwargs):
    # Delete all chats where the user is a participant
    Chat.objects.filter(participants=instance).delete()


class Message(models.Model):
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE)
    sender = models.ForeignKey("accounts.User", on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    type = models.CharField(
        max_length=6,
        choices={
            "txt": "txt",
            "img": "img",
            "doc": "doc",
            "aud": "aud",
            "vid": "vid",
        },
    )
    content = models.TextField(null=True, blank=True)
    file = models.FileField(null=True, blank=True, upload_to="chats")

    def __str__(self) -> str:
        return f"{self.sender.name}: {self.content}"


class PinnedChat(models.Model):
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="pinned_chats")
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name="pinned_by")
    pinned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "chat")
        ordering = ["-pinned_at"]

    def __str__(self):
        return f"{self.user.name} pinned {self.chat}"

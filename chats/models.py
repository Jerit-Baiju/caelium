from django.db import models


class Chat(models.Model):
    name = models.CharField(max_length=30, null=True, blank=True)
    participants = models.ManyToManyField('accounts.User')
    starred_messages = models.ManyToManyField('Message', related_name='starred_messages', blank=True)

    def __str__(self):
        participant_names = list(self.participants.values_list('username', flat=True))
        return f"{self.pk}: {', '.join(participant_names)}"

class Message(models.Model):
    MESSAGE_TYPE_CHOICES = [
        ('text', 'Text'),
        ('image', 'Image'),
        ('voice', 'Voice'),
        ('video', 'Video'),
    ]
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE)
    sender = models.ForeignKey('accounts.User', on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPE_CHOICES)

class TextMessage(models.Model):
    message = models.OneToOneField(Message, on_delete=models.CASCADE, primary_key=True)
    content = models.TextField()

class VoiceMessage(models.Model):
    message = models.OneToOneField(Message, on_delete=models.CASCADE, primary_key=True)
    audio_file = models.FileField(upload_to='chats/voices/')

class ImageMessage(models.Model):
    message = models.OneToOneField(Message, on_delete=models.CASCADE, primary_key=True)
    image = models.ImageField(upload_to='chats/images/')

class VideoMessage(models.Model):
    message = models.OneToOneField(Message, on_delete=models.CASCADE, primary_key=True)
    video_file = models.FileField(upload_to='chats/videos/')

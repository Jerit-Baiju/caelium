import json

import pytz
from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .models import Message


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        if self.scope['user'].is_authenticated:
            self.room_name = await self.get_room()
            self.room_group_name = f'chat_{self.room_name}'
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            await self.accept()

    async def disconnect(self, close_code):
        if self.scope['user'].is_authenticated:
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        if self.scope['user'].is_authenticated:
            data = json.loads(text_data)
            if str(data['type']) == 'message':
                message = str(data['content']).strip()[:1000]
                if message != "":
                    user = self.scope['user']
                    email = user.email
                    message_instance = await self.save_message(user, message)
                    message_time_utc = message_instance.time.replace(tzinfo=pytz.UTC)
                    indian_timezone = pytz.timezone('Asia/Kolkata')
                    time = message_time_utc.astimezone(indian_timezone).strftime('%I:%M %p')
                    await self.channel_layer.group_send(
                        self.room_group_name, {'type': 'chat.message', 'content': message, 'user': email, 'time': time}
                    )
            if data['type'] == 'status':
                status = data['content']
                if status in ['online', 'offline']:
                    await self.channel_layer.group_send(
                        self.room_group_name, {'type': 'user.status', 'content': status, 'user': self.scope['user'].email}
                    )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['content'],
            'user': event['user'],
            'time': event['time']
        }))

    async def user_status(self, event):
        await self.send(text_data=json.dumps({
            'type': 'status',
            'status': event['content'],
            'user': event['user']
        }))

    @sync_to_async
    def save_message(self, user, message):
        room = user.relationship()
        return Message.objects.create(room=room, user=user, content=message)

    @sync_to_async
    def get_room(self):
        return self.scope['user'].relationship().room

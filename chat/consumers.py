import json
from datetime import datetime

import pytz
from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from .models import Message


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = await self.get_room()
        self.room_group_name = f'chat_{self.room_name}'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = str(text_data_json['message']).strip()[:1000]
        if message != "":
            user = self.scope['user']
            email = user.email
            message_instance = await self.save_message(user, message)
            message_time_utc = message_instance.time.replace(tzinfo=pytz.UTC)
            indian_timezone = pytz.timezone('Asia/Kolkata')
            time = message_time_utc.astimezone(indian_timezone).strftime('%I:%M %p')
            await self.channel_layer.group_send(
                self.room_group_name, {'type': 'chat.message', 'message': message, 'user': email, 'time': time}
            )

    async def chat_message(self, event):
        # Send message to WebSocket
        # where the console gets
        await self.send(text_data=json.dumps({
            'type': 'message',
            'data': event['message'],
            'user': event['user'],
            'time': event['time']
        }))

    @sync_to_async
    def save_message(self, user, message):
        room = user.relationship()
        return Message.objects.create(room=room, user=user, content=message)

    @sync_to_async
    def get_room(self):
        return self.scope['user'].relationship().room

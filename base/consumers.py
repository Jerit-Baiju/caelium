import json
import os

import jwt
from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer
from django.conf import settings
from django.utils import timezone

from accounts.models import User
from base.utils import log_admin
from chats.models import Chat, Message


class BaseConsumer(WebsocketConsumer):
    active_connections = {}
    random_chat_queue = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None

    def connect(self):
        token = self.scope["url_route"]["kwargs"]["token"]
        try:
            decoded_token = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = decoded_token["user_id"]
            self.user = User.objects.get(id=user_id)
            self.user.is_online = True
            self.user.save()
            self.accept()

            # Add connection to tracking
            if user_id not in self.active_connections:
                self.active_connections[user_id] = set()
            self.active_connections[user_id].add(self.channel_name)

            self.broadcast_status(is_online=True)
            async_to_sync(self.channel_layer.group_add)(f"user_{user_id}", self.channel_name)
            self.send(text_data=json.dumps({"message": f"Welcome to Caelium, {self.user.username}!"}))
            online_users = self.get_online_users()
            print(f"User {self.user.username} connected")
            self.send(
                text_data=json.dumps(
                    {
                        "category": "online_users",
                        "online_users": online_users,
                    }
                )
            )
        except (jwt.ExpiredSignatureError, jwt.DecodeError, User.DoesNotExist):
            self.close()

    def has_other_connections(self):
        if self.user.id not in self.active_connections:
            return False
        connections = self.active_connections[self.user.id]
        connections.discard(self.channel_name)
        return bool(connections)

    def disconnect(self, close_code):
        if self.user:
            # Remove user from random chat queue if present
            self.remove_from_queue()
            print(f"User {self.user.username} disconnected")
            if self.user.id in self.active_connections:
                self.active_connections[self.user.id].discard(self.channel_name)
                if not self.active_connections[self.user.id]:
                    # No remaining connections for this user, set to offline
                    del self.active_connections[self.user.id]
                    self.user.is_online = False
                    self.user.update_last_seen()
                    self.user.save()
                    self.broadcast_status(is_online=False)
            async_to_sync(self.channel_layer.group_discard)(f"user_{self.user.id}", self.channel_name)

    def remove_from_queue(self):
        self.random_chat_queue = [user for user in self.random_chat_queue if user != self.user.id]

    def receive(self, text_data):
        try:
            data = json.loads(text_data)
            if data["category"] == "random_chat_request":
                self.handle_random_chat_request()
            elif data["category"] == "text_message":
                message = Message.objects.create(
                    chat_id=data["chat_id"],
                    sender=self.user,
                    content=data["message"],
                    type="txt",
                )
                chat = Chat.objects.get(id=data["chat_id"])
                chat.updated_time = timezone.now()
                chat.save()
                if message:
                    # Serialize message before sending it through the channel
                    message_data = {
                        "type": "new_message",
                        "message_data": {
                            "id": str(message.id),
                            "chat_id": str(message.chat.id),
                            "sender": str(message.sender.id),
                            "content": message.content,
                            "timestamp": str(message.timestamp),
                            "type": message.type,
                            "file": f"{os.environ['SERVER_HOST']}{message.file.url}" if message.file else None,
                        }
                    }
                    # Send message to all participants
                    for recipient in Chat.objects.get(id=data["chat_id"]).participants.all():
                        async_to_sync(self.channel_layer.group_send)(
                            f"user_{recipient.id}",
                            message_data,
                        )
                    
                    # Log message event to admin socket using existing utility function
                    log_admin({
                        "event_type": "new_message",
                        "sender": str(self.user.id),
                        "sender_username": self.user.username,
                        "chat_id": str(data["chat_id"]),
                        "content": data["message"],
                    })

            elif data["category"] == "file_message":
                message = Message.objects.get(id=data["message_id"])
                # Serialize message before sending it through the channel
                message_data = {
                    "type": "new_message",
                    "message_data": {
                        "id": str(message.id),
                        "chat_id": str(message.chat.id),
                        "sender": str(message.sender.id),
                        "content": message.content,
                        "timestamp": str(message.timestamp),
                        "type": message.type,
                        "file": f"{os.environ['SERVER_HOST']}{message.file.url}" if message.file else None,
                    }
                }
                for recipient in Chat.objects.get(id=data["chat_id"]).participants.all():
                    if recipient.id is not self.user.id:
                        async_to_sync(self.channel_layer.group_send)(
                            f"user_{recipient.id}", message_data
                        )
                
                # Log file message event to admin socket using existing utility function
                log_admin({
                    "event_type": "file_message",
                    "sender": str(self.user.id),
                    "sender_username": self.user.username,
                    "chat_id": str(data["chat_id"]),
                    "message_id": str(data["message_id"]),
                })
            elif data["category"] == "typing":
                chat = Chat.objects.get(id=data["chat_id"])
                data["sender"] = self.user.id
                for recipient in chat.participants.all():
                    if recipient.id is not self.user.id:
                        async_to_sync(self.channel_layer.group_send)(
                            f"user_{recipient.id}", {"type": "typing", "data": data}
                        )
            elif data["category"] == "active_connections_count":
                self.send_active_connections_count()

        except (json.JSONDecodeError, Message.DoesNotExist, Chat.DoesNotExist, KeyError) as e:
            print(" Error:", e)

    def handle_random_chat_request(self):
        print(f"User {self.user.username} requesting random chat")
        print(f"Current queue: {self.random_chat_queue}")

        # Remove self if already in queue
        if self.user.id in self.random_chat_queue:
            self.random_chat_queue.remove(self.user.id)

        # Try to find a match from the queue
        for waiting_user_id in list(self.random_chat_queue):  # Create a copy of the list to iterate
            try:
                waiting_user = User.objects.get(id=waiting_user_id)
                if waiting_user.is_online and waiting_user.id != self.user.id:
                    # Create new chat room for the matched users
                    chat = Chat.objects.create(is_random=True)
                    chat.participants.add(self.user, waiting_user)
                    chat.save()

                    # Remove the matched user from queue
                    self.random_chat_queue.remove(waiting_user_id)
                    print(f"Matched users: {self.user.username} with {waiting_user.username}")

                    # Notify both users
                    self.send(
                        text_data=json.dumps(
                            {
                                "category": "random_chat_matched",
                                "chat_id": str(chat.id),
                                "matched_user": {"id": str(waiting_user.id), "username": waiting_user.username},
                            }
                        )
                    )

                    async_to_sync(self.channel_layer.group_send)(
                        f"user_{waiting_user.id}",
                        {
                            "type": "random_chat_matched",
                            "data": {
                                "category": "random_chat_matched",
                                "chat_id": str(chat.id),
                                "matched_user": {"id": str(self.user.id), "username": self.user.username},
                            },
                        },
                    )
                    return
            except User.DoesNotExist:
                self.random_chat_queue.remove(waiting_user_id)
                continue

        # If no match found, add user to queue
        self.random_chat_queue.append(self.user.id)
        print(f"Added {self.user.username} to queue. Current queue: {self.random_chat_queue}")
        self.send(text_data=json.dumps({"category": "random_chat_queued", "message": "Looking for someone to chat with..."}))

    def random_chat_matched(self, event):
        self.send(text_data=json.dumps(event["data"]))

    def send_active_connections_count(self):
        active_connections_count = len(self.active_connections.get(self.user.id, []))
        self.send(text_data=json.dumps({"category": "active_connections_count", "count": active_connections_count}))

    def new_message(self, event):
        message_data = event["message_data"]
        self.send(
            text_data=json.dumps(
                {
                    "category": "new_message",
                    "type": message_data["type"],
                    "id": message_data["id"],
                    "chat": message_data["chat_id"],
                    "content": message_data["content"],
                    "sender": message_data["sender"],
                    "timestamp": message_data["timestamp"],
                    "file": message_data["file"],
                }
            )
        )

    def typing(self, event):
        self.send(text_data=json.dumps(event["data"]))

    def broadcast_status(self, is_online):
        status_data = {
            "type": "user_status_change",
            "user_id": self.user.id,
            "is_online": is_online,
            "last_seen": str(self.user.last_seen),
        }
        for chat in self.user.chats.all():
            for participant in chat.participants.all():
                if participant != self.user:
                    async_to_sync(self.channel_layer.group_send)(f"user_{participant.id}", status_data)

    def user_status_change(self, event):
        self.send(
            text_data=json.dumps(
                {
                    "category": "status_update",
                    "user_id": event["user_id"],
                    "is_online": event["is_online"],
                    "last_seen": event["last_seen"],
                }
            )
        )

    def get_online_users(self):
        online_users = set()  # Using set to avoid duplicates
        for chat in self.user.chats.all():
            for participant in chat.participants.all():
                if participant.is_online and participant.id != self.user.id:
                    online_users.add(participant.id)
        return list(online_users)

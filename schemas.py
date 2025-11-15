from pydantic import BaseModel
from typing import Optional


class User(BaseModel):
    id: int
    is_bot: bool
    first_name: str
    username: Optional[str] = None


class Chat(BaseModel):
    id: int
    type: str
    title: Optional[str] = None
    username: Optional[str] = None


class Message(BaseModel):
    message_id: int
    from_user: Optional[User] = None
    chat: Chat
    date: int
    text: Optional[str] = None


class Update(BaseModel):
    update_id: int
    message: Optional[Message] = None

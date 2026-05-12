# saves every inbound and outbound message to the db for audit purposes
# also defines the MessageLog dataclass that the rest of the app uses
# direction is inbound or outbound, channel is sms or voice

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class MessageLog:
    content: str
    direction: str   # "inbound" or "outbound"
    channel: str     # "sms" or "voice"
    task_id: Optional[str] = None
    # auto generate an id and timestamp if not provided
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def log_message(content: str, direction: str, channel: str, task_id: str = None) -> MessageLog:
    # helper to create a MessageLog without having to import the dataclass everywhere
    # TODO: actually write this to the messages table once db is set up
    return MessageLog(
        content=content,
        direction=direction,
        channel=channel,
        task_id=task_id
    )

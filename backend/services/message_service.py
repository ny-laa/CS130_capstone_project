# saves inbound + outbound messages to db 
# "messages" here may come from SMS or voice interactions
# task_id can be empty for messages that aren't connected to a specific task yet

from uuid import UUID
from sqlalchemy.orm import Session
from models.datatypes import MessageChannel, MessageDirection
from models.message import Message


def _get_direction(direction: MessageDirection | str) -> MessageDirection:
    # can pass either MessageDirection.INBOUND or "inbound"
    if isinstance(direction, MessageDirection):
        return direction

    try:
        return MessageDirection(direction)
    except ValueError:
        raise ValueError(f" This is an unsupported message direction: {direction}")


def _get_channel(channel: MessageChannel | str) -> MessageChannel:
    # can pass either MessageChannel.SMS or "sms"
    if isinstance(channel, MessageChannel):
        return channel

    try:
        return MessageChannel(channel)
    except ValueError:
        raise ValueError(f"This is an unsupported message channel: {channel}")


def create_message(
    db: Session,
    content: str,
    direction: MessageDirection | str,
    channel: MessageChannel | str,
    user_id: UUID | None = None,
    task_id: UUID | None = None,
) -> Message:
    """
    Save one inbound or outbound message to the db
    user_id identifies parent involved in the conversation
    task_id is optional cause some messagess may arrive before a task actuallyy exists
    """
    if not content.strip():
        raise ValueError("Message content cannot be empty")

    message = Message(
        content=content,
        direction=_get_direction(direction),
        channel=_get_channel(channel),
        user_id=user_id,
        task_id=task_id,
    )

    db.add(message)

    try:
        db.commit()
        db.refresh(message)
    except Exception:
        db.rollback()
        raise

    return message


def log_message(
    db: Session,
    content: str,
    direction: MessageDirection | str,
    channel: MessageChannel | str,
    user_id: UUID | None = None,
    task_id: UUID | None = None,
) -> Message:
    
    #This is bacially a readable wrapper used by API routes + workers

    return create_message(
        db=db,
        content=content,
        direction=direction,
        channel=channel,
        user_id=user_id,
        task_id=task_id,
    )


def get_messages_for_user(
    db: Session,
    user_id: UUID,
    limit: int = 50,
) -> list[Message]:
    """
    Return the user's most recent messages

    Can later be used to provide conversation context to the orchestrator
    """
    return (
        db.query(Message)
        .filter(Message.user_id == user_id)
        .order_by(Message.timestamp.desc())
        .limit(limit)
        .all()
    )


def get_messages_for_task(
    db: Session,
    task_id: UUID,
) -> list[Message]:
    """
    Returns all messages connected to a task in chronological order

    Can eb useful when reviewing a task that required followups questions
    or human approval.
    """
    return (
        db.query(Message)
        .filter(Message.task_id == task_id)
        .order_by(Message.timestamp.asc())
        .all()
    )
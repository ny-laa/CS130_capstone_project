#import all models so Base.metadata is populated for alembic autogen.

from models.message import Message
from models.preference import Preference
from models.task import Task
from models.user import User

__all__ = ["User", "Task", "Message", "Preference"]

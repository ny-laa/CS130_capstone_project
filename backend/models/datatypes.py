# all the shared types / enums used across the data model
# based on the design doc data model section
# if somethign is not clearly defined yet (like sms content structure)
# its left as a placeholder comment

from enum import Enum
from typing import Optional, Any
from uuid import UUID


# enums for various fields in the data model, helps keep things consistent and avoid typos


class Tools(str, Enum):
    SMS_TOOL  = "sms_tool"
    CALL_TOOL = "call_tool"
    CALENDAR_TOOL       = "calendar_tool"
    CALENDAR_DELETE_TOOL = "calendar_delete_tool"
    SCRIPT_TOOL         = "script_tool"
    GMAIL_TOOL          = "gmail_tool"

    # add more as we write. 



class CommStyle(str, Enum):
    BRIEF    = "brief"
    DETAILED = "detailed"


class PreferredChannel(str, Enum):
    SMS  = "sms"
    CALL = "call"


class TaskStatus(str, Enum):
    PENDING            = "PENDING"
    IN_PROGRESS        = "IN_PROGRESS"
    ESCALATION_PENDING = "ESCALATION_PENDING"
    COMPLETED          = "COMPLETED"
    FAILED             = "FAILED"


class TaskType(str, Enum):
    REMINDER            = "reminder"
    CALENDAR_UPDATE     = "calendar_update"
    INFORMATION_REQUEST = "information_request"
    MORNING_DIGEST      = "morning_digest"
    SMALLTALK           = "smalltalk"


class MessageDirection(str, Enum):
    INBOUND  = "inbound"
    OUTBOUND = "outbound"


class MessageChannel(str, Enum):
    SMS   = "sms"
    VOICE = "voice"


# instead of keeping database class types here, let's move it to sepecific moduels. 

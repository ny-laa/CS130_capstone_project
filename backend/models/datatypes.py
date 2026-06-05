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
    # business_call_tool: G dials an external number (e.g. pizza place) and
    # drives a goal-oriented back-and-forth with whoever answers, then SMSes
    # the user a summary. distinct from call_tool which calls the user.
    BUSINESS_CALL_TOOL = "business_call_tool"
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


# urgency level at which G escalates to a phone call instead of SMS.
# 'any'   = always call, 'high' = only for high-urgency tasks,
# 'never' = stay on SMS no matter what
class CallUrgency(str, Enum):
    ANY   = "any"
    HIGH  = "high"
    NEVER = "never"


# what morning digest includes besides the calendar
class DigestContent(str, Enum):
    CALENDAR        = "calendar"
    CALENDAR_EMAIL  = "calendar+email"
    CALENDAR_TASKS  = "calendar+tasks"


# voice/tone G uses in outbound messages
class Tone(str, Enum):
    CASUAL = "casual"
    FORMAL = "formal"


# what G does for scheduling conflict
class ConflictHandling(str, Enum):
    SUGGEST = "suggest"  # propose a reschedule
    FLAG    = "flag"     # just surface it, let parent decide


class MessageDirection(str, Enum):
    INBOUND  = "inbound"
    OUTBOUND = "outbound"


class MessageChannel(str, Enum):
    SMS   = "sms"
    VOICE = "voice"
    CHAT  = "chat"


# instead of keeping database class types here, let's move it to sepecific moduels. 

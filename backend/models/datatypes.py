# all the shared types / enums used across the data model
# based on the design doc data model section
# if somethign is not clearly defined yet (like sms content structure)
# its left as a placeholder comment

from enum import Enum
from typing import Optional, Any
from dataclasses import dataclass
from uuid import UUID, uuid4


# enums for various fields in the data model, helps keep things consistent and avoid typos

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


class MessageDirection(str, Enum):
    INBOUND  = "inbound"
    OUTBOUND = "outbound"


class MessageChannel(str, Enum):
    SMS   = "sms"
    VOICE = "voice"


# jsonb/structured types that are stored in the db as part of various tables, but we want to have a clear structure for them in the code

@dataclass
class BlockedWindow:
    # recurring time block where G shouldnt bother the parent
    # stored as JSONB array in users.blocked_windows
    start_time: str   # e.g. "12:00" in users local timezone
    end_time: str     # e.g. "16:00"


@dataclass
class PlanStep:
    # one step in a task's execution plan
    # stored as JSONB array in tasks.plan_steps
    tool: str         # e.g. "sms_tool", "calendar_tool"
    params: dict      # tool-specific params, structure varies per tool
    status: TaskStatus = TaskStatus.PENDING


# SMS message content structure (not clearly defined yet
# will be filled in once twilio webhook integration is done
SMSContent = Any  # placeholder

# Voice/call transcript structure — not clearly defined yet
# likely {"transcript": str, "duration": int, "recording_url": str} or smth
# will be filled in once deepgram + twilio voice is wired up
VoiceContent = Any  # placeholder

# calendar event structure from google calendar api: tbd
# will be defined once CalendarTool is implemented
CalendarEvent = Any  # placeholder

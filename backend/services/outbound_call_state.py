# in-memory state for in-flight outbound business calls (G calling a
# pizza place etc on behalf of the user). keyed by twilio CallSid. lives
# here (separate module) so the adapter that places the call and the
# webhook that handles the recipient's responses can both touch it
# without a circular import.
#
# wiped on server restart -- acceptable because a process restart kills
# the underlying twilio call too. for production this'd move to redis.

from dataclasses import dataclass, field
from uuid import UUID


@dataclass
class OutboundCallState:
    user_id: UUID          # who to SMS the summary to
    user_phone: str        # E.164 -- given to the business if they ask for a callback
    user_name: str         # for "calling on behalf of {name}"
    goal: str              # what we're trying to accomplish
    business_name: str | None = None
    history: list[dict] = field(default_factory=list)   # [{role, content}, ...]
    summary: str | None = None                          # set when claude flags hang_up
    started_iso: str | None = None


# CallSid -> state. populated by UserBusinessCallAdapter on place_call,
# read+mutated by the /webhooks/call/outbound-transcript handler, popped
# when claude says hang_up (or on Twilio's final status callback).
_active: dict[str, OutboundCallState] = {}


def register(call_sid: str, state: OutboundCallState) -> None:
    _active[call_sid] = state


def get(call_sid: str) -> OutboundCallState | None:
    return _active.get(call_sid)


def drop(call_sid: str) -> OutboundCallState | None:
    return _active.pop(call_sid, None)

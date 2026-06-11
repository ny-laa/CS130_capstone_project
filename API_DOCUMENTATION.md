# G — API Documentation

G is a personal AI secretary for busy parents. Parents reach G through three channels — a web chat UI, SMS, and voice phone calls — and G can set reminders, read and update Google Calendar, read Gmail, send texts, call the parent back, and even place outbound calls to businesses on the parent's behalf. This document is the complete reference for G's HTTP API: the REST endpoints the frontend uses, the Twilio webhooks that drive SMS and voice, the request/response schemas, and the shared enums.

- **Service name:** `g-backend`
- **Framework:** FastAPI (Python)
- **API version:** `0.1.0`
- **Interactive docs:** when the server is running, FastAPI serves auto-generated docs at `/docs` (Swagger UI) and `/redoc`.

---

## Base URL & environments

| Environment | Base URL |
|---|---|
| Local dev | `http://localhost:8000` (run `uvicorn main:app --reload` from `backend/`) |
| Production | `https://cs130capstoneproject-production.up.railway.app` |

The production base URL is inferred from `GOOGLE_REDIRECT_URI` in `config.py`. All REST endpoints below are relative to the base URL.

### CORS

The backend allows browser requests from:

- `http://localhost:<port>` and `https://localhost:<port>` — local Vite dev (any port; Vite auto-increments past 5173)
- `https://*.vercel.app` — production and preview deploys
- the value of the `FRONTEND_ORIGIN` environment variable, if set — for a custom domain

All methods and headers are allowed for these origins.

---

## Authentication

G uses **JWT bearer tokens**. A token is returned by the registration, login, and Google OAuth flows. Include it on subsequent requests:

```
Authorization: Bearer <token>
```

Token details:

- **Algorithm:** HS256, signed with the server's `JWT_SECRET`.
- **Claims:** `sub` (the user's UUID) and `exp` (expiry).
- **Lifetime:** 7 days (`JWT_EXPIRE_MINUTES = 60 * 24 * 7`).

---

## Conventions

- **IDs** are UUIDs (string form in JSON), e.g. `"550e8400-e29b-41d4-a716-446655440000"`.
- **Timestamps** are ISO 8601. Scheduling-related fields (`scheduled_at`) carry a timezone offset; the system assumes `America/Los_Angeles` for the user.
- **Content type** is `application/json` for request and response bodies unless noted (webhooks use form-encoded input and return XML/TwiML).
- **Partial updates** use `PATCH`; only the fields present in the body are changed, everything else is left untouched.

### Error model

Errors are returned as FastAPI's standard shape:

```json
{ "detail": "human-readable message" }
```

Common status codes used across the API:

| Status | Meaning in this API |
|---|---|
| `200 OK` | Successful read or action |
| `201 Created` | Resource created (register, create user/contact/provider/family member) |
| `204 No Content` | Successful delete (empty body) |
| `400 Bad Request` | Validation error at the service layer (e.g. bad input), or failed debug tool call |
| `401 Unauthorized` | Invalid email/password on login |
| `403 Forbidden` | Invalid Twilio signature on a webhook |
| `404 Not Found` | User / resource does not exist |
| `409 Conflict` | Duplicate (email/phone already exists), or an action that conflicts with current state (e.g. approving a task that isn't pending escalation) |
| `422 Unprocessable Entity` | FastAPI request-body validation failure (wrong types, missing required fields) |
| `500 Internal Server Error` | Unhandled server error; webhooks deliberately avoid 500s |

---

## Endpoint summary

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Service root / liveness banner |
| GET | `/health` | Liveness check (no DB) |
| GET | `/health/db` | Readiness check (counts DB tables) |
| POST | `/api/auth/register` | Create account with email + password |
| POST | `/api/auth/login` | Log in, get a token |
| GET | `/oauth/google` | Google OAuth callback (calendar + Gmail access) |
| POST | `/api/users` | Create a user (phone-based signup) |
| GET | `/api/users/{user_id}` | Get a user profile |
| PATCH | `/api/users/{user_id}` | Update profile (name / email / first phone) |
| PATCH | `/api/users/{user_id}/preferences` | Update G's behavior preferences |
| GET | `/api/users/{user_id}/messages` | Conversation history (audit log) |
| GET | `/api/users/{user_id}/tasks` | Tasks for a user |
| GET | `/api/users/{user_id}/family-members` | List family members |
| POST | `/api/users/{user_id}/family-members` | Add a family member |
| GET | `/api/users/{user_id}/family-members/{member_id}` | Get a family member |
| PATCH | `/api/users/{user_id}/family-members/{member_id}` | Update a family member |
| DELETE | `/api/users/{user_id}/family-members/{member_id}` | Delete a family member |
| GET | `/api/users/{user_id}/contacts` | List contacts (optional `?q=` name filter) |
| POST | `/api/users/{user_id}/contacts` | Add a contact |
| GET | `/api/users/{user_id}/contacts/{contact_id}` | Get a contact |
| PATCH | `/api/users/{user_id}/contacts/{contact_id}` | Update a contact |
| DELETE | `/api/users/{user_id}/contacts/{contact_id}` | Delete a contact |
| GET | `/api/users/{user_id}/providers` | List providers (optional `?specialty=`) |
| POST | `/api/users/{user_id}/providers` | Add a provider |
| GET | `/api/users/{user_id}/providers/{provider_id}` | Get a provider |
| PATCH | `/api/users/{user_id}/providers/{provider_id}` | Update a provider |
| DELETE | `/api/users/{user_id}/providers/{provider_id}` | Delete a provider |
| POST | `/api/chat` | Web chat — full agent loop |
| GET | `/api/tasks/user/{user_id}` | Tasks for a user (raw ORM shape) |
| POST | `/api/tasks/{task_id}/approve` | Approve an escalated task |
| POST | `/api/tasks/{task_id}/deny` | Deny an escalated task |
| POST | `/webhooks/sms` | Inbound SMS (Twilio) |
| POST | `/webhooks/call` | Inbound voice call (Twilio) |
| POST | `/webhooks/call/transcript` | Inbound voice — speech turn (Twilio) |
| POST | `/webhooks/call/outbound-transcript` | Outbound business call — employee turn (Twilio) |
| POST | `/debug/call` | (DEBUG only) Manually place a call |
| POST | `/debug/sms` | (DEBUG only) Manually send an SMS |
| POST | `/debug/notify/{user_id}` | (DEBUG only) Fire a proactive notification |

---

## Health & system

### GET `/`
Returns a small service banner. Used by Cloud Run / Railway service-URL checks.

**200 response**
```json
{ "service": "g-backend", "env": "development", "status": "ok" }
```

### GET `/health`
Liveness probe. Does not touch the database, so it stays fast even if Postgres is down.

**200 response**
```json
{ "status": "ok" }
```

### GET `/health/db`
Readiness probe. Counts the tables in the `public` schema as a connectivity sanity check.

**200 response**
```json
{ "status": "ok", "public_table_count": 9 }
```

---

## Authentication endpoints

### POST `/api/auth/register`
Create an account with email + password. Returns the new user and a JWT.

**Request body** (`UserRegister`)
```json
{ "name": "Jane Doe", "email": "jane@example.com", "password": "hunter2" }
```

**201 response** (`AuthResponse`)
```json
{
  "user": { /* UserResponse — see schemas */ },
  "token": "eyJhbGciOiJIUzI1NiIsInR..."
}
```

**Errors**
- `409 Conflict` — an account with this email already exists.

> Passwords are hashed with bcrypt. Inputs longer than 72 bytes are truncated to bcrypt's limit before hashing.

### POST `/api/auth/login`
Exchange email + password for a token.

**Request body** (`UserLogin`)
```json
{ "email": "jane@example.com", "password": "hunter2" }
```

**200 response** (`AuthResponse`) — same shape as register.

**Errors**
- `401 Unauthorized` — invalid email or password.

### GET `/oauth/google`
Google OAuth 2.0 callback. After the parent authorizes G on the Google consent screen, Google redirects here with a `code`. G exchanges the code for access/refresh tokens, decodes the parent's email and name from the `id_token`, upserts the user, stores the Google tokens (used for Calendar and Gmail), and then **redirects the browser** back to the frontend.

**Query parameters**
| Name | Type | Required | Description |
|---|---|---|---|
| `code` | string | yes | Authorization code from Google |

**Behavior**
- New users are created with a placeholder phone number (`g_xxxxxxxx`) until they set a real one.
- Google tokens are saved with a 1-hour expiry derived from Google's `expires_in`.

**Response:** `307` redirect to
```
{FRONTEND_URL}/oauth/callback?user_id=...&email=...&name=...&token=...&new_user=true|false
```

**Errors**
- `400 Bad Request` — Google rejected the token exchange.

---

## Users

### POST `/api/users`
Create a user via phone-based signup (distinct from the email/password register flow). Phone is required; email and name are optional and typically filled in later on the profile page.

**Request body** (`UserCreate`)
```json
{ "phone_number": "+13105550199", "email": "jane@example.com", "name": "Jane Doe" }
```

**201 response:** `UserResponse`.

**Errors**
- `409 Conflict` — phone or email already in use.

### GET `/api/users/{user_id}`
Hydrates the profile page "Your Info" section.

**200 response:** `UserResponse`.

**Errors**
- `404 Not Found` — user not found.

### PATCH `/api/users/{user_id}`
Update profile fields. Backs both the profile page "Your Info" save and onboarding step 1. `phone_number` can be set only when the user currently has none (first-time set during onboarding); changing an established phone is blocked at the service layer and returns a conflict.

**Request body** (`UserProfileUpdate`, all optional)
```json
{ "name": "Jane D.", "email": "jane.d@example.com", "phone_number": "+13105550199" }
```

**200 response:** `UserResponse`.

**Errors**
- `404 Not Found` — user not found.
- `409 Conflict` — e.g. attempting to change an already-set phone number, or a duplicate.

### PATCH `/api/users/{user_id}/preferences`
Update G's behavior preferences (communication style, notification timing, morning digest, escalation behavior, tone, etc.). This is a partial update: only fields that are sent (and non-null) are written.

**Request body** (`UserPreferencesUpdate`, all optional) — see [UserPreferencesUpdate](#userpreferencesupdate) for the full field list. Example:
```json
{
  "comm_style": "brief",
  "preferred_channel": "sms",
  "morning_digest_enabled": true,
  "morning_digest_time": "07:30",
  "escalation_timeout_minutes": 30,
  "tone": "casual"
}
```

**200 response:** `UserResponse`.

**Errors**
- `404 Not Found` — user not found.
- `422 Unprocessable Entity` — a value is out of its allowed range (e.g. `max_reminders` outside 1–10) or not a valid enum value.

### GET `/api/users/{user_id}/messages`
Conversation history (audit log), newest first. Used by the conversations page to replay a thread across SMS, voice, and chat.

**Query parameters**
| Name | Type | Default | Description |
|---|---|---|---|
| `limit` | integer | 50 | Max messages returned |

**200 response:** array of `MessageResponse`.

**Errors**
- `404 Not Found` — user not found.

### GET `/api/users/{user_id}/tasks`
Tasks for a user, newest first (PENDING / IN_PROGRESS / ESCALATION_PENDING / COMPLETED / FAILED). Backs the `/tasks` frontend page.

**Query parameters**
| Name | Type | Default | Description |
|---|---|---|---|
| `limit` | integer | 50 | Max tasks returned |

**200 response:** array of `TaskResponse`.

**Errors**
- `404 Not Found` — user not found.

> There is a second tasks-listing endpoint, `GET /api/tasks/user/{user_id}`, that returns the raw ORM rows rather than the `TaskResponse` schema. Prefer this one (`/api/users/{user_id}/tasks`) for the typed, documented shape.

---

## Family members

Dependents shown on the profile page. All routes are nested under a user and scoped to that user at the service layer.

**Base:** `/api/users/{user_id}/family-members`

### GET `/api/users/{user_id}/family-members`
List all family members for the user.
**200:** array of `FamilyMemberResponse`.

### POST `/api/users/{user_id}/family-members`
**Request body** (`FamilyMemberCreate`)
```json
{ "name": "Sam", "relation": "son", "phone_number": "+13105550123" }
```
`name` is required; `relation` and `phone_number` are optional. The phone lets G text/call the family member directly.
**201:** `FamilyMemberResponse`.
**Errors:** `404` if the user doesn't exist; `400` on other validation errors.

### GET `/api/users/{user_id}/family-members/{member_id}`
**200:** `FamilyMemberResponse`. **404** if not found.

### PATCH `/api/users/{user_id}/family-members/{member_id}`
Partial update (`FamilyMemberUpdate`, all fields optional).
**200:** `FamilyMemberResponse`. **404** if not found; **400** on validation error.

### DELETE `/api/users/{user_id}/family-members/{member_id}`
**204:** no content. **404** if not found.

---

## Contacts

Third parties G may call or text on the user's behalf (e.g. "call Mrs. Carter"). Only `name` is required.

**Base:** `/api/users/{user_id}/contacts`

### GET `/api/users/{user_id}/contacts`
List contacts. Supports a name search used by the orchestrator to resolve names.

**Query parameters**
| Name | Type | Description |
|---|---|---|
| `q` | string (optional) | Case-insensitive name filter |

**200:** array of `ContactResponse`.

### POST `/api/users/{user_id}/contacts`
**Request body** (`ContactCreate`)
```json
{ "name": "Mrs. Carter", "role": "babysitter", "org": "", "phone": "+13105550144" }
```
**201:** `ContactResponse`. **Errors:** `404` if user not found; `400` otherwise.

### GET `/api/users/{user_id}/contacts/{contact_id}`
**200:** `ContactResponse`. **404** if not found.

### PATCH `/api/users/{user_id}/contacts/{contact_id}`
Partial update (`ContactUpdate`). **200:** `ContactResponse`. **404 / 400** on error.

### DELETE `/api/users/{user_id}/contacts/{contact_id}`
**204:** no content. **404** if not found.

---

## Providers

Preferred service providers (dentist, pediatrician, etc.) — "who to pick" rather than "who to call." Distinct from contacts.

**Base:** `/api/users/{user_id}/providers`

### GET `/api/users/{user_id}/providers`
List providers. Supports specialty lookup used by the orchestrator (e.g. "find the user's dentist").

**Query parameters**
| Name | Type | Description |
|---|---|---|
| `specialty` | string (optional) | Filter by specialty |

**200:** array of `ProviderResponse`.

### POST `/api/users/{user_id}/providers`
**Request body** (`ProviderCreate`)
```json
{ "name": "Dr. Lee", "specialty": "pediatrician", "practice": "Sunny Kids Clinic" }
```
`name` is required. **201:** `ProviderResponse`. **Errors:** `404` if user not found; `400` otherwise.

### GET `/api/users/{user_id}/providers/{provider_id}`
**200:** `ProviderResponse`. **404** if not found.

### PATCH `/api/users/{user_id}/providers/{provider_id}`
Partial update (`ProviderUpdate`). **200:** `ProviderResponse`. **404 / 400** on error.

### DELETE `/api/users/{user_id}/providers/{provider_id}`
**204:** no content. **404** if not found.

---

## Chat (the agent endpoint)

### POST `/api/chat`
The web UI chat endpoint and the heart of G's agent loop. It mirrors the SMS webhook flow so both channels share the same orchestrator, task runner, and tools. The full path is: resolve the user → persist the inbound message → load history → build user context → call Claude for a structured plan → run tools (or schedule them) → persist results → return a reply.

**Auth resolution order:**
1. `Authorization: Bearer <token>` header (preferred).
2. `user_id` in the request body (fallback for the unauthenticated demo).
3. No user — runs in a limited demo mode using the in-session `messages` the frontend sends.

**Request body** (`ChatRequest`)
```json
{
  "message": "remind me to pick up Sam at 3pm",
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "messages": [
    { "role": "user", "content": "hi" },
    { "role": "assistant", "content": "Hello! How can I help?" }
  ]
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `message` | string | yes | The parent's latest message |
| `user_id` | string (UUID) | no | Fallback identity if no auth header |
| `messages` | array | no | Full in-session history (used only when not logged in) |

**200 response**
```json
{
  "reply": "Got it — I'll remind you to pick up Sam at 3pm.\n<task><type>Reminder</type><status>Pending</status><description>...</description><summary>...</summary></task>",
  "task_id": "9b2...",
  "escalated": false
}
```

| Field | Type | Description |
|---|---|---|
| `reply` | string | G's natural-language reply. When a task was created, an inline `<task>…</task>` block is appended for the frontend to render a task card. |
| `task_id` | string \| null | ID of the created/scheduled task, if any |
| `escalated` | boolean | `true` when the action needs the parent's approval (e.g. a calendar conflict) before it runs |

**How plans are executed**

Claude returns a structured plan with a `task_type` (one of `reminder`, `calendar_update`, `information_request`, `morning_digest`, `smalltalk`) and a list of `plan_steps`, each naming a tool. Routing then depends on the steps:

- **Smalltalk / no steps** → G replies directly, no task created.
- **A schedulable step with `scheduled_at`** (`sms_tool`, `call_tool`, or `business_call_tool` with a future time) → routed through the dispatch/Celery path, which creates the task row and fires the SMS/call at the scheduled time.
- **Immediate steps** → run inline through the TaskRunner. Calendar conflicts pause the task into `ESCALATION_PENDING` (returned as `escalated: true`); the parent approves or denies via the task endpoints below.

The tools available to the agent are `sms_tool`, `call_tool`, `business_call_tool`, `calendar_tool`, and `gmail_tool` (see [Tools](#tools-enum)).

**Error handling:** The endpoint is resilient — if Claude or a tool fails, it still returns `200` with a fallback `reply` (e.g. "I ran into a problem completing that. Please try again.") rather than surfacing a `500`.

---

## Tasks (approval workflow)

When G plans a high-stakes or conflicting action, it pauses in `ESCALATION_PENDING` and waits for the parent. These endpoints back the approve/deny buttons on the task card.

### GET `/api/tasks/user/{user_id}`
List tasks for a user (newest first). Returns the **raw ORM rows** (not the `TaskResponse` schema). For the typed shape, use `GET /api/users/{user_id}/tasks` instead.

**Query parameters:** `limit` (integer, default 50).

### POST `/api/tasks/{task_id}/approve`
Approve an escalated task. G resumes the task (e.g. forces past a calendar overlap) and persists the result.

**200 response**
```json
{ "task_id": "9b2...", "status": "COMPLETED" }
```
(`status` is the resulting `TaskStatus`.)

**Errors**
- `404 Not Found` — task or its user not found.
- `409 Conflict` — the task is not in `ESCALATION_PENDING` (its current status is included in the message).

### POST `/api/tasks/{task_id}/deny`
Deny an escalated task. G aborts it and marks it `FAILED`.

**200 response**
```json
{ "task_id": "9b2...", "status": "FAILED" }
```

**Errors**
- `404 Not Found` — task not found.
- `409 Conflict` — the task is not in `ESCALATION_PENDING`.

---

## Webhooks

These endpoints are called by **Twilio**, not by the frontend. They accept `application/x-www-form-urlencoded` bodies and return **TwiML** (XML). Every webhook validates Twilio's `X-Twilio-Signature` header (HMAC, keyed by `TWILIO_AUTH_TOKEN`) and returns `403` if the signature is invalid. They are intentionally designed to never return a `500` — on internal failure they still return valid TwiML so Twilio doesn't play its generic error message.

### POST `/webhooks/sms`
Handles inbound SMS. Validates the signature, looks up the user by phone number, routes the message through Claude, runs/schedules any tools, sends the reply via SMS, and returns empty TwiML. Unregistered numbers get a one-line onboarding nudge instead of being routed to the agent.

- **Input:** Twilio SMS form fields (`From`, `Body`, `X-Twilio-Signature`, …).
- **Output:** `200` with empty TwiML: `<?xml version="1.0" encoding="UTF-8"?><Response/>`.
- **403** on invalid signature.

### POST `/webhooks/call`
Handles an inbound voice call. Greets the caller and opens a `<Gather input="speech">` that posts the transcription to `/webhooks/call/transcript`. Unregistered numbers hear an onboarding message and the call ends.

- **Input:** Twilio voice form fields (`From`, `CallSid`, …).
- **Output:** `200` with TwiML (`<Gather>` + `<Say>`).
- **403** on invalid signature.

### POST `/webhooks/call/transcript`
Receives the speech transcription for an in-progress inbound call, runs it through Claude (with per-call conversation memory keyed by `CallSid`), dispatches any tool steps, speaks the reply, and gathers the next turn. Saying a goodbye phrase ("goodbye", "bye bye", "talk later", …) or staying silent ends the call cleanly.

- **Input:** Twilio fields including `CallSid`, `From`, `SpeechResult`.
- **Output:** `200` with TwiML.
- **403** on invalid signature.

### POST `/webhooks/call/outbound-transcript`
Drives an **outbound** business call (G calling, say, a pizza place on the parent's behalf). Twilio posts here each time the business employee finishes speaking. G runs Claude against the call's goal plus history and returns the next line, or hangs up and texts the parent a one-line summary when the goal is confirmed complete. Call state is tracked by `CallSid`; if the server restarted mid-call and the state is gone, G hangs up politely.

- **Input:** Twilio fields including `CallSid`, `SpeechResult`.
- **Output:** `200` with TwiML (continue gathering, or hang up).
- **403** on invalid signature.

---

## Debug endpoints

These are mounted only when the `DEBUG` environment variable is `true`, so they cannot be reached in production.

### POST `/debug/call`
Place an outbound call. The recipient hears `message`, then G listens and routes their speech through the normal transcript flow.

**Request body**
```json
{ "to": "+13105550199", "message": "Hi, this is a test call from G." }
```
**200:** `{ "status": "called", "sid": "<twilio-call-sid>" }`.
**Errors:** `500` if `PUBLIC_BASE_URL` is unset (Twilio needs an absolute callback URL); `400` if the call fails.

### POST `/debug/sms`
Send an outbound SMS.

**Request body**
```json
{ "to": "+13105550199", "body": "Test message from G." }
```
**200:** `{ "status": "sent", "sid": "<twilio-message-sid>" }`. **400** on failure.

### POST `/debug/notify/{user_id}`
Fire a proactive notification at a registered user, going through the same `notify_user` path the scheduler uses (channel routing, quiet hours, outbound logging).

**Request body**
```json
{ "message": "Don't forget Sam's dentist appt at 4pm.", "channel": "sms", "force": false }
```
| Field | Type | Default | Description |
|---|---|---|---|
| `message` | string | — | Text to deliver |
| `channel` | string \| null | user's `preferred_channel` | `"sms"` or `"call"` |
| `force` | boolean | `false` | Bypass the quiet-hours check |

**200:** the result of `notify_user`. **Errors:** `404` if the user doesn't exist; `400` on a value error.

---

## Schemas

### UserResponse
The canonical user object returned by the user, auth, and registration endpoints.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | |
| `name` | string \| null | Maps to the `name` DB column |
| `phone_number` | string \| null | |
| `email` | string \| null | |
| `comm_style` | `CommStyle` | `brief` / `detailed` |
| `preferred_channel` | `PreferredChannel` | `sms` / `call` |
| `call_urgency_threshold` | `CallUrgency` | `any` / `high` / `never` |
| `blocked_windows` | list \| dict \| null | Times G should not contact the user |
| `keep_free_windows` | list \| dict \| null | Times to keep free on the calendar |
| `active_days` | list \| null | Days G is active |
| `morning_digest_enabled` | boolean | |
| `morning_digest_time` | string \| null | `"HH:MM"` (max length 5) |
| `morning_digest_content` | `DigestContent` | `calendar` / `calendar+email` / `calendar+tasks` |
| `morning_digest_travel_time` | boolean | Include travel-time estimates |
| `escalation_timeout_minutes` | integer | |
| `auto_approve_low_risk` | boolean | |
| `max_reminders` | integer | |
| `tone` | `Tone` | `casual` / `formal` |
| `reminder_lead_time_minutes` | integer | |
| `conflict_handling` | `ConflictHandling` | `suggest` / `flag` |

### UserCreate
| Field | Type | Required | Notes |
|---|---|---|---|
| `phone_number` | string | yes | |
| `email` | string \| null | no | |
| `name` | string \| null | no | max length 120 |

### UserRegister
| Field | Type | Required |
|---|---|---|
| `name` | string | yes |
| `email` | string | yes |
| `password` | string | yes |

### UserLogin
| Field | Type | Required |
|---|---|---|
| `email` | string | yes |
| `password` | string | yes |

### AuthResponse
| Field | Type |
|---|---|
| `user` | `UserResponse` |
| `token` | string (JWT) |

### UserProfileUpdate
All optional. `name` (≤120), `email` (≤255), `phone_number` (≤20). `phone_number` is only settable when the user currently has none.

### UserPreferencesUpdate
All fields optional; only those sent (and non-null) are written.

| Field | Type | Constraints |
|---|---|---|
| `comm_style` | `CommStyle` | |
| `preferred_channel` | `PreferredChannel` | |
| `call_urgency_threshold` | `CallUrgency` | |
| `blocked_windows` | list \| dict | |
| `keep_free_windows` | list \| dict | |
| `active_days` | list[string] | |
| `morning_digest_enabled` | boolean | |
| `morning_digest_time` | string | max length 5 (`"HH:MM"`) |
| `morning_digest_content` | `DigestContent` | |
| `morning_digest_travel_time` | boolean | |
| `escalation_timeout_minutes` | integer | 5–120 |
| `auto_approve_low_risk` | boolean | |
| `max_reminders` | integer | 1–10 |
| `tone` | `Tone` | |
| `reminder_lead_time_minutes` | integer | ≥ 1 |
| `conflict_handling` | `ConflictHandling` | |

### TaskResponse
| Field | Type | Notes |
|---|---|---|
| `id` | UUID | |
| `status` | `TaskStatus` | |
| `type` | string | task type, e.g. `reminder` |
| `description` | string | |
| `plan_steps` | list \| dict \| null | JSONB plan, passed through as-is |
| `escalation_deadline` | datetime \| null | |
| `created_at` | datetime | |
| `updated_at` | datetime | |

### MessageResponse
| Field | Type | Notes |
|---|---|---|
| `id` | UUID | |
| `content` | string | |
| `direction` | `MessageDirection` | `inbound` / `outbound` |
| `channel` | `MessageChannel` | `sms` / `voice` / `chat` |
| `timestamp` | datetime | |
| `task_id` | UUID \| null | Links a message to the task that sent it |

### ContactCreate / ContactUpdate / ContactResponse
- **Create:** `name` (required, 1–120), `role` (≤120), `org` (≤160), `phone` (≤40).
- **Update:** same fields, all optional.
- **Response:** `id`, `user_id`, `name`, `role`, `org`, `phone`, `created_at`.

### ProviderCreate / ProviderUpdate / ProviderResponse
- **Create:** `name` (required, 1–120), `specialty` (≤120), `practice` (≤160).
- **Update:** same fields, all optional.
- **Response:** `id`, `user_id`, `name`, `specialty`, `practice`, `created_at`.

### FamilyMemberCreate / FamilyMemberUpdate / FamilyMemberResponse
- **Create:** `name` (required, 1–120), `relation` (≤60), `phone_number` (≤20).
- **Update:** same fields, all optional.
- **Response:** `id`, `user_id`, `name`, `relation`, `phone_number`, `created_at`.

### ChatRequest
| Field | Type | Required |
|---|---|---|
| `message` | string | yes |
| `user_id` | string \| null | no |
| `messages` | list[dict] \| null | no |

---

## Enums

### Tools (enum)
Tool names G's planner can put in `plan_steps`.

| Value | Meaning |
|---|---|
| `sms_tool` | Text the parent |
| `call_tool` | Call the parent |
| `business_call_tool` | Call an external business on the parent's behalf, then SMS a summary |
| `calendar_tool` | Create/update a Google Calendar event |
| `calendar_delete_tool` | Delete a calendar event |
| `script_tool` | (reserved) |
| `gmail_tool` | Read Gmail |

### TaskStatus
`PENDING`, `IN_PROGRESS`, `ESCALATION_PENDING`, `COMPLETED`, `FAILED`.

### TaskType
`reminder`, `calendar_update`, `information_request`, `morning_digest`, `smalltalk`.

### CommStyle
`brief`, `detailed`.

### PreferredChannel
`sms`, `call`.

### CallUrgency
`any` (always call), `high` (call only for high-urgency tasks), `never` (stay on SMS).

### DigestContent
`calendar`, `calendar+email`, `calendar+tasks`.

### Tone
`casual`, `formal`.

### ConflictHandling
`suggest` (propose a reschedule), `flag` (just surface it, let the parent decide).

### MessageDirection
`inbound`, `outbound`.

### MessageChannel
`sms`, `voice`, `chat`.

---

## Configuration reference

Environment variables read by the backend (`config.py`). Secrets must be supplied via the environment; the defaults shown for non-secrets are illustrative.

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Postgres connection string |
| `SUPABASE_URL` / `SUPABASE_ANON_KEY` / `SUPABASE_SERVICE_ROLE_KEY` | Supabase access |
| `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` / `TWILIO_PHONE_NUMBER` | Twilio SMS + voice (auth token also validates webhook signatures) |
| `ANTHROPIC_API_KEY` | Claude (primary LLM) |
| `OPENAI_API_KEY` | Fallback LLM |
| `DEEPGRAM_API_KEY` | Speech-to-text (planned real-time STT) |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REDIRECT_URI` | Google OAuth (Calendar + Gmail) |
| `FRONTEND_URL` / `FRONTEND_ORIGIN` | Redirect target after OAuth / extra CORS origin |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | Redis broker/result backend for scheduled tasks |
| `JWT_SECRET` / `JWT_EXPIRE_MINUTES` | JWT signing key and lifetime (default 7 days) |
| `TOKEN_ENCRYPTION_KEY` | Encrypts stored third-party tokens |
| `APP_ENV` | `development` / `staging` / `prod` |
| `LOG_LEVEL` | Logging verbosity |
| `DEBUG` | When `true`, mounts the `/debug/*` endpoints |
| `PUBLIC_BASE_URL` | Absolute base URL Twilio uses for callbacks (required by `/debug/call`) |

---

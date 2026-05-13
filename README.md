# G: Parent's personal secretary

This is the project directory for CS130 project.

## Setup

You'll need: Python 3.10+, a Twilio account with an SMS-capable **local** (non-toll-free) phone number, and [ngrok](https://ngrok.com) to expose your local server so Twilio can reach it.

### 1. Install backend deps

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Open `backend/.env` and fill in `TWILIO_AUTH_TOKEN` (Twilio Console → Account → Auth Token). 

### 2. Run the server

```bash
.venv/bin/uvicorn main:app --reload --proxy-headers --forwarded-allow-ips="*"
```

`--proxy-headers` is **required** when running behind ngrok — without it the URL the server reconstructs won't match the URL Twilio signed, and every webhook will 403.

### 3. Expose it via ngrok

In a separate terminal:

```bash
brew install ngrok                            # first time only
ngrok config add-authtoken <YOUR_AUTHTOKEN>   # first time only — copy from ngrok dashboard
ngrok http 8000
```

Copy the `https://*.ngrok-free.app` URL it prints. This URL changes every time you restart ngrok on the free tier — you'll need to re-paste it into Twilio each session.

### 4. Configure Twilio webhooks

In the Twilio Console → Phone Numbers → your number:

- **Voice Configuration** → "A call comes in" → Webhook → `https://<ngrok-url>/webhooks/call`, HTTP POST

Save both.

### 5. Test

- **Voice**: call your Twilio number — you should hear "Hi, this is G. What can I help you with?", and after you speak, hear your speech repeated back before it hangs up.


### File structure for now:
If you create new files or change directory structures, please run the 'tree' command in yoru terminal and update this section so everyone knows the new strucutre. 

```bash
.
├── backend
│   ├── adapters
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── communication
│   │   │   ├── __init__.py
│   │   │   ├── call_tool.py
│   │   │   └── sms_tool.py
│   │   ├── google
│   │   │   ├── __init__.py
│   │   │   ├── calendar_tool.py
│   │   │   └── gmail_tool.py
│   │   ├── llm
│   │   │   ├── __init__.py
│   │   │   ├── base_llm_adapter.py
│   │   │   ├── claude_adapter.py
│   │   │   └── gpt_adapter.py
│   │   └── speech
│   │       ├── __init__.py
│   │       └── deepgram_adapter.py
│   ├── alembic.ini
│   ├── api
│   │   ├── __init__.py
│   │   ├── auth
│   │   │   ├── __init__.py
│   │   │   └── oauth.py
│   │   └── webhooks
│   │       ├── __init__.py
│   │       ├── call.py
│   │       └── sms.py
│   ├── config.py
│   ├── database.py
│   ├── main.py
│   ├── middleware
│   │   ├── __init__.py
│   │   └── twilio_signature.py
│   ├── migrations
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions
│   ├── models
│   │   ├── __init__.py
│   │   ├── message.py
│   │   ├── preference.py
│   │   ├── task.py
│   │   └── user.py
│   ├── orchestrator
│   │   ├── __init__.py
│   │   ├── escalation_engine.py
│   │   ├── orchestrator.py
│   │   └── task_planner.py
│   ├── README.md
│   ├── requirements.txt
│   ├── schemas
│   │   ├── __init__.py
│   │   ├── message.py
│   │   ├── task.py
│   │   └── user.py
│   ├── services
│   │   ├── __init__.py
│   │   ├── message_service.py
│   │   ├── task_service.py
│   │   └── user_service.py
│   └── workers
│       ├── __init__.py
│       ├── celery_app.py
│       └── task_runner.py
├── CS130 Captone Design Doc Team 1.pdf
├── docker-compose.yml
├── frontend
│   ├── index.html
│   ├── package.json
│   ├── public
│   │   └── favicon.ico
│   ├── README.md
│   ├── src
│   │   ├── api
│   │   │   ├── auth.js
│   │   │   └── index.js
│   │   ├── App.jsx
│   │   ├── components
│   │   │   ├── common
│   │   │   │   ├── Button.jsx
│   │   │   │   └── Input.jsx
│   │   │   └── registration
│   │   │       ├── GoogleAuthButton.jsx
│   │   │       ├── PreferencesForm.jsx
│   │   │       └── RegistrationForm.jsx
│   │   ├── main.jsx
│   │   ├── pages
│   │   │   ├── OAuthCallback.jsx
│   │   │   └── Register.jsx
│   │   └── styles
│   │       └── index.css
│   └── vite.config.js
├── Project_Guideline__Idea,_Design_Doc,_Presentation.docx.pdf
└── README.md

```
27 directories, 71 files
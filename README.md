# G: Parent's personal secretary

This is the project directory for CS130 project. 





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




### How to run tests

We are currently using a pytest directory under /test. run

```bash
pytest tests -v

```

to run all tests in the directory. Pelase create different tests under organized layout similar to the actual directory to keep it easy to maintain. 
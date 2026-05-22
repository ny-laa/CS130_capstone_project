# main entry point, run this to start the server
# registers all the routes and middleware and stuff

from fastapi import FastAPI

from api.webhooks import call, sms

app = FastAPI(title="G")
app.include_router(sms.router)
app.include_router(call.router)

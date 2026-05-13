# loads env vars and app settings
# all the secrets like twilio keys and db url should be here, not hardcoded pls

import os

from dotenv import load_dotenv

load_dotenv()

TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")

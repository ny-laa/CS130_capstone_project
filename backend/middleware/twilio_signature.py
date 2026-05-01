# security layer: validates that requests actually come from twilio
# uses HMAC-SHA1 sig validation, we should make sure this is really sucure.
# if this fails just reject the request

# gmail tool is currently read only 
# access token is passed directly in params for now

import base64
from typing import Any
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from adapters.base import BaseToolAdapter
from sqlalchemy.orm import Session
from uuid import UUID
from services.user_service import get_access_token

class GmailTool(BaseToolAdapter):
    def __init__(self):
        super().__init__("gmail_tool")

    def _build_service(self, access_token: str): # creates Gmail API service object w/ users access token
        creds = Credentials(token=access_token)
        return build("gmail", "v1", credentials=creds)

    def _get_header(self, headers: list[dict[str, str]], header_name: str) -> str | None:
        # Gmail will return headers as a list of {"name": ..., "value": ...}
        # This helper finds the header we care about (ex: Subject, From, etcc) 
        for header in headers:
            if header.get("name", "").lower() == header_name.lower():
                return header.get("value")
        return None

    def _decode_body_data(self, data: str) -> str:
        # Gmail body data is base64url encoded => so we decode it into readable text
        decoded_bytes = base64.urlsafe_b64decode(data)
        return decoded_bytes.decode("utf-8", errors="ignore")

    def _extract_plain_text(self, payload: dict[str, Any]) -> str:
        # note some eamilas have bode directly as part of payload, but others are multi part so both are handleded here 
        body = payload.get("body", {})
        if body.get("data"):
            return self._decode_body_data(body["data"])

        parts = payload.get("parts", []) # handle multipart 
        for part in parts:
            mime_type = part.get("mimeType")
            part_body = part.get("body", {})

            if mime_type == "text/plain" and part_body.get("data"):
                return self._decode_body_data(part_body["data"])

            # handle nested parts
            if part.get("parts"):
                nested_text = self._extract_plain_text(part)
                if nested_text:
                    return nested_text

        return ""

    def read(
        self,
        access_token: str,
        query: str = "",
        max_results: int = 10,
        include_body: bool = False,
    ) -> list[dict[str, Any]]:
        """
        query uses Gmail search syntax.
        Example queries:
        - "hospital newer_than:1d"
        - "from:uclastud@example.com"
        - "subject:meeting newer_than:7d"
        """
        service = self._build_service(access_token)
        search_result = (
            service.users()
            .messages()
            .list(
                userId="me",
                q=query,
                maxResults=max_results,
            )
            .execute()
        )

        messages = search_result.get("messages", [])
        simplified_emails = []
        for message in messages:
            message_id = message.get("id")

            email_result = (
                service.users()
                .messages()
                .get(
                    userId="me",
                    id=message_id,
                    format="full",
                )
                .execute()
            )

            payload = email_result.get("payload", {})
            headers = payload.get("headers", [])
            email_info = {
                "id": email_result.get("id"),
                "thread_id": email_result.get("threadId"),
                "from": self._get_header(headers, "From"),
                "to": self._get_header(headers, "To"),
                "subject": self._get_header(headers, "Subject"),
                "date": self._get_header(headers, "Date"),
                "snippet": email_result.get("snippet"),
            }

            if include_body:
                email_info["body"] = self._extract_plain_text(payload)

            simplified_emails.append(email_info)

        return simplified_emails

    def execute(self, params: dict[str, Any], db: Session) -> Any: # main method called by orch
        user_id: UUID = params.get("user_id")
        if not user_id:
            raise ValueError("user_id needed")
        
        op = params.get("operation", "read")
        access_token = get_access_token(db, user_id)

        if not access_token:
            raise ValueError("access_token is required")

        if op == "read":
            return self.read(
                access_token=access_token,
                query=params.get("query", ""),
                max_results=params.get("max_results", 10),
                include_body=params.get("include_body", False),
            )

        raise ValueError(f"Unsupported gmail operation: {op}")
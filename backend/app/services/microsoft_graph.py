from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import msal

from app.config import get_settings


class MicrosoftGraphClient:
    _active_device_flow: dict[str, Any] | None = None
    _app: msal.PublicClientApplication | None = None
    _cache_path = Path(__file__).resolve().parents[1] / ".msal_token_cache.bin"

    def __init__(self) -> None:
        self.settings = get_settings()

        if not self.settings.graph_configured:
            raise ValueError("Microsoft Graph settings are not configured. Set MICROSOFT_TENANT_ID and MICROSOFT_CLIENT_ID.")

        if self.__class__._app is None:
            token_cache = msal.SerializableTokenCache()
            if self._cache_path.exists():
                # msal.SerializableTokenCache.deserialize expects a string
                token_cache.deserialize(self._cache_path.read_text(encoding='utf-8'))

            self.__class__._app = msal.PublicClientApplication(
                client_id=self.settings.microsoft_client_id,
                authority=f"{self.settings.microsoft_authority_host}/{self.settings.microsoft_tenant_id}",
                token_cache=token_cache,
            )

        self._app = self.__class__._app

    def _save_token_cache(self) -> None:
        if self._app is None:
            return

        # serialize() returns a string; write as text to disk
        try:
            self._cache_path.write_text(self._app.token_cache.serialize(), encoding='utf-8')
        except Exception:
            # Best-effort save; do not raise to avoid breaking API calls
            return

    def start_device_flow(self) -> dict[str, Any]:
        if self._app is None:
            raise ValueError("MSAL public client application is not initialized.")

        flow = self._app.initiate_device_flow(scopes=self.settings.graph_scope_list)
        if "user_code" not in flow or "device_code" not in flow:
            raise ValueError("Unable to start the Microsoft device flow.")

        self.__class__._active_device_flow = flow

        return {
            "message": "Open the verification URL in a browser and sign in with your Microsoft 365 account.",
            "verification_uri": flow["verification_uri"],
            "user_code": flow["user_code"],
            "device_code": flow["device_code"],
            "expires_in": flow.get("expires_in"),
            "interval": flow.get("interval"),
            "message_text": flow.get("message"),
        }

    def acquire_token_by_device_flow(self, flow: dict[str, Any]) -> dict[str, Any]:
        if self._app is None:
            raise ValueError("MSAL public client application is not initialized.")
        if not flow:
            raise ValueError("No active device flow exists. Please start Microsoft login first.")

        result = self._app.acquire_token_by_device_flow(flow)
        if "access_token" not in result:
            raise ValueError(result.get("error_description", "Authentication is still pending or was denied."))

        self._save_token_cache()
        self.__class__._active_device_flow = None

        return {
            "status": "success",
            "expires_in": result.get("expires_in"),
            "scope": result.get("scope"),
            "token_type": result.get("token_type"),
        }

    def complete_device_flow(self) -> dict[str, Any]:
        if not self.__class__._active_device_flow:
            raise ValueError("No active Microsoft device flow exists. Please call /microsoft/login first.")
        return self.acquire_token_by_device_flow(self.__class__._active_device_flow)

    def get_access_token(self) -> str:
        if self._app is None:
            raise ValueError("MSAL public client application is not initialized.")

        accounts = self._app.get_accounts()
        if not accounts:
            raise ValueError("No signed-in Microsoft user session is available. Run the device login flow first.")

        for account in accounts:
            result = self._app.acquire_token_silent(self.settings.graph_scope_list, account=account)
            if "access_token" in result:
                self._save_token_cache()
                return str(result["access_token"])

        raise ValueError("No signed-in Microsoft user session is available. Run the device login flow first.")

    async def get_me(self) -> dict[str, Any]:
        token = self.get_access_token()
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get("https://graph.microsoft.com/v1.0/me", headers=headers)
            response.raise_for_status()
            return response.json()

    async def get_todo_tasks(self) -> dict[str, Any]:
        token = self.get_access_token()
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get("https://graph.microsoft.com/v1.0/me/todo/lists", headers=headers)
            response.raise_for_status()
            return response.json()

    async def get_flagged_emails(self) -> dict[str, Any]:
        token = self.get_access_token()
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

        async with httpx.AsyncClient(timeout=20.0) as client:
            lists_response = await client.get("https://graph.microsoft.com/v1.0/me/todo/lists", headers=headers)
            lists_response.raise_for_status()
            lists_payload = lists_response.json()
            flagged_list = None

            for item in lists_payload.get("value", []):
                if item.get("wellknownListName") == "flaggedEmails":
                    flagged_list = item
                    break

            if flagged_list is None:
                raise ValueError("The Microsoft flaggedEmails list was not found in the signed-in user's To Do lists.")

            list_id = flagged_list["id"]
            tasks_response = await client.get(f"https://graph.microsoft.com/v1.0/me/todo/lists/{list_id}/tasks", headers=headers)
            tasks_response.raise_for_status()
            return tasks_response.json()

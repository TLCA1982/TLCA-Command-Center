from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException

from app.services.microsoft_graph import MicrosoftGraphClient
from app.services import companies as company_service
from app.config import get_settings

router = APIRouter(prefix="/microsoft", tags=["microsoft"])


@router.get("/health")
async def microsoft_health() -> dict[str, str]:
    settings = __import__("app.config", fromlist=["get_settings"]).get_settings()
    if not settings.graph_configured:
        return {"status": "not_configured"}
    return {"status": "configured"}


@router.post("/login")
async def start_microsoft_login() -> dict:
    try:
        client = MicrosoftGraphClient()
        return client.start_device_flow()
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/login/complete")
async def complete_microsoft_login() -> dict:
    try:
        client = MicrosoftGraphClient()
        return client.complete_device_flow()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/me")
async def get_current_user() -> dict:
    try:
        client = MicrosoftGraphClient()
        return await client.get_me()
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get("/todo/tasks")
async def get_todo_tasks() -> dict:
    try:
        client = MicrosoftGraphClient()
        return await client.get_todo_tasks()
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.get("/flagged-emails")
async def get_flagged_emails() -> dict:
    try:
        client = MicrosoftGraphClient()
        return await client.get_flagged_emails()
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/contacts/reconcile")
async def reconcile_contacts() -> dict:
    try:
        client = MicrosoftGraphClient()
        configured = client.settings.outlook_business_category_list
        outlook_contacts = await client.get_contacts_for_categories(configured)
        result = company_service.reconcile_outlook_contacts(outlook_contacts)
        return {"configured_categories": configured, **result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/contacts/reconcile/preview")
async def preview_contact_reconciliation() -> dict:
    return {"configured_categories": get_settings().outlook_business_category_list}

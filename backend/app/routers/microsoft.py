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


@router.get("/contacts/reconcile/preview/results")
async def preview_reconciliation_results() -> dict:
    try:
        client = MicrosoftGraphClient()
        configured = client.settings.outlook_business_category_list
        outlook_contacts = await client.get_contacts_for_categories(configured)
        return {"configured_categories": configured, **company_service.preview_outlook_reconciliation(outlook_contacts)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        graph_status = exc.response.status_code
        raise HTTPException(status_code=graph_status if 400 <= graph_status < 500 else 502, detail=f"Microsoft Graph returned HTTP {graph_status} while reading Outlook contacts.") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="Microsoft Graph could not be reached while reading Outlook contacts.") from exc


@router.get("/contacts/reconcile/preview/candidates")
async def preview_reconciliation_candidates() -> dict:
    try:
        client = MicrosoftGraphClient()
        configured = client.settings.outlook_business_category_list
        outlook_contacts = await client.get_contacts_for_categories(configured)
        return {"configured_categories": configured, **company_service.preview_outlook_candidates(outlook_contacts)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        graph_status = exc.response.status_code
        raise HTTPException(status_code=graph_status if 400 <= graph_status < 500 else 502, detail=f"Microsoft Graph returned HTTP {graph_status} while reading Outlook contacts.") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="Microsoft Graph could not be reached while reading Outlook contacts.") from exc


@router.get("/contacts/reconcile/preview/linked")
async def preview_linked_contacts() -> dict:
    try:
        client = MicrosoftGraphClient()
        linked_ids = company_service.get_linked_outlook_ids()
        outlook_contacts = []
        for contact_id in linked_ids:
            contact = await client.get_contact_by_id(contact_id)
            if contact is not None:
                outlook_contacts.append(contact)
        return {"configured_categories": client.settings.outlook_business_category_list, **company_service.compare_linked_outlook_contacts(outlook_contacts)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        graph_status = exc.response.status_code
        raise HTTPException(status_code=graph_status if 400 <= graph_status < 500 else 502, detail=f"Microsoft Graph returned HTTP {graph_status} while reading linked Outlook contacts.") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="Microsoft Graph could not be reached while reading linked Outlook contacts.") from exc


@router.post("/contacts/sync")
async def sync_linked_contacts() -> dict:
    try:
        return await company_service.synchronize_linked_outlook_contacts(MicrosoftGraphClient())
    except company_service.LinkedContactSyncError as exc:
        raise HTTPException(
            status_code=502,
            detail={"message": str(exc), "compensation_complete": exc.compensation_complete},
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail="Microsoft Graph update failed while synchronizing linked contacts.") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="Microsoft Graph could not be reached while synchronizing linked contacts.") from exc


@router.get("/contacts/reconcile/preview")
async def preview_contact_reconciliation() -> dict:
    return {"configured_categories": get_settings().outlook_business_category_list}

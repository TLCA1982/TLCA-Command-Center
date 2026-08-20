from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, HTTPException

from app.services.microsoft_graph import MicrosoftGraphClient
from app.services import manual_actions
from app.services import microsoft_metadata
from app.services import dossiers as dossier_service

router = APIRouter(prefix="/actions", tags=["actions"])


GRAPH_TIMEZONE_MAP = {
    "UTC": "UTC",
    "W. Europe Standard Time": "Europe/Berlin",
    "Romance Standard Time": "Europe/Paris",
    "Central Europe Standard Time": "Europe/Budapest",
}
TARGET_TIMEZONE = ZoneInfo("Europe/Brussels")


async def _get_all_todo_tasks(http_client: httpx.AsyncClient, list_id: str, headers: dict[str, str]) -> list[dict[str, Any]]:
    next_url = f"https://graph.microsoft.com/v1.0/me/todo/lists/{list_id}/tasks"
    tasks: list[dict[str, Any]] = []

    while next_url:
        tasks_response = await http_client.get(next_url, headers=headers)
        tasks_response.raise_for_status()
        tasks_payload = tasks_response.json()
        tasks.extend(tasks_payload.get("value", []))
        next_url = tasks_payload.get("@odata.nextLink")

    return tasks


def _normalize_date(value: Any) -> str:
    if not value:
        return ""

    if isinstance(value, str):
        return value.split("T")[0]

    if isinstance(value, dict):
        date_value = value.get("dateTime")
        if date_value:
            raw_timezone = str(value.get("timeZone") or "UTC")
            timezone_name = GRAPH_TIMEZONE_MAP.get(raw_timezone, raw_timezone)

            try:
                source_timezone = ZoneInfo(timezone_name)
            except Exception:
                source_timezone = timezone.utc

            parsed = datetime.fromisoformat(str(date_value).rstrip("Z"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=source_timezone)

            return parsed.astimezone(TARGET_TIMEZONE).date().isoformat()

        date_value = value.get("date")
        if date_value:
            return str(date_value).split("T")[0]

    return ""


def _map_status(status: str | None) -> str:
    status_map = {
        "notStarted": "Open",
        "inProgress": "Open",
        "completed": "Afgewerkt",
        "waitingOnOthers": "Wachtend",
        "deferred": "Uitgesteld",
    }
    return status_map.get(status, "Open")


def _map_importance(importance: str | None) -> str:
    importance_map = {
        "high": "Hoog",
        "normal": "Normaal",
        "low": "Laag",
    }
    return importance_map.get(importance, "Normaal")


def _normalize_task(task: dict[str, Any], source: str, microsoft_list: str) -> dict[str, Any]:
    body = task.get("body")
    body_content = body.get("content") if isinstance(body, dict) else ""

    linked_resources = task.get("linkedResources") or []
    web_link = task.get("webUrl")
    if not web_link and isinstance(linked_resources, list):
        for resource in linked_resources:
            if isinstance(resource, dict):
                candidate = resource.get("webUrl") or resource.get("applicationName")
                if candidate:
                    web_link = candidate
                    break

    return {
        "id": task.get("id", ""),
        "title": task.get("title", ""),
        "source": source,
        "status": _map_status(task.get("status")),
        "priority": _map_importance(task.get("importance")),
        "dueDate": _normalize_date(task.get("dueDateTime")),
        "createdDate": _normalize_date(task.get("createdDateTime")),
        "lastModifiedDate": _normalize_date(task.get("lastModifiedDateTime")),
        "customer": "",
        "contact": "",
        "notes": body_content,
        "webLink": web_link or "",
        "microsoftList": microsoft_list,
    }


async def _get_flagged_email_sender(http_client: httpx.AsyncClient, headers: dict[str, str], task: dict[str, Any]) -> dict[str, str]:
    linked_resources = task.get("linkedResources") or []
    if not isinstance(linked_resources, list):
        return {"senderName": "", "senderEmail": ""}

    for resource in linked_resources:
        if not isinstance(resource, dict):
            continue

        external_id = resource.get("externalId")
        application_name = str(resource.get("applicationName") or "").lower()
        if not external_id or ("outlook" not in application_name and "mail" not in application_name):
            continue

        try:
            message_response = await http_client.get(
                f"https://graph.microsoft.com/v1.0/me/messages/{quote(str(external_id), safe='')}",
                params={"$select": "from"},
                headers=headers,
            )
            message_response.raise_for_status()
            sender = message_response.json().get("from") or {}
            sender_address = sender.get("emailAddress") or {}
            return {
                "senderName": str(sender_address.get("name") or ""),
                "senderEmail": str(sender_address.get("address") or ""),
            }
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            return {"senderName": "", "senderEmail": ""}

    return {"senderName": "", "senderEmail": ""}


@router.get("/microsoft")
async def get_microsoft_actions() -> list[dict[str, Any]]:
    try:
        client = MicrosoftGraphClient()
        token = client.get_access_token()
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    combined: dict[str, dict[str, Any]] = {}

    try:
        async with httpx.AsyncClient(timeout=20.0) as http_client:
            lists_response = await http_client.get("https://graph.microsoft.com/v1.0/me/todo/lists", headers=headers)
            lists_response.raise_for_status()
            lists_payload = lists_response.json()

            for list_item in lists_payload.get("value", []):
                list_id = list_item.get("id")
                if not list_id:
                    continue

                list_name = list_item.get("displayName") or list_item.get("wellknownListName") or "Microsoft To Do"
                is_flagged_list = list_item.get("wellknownListName") == "flaggedEmails"
                source = "Outlook gemarkeerde mail" if is_flagged_list else "Microsoft To Do"

                tasks = await _get_all_todo_tasks(http_client, list_id, headers)

                for task in tasks:
                    normalized = _normalize_task(task, source, list_name)
                    if not normalized["id"]:
                        continue

                    if is_flagged_list:
                        normalized.update(await _get_flagged_email_sender(http_client, headers, task))

                    # merge local metadata if present
                    meta = microsoft_metadata.get(normalized["id"]) or {}
                    normalized["customer"] = meta.get("customer", "")
                    normalized["contact"] = meta.get("contact", "")
                    # return actionType in the same field name used by manual actions
                    normalized["actionType"] = meta.get("action_type") or normalized.get("actionType") or ""

                    combined.setdefault(normalized["id"], normalized)

    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Microsoft Graph request failed while collecting actions.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return list(combined.values())


@router.get("/manual")
async def get_manual_actions() -> list[dict[str, Any]]:
    # return manual actions stored locally
    try:
        records = manual_actions.get_all()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # normalize to same shape as microsoft endpoint
    normalized = []
    for r in records:
        normalized.append({
            "id": r.get("id", ""),
            "title": r.get("title", ""),
            "source": r.get("source", "Command Center"),
            "status": r.get("status", "Open"),
            "priority": r.get("priority", "Normaal"),
            "dueDate": r.get("dueDate", ""),
            "createdDate": r.get("createdDate", ""),
            "lastModifiedDate": r.get("lastModifiedDate", ""),
            "customer": r.get("customer", ""),
            "contact": r.get("contact", ""),
            "notes": r.get("notes", ""),
            "webLink": "",
            "microsoftList": "",
            "actionType": r.get("type", ""),
        })

    return normalized


@router.post("/manual")
async def create_manual_action(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload.get("title"):
        raise HTTPException(status_code=400, detail="Title is required")

    try:
        record = manual_actions.create(payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "id": record.get("id"),
        "title": record.get("title"),
        "source": record.get("source", "Command Center"),
        "status": record.get("status", "Open"),
        "priority": record.get("priority", "Normaal"),
        "dueDate": record.get("dueDate", ""),
        "createdDate": record.get("createdDate", ""),
        "lastModifiedDate": record.get("lastModifiedDate", ""),
        "customer": record.get("customer", ""),
        "contact": record.get("contact", ""),
        "notes": record.get("notes", ""),
        "webLink": "",
        "microsoftList": "",
        "actionType": record.get("type", ""),
    }


@router.put("/manual/{action_id}")
async def update_manual_action(action_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        updated = manual_actions.update(action_id, payload)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if updated is None:
        raise HTTPException(status_code=404, detail="Manual action not found")

    return {
        "id": updated.get("id"),
        "title": updated.get("title"),
        "source": updated.get("source", "Command Center"),
        "status": updated.get("status", "Open"),
        "priority": updated.get("priority", "Normaal"),
        "dueDate": updated.get("dueDate", ""),
        "createdDate": updated.get("createdDate", ""),
        "lastModifiedDate": updated.get("lastModifiedDate", ""),
        "customer": updated.get("customer", ""),
        "contact": updated.get("contact", ""),
        "notes": updated.get("notes", ""),
        "webLink": "",
        "microsoftList": "",
        "actionType": updated.get("type", ""),
    }


@router.delete("/manual/{action_id}")
async def delete_manual_action(action_id: str) -> dict[str, Any]:
    try:
        ok = manual_actions.delete(action_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not ok:
        raise HTTPException(status_code=404, detail="Manual action not found")

    return {"deleted": True}


@router.get("/")
async def get_all_actions() -> list[dict[str, Any]]:
    # combined: manual actions + microsoft actions
    combined: dict[str, dict[str, Any]] = {}

    # add manual first so manual items are present even if ids overlap
    try:
        manual_list = manual_actions.get_all()
        for r in manual_list:
            normalized = {
                "id": r.get("id", ""),
                "title": r.get("title", ""),
                "source": r.get("source", "Command Center"),
                "status": r.get("status", "Open"),
                "priority": r.get("priority", "Normaal"),
                "dueDate": r.get("dueDate", ""),
                "createdDate": r.get("createdDate", ""),
                "lastModifiedDate": r.get("lastModifiedDate", ""),
                "customer": r.get("customer", ""),
                "contact": r.get("contact", ""),
                "notes": r.get("notes", ""),
                "webLink": "",
                "microsoftList": "",
            }
            if normalized["id"]:
                combined.setdefault(normalized["id"], normalized)
    except Exception:
        # ignore DB errors here and continue to return Microsoft actions
        pass

    # fetch microsoft actions and merge
    try:
        ms_actions = await get_microsoft_actions()
        for a in ms_actions:
            if a.get("id"):
                # ensure metadata merged here too (for the combined /actions endpoint)
                meta = microsoft_metadata.get(a.get("id")) or {}
                a["customer"] = meta.get("customer", "")
                a["contact"] = meta.get("contact", "")
                a["actionType"] = meta.get("action_type") or a.get("actionType") or ""
                combined.setdefault(a.get("id"), a)
    except HTTPException:
        # propagate microsoft errors
        raise
    except Exception:
        # ignore other errors and return manual only
        pass

    # add active dossiers as normalized actions
    try:
        ds = dossier_service.get_for_actions()
        for d in ds:
            if d.get("id"):
                combined.setdefault(d.get("id"), d)
    except Exception:
        # ignore dossier errors
        pass

    return list(combined.values())


@router.put("/microsoft/{action_id}")
async def update_microsoft_action(action_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Update editable fields of a Microsoft To Do task.

    Editable fields: dueDate (ISO YYYY-MM-DD), status (Open/Wachtend/Uitgesteld/Afgewerkt), notes (string)
    The function searches the user's To Do lists to locate the task id, then patches the task via Microsoft Graph.
    """
    try:
        client = MicrosoftGraphClient()
        token = client.get_access_token()
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/json"}

    # prepare patch body
    patch_body: dict[str, Any] = {}
    if payload.get("dueDate"):
        # Graph expects a structured dueDateTime; use midnight UTC
        iso = str(payload.get("dueDate"))
        patch_body["dueDateTime"] = {"dateTime": f"{iso}T00:00:00", "timeZone": "UTC"}
    if payload.get("notes") is not None:
        patch_body["body"] = {"contentType": "text", "content": str(payload.get("notes") or "")}

    status_map = {
        "Open": "notStarted",
        "Afgewerkt": "completed",
        "Wachtend": "waitingOnOthers",
        "Uitgesteld": "deferred",
    }
    if payload.get("status"):
        mapped = status_map.get(payload.get("status"), None)
        if mapped is not None:
            patch_body["status"] = mapped

    if not patch_body:
        raise HTTPException(status_code=400, detail="No editable fields provided.")

    try:
        async with httpx.AsyncClient(timeout=20.0) as http_client:
            # find the task by scanning lists
            lists_resp = await http_client.get("https://graph.microsoft.com/v1.0/me/todo/lists", headers=headers)
            lists_resp.raise_for_status()
            lists = lists_resp.json().get("value", [])

            found = False
            for list_item in lists:
                list_id = list_item.get("id")
                if not list_id:
                    continue
                tasks = await _get_all_todo_tasks(http_client, list_id, headers)
                for task in tasks:
                    if task.get("id") == action_id:
                        # determine source for metadata
                        is_flagged = list_item.get("wellknownListName") == "flaggedEmails"
                        source_for_meta = "Outlook gemarkeerde mail" if is_flagged else "Microsoft To Do"

                        # patch this task
                        patch_resp = await http_client.patch(f"https://graph.microsoft.com/v1.0/me/todo/lists/{list_id}/tasks/{action_id}", headers=headers, json=patch_body)
                        if patch_resp.is_error:
                            print(
                                f"[Microsoft action update] Graph PATCH failed: "
                                f"status={patch_resp.status_code} body={patch_resp.text}",
                                flush=True,
                            )
                        patch_resp.raise_for_status()
                        updated_task = {**task, **patch_resp.json()}

                        if is_flagged and payload.get("dueDate") and mapped == "waitingOnOthers":
                            status_patch_resp = await http_client.patch(
                                f"https://graph.microsoft.com/v1.0/me/todo/lists/{list_id}/tasks/{action_id}",
                                headers=headers,
                                json={"status": "waitingOnOthers"},
                            )
                            if status_patch_resp.is_error:
                                print(
                                    f"[Microsoft action update] Graph status PATCH failed: "
                                    f"status={status_patch_resp.status_code} body={status_patch_resp.text}",
                                    flush=True,
                                )
                            status_patch_resp.raise_for_status()
                            updated_task.update(status_patch_resp.json())

                        # after successful Graph update, persist local metadata if provided in payload
                        try:
                            customer = payload.get("customer") if payload.get("customer") is not None else None
                            contact = payload.get("contact") if payload.get("contact") is not None else None
                            action_type = payload.get("actionType") if payload.get("actionType") is not None else None
                            microsoft_metadata.upsert(action_id, source=source_for_meta, customer=customer, contact=contact, action_type=action_type)
                        except Exception:
                            # don't fail the whole request if local metadata save fails; best-effort
                            pass

                        canonical = _normalize_task(updated_task, source_for_meta, list_item.get("displayName") or list_item.get("wellknownListName") or "Microsoft To Do")
                        if is_flagged:
                            canonical.update(await _get_flagged_email_sender(http_client, headers, updated_task))
                        metadata = microsoft_metadata.get(action_id) or {}
                        canonical["customer"] = metadata.get("customer", "")
                        canonical["contact"] = metadata.get("contact", "")
                        canonical["actionType"] = metadata.get("action_type", "")

                        found = True
                        break
                if found:
                    break

            if not found:
                raise HTTPException(status_code=404, detail="Microsoft action not found in user's To Do lists.")

    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Microsoft Graph request failed while updating action.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return canonical


@router.delete("/microsoft/{action_id}")
async def delete_microsoft_action(action_id: str) -> dict[str, Any]:
    try:
        client = MicrosoftGraphClient()
        token = client.get_access_token()
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=20.0) as http_client:
            lists_resp = await http_client.get("https://graph.microsoft.com/v1.0/me/todo/lists", headers=headers)
            lists_resp.raise_for_status()
            lists = lists_resp.json().get("value", [])

            found = False
            for list_item in lists:
                list_id = list_item.get("id")
                if not list_id:
                    continue
                tasks = await _get_all_todo_tasks(http_client, list_id, headers)
                for task in tasks:
                    if task.get("id") == action_id:
                        # delete the task
                        del_resp = await http_client.delete(f"https://graph.microsoft.com/v1.0/me/todo/lists/{list_id}/tasks/{action_id}", headers=headers)
                        if del_resp.status_code >= 200 and del_resp.status_code < 300:
                            found = True
                            break
                        else:
                            raise HTTPException(status_code=del_resp.status_code, detail="Failed to delete Microsoft action")
                if found:
                    break

            if not found:
                raise HTTPException(status_code=404, detail="Microsoft action not found in user's To Do lists.")

    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Microsoft Graph request failed while deleting action.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"deleted": True}

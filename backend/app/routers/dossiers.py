from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.services import dossiers as dossier_service

router = APIRouter(prefix="/dossiers", tags=["dossiers"])


@router.get("")
async def list_dossiers(active: bool = True) -> list[dict[str, Any]]:
    try:
        items = dossier_service.get_all(active_only=active)
        return items
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{dossier_id}")
async def get_dossier(dossier_id: str) -> dict[str, Any]:
    try:
        d = dossier_service.get_by_id(dossier_id)
        if d is None:
            raise HTTPException(status_code=404, detail="Dossier not found")
        return d
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("")
async def create_dossier(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        d = dossier_service.create(payload)
        return d
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.put("/{dossier_id}")
async def update_dossier(dossier_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        d = dossier_service.update(dossier_id, payload)
        if d is None:
            raise HTTPException(status_code=404, detail="Dossier not found")
        return d
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/{dossier_id}/events")
async def add_event(dossier_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        d = dossier_service.add_event(dossier_id, payload)
        if d is None:
            raise HTTPException(status_code=404, detail="Dossier not found")
        return d
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.put("/{dossier_id}/events/{event_id}")
async def update_event(dossier_id: str, event_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        d = dossier_service.update_event(dossier_id, event_id, payload)
        if d is None:
            raise HTTPException(status_code=404, detail="Dossier or event not found")
        return d
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/{dossier_id}/events/{event_id}")
async def delete_event(dossier_id: str, event_id: str) -> dict[str, Any]:
    try:
        d = dossier_service.delete_event(dossier_id, event_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if d is None:
        raise HTTPException(status_code=404, detail="Dossier or event not found")

    return {"deleted": True}


@router.delete("/{dossier_id}")
async def delete_dossier(dossier_id: str) -> dict[str, Any]:
    try:
        ok = dossier_service.delete(dossier_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not ok:
        raise HTTPException(status_code=404, detail="Dossier not found")

    return {"deleted": True}

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from app.services import companies as company_service

router = APIRouter(prefix="/companies", tags=["companies"])


def _bad_request(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


@router.get("")
async def list_companies() -> list[dict[str, Any]]:
    return company_service.get_all()


@router.post("")
async def create_company(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return company_service.create(payload)
    except ValueError as exc:
        raise _bad_request(exc) from exc


@router.get("/{company_id}")
async def get_company(company_id: str) -> dict[str, Any]:
    company = company_service.get_by_id(company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.put("/{company_id}")
async def update_company(company_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        company = company_service.update(company_id, payload)
    except ValueError as exc:
        raise _bad_request(exc) from exc
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.get("/{company_id}/contacts")
async def list_contacts(company_id: str) -> list[dict[str, Any]]:
    contacts = company_service.get_contacts(company_id)
    if contacts is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return contacts


@router.post("/{company_id}/contacts")
async def create_contact(company_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        contact = company_service.create_contact(company_id, payload)
    except company_service.OutlookContactCreationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise _bad_request(exc) from exc
    if contact is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return contact


@router.put("/{company_id}/contacts/{contact_id}")
async def update_contact(company_id: str, contact_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        contact = company_service.update_contact(company_id, contact_id, payload)
    except ValueError as exc:
        raise _bad_request(exc) from exc
    if contact is None:
        raise HTTPException(status_code=404, detail="Contact person not found for this company")
    return contact


@router.delete("/{company_id}/contacts/{contact_id}")
async def delete_contact(company_id: str, contact_id: str) -> dict[str, bool]:
    try:
        deleted = company_service.delete_contact(company_id, contact_id)
    except company_service.ContactPersonInUseError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Contact person not found for this company")
    return {"deleted": True}
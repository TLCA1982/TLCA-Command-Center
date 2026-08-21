from __future__ import annotations

import unittest
import uuid

from fastapi.testclient import TestClient

from app.main import app


class ContactPersonDeletionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        companies = cls.client.get("/companies")
        companies.raise_for_status()
        cls.company_id = companies.json()[0]["id"]

    def setUp(self) -> None:
        self.contact_ids: list[str] = []
        self.dossier_ids: list[str] = []

    def tearDown(self) -> None:
        for dossier_id in self.dossier_ids:
            self.client.delete(f"/dossiers/{dossier_id}")
        for contact_id in self.contact_ids:
            self.client.delete(f"/companies/{self.company_id}/contacts/{contact_id}")

    def create_contact(self) -> str:
        response = self.client.post(
            f"/companies/{self.company_id}/contacts",
            json={"name": f"__deletion_test_{uuid.uuid4()}__"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        contact_id = response.json()["id"]
        self.contact_ids.append(contact_id)
        return contact_id

    def create_dossier(self, contact_id: str | None = None) -> str:
        payload = {
            "company_id": self.company_id,
            "subject": f"__deletion_test_{uuid.uuid4()}__",
            "status": "Lopend",
        }
        if contact_id is not None:
            payload["primary_contact_person_id"] = contact_id
        response = self.client.post("/dossiers", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        dossier_id = response.json()["id"]
        self.dossier_ids.append(dossier_id)
        return dossier_id

    def test_unused_temporary_contact_can_be_deleted(self) -> None:
        contact_id = self.create_contact()

        response = self.client.delete(f"/companies/{self.company_id}/contacts/{contact_id}")

        self.assertEqual(response.status_code, 200, response.text)
        self.contact_ids.remove(contact_id)
        self.assertNotIn(
            contact_id,
            [contact["id"] for contact in self.client.get(f"/companies/{self.company_id}/contacts").json()],
        )

    def test_dossier_primary_contact_can_be_deleted_and_reference_is_cleared(self) -> None:
        contact_id = self.create_contact()
        dossier_id = self.create_dossier(contact_id)

        response = self.client.delete(f"/companies/{self.company_id}/contacts/{contact_id}")

        self.assertEqual(response.status_code, 200, response.text)
        self.contact_ids.remove(contact_id)
        dossier = self.client.get(f"/dossiers/{dossier_id}")
        self.assertEqual(dossier.status_code, 200, dossier.text)
        self.assertIsNone(dossier.json()["primary_contact_person_id"])

    def test_event_contact_cannot_be_deleted(self) -> None:
        contact_id = self.create_contact()
        dossier_id = self.create_dossier()
        event = self.client.post(
            f"/dossiers/{dossier_id}/events",
            json={
                "event_date": "2026-08-21",
                "event_type": "Notitie",
                "notes": "__deletion_test_event__",
                "contact_person_id": contact_id,
            },
        )
        self.assertEqual(event.status_code, 200, event.text)

        response = self.client.delete(f"/companies/{self.company_id}/contacts/{contact_id}")

        self.assertEqual(response.status_code, 409, response.text)
        self.assertIn("contact-moment history", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
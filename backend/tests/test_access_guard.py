import os
import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.secure_main import require_command_center_user
from fastapi.middleware.cors import CORSMiddleware

class AccessGuardTests(unittest.TestCase):
    def setUp(self):
        self.app=FastAPI()
        self.app.middleware('http')(require_command_center_user)
        self.app.add_middleware(CORSMiddleware,allow_origins=['https://trusted.example'],allow_methods=['*'],allow_headers=['*'])
        @self.app.get('/data')
        def data(): return {'allowed':True}
        self.client=TestClient(self.app)
        self.env=patch.dict(os.environ,{'TLCA_ALLOWED_USER_OBJECT_ID':'owner','WEBSITE_SITE_NAME':'tlca-commandcenter-api'})
        self.env.start()
    def tearDown(self): self.env.stop()
    def test_anonymous_denied(self): self.assertEqual(self.client.get('/data').status_code,401)
    def test_other_user_denied(self): self.assertEqual(self.client.get('/data',headers={'x-ms-client-principal-id':'other','x-ms-client-principal-idp':'aad'}).status_code,401)
    def test_other_provider_denied(self): self.assertEqual(self.client.get('/data',headers={'x-ms-client-principal-id':'owner','x-ms-client-principal-idp':'github'}).status_code,401)
    def test_azure_validated_owner_allowed(self): self.assertEqual(self.client.get('/data',headers={'x-ms-client-principal-id':'owner','x-ms-client-principal-idp':'aad'}).status_code,200)
    def test_missing_config_fails_closed(self):
        with patch.dict(os.environ,{'TLCA_ALLOWED_USER_OBJECT_ID':''}): self.assertEqual(self.client.get('/data').status_code,503)
    def test_preflight_has_no_data(self):
        r=self.client.options('/data',headers={'Origin':'https://trusted.example','Access-Control-Request-Method':'GET','Access-Control-Request-Headers':'authorization'})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.headers['access-control-allow-origin'],'https://trusted.example')
        self.assertNotIn('allowed',r.text)
    def test_non_azure_environment_denied(self):
        with patch.dict(os.environ,{'WEBSITE_SITE_NAME':''}): self.assertEqual(self.client.get('/data',headers={'x-ms-client-principal-id':'owner','x-ms-client-principal-idp':'aad'}).status_code,401)

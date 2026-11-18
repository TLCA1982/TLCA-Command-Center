# Production access control

Production must start with `python -m uvicorn app.secure_main:app --host 0.0.0.0 --port 8000`.
Do not use `app.main:app` as the public production entrypoint.

Azure App Service Easy Auth must remain enabled with the single-tenant Microsoft provider,
issuer and audience validation, and allowed user/client restrictions. Easy Auth validates
bearer tokens and strips externally supplied `X-MS-CLIENT-PRINCIPAL-*` headers.
The server guard trusts those headers only behind App Service, requires the configured
`TLCA_ALLOWED_USER_OBJECT_ID` and the `aad` provider, and otherwise fails closed.

The browser uses MSAL authorization code flow with PKCE. Client IDs, tenant IDs and
object IDs in browser configuration are public identifiers, never secrets. All data
requests go through `apiFetch`; tokens are attached only to the configured API origin.

After deploying `app.secure_main`, the Azure global anonymous-request policy may allow
requests to reach the guard so CORS preflight works. This must never disable the
Microsoft provider or the guard. OPTIONS responses contain no application data.

Required live checks after configuration changes: anonymous requests return 401;
spoofed identity headers return 401; wrong-audience tokens return 401; other users
are denied; only the assigned owner's valid token can read application data.

Run tests: `python -m unittest discover -s backend/tests -p test_access_guard.py`
and `node --test frontend/tests/api-auth.test.cjs`.

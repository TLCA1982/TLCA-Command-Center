"""Production entrypoint: fail-closed access control after Azure token validation."""
import os
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.main import app

# App Service Easy Auth validates tokens and strips externally supplied identity headers.
# Deny all data routes unless that trusted identity is the explicitly allowed user.
@app.middleware("http")
async def require_command_center_user(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)
    allowed_user = os.environ.get("TLCA_ALLOWED_USER_OBJECT_ID", "")
    if not allowed_user:
        return JSONResponse(status_code=503, content={"detail": "Toegangsbeveiliging is niet geconfigureerd."})
    if (not os.environ.get("WEBSITE_SITE_NAME")
            or request.headers.get("x-ms-client-principal-id") != allowed_user
            or request.headers.get("x-ms-client-principal-idp") != "aad"):
        return JSONResponse(status_code=401, content={"detail": "Microsoft-aanmelding vereist."})
    return await call_next(request)



# Keep CORS outside the access guard so the browser can receive 401 responses.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://black-flower-0d59db80f.3.azurestaticapps.net"],
    allow_credentials=False, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

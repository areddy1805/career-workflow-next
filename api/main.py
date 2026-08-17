import os
from dotenv import load_dotenv

# Load environment variables before initializing the app
load_dotenv(".env")

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router
from api.routers.audit import router as audit_router
from api.routers.ledger import router as ledger_router
from api.routers.logs import router as logs_router
from api.routers.providers import router as providers_router
from api.routers.developer import router as developer_router
from api.routers.copilot import router as copilot_router

app = FastAPI(title="Career Workflow API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
app.include_router(audit_router, prefix="/api")
app.include_router(ledger_router, prefix="/api")
app.include_router(logs_router, prefix="/api")
app.include_router(providers_router, prefix="/api")
app.include_router(developer_router, prefix="/api")
app.include_router(copilot_router, prefix="/api")
from api.routers.copilot_ext import router as copilot_ext_router

app.include_router(copilot_ext_router, prefix="/api")
from api.routers.copilot_ext_events import router as copilot_ext_events_router

app.include_router(copilot_ext_events_router, prefix="/api")

if __name__ == "__main__":
    uvicorn.run("api.main:app", host="127.0.0.1", port=8000, reload=True)

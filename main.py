import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
load_dotenv(".env")

from config.database import engine, Base
import user.adapter.outbound.persistence.models  # noqa: F401
import composition.adapter.outbound.persistence.models  # noqa: F401
import asset.adapter.outbound.models  # noqa: F401
import credit_account.adapter.outbound.models  # noqa: F401

from composition.adapter.inbound.fastapi.composition_router import router as composition_router
from user.adapter.inbound.fastapi.oauth2 import router as oauth_router
from user.adapter.inbound.fastapi.user_router import router as user_router

Base.metadata.create_all(bind=engine)

app = FastAPI()

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(composition_router)
app.include_router(oauth_router)
app.include_router(user_router)

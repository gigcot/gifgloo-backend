from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from composition.adapter.inbound.fastapi.composition_router import router as composition_router
from user.adapter.inbound.fastapi.oauth2 import router as oauth_router
from user.adapter.inbound.fastapi.user_router import router as user_router
from dotenv import load_dotenv
load_dotenv(".env")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(composition_router)
app.include_router(oauth_router)
app.include_router(user_router)

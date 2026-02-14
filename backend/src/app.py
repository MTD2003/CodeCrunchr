from fastapi import FastAPI
from dotenv import load_dotenv

from .routers import ping_router

load_dotenv()

app = FastAPI()

app.include_router(ping_router)

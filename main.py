from fastapi import FastAPI
from routes.entry import entry_root
from routes.signup import signup_root
from routes.books import book_root

from config import init_db, close_db
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    await init_db()
    yield
    await close_db()


app = FastAPI(lifespan=lifespan)
app.include_router(entry_root)
app.include_router(signup_root)
app.include_router(book_root)


    
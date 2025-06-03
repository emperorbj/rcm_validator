from fastapi import APIRouter


entry_root = APIRouter()


@entry_root.get("/api")
async def new_response():
    response = {
        "name":"fully automated"
    }
    return response

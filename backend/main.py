from fastapi import FastAPI
from versus_games.lobby import router as lobby_router

app = FastAPI(title="Versus Games API", version="0.1.0")
app.include_router(lobby_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
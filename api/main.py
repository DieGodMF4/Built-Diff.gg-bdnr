"""(Opcional) API REST con FastAPI."""
import os, sys
from typing import List
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from database.connection import get_champions_collection, get_items_collection, test_connection
from recommender.engine import recommend

app = FastAPI(title="LoL Draft Item Recommender", version="3.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class DraftRequest(BaseModel):
    champion: str
    allies: List[str] = []
    enemies: List[str] = []

@app.get("/health")
def health():
    return {"status": "ok" if test_connection() else "degraded"}

@app.get("/champions")
def list_champions():
    docs = list(get_champions_collection().find({}, {"_id": 0, "champion_id": 1, "name": 1,
                                                      "archetype": 1, "damage_profile": 1}))
    return {"count": len(docs), "champions": docs}

@app.get("/items")
def list_items():
    docs = list(get_items_collection().find({}, {"_id": 0, "item_id": 1, "name": 1,
                                                  "subclass": 1, "priority": 1, "gold": 1}))
    return {"count": len(docs), "items": docs}

@app.post("/recommend")
def get_recommendation(draft: DraftRequest):
    result = recommend(draft.champion, draft.allies, draft.enemies)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result

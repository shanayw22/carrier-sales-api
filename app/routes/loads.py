import json
import os

from fastapi import APIRouter, HTTPException


router = APIRouter(prefix="/loads", tags=["loads"])
LOADS_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "loads.json")


def _load_data():
    with open(LOADS_FILE, "r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


@router.get("/{load_id}")
async def get_load(load_id: str):
    loads = _load_data()
    match = next((load for load in loads if load["load_id"].upper() == load_id.upper()), None)
    if not match:
        raise HTTPException(
            status_code=404,
            detail={"error": "Load not found", "load_id": load_id},
        )
    return match
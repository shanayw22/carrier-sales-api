from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CallRecord


router = APIRouter(prefix="/webhook", tags=["webhook"])


BOOKED_OUTCOMES = {"booked", "success", "sucess", "yes", "transferred"}
RATE_DECLINED_OUTCOMES = {"rate too high", "rate_too_high"}
NOT_INTERESTED_OUTCOMES = {"not interested", "not_interested"}


def _normalize_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_outcome(value: str) -> str:
    normalized = value.strip().lower().replace("-", " ")
    normalized = " ".join(normalized.split())

    if normalized in BOOKED_OUTCOMES:
        return "booked"
    if normalized in RATE_DECLINED_OUTCOMES:
        return "rate_too_high"
    if normalized in NOT_INTERESTED_OUTCOMES:
        return "not_interested"

    return normalized.replace(" ", "_")


def _normalize_sentiment(value: Optional[str]) -> Optional[str]:
    normalized = _normalize_text(value)
    return normalized.title() if normalized else None


class CallCompletePayload(BaseModel):
    call_id: str
    caller_phone: Optional[str] = None
    carrier_name: Optional[str] = None
    mc_number: Optional[str] = None
    dot_number: Optional[str] = None
    allowed_to_operate: Optional[str] = None
    load_id: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    equipment_type: Optional[str] = None
    offered_rate: Optional[float] = None
    final_rate: Optional[float] = None
    loadboard_rate: Optional[float] = None
    outcome: str
    sentiment: Optional[str] = None
    negotiation_rounds: Optional[int] = 0
    call_duration_seconds: Optional[int] = None


@router.post("/call-complete")
async def call_complete(payload: CallCompletePayload, db: Session = Depends(get_db)):
    payload.outcome = _normalize_outcome(payload.outcome)
    payload.sentiment = _normalize_sentiment(payload.sentiment)
    payload.caller_phone = _normalize_text(payload.caller_phone)
    payload.carrier_name = _normalize_text(payload.carrier_name)
    payload.mc_number = _normalize_text(payload.mc_number)
    payload.dot_number = _normalize_text(payload.dot_number)
    payload.allowed_to_operate = _normalize_text(payload.allowed_to_operate)
    payload.load_id = _normalize_text(payload.load_id)
    payload.origin = _normalize_text(payload.origin)
    payload.destination = _normalize_text(payload.destination)
    payload.equipment_type = _normalize_text(payload.equipment_type)

    existing_record = db.query(CallRecord).filter(CallRecord.call_id == payload.call_id).one_or_none()

    if existing_record is None:
        record = CallRecord(**payload.model_dump())
        db.add(record)
        status = "created"
    else:
        for field_name, value in payload.model_dump().items():
            setattr(existing_record, field_name, value)
        status = "updated"

    db.commit()
    return {"status": status, "call_id": payload.call_id}
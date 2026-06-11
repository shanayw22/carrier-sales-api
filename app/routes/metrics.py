from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CallRecord


router = APIRouter(prefix="/metrics", tags=["metrics"])


def _serialize_call(call: CallRecord) -> dict:
    return {
        "call_id": call.call_id,
        "carrier_name": call.carrier_name,
        "mc_number": call.mc_number,
        "load_id": call.load_id,
        "outcome": call.outcome,
        "final_rate": call.final_rate,
        "loadboard_rate": call.loadboard_rate,
        "sentiment": call.sentiment,
        "negotiation_rounds": call.negotiation_rounds,
        "call_duration_seconds": call.call_duration_seconds,
        "created_at": call.created_at.isoformat() if call.created_at else None,
    }


@router.get("/summary")
async def summary(db: Session = Depends(get_db)):
    total = db.query(func.count(CallRecord.id)).scalar()
    booked = db.query(func.count(CallRecord.id)).filter(CallRecord.outcome == "booked").scalar()
    avg_rounds = db.query(func.avg(CallRecord.negotiation_rounds)).scalar()
    avg_duration = db.query(func.avg(CallRecord.call_duration_seconds)).scalar()
    avg_final_rate = db.query(func.avg(CallRecord.final_rate)).scalar()

    outcomes = db.query(CallRecord.outcome, func.count(CallRecord.id)).group_by(
        CallRecord.outcome
    ).all()
    sentiments = db.query(CallRecord.sentiment, func.count(CallRecord.id)).group_by(
        CallRecord.sentiment
    ).all()

    return {
        "total_calls": total or 0,
        "booking_rate": round((booked / total) * 100, 1) if total else 0,
        "avg_negotiation_rounds": round(float(avg_rounds), 1) if avg_rounds else 0,
        "avg_call_duration_seconds": round(float(avg_duration), 1) if avg_duration else 0,
        "avg_final_rate": round(float(avg_final_rate), 2) if avg_final_rate else 0,
        "outcomes": {outcome: count for outcome, count in outcomes},
        "sentiments": {sentiment: count for sentiment, count in sentiments if sentiment},
    }


@router.get("/dashboard")
async def dashboard_metrics(db: Session = Depends(get_db)):
    total = db.query(func.count(CallRecord.id)).scalar() or 0
    booked = db.query(func.count(CallRecord.id)).filter(CallRecord.outcome == "booked").scalar() or 0
    avg_rounds = db.query(func.avg(CallRecord.negotiation_rounds)).scalar()
    avg_duration = db.query(func.avg(CallRecord.call_duration_seconds)).scalar()
    avg_final_rate = db.query(func.avg(CallRecord.final_rate)).scalar()
    avg_loadboard_rate = db.query(func.avg(CallRecord.loadboard_rate)).scalar()

    outcomes = db.query(CallRecord.outcome, func.count(CallRecord.id)).group_by(
        CallRecord.outcome
    ).all()
    sentiments = db.query(CallRecord.sentiment, func.count(CallRecord.id)).group_by(
        CallRecord.sentiment
    ).all()
    top_lanes = (
        db.query(
            CallRecord.origin,
            CallRecord.destination,
            func.count(CallRecord.id).label("call_count"),
        )
        .filter(CallRecord.origin.isnot(None), CallRecord.destination.isnot(None))
        .group_by(CallRecord.origin, CallRecord.destination)
        .order_by(func.count(CallRecord.id).desc())
        .limit(5)
        .all()
    )
    recent_calls = db.query(CallRecord).order_by(CallRecord.created_at.desc()).limit(10).all()

    return {
        "kpis": {
            "total_calls": total,
            "booked_calls": booked,
            "booking_rate": round((booked / total) * 100, 1) if total else 0,
            "avg_negotiation_rounds": round(float(avg_rounds), 1) if avg_rounds else 0,
            "avg_call_duration_seconds": round(float(avg_duration), 1) if avg_duration else 0,
            "avg_final_rate": round(float(avg_final_rate), 2) if avg_final_rate else 0,
            "avg_rate_delta": round(float(avg_final_rate - avg_loadboard_rate), 2)
            if avg_final_rate is not None and avg_loadboard_rate is not None
            else 0,
        },
        "outcomes": [
            {"label": outcome or "unknown", "value": count} for outcome, count in outcomes
        ],
        "sentiments": [
            {"label": sentiment or "unknown", "value": count}
            for sentiment, count in sentiments
            if sentiment or count
        ],
        "top_lanes": [
            {
                "label": f"{origin} -> {destination}",
                "value": call_count,
            }
            for origin, destination, call_count in top_lanes
        ],
        "recent_calls": [_serialize_call(call) for call in recent_calls],
    }


@router.get("/calls")
async def call_list(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)):
    calls = (
        db.query(CallRecord)
        .order_by(CallRecord.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [_serialize_call(call) for call in calls]


@router.delete("/flush")
async def flush_metrics(db: Session = Depends(get_db)):
    deleted_records = db.query(CallRecord).delete()
    db.commit()
    return {"status": "ok", "deleted_records": deleted_records}
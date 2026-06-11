import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class CallRecord(Base):
    __tablename__ = "call_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    call_id = Column(String, unique=True, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    caller_phone = Column(String, nullable=True)
    carrier_name = Column(String, nullable=True)
    mc_number = Column(String, nullable=True)
    dot_number = Column(String, nullable=True)
    allowed_to_operate = Column(String, nullable=True)
    load_id = Column(String, nullable=True)
    origin = Column(String, nullable=True)
    destination = Column(String, nullable=True)
    equipment_type = Column(String, nullable=True)
    offered_rate = Column(Float, nullable=True)
    final_rate = Column(Float, nullable=True)
    loadboard_rate = Column(Float, nullable=True)
    outcome = Column(String, nullable=False)
    sentiment = Column(String, nullable=True)
    negotiation_rounds = Column(Integer, default=0)
    call_duration_seconds = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
"""原始外部事件与隐患的不可变接收凭据。"""
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from app.database import Base


class IntegrationReceipt(Base):
    __tablename__ = 'integration_receipts'
    __table_args__ = (UniqueConstraint('external_source', 'external_no', name='uq_integration_receipt_source_no'),)
    id = Column(Integer, primary_key=True)
    external_source = Column(String(50), nullable=False)
    external_no = Column(String(50), nullable=False)
    payload_hash = Column(String(64), nullable=False)
    payload = Column(JSON, nullable=False)
    hazard_id = Column(Integer, ForeignKey('hazards.id'), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

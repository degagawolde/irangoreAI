from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.database import Base


class QueryLog(Base):
    __tablename__ = "query_logs"

    id           = Column(Integer, primary_key=True, index=True)
    question     = Column(Text, nullable=False)
    jurisdiction = Column(String(100), default="Ethiopia")
    answer       = Column(Text)
    sources      = Column(Text)          # stored as JSON string
    created_at   = Column(DateTime(timezone=True), server_default=func.now())
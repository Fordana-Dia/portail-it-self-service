from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    role = Column(String, default="developer")
    team = Column(String)
    password = Column(String, nullable=True)

class Environment(Base):
    __tablename__ = "environments"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True)
    type = Column(String)
    requested_by = Column(Integer, ForeignKey("users.id"))
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    action = Column(String)
    ressource = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

# -*- coding: utf-8 -*-
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# Используем SQLite файл
SQLALCHEMY_DATABASE_URL = "sqlite:///./sql_app.db"

# Создаем движок
# connect_args={"check_same_thread": False} нужен для SQLite в многопоточном приложении (FastAPI)
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# ====================
# МОДЕЛИ ДАННЫХ
# ====================

class User(Base):
    """Пользователь системы"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    
    tokens = relationship("Token", back_populates="user")
    auth_codes = relationship("AuthCode", back_populates="user")
    device_metas = relationship("DeviceMeta", back_populates="user")


class AuthCode(Base):
    """Временные коды авторизации (OAuth2)"""
    __tablename__ = "auth_codes"

    code = Column(String, primary_key=True, index=True)
    client_id = Column(String)
    redirect_uri = Column(String)
    exp = Column(Float) # Timestamp истечения
    
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="auth_codes")


class TelegramUser(Base):
    """Пользователи Телеграм бота"""
    __tablename__ = "telegram_users"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, unique=True, index=True)
    first_name = Column(String, nullable=True)
    username = Column(String, nullable=True)


class Token(Base):
    """Токены доступа (Access & Refresh)"""
    __tablename__ = "tokens"

    access_token = Column(String, primary_key=True, index=True)
    refresh_token = Column(String, unique=True, index=True)
    client_id = Column(String)
    exp = Column(Float) # Timestamp истечения access token
    refresh_exp = Column(Float) # Timestamp истечения refresh token
    
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="tokens")


class DeviceMeta(Base):
    """Метаданные устройств (Имена, Комнаты)"""
    __tablename__ = "device_meta"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, index=True) # ID устройства в системе (esp8266_...)
    
    custom_name = Column(String) # "Люстра"
    room = Column(String)        # "Гостиная"
    type = Column(String)        # "devices.types.light"
    
    user_id = Column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="device_metas")

# Dependency для получения сессии БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

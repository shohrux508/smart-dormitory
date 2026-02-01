# -*- coding: utf-8 -*-
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, ForeignKey, UniqueConstraint, BigInteger
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

# Примечание: Таблица User удалена полностью.
# Вместо нее используем telegram_id как внешний идентификатор.

class TelegramBookmark(Base):
    """
    Закладки устройств пользователя Telegram.
    Это НЕ аккаунт, а просто локальная книга сохраненных устройств.
    """
    __tablename__ = "telegram_bookmarks"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, index=True) # ID пользователя в Telegram
    device_id = Column(String, index=True)       # ID устройства
    
    # Локальные настройки отображения для конкретного пользователя
    custom_name = Column(String) # "Люстра"
    room = Column(String)        # "Гостиная"

    # Ограничение: один пользователь может добавить устройство только один раз
    __table_args__ = (
        UniqueConstraint('telegram_id', 'device_id', name='uq_telegram_device'),
    )


class AuthCode(Base):
    """Временные коды авторизации (OAuth2)"""
    __tablename__ = "auth_codes"

    code = Column(String, primary_key=True, index=True)
    client_id = Column(String)
    redirect_uri = Column(String)
    exp = Column(Float) # Timestamp истечения
    
    # Ссылка на Telegram пользователя (без внешнего ключа к таблице users)
    telegram_id = Column(BigInteger, index=True)


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
    
    # Ссылка на Telegram пользователя
    telegram_id = Column(BigInteger, index=True)


# Dependency для получения сессии БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

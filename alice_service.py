# -*- coding: utf-8 -*-
"""
Модуль интеграции с Яндекс Алисой (Smart Home V1.0).
Объединяет функционал OAuth2-провайдера и API Умного Дома.
Использует базу данных SQLite для хранения токенов и настроек.
"""

import secrets
import time
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Depends, Request, Form
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.params import Header
from sqlalchemy.orm import Session

# Импортируем менеджер устройств
from devices_core import manager
# Импортируем БД
from database import get_db, User, AuthCode, Token, DeviceMeta

# ==========================================
# КОНФИГУРАЦИЯ
# ==========================================

CLIENT_ID = "my-smart-home"
CLIENT_SECRET = "supersecret123"
ACCESS_TTL = 3600  # 1 час
REFRESH_TTL = 3600 * 24 * 30  # 30 дней

router = APIRouter(tags=["Yandex Alice Integration"])


# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================

def now() -> float:
    return time.time()

def get_or_create_user(db: Session, username: str) -> User:
    user = db.query(User).filter(User.username == username).first()
    if not user:
        user = User(username=username)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

async def get_current_user(
    authorization: str = Header(..., alias="Authorization"),
    db: Session = Depends(get_db)
) -> User:
    """Проверяет токен в БД и возвращает пользователя."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    
    token_str = authorization.split(" ", 1)[1].strip()
    
    # Ищем токен в БД
    token_record = db.query(Token).filter(Token.access_token == token_str).first()
    
    if not token_record:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    if token_record.exp < now():
        raise HTTPException(status_code=401, detail="Token expired")
    
    return token_record.user


# ==========================================
# OAUTH2 АВТОРИЗАЦИЯ
# ==========================================

@router.get("/authorize")
async def authorize(request: Request, db: Session = Depends(get_db)):
    params = dict(request.query_params)
    client_id = params.get("client_id")
    redirect_uri = params.get("redirect_uri")
    state = params.get("state")

    if client_id != CLIENT_ID:
        raise HTTPException(status_code=400, detail="Unknown client_id")
    
    if not redirect_uri:
        raise HTTPException(status_code=400, detail="Missing redirect_uri")

    username = params.get("user")

    if not username:
        # Форма входа по-прежнему простая
        html = f"""
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Вход в Умный Дом</title>
            <style>
                body {{ font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; background-color: #f5f5f5; }}
                .login-card {{ background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); width: 100%; max-width: 400px; }}
                h2 {{ text-align: center; color: #333; }}
                input {{ width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #ddd; border-radius: 6px; box-sizing: border-box; }}
                button {{ width: 100%; padding: 12px; background-color: #fc3f1d; color: white; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; }}
                button:hover {{ background-color: #e02b0c; }}
            </style>
        </head>
        <body>
          <div class="login-card">
            <h2>Авторизация</h2>
            <form method="get" action="">
                <input type="hidden" name="client_id" value="{client_id}">
                <input type="hidden" name="redirect_uri" value="{redirect_uri}">
                <input type="hidden" name="state" value="{state or ''}">
                <input type="hidden" name="response_type" value="code">
                <label>Ваше имя (User ID):</label>
                <input name="user" placeholder="shohruh" required value="shohruh">
                <button type="submit">Разрешить</button>
            </form>
          </div>
        </body>
        </html>
        """
        return HTMLResponse(html)

    # Создаем/получаем пользователя
    user = get_or_create_user(db, username)

    # Генерируем код
    code_str = secrets.token_urlsafe(24)
    auth_code = AuthCode(
        code=code_str,
        client_id=client_id,
        redirect_uri=redirect_uri,
        exp=now() + 600,
        user_id=user.id
    )
    db.add(auth_code)
    db.commit()
    
    sep = "&" if "?" in redirect_uri else "?"
    location = f"{redirect_uri}{sep}code={code_str}"
    if state:
        location += f"&state={state}"
        
    return RedirectResponse(location, status_code=302)


@router.post("/token")
async def token(request: Request, db: Session = Depends(get_db)):
    form = dict(await request.form())
    grant_type = form.get("grant_type")
    c_id = form.get("client_id")
    c_secret = form.get("client_secret")

    if c_id != CLIENT_ID or c_secret != CLIENT_SECRET:
        raise HTTPException(status_code=401, detail="Invalid client credentials")

    if grant_type == "authorization_code":
        code_str = form.get("code")
        
        # Ищем код в БД
        code_record = db.query(AuthCode).filter(AuthCode.code == code_str).first()
        
        if not code_record or code_record.exp < now():
            raise HTTPException(status_code=400, detail="Invalid or expired code")

        user_id = code_record.user_id
        # Удаляем использованный код
        db.delete(code_record)
        
        # Генерируем токены
        access_token = secrets.token_urlsafe(32)
        refresh_token = secrets.token_urlsafe(32)
        
        new_token = Token(
            access_token=access_token,
            refresh_token=refresh_token,
            client_id=c_id,
            exp=now() + ACCESS_TTL,
            refresh_exp=now() + REFRESH_TTL,
            user_id=user_id
        )
        db.add(new_token)
        db.commit()

        return JSONResponse({
            "token_type": "bearer", "access_token": access_token, "expires_in": ACCESS_TTL, "refresh_token": refresh_token
        })

    elif grant_type == "refresh_token":
        ws_refresh = form.get("refresh_token")
        
        token_record = db.query(Token).filter(Token.refresh_token == ws_refresh).first()
        
        if not token_record or token_record.refresh_exp < now():
            # Если токен протух - удаляем
            if token_record:
                db.delete(token_record)
                db.commit()
            raise HTTPException(status_code=400, detail="Invalid or expired refresh_token")

        user_id = token_record.user_id
        
        # Удаляем старый токен (ротация)
        db.delete(token_record)
        
        # Выдаем новые
        new_access = secrets.token_urlsafe(32)
        new_refresh = secrets.token_urlsafe(32)
        
        new_token_obj = Token(
            access_token=new_access,
            refresh_token=new_refresh,
            client_id=c_id,
            exp=now() + ACCESS_TTL,
            refresh_exp=now() + REFRESH_TTL,
            user_id=user_id
        )
        db.add(new_token_obj)
        db.commit()
        
        return JSONResponse({
            "token_type": "bearer", "access_token": new_access, "expires_in": ACCESS_TTL, "refresh_token": new_refresh
        })

    raise HTTPException(status_code=400, detail="Unsupported grant_type")


@router.post("/token/refresh")
async def token_refresh_legacy(request: Request, db: Session = Depends(get_db)):
    return await token(request, db)


# ==========================================
# SMART HOME API (v1.0)
# ==========================================

@router.head("/v1.0")
@router.head("/v1.0/")
async def check_availability_head():
    return JSONResponse(content={}, status_code=200)

@router.get("/v1.0/ping")
@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.get("/v1.0/user/devices")
async def list_devices(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    request_id = str(secrets.token_hex(8))
    
    devices_resp = []
    
    # Получаем живые устройства из менеджера
    live_devices = manager.list_devices()
    
    for d_info in live_devices:
        d_id = d_info["device_id"]
        
        # Ищем настройки в БД для этого пользователя
        meta = db.query(DeviceMeta).filter(
            DeviceMeta.device_id == d_id, 
            DeviceMeta.user_id == user.id
        ).first()
        
        # Дефолтные значения
        name = meta.custom_name if meta else f"Device {d_id}"
        room = meta.room if meta else "Комната"
        description = "Smart Desk Light"
        
        devices_resp.append({
            "id": d_id,
            "name": name,
            "description": description,
            "room": room,
            "type": "devices.types.light",
            "capabilities": [
                {
                    "type": "devices.capabilities.on_off",
                    "retrievable": True,
                    "reportable": True
                }
            ],
            "device_info": {
                "manufacturer": "Antigravity",
                "model": "ESP8266",
            }
        })

    return {
        "request_id": request_id,
        "payload": {
            "user_id": str(user.username), # Возвращаем username как ID для Алисы
            "devices": devices_resp
        }
    }


@router.post("/v1.0/user/devices/query")
async def query_devices(request: Request, user: User = Depends(get_current_user)):
    body = await request.json()
    devices_req = body.get("devices", [])
    request_id = str(secrets.token_hex(8))
    
    devices_resp = []
    for d in devices_req:
        dev_id = d.get("id")
        device = manager.get_device(dev_id)
        
        state_val = False
        if device:
             state_val = (device.state == "ON")
        
        devices_resp.append({
            "id": dev_id,
            "capabilities": [
                {
                    "type": "devices.capabilities.on_off",
                    "state": {
                        "instance": "on",
                        "value": state_val
                    }
                }
            ]
        })

    return {
        "request_id": request_id,
        "payload": {
            "devices": devices_resp
        }
    }


@router.post("/v1.0/user/devices/action")
async def action_devices(request: Request, user: User = Depends(get_current_user)):
    body = await request.json()
    payload = body.get("payload", {})
    devices_req = payload.get("devices", [])
    request_id = str(secrets.token_hex(8))

    devices_resp = []
    
    for d in devices_req:
        dev_id = d.get("id")
        caps_results = []
        
        for cap in d.get("capabilities", []):
            cap_type = cap.get("type")
            state = cap.get("state", {})
            
            if cap_type == "devices.capabilities.on_off":
                value = state.get("value") # True/False
                
                # Отправляем команду
                cmd = "TURN_ON" if value else "TURN_OFF"
                await manager.send_command(dev_id, cmd)
                
                caps_results.append({
                    "type": cap_type,
                    "state": {
                        "instance": "on",
                        "action_result": {
                            "status": "DONE"
                        }
                    }
                })
        
        devices_resp.append({
            "id": dev_id,
            "capabilities": caps_results
        })

    return {
        "request_id": request_id,
        "payload": {
            "devices": devices_resp
        }
    }


@router.post("/v1.0/user/unlink")
async def unlink_user(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    req_id = request.headers.get("X-Request-Id", str(secrets.token_hex(8)))
    
    # Удаляем все токены этого пользователя (или конкретный)
    # Здесь упрощенно удаляем все
    db.query(Token).filter(Token.user_id == user.id).delete()
    db.commit()
    
    return {"request_id": req_id}


@router.get("/user/info")
async def debug_user_info(user: User = Depends(get_current_user)):
    return {"status": "ok", "user_id": user.id, "username": user.username}

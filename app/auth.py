import secrets
from typing import Dict, Any

from fastapi import HTTPException, APIRouter
from fastapi.params import Header
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, HTMLResponse

from config import DB, auth_codes, now, ensure_user_initialized, access_tokens, ACCESS_TTL, refresh_tokens, REFRESH_TTL


router = APIRouter()


# ====== АУТЕНТИФИКАЦИЯ ДЛЯ АЛИСЫ ======
def auth_yandex(authorization: str = Header(default="")) -> Dict[str, Any]:
    print(authorization)
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    t = authorization.split(" ", 1)[1].strip()
    user_id = DB["tokens"].get(t)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    return DB["users"][user_id]


# ====== ЭНДПОИНТЫ АЛИСЫ ======
@router.get("/authorize")
async def authorize(request: Request):
    """
    Имитация страницы логина/согласия.
    При первом заходе покажет простую форму (ввести имя пользователя).
    После «входа» редиректит обратно в redirect_uri с code (+state, если был).
    """
    q = dict(request.query_params)
    client_id = q.get("client_id")
    redirect_uri = q.get('redirect_uri')
    state = q.get("state")
    response_type = q.get("response_type", "code")

    if client_id != 'my-smart-home' or response_type != "code" or not redirect_uri:
        raise HTTPException(status_code=400, detail="Bad authorize request")
    username = q.get("user")  # для демо можно сразу передать ?user=shohruh

    if not username:
        # Простая HTML-форма «входа»
        html = f"""
        <html><body style="font-family: sans-serif">
          <h2>Вход в аккаунт устройства</h2>
          <form method="get" action="/authorize">
            <input type="hidden" name="client_id" value="{client_id}">
            <input type="hidden" name="redirect_uri" value="{redirect_uri}">
            <input type="hidden" name="state" value="{state or ''}">
            <input type="hidden" name="response_type" value="code">
            <label>Имя пользователя:</label>
            <input name="user" placeholder="shohruh" required>
            <button type="submit">Войти и выдать код</button>
          </form>
        </body></html>
        """
        return HTMLResponse(html)

    # «Логин успешен» -> выдаём одноразовый code
    code = secrets.token_urlsafe(24)
    auth_codes[code] = {
        "user_id": username,
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "exp": now() + 600,  # 10 минут
    }
    sep = "&" if "?" in redirect_uri else "?"
    location = f"{redirect_uri}{sep}code={code}" + (f"&state={state}" if state else "")
    return RedirectResponse(location, status_code=302)


# --------- OAUTH2: /token + /token/refresh ---------
@router.post("/token")
async def token(request: Request):
    print('Алиса сделала запрос на сервер!')
    form = dict(await request.form())
    grant_type = form.get("grant_type")
    client_id = form.get("client_id")
    client_secret = form.get("client_secret")

    if client_id != 'my-smart-home' or client_secret != 'supersecret123':
        raise HTTPException(status_code=401, detail="Invalid client")

    if grant_type == "authorization_code":
        code = form.get("code")
        data = auth_codes.pop(code, None)
        if not data or data["exp"] < now():
            raise HTTPException(status_code=400, detail="Invalid or expired code")

        user_id = data["user_id"]
        ensure_user_initialized(user_id)
        access = 'alice-demo'
        refresh = 'alice-demo'
        access_tokens[access] = {
            "user_id": user_id, "client_id": client_id,
            "exp": now() + ACCESS_TTL, "refresh_token": refresh
        }
        refresh_tokens[refresh] = {
            "user_id": user_id, "client_id": client_id,
            "exp": now() + REFRESH_TTL
        }
        return JSONResponse({
            "token_type": "bearer",
            "access_token": access,
            "expires_in": ACCESS_TTL,
            "refresh_token": refresh,
            "scope": "devices"
        })

    elif grant_type == "refresh_token":
        # допускаем refresh и тут (на случай если Яндекс будет слать сюда)
        refresh = form.get("refresh_token")
        info = refresh_tokens.get(refresh)
        if not info or info["exp"] < now():
            raise HTTPException(status_code=400, detail="Invalid or expired refresh_token")

        user_id = info["user_id"]
        access = 'alice-demo'
        new_refresh = 'alice-demo'
        access_tokens[access] = {
            "user_id": user_id, "client_id": client_id,
            "exp": now() + ACCESS_TTL, "refresh_token": new_refresh
        }
        refresh_tokens[new_refresh] = {
            "user_id": user_id, "client_id": client_id,
            "exp": now() + REFRESH_TTL
        }
        return JSONResponse({
            "token_type": "bearer",
            "access_token": access,
            "expires_in": ACCESS_TTL,
            "refresh_token": new_refresh,
            "scope": "devices"
        })

    else:
        raise HTTPException(status_code=400, detail="Unsupported grant_type")


@router.post("/token/refresh")
async def token_refresh(request: Request):
    form = dict(await request.form())
    print(form)
    client_id = form.get("client_id")
    client_secret = form.get("client_secret")
    refresh = form.get("refresh_token")

    if client_id != 'my-smart-home' or client_secret != 'supersecret123':
        raise HTTPException(status_code=401, detail="Invalid client")

    return JSONResponse({
        "token_type": "bearer",
        "access_token": 'alice-demo',
        "expires_in": ACCESS_TTL,
        "refresh_token": 'alice-demo',
        "scope": "devices"
    })

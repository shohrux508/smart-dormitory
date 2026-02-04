import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db, TelegramBookmark
from app.services.devices import manager, Device
import app.routers.alice as alice_service
from app.config import settings


# --- Setup In-Memory DB for Tests ---
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def init_db():
    # Create tables
    Base.metadata.create_all(bind=engine)
    # Clear manager state
    manager.devices.clear()
    yield
    # Drop tables
    Base.metadata.drop_all(bind=engine)


def test_authorize_page():
    response = client.get(f"/authorize?client_id={settings.ALICE_CLIENT_ID}&redirect_uri=https://ya.ru&response_type=code&state=123")
    assert response.status_code == 200
    assert "Вход в Умный Дом" in response.text

def test_full_oauth_flow():
    # 1. Authorize with numeric user ID
    response = client.get(
        "/authorize", 
        params={
            "client_id": settings.ALICE_CLIENT_ID,
            "redirect_uri": "https://ya.ru",
            "response_type": "code",
            "state": "123",
            "user": "123456789" # Valid numeric ID
        },
        follow_redirects=False
    )
    
    assert response.status_code == 302
    location = response.headers["location"]
    assert "code=" in location
    
    # Extract code
    import urllib.parse
    parsed = urllib.parse.urlparse(location)
    qs = urllib.parse.parse_qs(parsed.query)
    code = qs["code"][0]
    
    # 2. Exchange Token
    response = client.post("/token", data={
        "grant_type": "authorization_code",
        "code": code,
        "client_id": settings.ALICE_CLIENT_ID,
        "client_secret": settings.ALICE_CLIENT_SECRET
    })
    
    assert response.status_code == 200
    tokens = response.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    
    return tokens["access_token"]

def test_list_devices_with_custom_name():
    # 1. Get token for user 123456789
    token = test_full_oauth_flow()
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Add device to manager (online status)
    dev_id = "temp_esp"
    manager.devices[dev_id] = Device(device_id=dev_id, state="OFF", status="online")
    
    # 3. Add Bookmark manually (mimic adding via Telegram Bot)
    db = TestingSessionLocal()
    bookmark = TelegramBookmark(
        telegram_id=123456789,
        device_id=dev_id,
        custom_name="Кухня",
        room="Дом"
    )
    db.add(bookmark)
    db.commit()
    db.close()
    
    # 4. Check Discovery Service
    d_resp = client.get("/v1.0/user/devices", headers=headers)
    assert d_resp.status_code == 200
    payload = d_resp.json()["payload"]
    devices = payload["devices"]
    
    assert len(devices) == 1
    assert devices[0]["id"] == dev_id
    assert devices[0]["name"] == "Кухня"
    assert devices[0]["room"] == "Дом"

def test_full_flow_shohruh():
    # 1. Log in as shohruh (using arbitrary ID 508)
    user_id = "508"
    response = client.get(
        "/authorize", 
        params={
            "client_id": settings.ALICE_CLIENT_ID, 
            "redirect_uri": "https://ya.ru", 
            "user": user_id 
        }, 
        follow_redirects=False
    )
    code = response.headers["location"].split("code=")[1].split("&")[0]
    
    resp = client.post("/token", data={"grant_type": "authorization_code", "code": code, "client_id": settings.ALICE_CLIENT_ID, "client_secret": settings.ALICE_CLIENT_SECRET})
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Add device
    dev_id = "lamp_1"
    manager.devices[dev_id] = Device(device_id=dev_id)
    
    # 3. Manually add bookmark (since API is restricted)
    db = TestingSessionLocal()
    bookmark = TelegramBookmark(
        telegram_id=int(user_id),
        device_id=dev_id,
        custom_name="Люстра",
        room="Зал"
    )
    db.add(bookmark)
    db.commit()
    db.close()
    
    # 4. Check Discovery Service
    d_resp = client.get("/v1.0/user/devices", headers=headers)
    assert d_resp.status_code == 200
    devices = d_resp.json()["payload"]["devices"]
    
    assert len(devices) == 1
    assert devices[0]["name"] == "Люстра"
    assert devices[0]["room"] == "Зал"

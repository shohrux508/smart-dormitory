import sys
import os

# Add project root to sys.path
sys.path.append(os.getcwd())

from app.database import SessionLocal, TelegramBookmark, Token, engine, Base
from app.routers.alice import router
from sqlalchemy import inspect

def test_db():
    print("--- Testing Database Schema ---")
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"Tables found: {tables}")
    
    if "telegram_bookmarks" not in tables:
        print("❌ FAILED: telegram_bookmarks table missing!")
        return
    if "users" in tables:
        print("⚠️ WARNING: users table still exists (did not delete db?)")
    
    print("✅ Schema verified.")

    print("\n--- Testing TelegramBookmark Insert ---")
    db = SessionLocal()
    try:
        # Clear old test data
        db.query(TelegramBookmark).filter(TelegramBookmark.telegram_id == 12345).delete()
        db.commit()

        # Insert
        bm = TelegramBookmark(
            telegram_id=12345,
            device_id="test_lamp_1",
            custom_name="Тестовая Лампа",
            room="Тест"
        )
        db.add(bm)
        db.commit()
        print("✅ Bookmark inserted.")
        
        # Verify
        stored = db.query(TelegramBookmark).filter(TelegramBookmark.telegram_id == 12345).first()
        if stored and stored.device_id == "test_lamp_1":
            print(f"✅ Read back: {stored.custom_name} ({stored.device_id})")
        else:
            print("❌ FAILED: Could not read back bookmark.")
        
    except Exception as e:
        print(f"❌ FAILED: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    try:
        test_db()
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")

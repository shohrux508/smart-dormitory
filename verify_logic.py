import asyncio
import os
import database
from datetime import datetime

async def test_logic():
    print("[TEST] Starting V2 Logic Verification...")
    
    if os.path.exists("room.db"):
        try:
            os.remove("room.db")
        except PermissionError:
            print("[WARN] Could not delete room.db, it might be in use.")
            return
    
    await database.init_db()
    print("[OK] Database initialized.")

    # 1. Add Users with usernames
    users_data = [
        (101, "alice_u", "Alice"),
        (102, "bob_u", "Bob"),
        (103, None, "CharlieNoNick"), # No username
        (104, "dave_u", "Dave")
    ]
    
    for uid, uname, fullname in users_data:
        success = await database.add_user(uid, uname, fullname)
        if success:
            print(f"[OK] Added {fullname} (@{uname})")
        else:
            print(f"[ERR] Failed to add {fullname}")

    count = await database.get_user_count()
    assert count == 4
    print(f"[OK] Count is 4.")

    # 2. Test Task Assignment
    print("[TEST] Testing Task Assignment...")
    
    # assign to Bob
    target = await database.get_user_by_username("bob_u")
    assert target is not None
    assert target['telegram_id'] == 102
    print("[OK] Found Bob by username.")

    await database.update_user_task(target['telegram_id'], "Clean Windows")
    
    # Verify
    bob_check = await database.get_user(102)
    assert bob_check['user_task'] == "Clean Windows"
    print(f"[OK] Bob's task updated to: {bob_check['user_task']}")

    # 3. Test Rotation Logic simulation
    print("[TEST] Testing Rotation Logic...")
    all_users = await database.get_users()
    day_of_year = datetime.now().timetuple().tm_yday
    idx = day_of_year % len(all_users)
    selected_user = all_users[idx]
    print(f"[INFO] Day of year: {day_of_year}")
    print(f"[INFO] Index: {idx}")
    print(f"[INFO] Selected User for Today: {selected_user['full_name']}")
    
    # 4. Cleanup
    print("\n[DONE] V2 Logic Verification Passed!")

if __name__ == "__main__":
    asyncio.run(test_logic())

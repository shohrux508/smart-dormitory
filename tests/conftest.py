import sys
import os
import pytest
import asyncio
from unittest.mock import AsyncMock

# Add project root to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.devices import manager as device_manager

# Patch start_bot and stop_bot to prevent actual polling during tests
@pytest.fixture(autouse=True)
def mock_telegram_bot(monkeypatch):
    mock_start = AsyncMock()
    mock_stop = AsyncMock()
    
    monkeypatch.setattr("app.services.telegram_bot.start_bot", mock_start)
    monkeypatch.setattr("app.services.telegram_bot.stop_bot", mock_stop)
    
    # Also patch the heartbeat loop to avoid infinite background tasks
    async def mock_heartbeat():
        # Do nothing, just return immediately
        pass
        
    # Patch the method on the specific instance used by main.py
    monkeypatch.setattr(device_manager, "run_heartbeat", mock_heartbeat)
    
    yield mock_start, mock_stop

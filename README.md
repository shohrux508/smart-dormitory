# 📡 SMART-DORMITORY: Desk Light Control

**Version:** v3.1 (Web Dashboard & Alice Integration)  
**Status:** 🟢 Stable

Система управления умным освещением в общежитии ("Умное Общежитие"). Обеспечивает надежное управление устройствами (ESP8266/ESP32) через WebSocket с поддержкой восстановления соединений, имеет красивый веб-интерфейс и полную интеграцию с голосовым помощником **Яндекс Алиса**.

## 🚀 Основные Возможности

### 🖥️ Современный Web Dashboard
- **Glassmorphism Design**: Стильный и современный интерфейс с эффектом матового стекла.
- **Real-time Updates**: Мгновенное обновление статусов устройств через WebSocket.
- **Responsive**: Адаптирован под мобильные устройства и десктопы.
- **Тёмная тема**: Автоматическая поддержка системной темы.

### 🛡️ Reliability Layer (Слой Надежности)
- **Server Authority**: Сервер является единственным источником истины. При подключении устройство сразу синхронизируется с состоянием на сервере.
- **Heartbeat & Monitoring**: Строгий контроль соединения. Сервер отправляет `ping` каждые 5 сек. Если нет `pong` в течение 15 сек — устройство помечается `offline`.
- **Optimistic UI**: API принимает команды мгновенно, даже если устройство оффлайн. Состояние применится при следующем подключении.

### 🗣️ Интеграция с Яндекс Алисой
- **OAuth2 Server**: Встроенный провайдер авторизации (Login, Token Refresh) для связки аккаунтов.
- **Smart Home API**: Реализация протокола Умного Дома Яндекса (Discovery, Query, Action).
- **Голосовое управление**: "Алиса, включи свет", "Алиса, выключи лампу".

### 🤖 Telegram Интеграция (Foundation)
- **Telegram Bookmarks**: Система привязки устройств к Telegram ID пользователей (в разработке).
- **Aiogram**: Поддержка библиотеки `aiogram` для реализации бота.

## 🛠 Технологический стек

- **Backend**: Python 3.11, FastAPI, Uvicorn
- **Frontend**: HTML5, CSS3 (Glassmorphism), Vanilla JS
- **Protocol**: WebSockets (Custom JSON Protocol), HTTP REST
- **Storage**: 
  - **RAM**: Состояния устройств (In-Memory для максимальной скорости).
  - **SQLite**: Пользователи, токены авторизации Алисы и закладки устройств (SQLAlchemy).
- **Interactive**: Aiogram (Telegram Bot support).
- **Hardware**: ESP8266 / ESP32 (Arduino Framework).

## 📂 Структура проекта

```
.
├── app/
│   ├── main.py               # Точка входа (FastAPI), WebSocket роутинг
│   ├── database.py           # Модели БД (Telegram, Auth, Token)
│   ├── routers/
│   │   └── alice.py          # Роуты для Яндекс Алисы (OAuth2 + API)
│   └── services/
│       └── devices.py        # Логика управления устройствами (Manager)
├── static/                   # Файлы веб-дашборда
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── tests/                    # Автотесты (Pytest)
├── docs/                     # Документация
├── mock_esp.py               # Эмулятор устройства (Firmware v3)
├── requirements.txt          # Зависимости Python
└── walkthrough.md            # Пошаговое руководство
```

## ⚙️ Установка и Запуск

### 1. Установка зависимостей
Рекомендуется использовать виртуальное окружение.
```bash
pip install -r requirements.txt
```

### 2. Запуск сервера
```bash
uvicorn app.main:app --reload
```
При первом запуске автоматически создастся файл базы данных `sql_app.db`. 
- **API**: `http://127.0.0.1:8000/docs`
- **Dashboard**: `http://127.0.0.1:8000/`

### 3. Запуск эмулятора
Для проверки работы системы без физического устройства:
```bash
python mock_esp.py --device-id my_lamp
```
Эмулятор подключится к серверу, синхронизирует состояние и будет поддерживать heartbeat.

### 4. Тестирование
```bash
pytest
```
Запустит все тесты, включая сценарии авторизации Алисы и управления устройствами.

## 🔌 API Эндпоинты

### Управление устройствами (REST)
| Метод | URL | Описание |
|-------|-----|----------|
| `GET` | `/api/devices` | Список устройств и их статусов |
| `POST` | `/api/devices/{id}/turn_on` | Включить устройство |
| `POST` | `/api/devices/{id}/turn_off` | Выключить устройство |

### Яндекс Алиса (Smart Home)
- **Auth URL**: `https://<domain>/api/alice/authorize`
- **Token URL**: `https://<domain>/api/alice/token`
- **Endpoint URL**: `https://<domain>/api/alice/v1.0`

## 📡 Протокол (WebSocket v3)

Обмен данными происходит в формате JSON.

**Device (Client) → Server:**
- `{"type": "hello", ...}`: Идентификация при подключении.
- `{"type": "pong"}`: Ответ на ping сервера.

**Server → Device (Client):**
- `{"type": "sync_state", "state": "ON"}`: Синхронизация при подключении.
- `{"type": "ping"}`: Проверка связи (каждые 5 сек).
- `{"type": "command", "action": "TURN_ON"}`: Команда управления.

---
Разработано в рамках проекта Antigravity.

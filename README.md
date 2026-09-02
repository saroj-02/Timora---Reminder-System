# ⏰ Timora – Smart Task Reminder Web Application

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)
[![NiceGUI](https://img.shields.io/badge/NiceGUI-2.8-purple.svg)](https://nicegui.io/)
[![MongoDB](https://img.shields.io/badge/MongoDB-7.0-green.svg)](https://www.mongodb.com/)
[![License](https://img.shields.io/badge/License-MIT-brightgreen.svg)](LICENSE)

A complete, modern, production-grade Task Reminder SaaS Web Application built entirely in **Python** using **FastAPI**, **NiceGUI**, **Beanie ODM / MongoDB**, **APScheduler**, and the **Web Push API / Service Worker**.

---

## 📑 Table of Contents

1. [Project Overview](#1-project-overview)
2. [Key Features](#2-key-features)
3. [Technology Stack](#3-technology-stack)
4. [Architecture & Notification Flow](#4-architecture--notification-flow)
5. [Folder Structure](#5-folder-structure)
6. [MongoDB Setup](#6-mongodb-setup)
7. [Environment Variables](#7-environment-variables)
8. [Local Installation](#8-local-installation)
9. [Running FastAPI](#9-running-fastapi)
10. [Running NiceGUI](#10-running-nicegui)
11. [Running APScheduler](#11-running-apscheduler)
12. [Redis Setup](#12-redis-setup)
13. [Celery Background Worker Setup](#13-celery-background-worker-setup)
14. [VAPID Key Generation](#14-vapid-key-generation)
15. [Web Push Setup](#15-web-push-setup)
16. [Service Worker Setup](#16-service-worker-setup)
17. [Running Automated Tests](#17-running-automated-tests)
18. [Docker & Containerized Setup](#18-docker--containerized-setup)
19. [Production Deployment](#19-production-deployment)
20. [Troubleshooting & FAQs](#20-troubleshooting--faqs)

---

## 1. Project Overview

**Timora** is designed to solve the critical problems of web-based task reminders:
- Standard web apps only fire alerts while an active tab is open using client-side JavaScript timers (`setTimeout`), which fail immediately if the browser tab is closed.
- Real-world users are located across different timezones, requiring strict UTC storage with IANA timezone transformations that accurately respect Daylight Saving Time (DST) and midnight date boundaries.
- Reminders must support recurring intervals (Daily, Weekdays, Weekly, Monthly, Yearly), customizable pre-reminder notifications, snoozing, and rescheduling.

Timora executes all reminder scheduling on the backend, delivering browser and OS-level Web Push notifications through a registered Service Worker even when the tab is closed, and animated popups with a Web Audio chime when the user is actively browsing.

---

## 2. Key Features

- 🔐 **Full Authentication**: Secure signup with real-time password strength meter, argon2-cffi hashing, JWT session cookies (HttpOnly) and Bearer header support.
- 🌍 **Timezone-Aware Engine**: Powered by Python's `zoneinfo` standard library and IANA timezone database. Stores timestamps in UTC; renders according to user's localized zone. Automatic browser timezone detection with manual override.
- 🔔 **Dual-Mode Notifications**:
  - *Website Closed*: Web Push API + VAPID encryption → Service Worker → Native OS Notification with Action Buttons (Done / Snooze / Open).
  - *Website Open*: Animated, glassmorphism modal popup + smooth multi-frequency chime generated via the HTML5 Web Audio API.
- ⏰ **Smart Snooze & Reschedule**: Instant 5m, 10m, 15m, 30m, or 1h snoozing with automatic re-arming.
- 🔁 **Recurring Reminders**: Daily, Weekday-only, Weekly, Monthly, and Yearly recurring schedules calculated dynamically according to local timezone.
- 📅 **Interactive Calendar**: Monthly view displaying colored priority tags on scheduled dates with direct detail viewing.
- 🔍 **Search & Multi-Filter**: Real-time search across titles, descriptions, categories, and priorities with sorting by nearest, newest, oldest, or priority.
- 🎨 **Modern SaaS Aesthetics**: Purple/Blue/Cyan gradient palette, dark & light themes, smooth card hover micro-animations, glassmorphism cards, and responsive sidebar navigation.
- 🛡️ **Production-Ready Architecture**: Swappable scheduler engine (In-process APScheduler for development, Celery + Redis for horizontal scale).

---

## 3. Technology Stack

| Layer | Technologies |
|---|---|
| **Backend & REST API** | Python 3.12+, FastAPI, Pydantic v2, Pydantic Settings, Uvicorn, SlowAPI (Rate Limiting) |
| **Frontend UI** | NiceGUI 2.8, Quasar / Tailwind-based Python components, Vanilla CSS Design System |
| **Database & ODM** | MongoDB 7.0, Motor (Async Driver), Beanie ODM |
| **Authentication** | Argon2-cffi, PyJWT, HttpOnly Cookies |
| **Timezone Management** | Python `zoneinfo`, `tzdata` (IANA Timezone Database) |
| **Scheduling** | APScheduler (Dev/Single-node), Celery 5.4 + Redis 7.2 (Production/Multi-node) |
| **Push Notifications** | Web Push API, `pywebpush`, `py-vapid`, Service Worker (PWA Manifest) |
| **Testing** | Pytest, Pytest-Asyncio, HTTPX, Mongomock-motor |
| **DevOps** | Docker, Docker Compose, Multi-stage builds |

---

## 4. Architecture & Notification Flow

```
                                  TIMORA WEB APP
                                        │
                                        ▼
                                   USER LOGIN
                                        │
                                        ▼
                            TIMEZONE AUTO-DETECTION
                         (Intl.DateTimeFormat API)
                                        │
                                        ▼
                              ENABLE NOTIFICATIONS
                         (VAPID + Service Worker)
                                        │
                                        ▼
                                CREATE REMINDER
                          (Date + Local Time + Category)
                                        │
                                        ▼
                             UTC CONVERSION (zoneinfo)
                                        │
                                        ▼
                                 MONGODB STORAGE
                           (Status: PENDING, Time: UTC)
                                        │
                                        ▼
                           BACKGROUND SCHEDULER WORKER
                         (APScheduler / Celery Beat 30s)
                                        │
                                        ▼
                               REMINDER BECOMES DUE
                                        │
                     ┌──────────────────┴──────────────────┐
                     ▼                                     ▼
             WEBSITE OPEN (TAB ACTIVE)             WEBSITE / TAB CLOSED
                     │                                     │
                     ▼                                     ▼
         IN-APP ANIMATED POPUP                         WEB PUSH
                   +                                (pywebpush + VAPID)
          WEB AUDIO CHIME (C5-E5-G5-C6)                    │
                     │                                     ▼
                     │                               SERVICE WORKER
                     │                                     │
                     │                                     ▼
                     │                             NATIVE OS NOTIFICATION
                     │                          [ DONE ]  [ SNOOZE ]  [ OPEN ]
                     │                                     │
                     └──────────────────┬──────────────────┘
                                        ▼
                                COMPLETED / SNOOZED
```

---

## 5. Folder Structure

```text
Timora-Smart Reminder/
├── app/
│   ├── config.py                 # Pydantic Settings reading .env
│   ├── database.py               # Motor async client & Beanie initialization
│   ├── main.py                   # NiceGUI + FastAPI integration entrypoint
│   ├── worker.py                 # Production Celery worker definition
│   │
│   ├── models/                   # Beanie Document Models
│   │   ├── user.py               # User model with timezone & settings
│   │   ├── reminder.py           # Reminder model with UTC time & enums
│   │   └── push_subscription.py  # Web Push subscription endpoint model
│   │
│   ├── schemas/                  # Pydantic validation schemas
│   │   ├── auth.py               # Signup, Login, Token schemas
│   │   ├── reminder.py           # Reminder CRUD & action schemas
│   │   └── user.py               # User profile & preferences schemas
│   │
│   ├── routes/                   # FastAPI REST Endpoints
│   │   ├── auth.py               # /api/auth (signup, login, logout, me)
│   │   ├── reminders.py          # /api/reminders (CRUD, snooze, complete)
│   │   ├── users.py              # /api/users (profile, password)
│   │   └── notifications.py      # /api/notifications (subscribe, test)
│   │
│   ├── services/                 # Business Logic Layer
│   │   ├── auth_service.py       # Argon2 hashing & JWT encoding/decoding
│   │   ├── reminder_service.py   # CRUD, recurrence calculations
│   │   ├── notification_service.py # Web Push delivery & 410 cleanup
│   │   └── scheduler_service.py  # APScheduler polling worker
│   │
│   ├── frontend/                 # NiceGUI Python UI Layer
│   │   ├── state.py              # Session storage & auth tokens
│   │   ├── theme.py              # CSS Design system & dark/light styles
│   │   ├── api_client.py         # HTTP client helper for NiceGUI
│   │   ├── layouts/
│   │   │   └── main_layout.py    # Desktop sidebar & mobile navigation
│   │   ├── pages/
│   │   │   ├── login.py          # Modern Glassmorphic Login
│   │   │   ├── signup.py         # Signup with password strength meter
│   │   │   ├── timezone_setup.py # Country/Timezone auto-detect onboarding
│   │   │   ├── dashboard.py      # Main dashboard with statistics
│   │   │   ├── reminders.py      # Searchable & filterable reminder list
│   │   │   ├── calendar_page.py  # Interactive monthly calendar
│   │   │   └── settings.py       # User profile, sounds, and security
│   │   └── components/
│   │       ├── reminder_card.py  # Interactive reminder card with actions
│   │       ├── reminder_modal.py # Create/Edit reminder modal dialog
│   │       ├── reminder_popup.py # In-app alert popup + Web Audio chime
│   │       └── toast.py          # Toast notification helpers
│   │
│   └── utils/
│       └── timezone.py           # zoneinfo conversions & IANA mappings
│
├── static/                       # Static web assets
│   ├── service-worker.js         # Push listener & notification handler
│   ├── manifest.json             # PWA Web Manifest
│   └── icons/                    # App icons (192x192, 512x512, badge-72)
│
├── scripts/
│   ├── generate_icons.py         # Icon asset builder in pure Python
│   └── generate_vapid.py         # Standalone VAPID key generator
│
├── tests/                        # Comprehensive Pytest Suite
│   ├── conftest.py               # Async DB & client fixtures
│   ├── test_auth.py              # Authentication test cases
│   ├── test_reminders.py         # Reminder lifecycle & isolation tests
│   ├── test_timezones.py         # IANA timezone & DST conversion tests
│   ├── test_scheduler.py         # Due detection & recurrence tests
│   └── test_notifications.py     # Web Push subscription tests
│
├── .env.example                  # Environment variable template
├── .env                          # Local environment secrets
├── requirements.txt              # Pinned Python dependencies
├── Dockerfile                    # Multi-stage production Dockerfile
├── docker-compose.yml            # Full containerized stack (App, Mongo, Redis)
└── README.md                     # Comprehensive documentation
```

---

## 6. MongoDB Setup

Timora requires MongoDB 6.0+.

### Option A: Local MongoDB
Install and run MongoDB on your system:
```bash
# macOS via Homebrew
brew tap mongodb/brew
brew install mongodb-community@7.0
brew services start mongodb-community@7.0

# Linux (Ubuntu/Debian)
sudo apt-get install -y mongodb-org
sudo systemctl start mongod
```

### Option B: MongoDB via Docker
```bash
docker run -d --name timora-mongo -p 27017:27017 -v timora_data:/data/db mongo:7.0
```

---

## 7. Environment Variables

Create a `.env` file in the project root based on `.env.example`:

```bash
cp .env.example .env
```

| Variable | Default Value | Description |
|---|---|---|
| `MONGODB_URL` | `mongodb://localhost:27017` | MongoDB connection URI |
| `DATABASE_NAME` | `timora` | Database collection name |
| `JWT_SECRET` | *(Random 64-hex string)* | Secret for signing auth tokens |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Access token lifespan |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `30` | Remember-me token lifespan |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis broker for Celery worker |
| `VAPID_PUBLIC_KEY` | *(Auto-generated on 1st run)* | VAPID public key for Web Push |
| `VAPID_PRIVATE_KEY` | *(Auto-generated on 1st run)* | VAPID private key (Keep secret) |
| `VAPID_CLAIMS_EMAIL` | `admin@timora.app` | Contact email for push services |
| `APP_HOST` | `0.0.0.0` | Host to bind server to |
| `APP_PORT` | `8000` | Port for web application |
| `APP_URL` | `http://localhost:8000` | Public URL for notification redirects |

---

## 8. Local Installation

### Prerequisites
- Python 3.12 or newer
- Git

### 1. Clone & Set Up Virtual Environment
```bash
git clone <repository-url>
cd "Timora-Smart Reminder"

python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 2. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Generate Static Icons (if needed)
```bash
python3 scripts/generate_icons.py
```

---

## 9. Running FastAPI & NiceGUI

NiceGUI and FastAPI are unified into a single runtime server. Run the application with:

```bash
python3 -m app.main
```

Or using Uvicorn directly:
```bash
uvicorn app.main:fast_api --host 0.0.0.0 --port 8000 --reload
```

Open your browser and navigate to:
👉 **`http://localhost:8000`**

- **Web Application UI**: `http://localhost:8000/`
- **Swagger Interactive API Docs**: `http://localhost:8000/api/docs`
- **ReDoc API Documentation**: `http://localhost:8000/api/redoc`

---

## 10. Running NiceGUI

NiceGUI serves the frontend UI routes (`/dashboard`, `/reminders`, `/calendar`, `/settings`, `/login`, `/signup`). It automatically boots when running `app.main`.

Key characteristics:
- Python-driven UI with native reactivity
- Fast single-page application experience with zero React/Node build steps
- Quasar and Material Icons component styling

---

## 11. Running APScheduler

APScheduler starts automatically during the FastAPI application lifespan in `app/main.py`.

- **Interval**: Runs every **30 seconds** (customizable via `POLL_INTERVAL_SECONDS` in `app/services/scheduler_service.py`).
- **Idempotency**: It queries `status="pending"` and `scheduled_time_utc <= now_utc`, marks `notification_sent_at`, and updates the status to prevent duplicate firing.
- **Server Restart Recovery**: On startup, any due reminders that were missed during downtime are detected and immediately dispatched.

---

## 12. Redis Setup

For production Celery-based scheduling, Redis serves as the message broker.

```bash
# Run Redis via Docker
docker run -d --name timora-redis -p 6379:6379 redis:7.2-alpine
```

---

## 13. Celery Background Worker Setup

To use the production Celery worker with Celery Beat:

```bash
# Start Celery Worker with embedded Beat scheduler
celery -A app.worker.celery_app worker --beat --loglevel=info
```

---

## 14. VAPID Key Generation

VAPID (Voluntary Application Server Identification) keys are generated automatically when Timora boots for the first time if none are provided.

To generate new keys manually at any time:
```bash
python3 scripts/generate_vapid.py
```
Copy the printed `VAPID_PUBLIC_KEY` and `VAPID_PRIVATE_KEY` into your `.env` file.

---

## 15. Web Push Setup

Web Push enables notification delivery when the browser or tab is closed:
1. When a user clicks **"Enable Notifications"** on the Dashboard, the browser prompts for permission.
2. The browser creates a `PushSubscription` containing an endpoint URL and elliptic-curve encryption keys (`p256dh`, `auth`).
3. The subscription is saved to MongoDB via `POST /api/notifications/subscribe`.
4. When a reminder triggers, the backend encrypts the payload with VAPID credentials via `pywebpush` and posts to the push service (e.g. Google FCM, Mozilla autopush, Apple WebPush).

---

## 16. Service Worker Setup

The Service Worker is located at `static/service-worker.js`.
- Automatically registered by the client with scope `/`.
- Listens for `push` events and displays native OS notifications.
- Handles `notificationclick` events:
  - Clicking **"Done"** directly marks the reminder as completed.
  - Clicking **"Snooze 10m"** snoozes the reminder for 10 minutes.
  - Clicking the notification body focuses or opens the Timora dashboard.

---

## 17. Running Automated Tests

Run the full automated test suite using `pytest`:

```bash
pytest tests/ -v
```

### Test Coverage Summary:
- ✅ `test_auth.py`: Signup, Login, Password strength validation, duplicate prevention, JWT decode, unauthorized blocks.
- ✅ `test_reminders.py`: Complete CRUD lifecycle, past-time rejection, snooze, reschedule, mark done, and cross-user data isolation.
- ✅ `test_timezones.py`: IANA conversions across IST, EST/EDT, PST/PDT, BST/GMT, JST, AEDT/AEST, DST shifts, and date boundary crossings.
- ✅ `test_scheduler.py`: Due reminder polling, notification idempotency, snoozed recovery, and recurrence algorithms (Daily, Weekdays, Weekly, Monthly, Yearly).
- ✅ `test_notifications.py`: VAPID key distribution, push subscription upserts, and unsubscribe flows.

---

## 18. Docker & Containerized Setup

Build and run the entire stack (MongoDB, Redis, Web App, Celery Worker) using Docker Compose:

```bash
# Build and start all services
docker compose up --build -d

# View application logs
docker compose logs -f app

# Stop all containers
docker compose down
```

---

## 19. Production Deployment

### Production Checklist:
1. **Domain & HTTPS**: Web Push and Service Workers **require** HTTPS (or `localhost` for local dev). Set up an SSL certificate with Let's Encrypt / Caddy / Nginx.
2. **Environment Variables**:
   - Set `APP_DEBUG=false`.
   - Set `APP_URL=https://your-domain.com`.
   - Generate a cryptographically secure `JWT_SECRET`.
   - Configure a valid contact email in `VAPID_CLAIMS_EMAIL`.
3. **Reverse Proxy (Nginx Example)**:
```nginx
server {
    server_name timora.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 20. Troubleshooting & FAQs

### 1. Notifications are not appearing when tab is closed
- Ensure you have granted browser notification permission (`Dashboard -> Enable Notifications`).
- Web Push requires HTTPS in production (Chrome/Firefox/Safari block Service Workers on insecure HTTP origins other than `localhost`).
- Verify that your OS has not enabled "Do Not Disturb" or "Focus Assist".

### 2. Timezone displays incorrectly
- Check that you have selected a valid IANA timezone (e.g. `Asia/Kolkata` or `America/New_York`) on the Settings page.
- Timora uses Python's standard `zoneinfo` and never relies on ambiguous 3-letter abbreviations.

### 3. Audio chime doesn't play
- Modern browsers require at least one user interaction (click) on the page before web audio can play due to browser autoplay policies.
- Check that "Reminder Sound" is enabled in Settings and the volume slider is above 0.

### 4. Database connection error on startup
- Ensure MongoDB is running on port 27017 (`brew services list` or `docker ps`).
- Check `MONGODB_URL` in `.env`.

---

## 📄 License

MIT License. Free for personal and commercial use.

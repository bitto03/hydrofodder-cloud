# HydroFodder Cloud — Local-First IoT SaaS MVP

A production-oriented Django foundation for a Hydroponic Fodder IoT platform. This package is intentionally **local-first**: you can test authentication, device ownership, secure device credentials, telemetry, desired/actual relay state, command acknowledgment, WebSocket dashboard updates, and schedule persistence before introducing MQTT infrastructure.

## Current status

### Implemented
- Custom Django user model using email login
- Registration, login, logout, Django password-reset flow hooks
- Server-side device ownership enforcement
- Device UID + one-time random device token; only the token hash is stored
- Four relays per registered device
- Desired state vs actual state
- Command lifecycle: pending -> acknowledged/failed
- Device heartbeat and online/offline calculation
- DHT-style temperature/humidity telemetry with validation and history model
- Browser dashboard with live WebSocket updates
- Relay schedules stored in the database
- Celery/Redis schedule scanner for cloud scheduling
- PostgreSQL-ready configuration
- Docker Compose for Django + PostgreSQL + Redis + worker + beat
- Django Admin
- Automated tests for ownership and device API authentication
- HTTP device simulator for local end-to-end testing
- ESP32 firmware skeleton with non-blocking loop structure

### Partially implemented / next phase
- MQTT transport is not wired in this first local package. The database/API boundary is designed so MQTT can replace device command polling without changing the core domain model.
- ESP32 local schedule persistence/offline execution is not implemented in the included firmware skeleton yet.
- OTA, TLS certificate provisioning, per-device MQTT ACLs, credential rotation UI, email verification, SMTP, rate limiting, metrics, alerting, and telemetry retention jobs belong to subsequent phases.
- Celery cloud scheduling queues OFF commands after `run_seconds`, but reliable safety-critical scheduling should ultimately be mirrored to ESP32 local storage so loss of Internet does not stop irrigation cycles.

## Architecture

```text
Browser
  | HTTPS / WebSocket
  v
Django ASGI
  |-- Accounts / ownership authorization
  |-- Device/relay desired & actual state
  |-- Command lifecycle
  |-- Telemetry API
  |-- WebSocket event broadcast
  |
  +--> PostgreSQL (SQLite for easiest local run)
  +--> Redis + Celery (optional locally, required for cloud schedule worker)
  |
  +--> Device transport boundary
         |-- HTTP polling/simulator in this MVP
         `-- MQTT/TLS + per-device ACLs in next phase

ESP32
  | heartbeat / telemetry / command ack
  v
Device-authenticated endpoints
```

## Why MQTT is the recommended production device transport

For the final product, use MQTT over TLS for **ESP32 <-> cloud**, WebSockets for **browser <-> Django**, and REST for CRUD/configuration. MQTT is better suited to long-lived device sessions, Last Will and Testament, QoS, retained state/configuration, lightweight messages, and broker-side topic ACLs. The browser should not connect directly to the ESP32.

Recommended topic shape for the next phase:

```text
v1/devices/<device_uid>/telemetry
v1/devices/<device_uid>/state/reported
v1/devices/<device_uid>/state/desired
v1/devices/<device_uid>/commands
v1/devices/<device_uid>/acks
v1/devices/<device_uid>/status
```

Use TLS, unique device credentials/certificates, and broker ACLs that only allow each device to access its own namespace.

## Local test — simplest path (`runserver 0.0.0.0`)

### 1. Requirements

Recommended: Python 3.13 and a virtual environment.

```bash
cd hydrofodder_cloud
python -m venv .venv
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Environment

Copy `.env.example` to `.env`.

Linux/macOS:

```bash
cp .env.example .env
```

Windows:

```powershell
Copy-Item .env.example .env
```

For this first local test, leave `DATABASE_URL` and `REDIS_URL` empty. Django will use SQLite and an in-memory Channels layer.

### 3. Database

```bash
python manage.py migrate
python manage.py createsuperuser
```

### 4. Start local server on all interfaces

```bash
python manage.py runserver 0.0.0.0:8000
```

On the same PC open:

```text
http://127.0.0.1:8000/
```

From another device on the same LAN, use your computer's LAN IP, for example:

```text
http://192.168.1.50:8000/
```

If accessing from another LAN device, add that LAN IP to `ALLOWED_HOSTS` in `.env` and restart Django.

**Security:** `runserver` is development-only. Never expose it directly to the public Internet.

## Local end-to-end device simulation

1. Register a user.
2. Login.
3. Click **Add Device**.
4. Create a device.
5. Copy both the Device UID and the one-time token shown on screen.
6. Keep Django running.
7. In a second terminal, activate the same venv and run:

```bash
python tools/device_simulator.py \
  --uid YOUR_DEVICE_UID \
  --token YOUR_DEVICE_TOKEN \
  --server http://127.0.0.1:8000
```

The simulator will:
- send heartbeats,
- send temperature/humidity telemetry,
- poll pending relay commands,
- simulate the relay state change,
- acknowledge each command.

Now toggle Relay 1-4 in the web dashboard. You should see:

```text
Sending...
-> Pending device acknowledgment
-> simulator receives command
-> simulator acknowledges
-> Actual state updates in dashboard
```

This specifically verifies that the UI does **not** treat a button click as proof that the physical relay changed.

## Test suite

```bash
python manage.py check
python manage.py test
```

The included tests verify that one user cannot command another user's device and that the device credential can authenticate telemetry.

## PostgreSQL + Redis + Celery local stack

For a closer-to-production local environment:

```bash
docker compose up --build
```

In another terminal after services are healthy:

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

Then open `http://127.0.0.1:8000/`.

The worker and beat services enable cloud-side schedule scanning. The beat scheduler checks due schedules every 5 seconds. For each due schedule it creates an ON command and schedules an OFF command after `run_seconds`.

## Important timer architecture

Critical irrigation timing must **not** depend exclusively on the browser or cloud. Recommended production responsibility split:

```text
Cloud
- Own schedule configuration/version
- Validate schedules
- Store canonical configuration
- Send schedule revisions to device
- Audit executions / missed cycles
- Run fallback/coordination jobs

ESP32
- Persist latest validated schedule locally (NVS)
- Execute schedule while Internet is unavailable
- Enforce safety limits
- Record execution IDs/events for later sync
- Reconcile with cloud after reconnect

Browser
- Configure schedules
- Display desired/reported state and execution history
- Never execute critical timers itself
```

## Desired vs actual state

`Relay.desired_state` is what the cloud wants. `Relay.actual_state` is only changed by a device acknowledgment/report.

A command is created as `pending`. The device then reports whether it executed the command. This is the foundation for timeout/retry/idempotency logic in the MQTT phase.

## Device credential model

A generated `device_uid` is the public identifier. It is **not a secret**. The device token is random and shown once. Only its SHA-256 digest is stored in the database.

For commercialization, evolve this toward one of these provisioning strategies:
- per-device client certificate / mTLS,
- broker-issued username + high-entropy secret with rotation,
- factory bootstrap credential exchanged for operational credentials.

Do not use the ESP32 MAC address as authentication.

## Relay / mains electrical safety

Do not assume a 4-channel relay board is safe for your pump or mains voltage merely because it has relay contacts.

Before wiring a load verify:
- relay contact voltage/current ratings for the actual load category,
- pump startup/inrush current,
- AC vs DC switching rating,
- isolation/creepage/clearance on the relay module,
- enclosure and strain relief,
- grounding/earthing,
- relay input logic compatibility with ESP32 3.3 V,
- whether the relay is active LOW or active HIGH,
- suppression appropriate for inductive loads.

For mains-voltage work, use appropriately rated components/enclosures and a qualified electrician where required. Keep low-voltage ESP32 wiring physically separated from hazardous voltage.

## ESP32 pin sketch

The included firmware skeleton currently uses:

```text
DHT11 DATA -> GPIO 4
Relay 1 IN -> GPIO 16
Relay 2 IN -> GPIO 17
Relay 3 IN -> GPIO 18
Relay 4 IN -> GPIO 19
ESP32 GND -> relay/sensor low-voltage reference, only if the specific module topology requires/common-ground permits it
```

**Do not wire solely from this list until the exact relay board, power supply, pump voltage/current, and active HIGH/LOW behavior are confirmed.**

## Production deployment direction — Railway

The repository contains a Dockerfile suitable for a Django ASGI service. A production Railway layout should be separated into services:

```text
Public Django/Daphne service
PostgreSQL service
Redis service
Celery worker service
Celery beat service
External/managed MQTT broker or separately hosted broker
```

Before production:
- set `DEBUG=0`,
- generate a strong `SECRET_KEY`,
- configure `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`,
- use Railway PostgreSQL/Redis service variables,
- run migrations as a pre-deploy/release step,
- configure HTTPS and secure cookies,
- add health checks and structured monitoring,
- never commit `.env` or device secrets.

## Suggested next development phase

1. Run and verify this local package.
2. Connect the physical ESP32 over local HTTP or immediately introduce a local MQTT broker.
3. Implement MQTT adapter in Django as an independent worker/service.
4. Add device LWT/heartbeat and command timeout/retry/idempotency.
5. Implement ESP32 NVS schedule persistence and offline execution.
6. Add schedule revision/version reconciliation.
7. Move local stack to PostgreSQL + Redis.
8. Deploy Django/PostgreSQL/Redis/worker to Railway.
9. Integrate a TLS-capable MQTT broker with per-device ACLs.
10. Perform security and failure-mode testing before controlling real pumps unattended.

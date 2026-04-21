# Test Process: mfa-chain-orchestrator

This document defines a repeatable local test process for the FastAPI test app with two MFA apps.

## Prerequisites

- Python 3.10+
- Project dependencies:

```bash
pip install -r requirements.txt
pip install fastapi uvicorn
```

Optional QR PNG support:

```bash
pip install qrcode[pil]
```

## Start the Test App

Run from repository root:

```bash
PYTHONPATH=src uvicorn examples.fastapi_test_app:app --reload
```

Base URL used below:

```text
http://127.0.0.1:8000
```

## Browser UI Walkthrough

Open:

- `http://127.0.0.1:8000/` (or `/ui`)

UI steps:

1. Enter `user_id`.
2. Click enroll for `google_auth` and `ms_auth`.
3. Scan returned QR codes in each app (or use manual secret entry).
4. Click start attempt.
5. Enter code from expected factor and click verify.

The detailed curl-based process is below.

## Onboard 2 MFA Apps

Use one `user_id` (example: `alice`) and enroll both factors.

### 1. Enroll Google Authenticator factor

```bash
curl -s -X POST http://127.0.0.1:8000/users/alice/factors/google_auth/enroll
```

Expected:
- `otpauth_uri` for app scan
- `secret` (test-only helper)
- `qr_png_base64` (non-empty when `qrcode[pil]` is installed)

### 2. Enroll Microsoft Authenticator factor

```bash
curl -s -X POST http://127.0.0.1:8000/users/alice/factors/ms_auth/enroll
```

Expected same fields as above.

### 3. Scan each `otpauth_uri` in the matching authenticator app

- Scan Google URI into Google Authenticator
- Scan Microsoft URI into Microsoft Authenticator

If scanning is not convenient, manual secret entry also works.

## Login Attempt (MFA Chain)

### 1. Start MFA attempt

```bash
curl -s -X POST http://127.0.0.1:8000/users/alice/attempt/start
```

Save these fields:
- `session_id`
- `current_factor_id`

### 2. Get current expected step + test code (debug helper)

```bash
curl -s http://127.0.0.1:8000/attempt/<session_id>/debug/current-code
```

Returns:
- `factor_id` (must be submitted in verify call)
- `code`

### 3. Verify current step

```bash
curl -s -X POST http://127.0.0.1:8000/attempt/verify \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "<session_id>",
    "factor_id": "<factor_id from debug or UI step>",
    "user_input": "<6-digit code>",
    "window": 1
  }'
```

Expected:
- If first step valid: `success: true`, `is_complete: false`
- If second step valid: `success: true`, `is_complete: true`

Repeat step 2 and step 3 until complete.

## Security/Failure Tests

### A. Wrong code triggers reset

Submit invalid code `000000`.

Expected:
- `success: false`
- `is_complete: false`
- `next_factor_label` contains `RESET -> restart with ...`

### B. Out-of-order factor is blocked

Send `factor_id` that is not the expected current factor.

Expected:
- HTTP `409`
- detail indicates expected factor and attempted factor

### C. Missing enrollment blocked at attempt start

Try starting attempt before enrolling both required factors.

Expected:
- HTTP `400`
- detail lists missing factors

## Notes

- `/attempt/{session_id}/debug/current-code` is test-only and must not exist in production.
- Enroll endpoint returning `secret` is test-only.
- Test app state is in-memory only; restarting server clears users and sessions.

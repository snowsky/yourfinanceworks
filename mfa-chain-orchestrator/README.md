# mfa-chain-orchestrator

Policy-driven MFA chain orchestration with strict step order, TOTP verification, and reset-on-failure behavior.

## Features

- `fixed` or `random` MFA factor sequencing per attempt.
- Enforced `required_steps` with validated policy definitions.
- TOTP verification via `pyotp`.
- Strict ordering protection via `MFAChainBreached`.
- Security hardening: any single failure returns `RESET` and forces restart from Token 1.

## Installation

```bash
pip install -r requirements.txt
```

or

```bash
pip install .
```

## Usage

```python
from mfa_chain_orchestrator import MFAOrchestrator, Policy

policy = Policy(
    mode="random",
    required_steps=2,
    factors=[
        {"id": "token_1", "label": "Authenticator App", "type": "totp"},
        {"id": "token_2", "label": "Backup Device", "type": "totp"},
        {"id": "token_3", "label": "Hardware Token", "type": "totp"},
    ],
)

orchestrator = MFAOrchestrator(policy)
chain = orchestrator.initialize_attempt()
first = chain[0]

# Verify step 1
result = orchestrator.verify_step(
    secret="JBSWY3DPEHPK3PXP",  # Base32 secret
    user_input="123456",
    window=1,
    factor_id=first.id,
)

if not result.success and result.next_factor_label == "RESET":
    # Restart from Token 1 (call initialize_attempt again if desired)
    pass
```

## FastAPI Session Integration Example

```python
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from mfa_chain_orchestrator import MFAChainBreached, MFAOrchestrator, Policy

app = FastAPI()

policy = Policy(
    mode="fixed",
    required_steps=2,
    factors=[
        {"id": "token_1", "label": "Token 1", "type": "totp"},
        {"id": "token_2", "label": "Token 2", "type": "totp"},
    ],
)

orchestrator_store: dict[str, MFAOrchestrator] = {}


class StepVerifyPayload(BaseModel):
    factor_id: str
    user_input: str


def get_orchestrator(session_id: str) -> MFAOrchestrator:
    if session_id not in orchestrator_store:
        orchestrator = MFAOrchestrator(policy)
        chain = orchestrator.initialize_attempt()
        # Persist chain metadata in your server-side session store if needed.
        orchestrator_store[session_id] = orchestrator
    return orchestrator_store[session_id]


@app.post("/mfa/verify")
def verify_step(payload: StepVerifyPayload, request: Request):
    session_id = request.headers.get("X-Session-Id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing session id")

    orchestrator = get_orchestrator(session_id)

    try:
        result = orchestrator.verify_step(
            secret="JBSWY3DPEHPK3PXP",  # fetch per-user secret from secure storage
            user_input=payload.user_input,
            window=1,
            factor_id=payload.factor_id,
        )
    except MFAChainBreached as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if not result.success and result.next_factor_label == "RESET":
        # Any failure hard-resets chain state.
        orchestrator.initialize_attempt()
        raise HTTPException(status_code=401, detail="MFA reset. Start again from Token 1.")

    if result.is_complete:
        return {"authenticated": True}

    return {
        "authenticated": False,
        "next_factor_label": result.next_factor_label,
    }
```

## Security Notes

- `verify_step()` validates code shape (`6` digits) before TOTP verification.
- On any failure, cursor resets to the first step and returns `next_factor_label="RESET"`.
- Out-of-order calls can be blocked by passing `factor_id`; mismatches raise `MFAChainBreached`.
- Store secrets in an HSM/KMS-backed vault, never in plaintext config.

## Public API

- `MFAOrchestrator(policy: Policy)`
- `MFAOrchestrator.initialize_attempt() -> list[FactorDefinition]`
- `MFAOrchestrator.verify_step(secret: str, user_input: str, window: int, factor_id: str | None = None) -> Result`
- `MFAChainBreached`
- `Policy`, `FactorDefinition`, `Result`

## Runnable Test App (FastAPI)

A ready-to-run test app is included at `examples/fastapi_test_app.py`.

### 1. Install extra test-app dependencies

```bash
pip install fastapi uvicorn
```

Optional QR PNG payload support:

```bash
pip install qrcode[pil]
```

### 2. Run the app

```bash
PYTHONPATH=src uvicorn examples.fastapi_test_app:app --reload
```

### 3. Browser UI (recommended)

Open:

- `http://127.0.0.1:8000/` (or `http://127.0.0.1:8000/ui`)

The UI guides users through:

- enrolling Google and Microsoft authenticator factors
- starting a login attempt
- verifying each MFA step in order

### 4. API-first test flow (curl)

### 4. Test the flow

Enroll two different authenticator apps for one user:

```bash
curl -s -X POST http://127.0.0.1:8000/users/alice/factors/google_auth/enroll
curl -s -X POST http://127.0.0.1:8000/users/alice/factors/ms_auth/enroll
```

Then start an attempt:

```bash
curl -s -X POST http://127.0.0.1:8000/users/alice/attempt/start
```

Get the currently expected factor + a debug code:

```bash
curl -s http://127.0.0.1:8000/attempt/<session_id>/debug/current-code
```

Verify:

```bash
curl -s -X POST http://127.0.0.1:8000/attempt/verify \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "<session_id>",
    "factor_id": "<expected factor_id>",
    "user_input": "<code>",
    "window": 1
  }'
```

If verification fails, the orchestrator returns reset behavior and the chain restarts from step 1.
For the full scriptable process, see `TEST_PROCESS.md`.

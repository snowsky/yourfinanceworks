#!/usr/bin/env python3
"""Concurrent-load reproduction for per-tenant DB connection-pool exhaustion.

Fires a burst of *load* requests (default: the AI chat endpoint, which holds a
tenant DB connection across slow LLM + nested self-HTTP calls) while periodically
*probing* a cheap victim endpoint (default: the invoice list). If the probe slows
down or starts failing while the load runs, the load endpoint is starving the
tenant pool — the `read_invoices` QueuePool-timeout signature.

Run it INSIDE the api container (httpx + localhost:8000 are available there):

    docker compose exec api python scripts/pool_loadtest.py \
        --token "<JWT>" --tenant 1 \
        --concurrency 20 --duration 30

Get <JWT> from your browser DevTools (the Authorization header on any API call)
or an API login. To reproduce the AI amplification specifically, the tenant must
have a working (ideally not-instant) AI provider configured, since /ai/chat only
holds the connection while the LLM call runs. Otherwise point --load-endpoint at
any genuinely slow endpoint.

Pair with YFW_LOG_POOL_STATS=1 on the api service to watch pool checkouts climb.
"""

import argparse
import asyncio
import json
import statistics
import time

import httpx


async def _timed(client, method, url, headers, body):
    t0 = time.perf_counter()
    try:
        r = await client.request(method, url, headers=headers, json=body, timeout=60.0)
        return (time.perf_counter() - t0, r.status_code, None)
    except Exception as e:  # noqa: BLE001
        return (time.perf_counter() - t0, None, type(e).__name__)


def _summarize(name, results):
    if not results:
        print(f"{name}: no requests")
        return
    lat = [r[0] for r in results]
    ok = sum(1 for r in results if r[1] and r[1] < 400)
    errs: dict[str, int] = {}
    for _, status, exc in results:
        key = exc or (f"HTTP {status}" if status and status >= 400 else None)
        if key:
            errs[key] = errs.get(key, 0) + 1
    print(f"\n{name}: {len(results)} reqs, {ok} ok")
    print(f"  latency  p50={statistics.median(lat):.2f}s  max={max(lat):.2f}s")
    if errs:
        print(f"  failures: {errs}")


async def run(args):
    headers = {
        "Authorization": f"Bearer {args.token}",
        "X-Tenant-ID": str(args.tenant),
        "Content-Type": "application/json",
    }
    body = json.loads(args.load_body) if args.load_body else None
    base = args.base_url.rstrip("/")
    load_url = base + args.load_endpoint
    probe_url = base + args.probe_endpoint

    load_results: list = []
    probe_results: list = []
    stop = asyncio.Event()

    async with httpx.AsyncClient() as client:

        async def load_worker():
            while not stop.is_set():
                load_results.append(await _timed(client, args.load_method, load_url, headers, body))

        async def prober():
            while not stop.is_set():
                r = await _timed(client, "GET", probe_url, headers, None)
                probe_results.append(r)
                flag = "" if (r[1] and r[1] < 400) else "  <-- FAIL/SLOW"
                print(f"  probe {args.probe_endpoint}: {r[0]:.2f}s status={r[1]} err={r[2]}{flag}")
                await asyncio.sleep(args.probe_interval)

        print(
            f"Driving {args.concurrency} concurrent {args.load_method} {args.load_endpoint} "
            f"for {args.duration}s; probing {args.probe_endpoint} every {args.probe_interval}s...\n"
        )
        workers = [asyncio.create_task(load_worker()) for _ in range(args.concurrency)]
        prober_task = asyncio.create_task(prober())
        await asyncio.sleep(args.duration)
        stop.set()
        await asyncio.gather(*workers, prober_task, return_exceptions=True)

    _summarize(f"LOAD  ({args.load_endpoint})", load_results)
    _summarize(f"PROBE ({args.probe_endpoint})", probe_results)
    print(
        "\nInterpretation: if PROBE latency spikes or shows ReadTimeout/HTTP 500 while LOAD"
        "\nruns, the load endpoint is starving the tenant pool. With the pool_timeout fix,"
        "\nexpect failures within ~10s instead of 30s hangs."
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--base-url", default="http://localhost:8000/api/v1")
    ap.add_argument("--token", required=True, help="Bearer JWT for an authenticated tenant user")
    ap.add_argument("--tenant", required=True, help="Tenant id (X-Tenant-ID header)")
    ap.add_argument("--load-endpoint", default="/ai/chat")
    ap.add_argument("--load-method", default="POST")
    ap.add_argument("--load-body", default='{"message":"hello","mode":"onboarding"}')
    ap.add_argument("--probe-endpoint", default="/invoices/")
    ap.add_argument("--concurrency", type=int, default=20)
    ap.add_argument("--duration", type=float, default=30.0)
    ap.add_argument("--probe-interval", type=float, default=1.0)
    asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    main()

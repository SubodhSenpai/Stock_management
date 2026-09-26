"""Load test the running API and report latency percentiles.

Start the server first, then:

    python -m scripts.loadtest --users 50 --requests 20

It signs in once per simulated user, then fires concurrent requests at a mix of read
endpoints, plus a burst of competing stock reservations to show that the locking holds
under load. Nothing is mocked; this drives the real server over HTTP.

Results are written to backend/reports/LOAD-TEST.md, which is git-ignored: it is
generated output that depends on the machine it ran on.
"""

import argparse
import statistics
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

REPORT_PATH = Path(__file__).resolve().parents[1] / "reports" / "LOAD-TEST.md"
DEFAULT_BASE_URL = "http://127.0.0.1:8000/api/v1"
DEFAULT_LOGIN = ("manager1", "Manager@123")

READ_ENDPOINTS = [
    ("dashboard", "/dashboard/summary"),
    ("operations", "/operations?page_size=20"),
    ("stock", "/stock?page_size=20"),
    ("products", "/products?page_size=20"),
    ("moves", "/moves?limit=20"),
    ("search", "/products?q=des"),
]


@dataclass
class Results:
    name: str
    latencies_ms: list[float] = field(default_factory=list)
    statuses: Counter = field(default_factory=Counter)
    errors: list[str] = field(default_factory=list)

    def record(self, status: int, elapsed_ms: float) -> None:
        self.latencies_ms.append(elapsed_ms)
        self.statuses[status] += 1

    @property
    def ok(self) -> int:
        return sum(count for status, count in self.statuses.items() if status < 400)

    def percentile(self, fraction: float) -> float:
        if not self.latencies_ms:
            return 0.0
        ordered = sorted(self.latencies_ms)
        index = min(int(len(ordered) * fraction), len(ordered) - 1)
        return ordered[index]

    def summary_row(self) -> str:
        count = len(self.latencies_ms)
        if not count:
            return f"  {self.name:<14} no samples"
        return (
            f"  {self.name:<14} n={count:<6} ok={self.ok:<6} "
            f"avg={statistics.mean(self.latencies_ms):7.1f}ms  "
            f"p50={self.percentile(0.50):7.1f}ms  "
            f"p95={self.percentile(0.95):7.1f}ms  "
            f"max={max(self.latencies_ms):7.1f}ms"
        )


def sign_in(base_url: str, login_id: str, password: str) -> httpx.Client:
    client = httpx.Client(base_url=base_url, timeout=30.0)
    response = client.post("/auth/login", json={"login_id": login_id, "password": password})
    if response.status_code != 200:
        raise SystemExit(
            f"Could not sign in as {login_id} ({response.status_code}). "
            "Is the server running and the database seeded?"
        )
    return client


def hammer_reads(clients: list[httpx.Client], requests_each: int) -> dict[str, Results]:
    """Every simulated user walks the read endpoints, all at the same time."""
    results = {name: Results(name) for name, _ in READ_ENDPOINTS}

    def one_user(client: httpx.Client) -> None:
        for index in range(requests_each):
            name, path = READ_ENDPOINTS[index % len(READ_ENDPOINTS)]
            started = time.perf_counter()
            try:
                response = client.get(path)
                elapsed = (time.perf_counter() - started) * 1000
                results[name].record(response.status_code, elapsed)
            except httpx.HTTPError as error:
                results[name].errors.append(str(error))

    with ThreadPoolExecutor(max_workers=len(clients)) as pool:
        list(pool.map(one_user, clients))
    return results


def contend_for_stock(clients: list[httpx.Client]) -> Results:
    """Every user tries to reserve the same product at once.

    Correct behaviour is that nobody errors: whoever cannot be satisfied is put into
    Waiting rather than failing or overselling.
    """
    results = Results("reserve")

    # Pick a product and location that actually holds free stock, otherwise every
    # request would simply be told to wait and nothing would contend.
    rows = [
        row
        for row in clients[0].get("/stock?page_size=50").json()["items"]
        if float(row["free_to_use"]) >= len(clients)
    ]
    partners = clients[0].get("/partners?type=customer&page_size=1").json()["items"]
    if not rows or not partners:
        print("  (skipped: seed the database first)")
        return results

    row = max(rows, key=lambda item: float(item["free_to_use"]))
    product_id, location_id = row["product"]["id"], row["location"]["id"]
    partner_id = partners[0]["id"]
    print(
        f"  contending for {row['product']['sku']} at {row['location']['code']} "
        f"({row['free_to_use']} free)"
    )

    def one_user(client: httpx.Client) -> None:
        started = time.perf_counter()
        created = client.post(
            "/operations",
            json={
                "type": "delivery",
                "source_location_id": location_id,
                "partner_id": partner_id,
                "lines": [{"product_id": product_id, "quantity": "1"}],
            },
        )
        if created.status_code != 201:
            results.record(created.status_code, (time.perf_counter() - started) * 1000)
            return
        confirmed = client.post(f"/operations/{created.json()['id']}/confirm")
        results.record(confirmed.status_code, (time.perf_counter() - started) * 1000)
        if confirmed.status_code == 200:
            results.errors.append(confirmed.json()["status"])
        else:
            results.errors.append(f"http-{confirmed.status_code}")

    with ThreadPoolExecutor(max_workers=len(clients)) as pool:
        list(pool.map(one_user, clients))
    return results


def check_rate_limiting(base_url: str) -> None:
    """Confirm repeated bad logins start getting refused."""
    client = httpx.Client(base_url=base_url, timeout=10.0)
    statuses = [
        client.post(
            "/auth/login", json={"login_id": "manager1", "password": "Wr0ng!Password"}
        ).status_code
        for _ in range(8)
    ]
    client.close()
    throttled = statuses.count(429)
    verdict = "throttled" if throttled else "NOT THROTTLED"
    print(f"  8 bad logins -> {statuses.count(401)} refused, {throttled} rate limited [{verdict}]")


def write_report(
    args: argparse.Namespace,
    results: dict[str, Results],
    elapsed: float,
    contention: Results,
) -> None:
    """Save the run so the numbers can be quoted later without re-running it."""
    completed = sum(len(result.latencies_ms) for result in results.values())
    failed = sum(len(result.latencies_ms) - result.ok for result in results.values())

    lines = [
        "# StockSense - Load Test",
        "",
        f"Generated {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')} by "
        "`python -m scripts.loadtest`.",
        "",
        f"{args.users} concurrent users x {args.requests} requests against {args.base_url}.",
        "",
        "## Read endpoints",
        "",
        "| Endpoint | Requests | OK | Average | p50 | p95 | Max |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for result in results.values():
        if not result.latencies_ms:
            continue
        lines.append(
            f"| {result.name} | {len(result.latencies_ms)} | {result.ok} "
            f"| {statistics.mean(result.latencies_ms):.0f}ms "
            f"| {result.percentile(0.50):.0f}ms | {result.percentile(0.95):.0f}ms "
            f"| {max(result.latencies_ms):.0f}ms |"
        )

    lines += [
        "",
        f"**{completed} requests in {elapsed:.2f}s = {completed / elapsed:.0f} req/s, "
        f"{failed} failure(s).**",
        "",
    ]

    if contention.latencies_ms:
        outcomes = Counter(contention.errors)
        lines += [
            "## Contended reservations",
            "",
            f"{args.users} users reserving the same product at the same moment.",
            "",
            f"- outcomes: {dict(outcomes)}",
            f"- status codes: {dict(contention.statuses)}",
            f"- p95 {contention.percentile(0.95):.0f}ms",
            "",
            "Nobody errors: whoever cannot be satisfied is put into Waiting, so the lock",
            "serialises the work rather than failing requests or overselling.",
            "",
        ]

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport written to {REPORT_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--users", type=int, default=50, help="concurrent simulated users")
    parser.add_argument("--requests", type=int, default=20, help="requests per user")
    parser.add_argument(
        "--skip-rate-limit-check",
        action="store_true",
        help="leave the login limiter untouched, so the script can be re-run immediately",
    )
    args = parser.parse_args()

    print(f"Signing in {args.users} client(s)...")
    clients = [sign_in(args.base_url, *DEFAULT_LOGIN) for _ in range(args.users)]

    try:
        total = args.users * args.requests
        print(f"\nRead load: {args.users} users x {args.requests} requests = {total}")
        started = time.perf_counter()
        results = hammer_reads(clients, args.requests)
        elapsed = time.perf_counter() - started

        for result in results.values():
            print(result.summary_row())

        completed = sum(len(result.latencies_ms) for result in results.values())
        failed = sum(len(result.latencies_ms) - result.ok for result in results.values())
        print(f"\n  {completed} requests in {elapsed:.2f}s = {completed / elapsed:.0f} req/s")
        print(f"  failures: {failed}")

        print(f"\nContended reservations: {args.users} users, same product")
        contention = contend_for_stock(clients)
        if contention.latencies_ms:
            print(contention.summary_row())
            outcomes = Counter(contention.errors)
            print(f"  outcomes: {dict(outcomes)}")
            print(f"  status codes: {dict(contention.statuses)}")

        write_report(args, results, elapsed, contention)

        if args.skip_rate_limit_check:
            print("\nRate limiting check skipped")
        else:
            print("\nRate limiting")
            check_rate_limiting(args.base_url)
    finally:
        for client in clients:
            client.close()


if __name__ == "__main__":
    main()

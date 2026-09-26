"""Turn a pytest run into a QA-style test report.

Enable it with:

    python -m pytest --qa-report

The report is written to `backend/reports/`, which is git-ignored: it is generated output,
regenerated on every run, so it does not belong in version control.

Each test is listed with the area it covers, the scenario, the expected result and what
actually happened. Test names are written as sentences, so the name itself states the
expectation; the docstring, when present, adds the reason it matters.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

# Generated output stays local to the backend and is not committed.
REPORT_PATH = Path(__file__).resolve().parents[1] / "reports" / "TEST-REPORT.md"

AREA_NAMES = {
    "test_database_constraints": "Database integrity",
    "test_auth_api": "Authentication",
    "test_security": "Security",
    "test_stock_engine": "Inventory engine",
    "test_operations_api": "REST API",
    "test_concurrency": "Concurrency",
}

STATUS_LABEL = {"passed": "PASS", "failed": "FAIL", "skipped": "SKIP", "error": "ERROR"}


@dataclass
class TestCase:
    number: int
    area: str
    group: str
    scenario: str
    note: str
    status: str
    duration_ms: float
    detail: str = ""


def humanise(node_name: str) -> str:
    """`test_a_short_delivery_waits` -> `A short delivery waits`, keeping any parameters."""
    name, _, parameters = node_name.partition("[")
    sentence = name.removeprefix("test_").replace("_", " ").strip()
    sentence = sentence[:1].upper() + sentence[1:]
    if parameters:
        sentence += f" [{parameters.rstrip(']')}]"
    return sentence


def group_of(nodeid: str) -> str:
    """The test class, if the test lives in one."""
    parts = nodeid.split("::")
    if len(parts) < 3:
        return "General"
    return humanise(parts[1].removeprefix("Test"))


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--qa-report",
        action="store_true",
        default=False,
        help="write a QA-style test report to docs/TEST-REPORT.md",
    )


class QaReportPlugin:
    def __init__(self) -> None:
        self.cases: list[TestCase] = []
        self.started = datetime.now(UTC)

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item: pytest.Item, call: pytest.CallInfo):
        outcome = yield
        report = outcome.get_result()
        if report.when != "call" and not (report.when == "setup" and report.failed):
            return

        module = item.nodeid.split("/")[-1].split("::")[0].removesuffix(".py")
        docstring = (item.function.__doc__ or "").strip().split("\n")[0]

        detail = ""
        if report.failed:
            detail = str(report.longrepr).strip().split("\n")[-1][:200]

        self.cases.append(
            TestCase(
                number=len(self.cases) + 1,
                area=AREA_NAMES.get(module, module),
                group=group_of(item.nodeid),
                scenario=humanise(item.nodeid.split("::")[-1]),
                note=docstring,
                status=STATUS_LABEL.get(report.outcome, report.outcome.upper()),
                duration_ms=report.duration * 1000,
                detail=detail,
            )
        )

    def pytest_sessionfinish(self, session: pytest.Session) -> None:
        if not self.cases:
            return
        path = Path(__file__).resolve().parent / REPORT_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.render(), encoding="utf-8")
        print(f"\nQA report written to {path}")

    def render(self) -> str:
        passed = sum(1 for case in self.cases if case.status == "PASS")
        failed = sum(1 for case in self.cases if case.status in {"FAIL", "ERROR"})
        skipped = sum(1 for case in self.cases if case.status == "SKIP")
        total_ms = sum(case.duration_ms for case in self.cases)

        lines = [
            "# StockSense - Test Report",
            "",
            f"Generated {self.started.strftime('%Y-%m-%d %H:%M UTC')} by `pytest --qa-report`.",
            "",
            "Every case runs against a real PostgreSQL database. The schema under test is built",
            "by running the migrations, so the migrations are covered too.",
            "",
            "## Summary",
            "",
            "| Total | Passed | Failed | Skipped | Duration |",
            "|------:|-------:|-------:|--------:|---------:|",
            f"| {len(self.cases)} | {passed} | {failed} | {skipped} | {total_ms / 1000:.1f}s |",
            "",
        ]

        by_area: dict[str, list[TestCase]] = {}
        for case in self.cases:
            by_area.setdefault(case.area, []).append(case)

        lines += ["## Coverage by area", "", "| Area | Cases | Passed |", "|---|---:|---:|"]
        for area, cases in by_area.items():
            ok = sum(1 for case in cases if case.status == "PASS")
            lines.append(f"| {area} | {len(cases)} | {ok} |")
        lines.append("")

        for area, cases in by_area.items():
            lines += [f"## {area}", ""]
            for group in dict.fromkeys(case.group for case in cases):
                lines += [
                    f"### {group}",
                    "",
                    "| # | Scenario / expected result | Why it matters | Actual | Time |",
                    "|---|---|---|---|---:|",
                ]
                for case in (c for c in cases if c.group == group):
                    actual = (
                        case.status if case.status == "PASS" else f"{case.status}: {case.detail}"
                    )
                    note = case.note or "-"
                    lines.append(
                        f"| {case.number} | {case.scenario} | {note} | {actual} "
                        f"| {case.duration_ms:.0f}ms |"
                    )
                lines.append("")

        return "\n".join(lines)


def pytest_configure(config: pytest.Config) -> None:
    if config.getoption("--qa-report"):
        config.pluginmanager.register(QaReportPlugin(), "qa-report-plugin")

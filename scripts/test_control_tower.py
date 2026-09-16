#!/usr/bin/env python3
"""tests/ 하위 테스트 모듈(test_*.py)을 파일 단위로 완전히 독립된
서브프로세스에서 병렬 실행하고, 모듈별 결과를 표로 보고하는 컨트롤 타워.

pytest-xdist(워커 프로세스 재사용) 대신 모듈마다 새 파이썬 프로세스를 쓰는
이유: 일부 테스트 파일이 importlib.reload로 전역 모듈 상태(레이트리미터 등)를
바꾸는데, 워커를 재사용하면 이런 상태가 다른 모듈로 새어나갈 수 있다. 모듈마다
새 프로세스를 쓰면 그런 오염과 무관하게 안전하다. 대신 매 모듈마다 파이썬
인터프리터/앱 임포트 비용이 반복되므로, 코어 수가 적은 환경에서는 전체 실행
시간이 단일 프로세스 실행보다 더 걸릴 수도 있다.

사용법:
    python scripts/test_control_tower.py                # 전체 모듈
    python scripts/test_control_tower.py backend analyze # 경로에 포함된 모듈만
    python scripts/test_control_tower.py --workers 8
"""

from __future__ import annotations

import argparse
import concurrent.futures
import os
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = ROOT / "tests"

_COLOR = sys.stdout.isatty()
_GREEN = "\033[32m" if _COLOR else ""
_RED = "\033[31m" if _COLOR else ""
_RESET = "\033[0m" if _COLOR else ""


@dataclass
class ModuleResult:
    module: str
    returncode: int
    duration: float
    stdout: str
    stderr: str
    tests: int = 0
    failures: int = 0
    errors: int = 0
    skipped: int = 0
    xml_ok: bool = False

    @property
    def passed(self) -> bool:
        return self.returncode == 0

    @property
    def counts_label(self) -> str:
        if not self.xml_ok:
            return "(junit-xml 없음)"
        parts = [f"{self.tests}개"]
        if self.failures:
            parts.append(f"실패 {self.failures}")
        if self.errors:
            parts.append(f"에러 {self.errors}")
        if self.skipped:
            parts.append(f"스킵 {self.skipped}")
        return " ".join(parts)


def discover_modules(patterns: list[str]) -> list[Path]:
    modules = sorted(TESTS_DIR.rglob("test_*.py"))
    if not patterns:
        return modules
    return [m for m in modules if any(p in m.as_posix() for p in patterns)]


def run_module(module: Path, xml_dir: Path) -> ModuleResult:
    rel = module.relative_to(ROOT).as_posix()
    xml_path = xml_dir / (rel.replace("/", "__") + ".xml")

    start = time.monotonic()
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            str(module),
            f"--junit-xml={xml_path}",
            "-p",
            "no:cacheprovider",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    duration = time.monotonic() - start

    result = ModuleResult(
        module=rel,
        returncode=proc.returncode,
        duration=duration,
        stdout=proc.stdout,
        stderr=proc.stderr,
    )

    if xml_path.exists():
        try:
            root_el = ET.parse(xml_path).getroot()
            suite = root_el if root_el.tag == "testsuite" else root_el.find("testsuite")
            if suite is not None:
                result.tests = int(suite.get("tests", 0))
                result.failures = int(suite.get("failures", 0))
                result.errors = int(suite.get("errors", 0))
                result.skipped = int(suite.get("skipped", 0))
                result.xml_ok = True
        except ET.ParseError:
            pass

    return result


def format_table(results: list[ModuleResult]) -> str:
    module_width = max((len(r.module) for r in results), default=6)
    header = f"{'상태':<4} {'모듈':<{module_width}} {'결과':<24} {'소요(s)':>8}"
    lines = [header, "-" * len(header)]
    for r in results:
        status = f"{_GREEN}PASS{_RESET}" if r.passed else f"{_RED}FAIL{_RESET}"
        lines.append(
            f"{status:<{4 + len(_GREEN) + len(_RESET)}} "
            f"{r.module:<{module_width}} {r.counts_label:<24} {r.duration:>8.2f}"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="tests/ 모듈을 파일 단위 서브프로세스로 병렬 실행하는 컨트롤 타워"
    )
    parser.add_argument(
        "patterns",
        nargs="*",
        help="모듈 경로에 포함될 부분 문자열로 필터링 (예: backend analyze)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=os.cpu_count() or 4,
        help="동시 실행할 워커 수 (기본: CPU 코어 수)",
    )
    args = parser.parse_args()

    modules = discover_modules(args.patterns)
    if not modules:
        print("실행할 테스트 모듈을 찾지 못했어.")
        return 1

    print(f"[컨트롤 타워] {len(modules)}개 모듈을 워커 {args.workers}개로 병렬 실행한다...\n")

    wall_start = time.monotonic()
    results: list[ModuleResult] = []
    with tempfile.TemporaryDirectory(prefix="control_tower_junit_") as tmp:
        xml_dir = Path(tmp)
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = [executor.submit(run_module, m, xml_dir) for m in modules]
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())
    wall_time = time.monotonic() - wall_start

    results.sort(key=lambda r: r.module)

    print(format_table(results))

    serial_time = sum(r.duration for r in results)
    total_tests = sum(r.tests for r in results)
    total_failures = sum(r.failures + r.errors for r in results)
    failed_modules = [r for r in results if not r.passed]

    print()
    print(f"총 {len(results)}개 모듈 / {total_tests}개 테스트 — 실패 {total_failures}개")
    if wall_time > 0:
        speedup = serial_time / wall_time
        print(f"병렬 실행 시간: {wall_time:.2f}s (직렬 환산 {serial_time:.2f}s, {speedup:.1f}배)")

    if failed_modules:
        print(f"\n=== 실패한 모듈 상세 ({len(failed_modules)}개) ===")
        for r in failed_modules:
            print(f"\n--- {r.module} (returncode={r.returncode}) ---")
            tail = "\n".join(r.stdout.strip().splitlines()[-40:])
            print(tail)
            if r.stderr.strip():
                print("[stderr]")
                print(r.stderr.strip()[-2000:])

    return 1 if failed_modules else 0


if __name__ == "__main__":
    raise SystemExit(main())

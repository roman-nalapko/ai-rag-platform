import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

executed_lines: dict[str, set[int]] = {}


def trace_lines(frame, event, arg):  # type: ignore[no-untyped-def]
    if event == "line":
        filename = frame.f_code.co_filename
        if "/app/" in filename and not filename.endswith("_test.py"):
            norm_path = os.path.relpath(filename, str(ROOT))
            if norm_path not in executed_lines:
                executed_lines[norm_path] = set()
            executed_lines[norm_path].add(frame.f_lineno)
    return trace_lines


def get_executable_lines(file_path: Path) -> set[int]:
    """Find non-empty, non-comment lines."""
    executable = set()
    lines = file_path.read_text(encoding="utf-8").splitlines()
    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if (
            stripped
            and not stripped.startswith("#")
            and not stripped.startswith('"""')
            and not stripped.startswith("'''")
        ):
            executable.add(idx)
    return executable


def main() -> None:
    print("=" * 80)
    print("📊 Estimating Source-Line Execution via Built-in Tracer")
    print("=" * 80)

    sys.settrace(trace_lines)
    exit_code = pytest.main(["-q", "--no-header", "tests"])
    sys.settrace(None)

    app_dir = ROOT / "app"
    app_files = sorted(list(app_dir.rglob("*.py")))

    total_exec_lines = 0
    total_hit_lines = 0

    print(f"\n{'Module':<45} {'Lines':<10} {'Hits':<10} {'Coverage':<10}")
    print("-" * 75)

    for py_file in app_files:
        if py_file.name == "__init__.py" and py_file.stat().st_size == 0:
            continue
        rel_path = os.path.relpath(py_file, str(ROOT))
        exec_lines = get_executable_lines(py_file)
        hits = executed_lines.get(rel_path, set()).intersection(exec_lines)

        count_exec = len(exec_lines)
        count_hits = len(hits)
        pct = (count_hits / count_exec * 100) if count_exec > 0 else 100.0

        total_exec_lines += count_exec
        total_hit_lines += count_hits

        print(f"{rel_path:<45} {count_exec:<10} {count_hits:<10} {pct:>6.1f}%")

    total_pct = (
        (total_hit_lines / total_exec_lines * 100) if total_exec_lines > 0 else 100.0
    )
    print("=" * 75)
    print(
        f"{'TOTAL APP CODEBASE':<45} {total_exec_lines:<10} {total_hit_lines:<10} {total_pct:>6.1f}%\n"
    )
    print(f"Pytest Exit Code: {exit_code}")


if __name__ == "__main__":
    main()

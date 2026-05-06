#!/usr/bin/env python3
"""Generate quality matrix data from data/triz_matrix.xls.

This is a one-off helper script that parses the 39x39 contradiction matrix from
the legacy XLS file and rewrites only the MATRIX literal block in:
    src/smartriz/data_generation/quality/matrix.py
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import xlrd

SIZE = 39
PRINCIPLE_MIN = 1
PRINCIPLE_MAX = 40

MATRIX_START = "# fmt: off\nMATRIX: dict[int, dict[int, list[int]]] = {\n"
MATRIX_BLOCK_RE = re.compile(
    r"# fmt: off\nMATRIX: dict\[int, dict\[int, list\[int\]\]\] = \{\n.*?\n\}\n# fmt: on",
    re.DOTALL,
)


def _to_header_id(value: object) -> int | None:
    """Convert a cell value into a parameter id if possible."""
    if isinstance(value, float):
        ivalue = int(value)
        if value == ivalue and 1 <= ivalue <= SIZE:
            return ivalue
        return None
    if isinstance(value, int):
        return value if 1 <= value <= SIZE else None

    text = str(value).strip()
    if not text:
        return None

    # Supports values like "12", "12. Parameter", "Parameter (#12)".
    matches = re.findall(r"\d+", text)
    if not matches:
        return None
    number = int(matches[0])
    return number if 1 <= number <= SIZE else None


def _is_expected_sequence(values: list[object]) -> bool:
    return [_to_header_id(v) for v in values] == list(range(1, SIZE + 1))


def _find_layout(sheet: xlrd.sheet.Sheet) -> tuple[int, int, int]:
    """Find data layout in worksheet.

    Returns (data_row_start, data_col_start, improving_id_col) where:
    - worsening ids are on row (data_row_start - 1), columns data_col_start..+38
    - improving ids are in column improving_id_col, rows data_row_start..+38
    """
    max_row = sheet.nrows - SIZE
    max_col = sheet.ncols - SIZE

    # Find worsening header sequence 1..39 on one row.
    for header_row in range(max_row):
        for data_col_start in range(max_col):
            values = [sheet.cell_value(header_row, data_col_start + i) for i in range(SIZE)]
            if not _is_expected_sequence(values):
                continue

            data_row_start = header_row + 1
            if data_row_start + SIZE > sheet.nrows:
                continue

            candidate_cols = range(max(0, data_col_start - 3), data_col_start + 1)
            for improving_col in candidate_cols:
                improving_values = [
                    sheet.cell_value(data_row_start + i, improving_col) for i in range(SIZE)
                ]
                if _is_expected_sequence(improving_values):
                    return data_row_start, data_col_start, improving_col

    raise RuntimeError("Could not detect 39x39 matrix layout in worksheet")


def _parse_principles(value: object) -> list[int]:
    if value is None:
        return []
    if isinstance(value, float):
        ivalue = int(value)
        if value == ivalue and PRINCIPLE_MIN <= ivalue <= PRINCIPLE_MAX:
            return [ivalue]
        return []
    if isinstance(value, int):
        return [value] if PRINCIPLE_MIN <= value <= PRINCIPLE_MAX else []

    text = str(value).strip()
    if not text:
        return []

    items = []
    for token in re.findall(r"\d+", text):
        number = int(token)
        if PRINCIPLE_MIN <= number <= PRINCIPLE_MAX:
            items.append(number)
    return sorted(set(items))


def extract_matrix(xls_path: Path, sheet_name: str | None = None) -> dict[int, dict[int, list[int]]]:
    workbook = xlrd.open_workbook(xls_path.as_posix())
    if sheet_name:
        sheet = workbook.sheet_by_name(sheet_name)
    else:
        sheet = workbook.sheet_by_index(0)

    data_row_start, data_col_start, improving_col = _find_layout(sheet)

    matrix: dict[int, dict[int, list[int]]] = {}
    worsening_headers = [
        _to_header_id(sheet.cell_value(data_row_start - 1, data_col_start + j)) for j in range(SIZE)
    ]
    if worsening_headers != list(range(1, SIZE + 1)):
        raise RuntimeError("Detected worsening headers are invalid")

    for i in range(SIZE):
        improving_id = _to_header_id(sheet.cell_value(data_row_start + i, improving_col))
        if improving_id is None:
            raise RuntimeError(f"Invalid improving header at row {data_row_start + i}")
        row_data: dict[int, list[int]] = {}
        for j in range(SIZE):
            worsening_id = worsening_headers[j]
            assert worsening_id is not None
            row_data[worsening_id] = _parse_principles(
                sheet.cell_value(data_row_start + i, data_col_start + j)
            )
        matrix[improving_id] = row_data

    # Keep diagonal deterministic and aligned with current behavior.
    for idx in range(1, SIZE + 1):
        matrix[idx][idx] = []
    return matrix


def validate_matrix(matrix: dict[int, dict[int, list[int]]]) -> None:
    expected = set(range(1, SIZE + 1))
    if set(matrix.keys()) != expected:
        missing = sorted(expected - set(matrix.keys()))
        raise RuntimeError(f"Missing improving keys: {missing}")

    for improving_id in range(1, SIZE + 1):
        row = matrix[improving_id]
        if set(row.keys()) != expected:
            missing = sorted(expected - set(row.keys()))
            raise RuntimeError(f"Missing worsening keys in row {improving_id}: {missing}")
        for worsening_id, principles in row.items():
            bad = [p for p in principles if not (PRINCIPLE_MIN <= p <= PRINCIPLE_MAX)]
            if bad:
                raise RuntimeError(
                    f"Out-of-range principles at ({improving_id}, {worsening_id}): {bad}"
                )


def _format_row_entries(entries: list[str], indent: str = "        ", width: int = 100) -> list[str]:
    lines: list[str] = []
    current = indent
    for entry in entries:
        token = f"{entry}, "
        if len(current) + len(token) > width:
            lines.append(current.rstrip())
            current = indent + token
        else:
            current += token
    if current.strip():
        lines.append(current.rstrip())
    return lines


def render_matrix_block(matrix: dict[int, dict[int, list[int]]]) -> str:
    lines = [MATRIX_START]
    for improving_id in range(1, SIZE + 1):
        lines.append(f"    {improving_id}: {{")
        row_entries: list[str] = []
        for worsening_id in range(1, SIZE + 1):
            values = ",".join(str(v) for v in matrix[improving_id][worsening_id])
            row_entries.append(f"{worsening_id}: [{values}]")
        lines.extend(_format_row_entries(row_entries))
        lines.append("    },")
    lines.append("}")
    lines.append("# fmt: on")
    return "\n".join(lines)


def rewrite_matrix_file(matrix_file: Path, rendered_block: str) -> bool:
    original = matrix_file.read_text(encoding="utf-8")
    if not MATRIX_BLOCK_RE.search(original):
        raise RuntimeError("MATRIX block markers not found in matrix.py")

    updated = MATRIX_BLOCK_RE.sub(rendered_block, original, count=1)
    changed = updated != original
    if changed:
        matrix_file.write_text(updated, encoding="utf-8")
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--xls",
        default="data/triz_matrix.xls",
        help="Path to source XLS matrix file",
    )
    parser.add_argument(
        "--matrix-file",
        default="src/smartriz/data_generation/quality/matrix.py",
        help="Path to target matrix.py file",
    )
    parser.add_argument(
        "--sheet-name",
        default=None,
        help="Optional sheet name. Defaults to first sheet.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate generation and exit non-zero if matrix.py is outdated.",
    )
    args = parser.parse_args()

    xls_path = Path(args.xls)
    matrix_file = Path(args.matrix_file)
    matrix = extract_matrix(xls_path=xls_path, sheet_name=args.sheet_name)
    validate_matrix(matrix)
    rendered = render_matrix_block(matrix)

    original = matrix_file.read_text(encoding="utf-8")
    updated = MATRIX_BLOCK_RE.sub(rendered, original, count=1)
    if updated == original:
        print("matrix.py already up to date.")
        return 0

    if args.check:
        print("matrix.py is out of date. Run scripts/generate_matrix_from_xls.py to update.")
        return 1

    matrix_file.write_text(updated, encoding="utf-8")
    print(f"Updated {matrix_file} from {xls_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

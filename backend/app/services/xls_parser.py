"""HDFC .xls parser using xlrd for legacy CDFV2 format."""

import logging
from typing import Generator

import xlrd

from app.core.constants import EXCEL_BATCH_SIZE

logger = logging.getLogger(__name__)

# CDFV2 magic bytes
CDFV2_MAGIC = b"\xd0\xcf\x11\xe0"


def is_xls_file(file_path: str) -> bool:
    """Detect legacy .xls format via CDFV2 magic bytes."""
    try:
        with open(file_path, "rb") as f:
            return f.read(4) == CDFV2_MAGIC
    except Exception:
        return False


class XlsParser:
    """Parse HDFC legacy .xls bank statement using xlrd.

    Layout:
    - Rows 0-3: metadata (skip)
    - Row 4: headers (DATE|BRANCH|DESCRIPTION|REFERENCE NO|VALUE DATE|DEBITS|CREDITS|BALANCE)
    - Rows 5..N-4: data
    - Last 4 rows: summary (skip)
    """

    EXPECTED_HEADERS = {"DATE", "BRANCH", "DESCRIPTION", "REFERENCE NO", "VALUE DATE", "DEBITS", "CREDITS", "BALANCE"}

    @staticmethod
    def extract_bank_id(description: str) -> str | None:
        """Extract bank_id: description.split(' - ')[3].strip().upper()"""
        try:
            parts = str(description).split(" - ")
            if len(parts) > 3:
                return parts[3].strip().upper()
        except Exception:
            pass
        return None

    @staticmethod
    def parse_amount(value) -> float:
        if value is None:
            return 0.0
        try:
            return float(str(value).replace(",", ""))
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def extract_customer(description: str) -> str:
        parts = str(description).split(" - ")
        if len(parts) > 5:
            return parts[-1].strip()
        return "N/A"

    def parse(self, file_path: str) -> Generator[list[dict], None, None]:
        """Yield batches of bank entry dicts from .xls file."""
        wb = xlrd.open_workbook(file_path)
        ws = wb.sheet_by_index(0)

        # Find header row
        header_row_idx = None
        col_map: dict[str, int] = {}

        for row_idx in range(min(10, ws.nrows)):
            values = [str(ws.cell_value(row_idx, c)).strip().upper() for c in range(ws.ncols)]
            if "DATE" in values:
                header_row_idx = row_idx
                for col_idx, val in enumerate(values):
                    if val:
                        col_map[val] = col_idx
                break

        if header_row_idx is None:
            raise ValueError("Could not find header row in .xls file")

        # Data rows: skip header, skip last 4 summary rows
        data_start = header_row_idx + 1
        data_end = ws.nrows - 4

        batch: list[dict] = []

        for row_idx in range(data_start, max(data_start, data_end)):
            desc = str(ws.cell_value(row_idx, col_map.get("DESCRIPTION", 0)) or "")
            bank_id = self.extract_bank_id(desc)
            if bank_id is None:
                continue

            debit = self.parse_amount(
                ws.cell_value(row_idx, col_map["DEBITS"]) if "DEBITS" in col_map else None
            )
            credit = self.parse_amount(
                ws.cell_value(row_idx, col_map["CREDITS"]) if "CREDITS" in col_map else None
            )

            entry = {
                "bank_id": bank_id,
                "date": str(ws.cell_value(row_idx, col_map.get("DATE", 0)) or ""),
                "description": desc,
                "debit_amount": debit,
                "credit_amount": credit,
                "branch": str(ws.cell_value(row_idx, col_map.get("BRANCH", 0)) or "") if "BRANCH" in col_map else "",
                "reference_no": str(ws.cell_value(row_idx, col_map.get("REFERENCE NO", 0)) or "") if "REFERENCE NO" in col_map else "",
                "customer_name": self.extract_customer(desc),
            }
            batch.append(entry)
            if len(batch) >= EXCEL_BATCH_SIZE:
                yield batch
                batch = []

        if batch:
            yield batch

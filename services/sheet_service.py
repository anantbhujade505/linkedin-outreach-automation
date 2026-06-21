from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

import gspread

from models.schemas import Settings, SheetTarget
from utils.validators import is_linkedin_profile_url


class SheetService:
    REQUIRED_HEADERS = [
        "linkedin_url",
        "first_name",
        "company",
        "notes",
        "status",
        "sent_timestamp",
        "accepted_timestamp",
        "withdrawn_timestamp",
        "generated_note",
        "generated_comment",
        "error_message",
    ]

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._worksheet = None
        self._local_headers: list[str] | None = None

    def worksheet(self):
        if self._worksheet is None:
            self.settings.require_sheet_credentials()
            client = gspread.service_account(filename=self.settings.google_service_account_file)
            sheet = client.open_by_key(self.settings.google_sheet_id)
            self._worksheet = sheet.worksheet(self.settings.google_worksheet_name)
            self.ensure_headers()
        return self._worksheet

    @property
    def use_local_csv(self) -> bool:
        return not self.settings.google_sheet_id

    def ensure_headers(self) -> None:
        worksheet = self._worksheet
        headers = worksheet.row_values(1)
        if not headers:
            worksheet.append_row(self.REQUIRED_HEADERS)
            return
        missing = [header for header in self.REQUIRED_HEADERS if header not in headers]
        if missing:
            worksheet.update(range_name="1:1", values=[headers + missing])

    def read_targets(self, max_rows: int) -> list[SheetTarget]:
        if self.use_local_csv:
            return self._read_local_targets(max_rows)
        rows = self.worksheet().get_all_records()
        targets: list[SheetTarget] = []
        for index, row in enumerate(rows, start=2):
            url = str(row.get("linkedin_url", "")).strip()
            status = str(row.get("status", "")).strip().lower()
            if not url or status in {"request_sent", "accepted", "withdrawn", "skipped"}:
                continue
            if not is_linkedin_profile_url(url):
                self.update_row(index, {"status": "failed", "error_message": "Invalid LinkedIn profile URL"})
                continue
            targets.append(
                SheetTarget(
                    row_number=index,
                    linkedin_url=url,
                    first_name=str(row.get("first_name") or "").strip() or None,
                    company=str(row.get("company") or "").strip() or None,
                    notes=str(row.get("notes") or "").strip() or None,
                    status=status or None,
                )
            )
            if len(targets) >= max_rows:
                break
        return targets

    def update_row(self, row_number: int, values: dict[str, Any]) -> None:
        if self.use_local_csv:
            self._update_local_row(row_number, values)
            return
        worksheet = self.worksheet()
        headers = worksheet.row_values(1)
        updates = []
        for key, value in values.items():
            if key not in headers:
                continue
            col = headers.index(key) + 1
            if isinstance(value, datetime):
                value = value.isoformat()
            updates.append({"range": gspread.utils.rowcol_to_a1(row_number, col), "values": [[value or ""]]})
        if updates:
            worksheet.batch_update(updates)

    def _read_local_targets(self, max_rows: int) -> list[SheetTarget]:
        path = Path(self.settings.local_targets_csv)
        if not path.exists():
            raise ValueError(f"Local targets CSV not found: {path}")
        targets: list[SheetTarget] = []
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            self._local_headers = reader.fieldnames or self.REQUIRED_HEADERS
            for index, row in enumerate(reader, start=2):
                url = str(row.get("linkedin_url", "")).strip()
                status = str(row.get("status", "")).strip().lower()
                if not url or status in {"request_sent", "accepted", "withdrawn", "skipped"}:
                    continue
                if not is_linkedin_profile_url(url):
                    continue
                targets.append(
                    SheetTarget(
                        row_number=index,
                        linkedin_url=url,
                        first_name=str(row.get("first_name") or "").strip() or None,
                        company=str(row.get("company") or "").strip() or None,
                        notes=str(row.get("notes") or "").strip() or None,
                        status=status or None,
                    )
                )
                if len(targets) >= max_rows:
                    break
        return targets

    def _update_local_row(self, row_number: int, values: dict[str, Any]) -> None:
        path = Path(self.settings.local_targets_csv)
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
            headers = list(rows[0].keys()) if rows else self.REQUIRED_HEADERS
        for header in self.REQUIRED_HEADERS:
            if header not in headers:
                headers.append(header)
        index = row_number - 2
        if index < 0 or index >= len(rows):
            return
        for key, value in values.items():
            if key in headers:
                rows[index][key] = value.isoformat() if isinstance(value, datetime) else str(value or "")
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)

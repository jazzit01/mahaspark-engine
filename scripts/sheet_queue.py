"""Google Sheets job queue (unchanged semantics from the previous engine).

Columns A-M are exactly the legacy layout so existing rows keep working; N-P are appended:

 A Status  B Raw_News_Input  C Badge  D Headline  E Hook_Pill  F Bullets  G YT_Title  H YT_Desc
 I YT_Tags  J IG_Caption  K Image_Path  L Created_At  M Error_Log  | N Source_URL  O Visual_Theme
 P Summary_5W1H

Status flow: PENDING -> PROCESSING -> DONE | ERROR | REJECTED. A run that finds no AI provider puts
the row back to PENDING so it is retried (ERROR rows are never retried).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from config import ROOT

IST = timezone(timedelta(hours=5, minutes=30))
DEFAULT_SHEET_ID = "1Hoq6Qshq7RZNh3cV7AmmUqVbF1ULnwXqf1uaU4_FlC4"
CREDS_FILE = str(ROOT / "credentials.json")

COL_STATUS, COL_RAW, COL_ERROR_LOG = 1, 2, 13
COL_SOURCE_URL, COL_THEME, COL_SUMMARY = 14, 15, 16
TOTAL_COLUMNS = 16
EXTRA_HEADERS = {COL_SOURCE_URL: "Source_URL", COL_THEME: "Visual_Theme", COL_SUMMARY: "Summary_5W1H"}

PENDING, PROCESSING, DONE, ERROR, REJECTED = "PENDING", "PROCESSING", "DONE", "ERROR", "REJECTED"


@dataclass
class PendingRow:
    index: int  # 1-based sheet row
    raw_input: str
    source_url: str


def now_ist() -> str:
    return datetime.now(IST).strftime("%d-%m-%Y %I:%M:%S %p")


def summary_5w1h_text(five: dict) -> str:
    labels = [("what", "काय"), ("when", "केव्हा"), ("who", "कोण"), ("where", "कुठे"), ("why", "का"), ("how", "कसे")]
    return "\n".join(f"{marathi}: {five.get(key, '—')}" for key, marathi in labels)


class SheetQueue:
    def __init__(self, sheet):
        self.sheet = sheet

    @classmethod
    def connect(cls) -> "SheetQueue":
        import gspread  # lazy: only the real pipeline needs it

        client = gspread.service_account(filename=CREDS_FILE)
        sheet = client.open_by_key(os.getenv("GOOGLE_SHEET_ID") or DEFAULT_SHEET_ID).sheet1
        queue = cls(sheet)
        queue.ensure_columns()
        return queue

    # ----- setup ------------------------------------------------------------------------------

    def ensure_columns(self) -> None:
        """Add the N-P columns and their headers when they are not there yet."""
        if getattr(self.sheet, "col_count", TOTAL_COLUMNS) < TOTAL_COLUMNS:
            self.sheet.add_cols(TOTAL_COLUMNS - self.sheet.col_count)
        header = self.sheet.row_values(1)
        for col, name in EXTRA_HEADERS.items():
            if len(header) < col or not str(header[col - 1]).strip():
                self.sheet.update_cell(1, col, name)

    # ----- reading ----------------------------------------------------------------------------

    def _rows(self) -> list[list[str]]:
        return self.sheet.get_all_values()

    def known_keys(self) -> set[str]:
        """Lower-cased raw inputs and source URLs already queued (for de-duplication)."""
        keys: set[str] = set()
        for row in self._rows()[1:]:
            if len(row) >= COL_RAW and row[COL_RAW - 1].strip():
                keys.add(row[COL_RAW - 1].strip().lower())
            if len(row) >= COL_SOURCE_URL and row[COL_SOURCE_URL - 1].strip():
                keys.add(row[COL_SOURCE_URL - 1].strip().lower())
        return keys

    def pending_rows(self) -> list[PendingRow]:
        rows = self._rows()
        if len(rows) < 2:
            return []
        out = []
        for i, row in enumerate(rows[1:], start=2):
            status = row[COL_STATUS - 1].strip().upper() if len(row) >= COL_STATUS else ""
            raw = row[COL_RAW - 1].strip() if len(row) >= COL_RAW else ""
            url = row[COL_SOURCE_URL - 1].strip() if len(row) >= COL_SOURCE_URL else ""
            if status == PENDING and raw:
                out.append(PendingRow(i, raw, url))
        return out

    # ----- writing ----------------------------------------------------------------------------

    def append_pending(self, raw_input: str, source_url: str) -> None:
        row = [""] * TOTAL_COLUMNS
        row[COL_STATUS - 1] = PENDING
        row[COL_RAW - 1] = raw_input
        row[12 - 1] = now_ist()  # Created_At (column L); internal only, never shown on screen
        row[COL_SOURCE_URL - 1] = source_url
        self.sheet.append_row(row)

    def set_status(self, row: int, status: str, note: str | None = None) -> None:
        self.sheet.update_cell(row, COL_STATUS, status)
        if note is not None:
            self.sheet.update_cell(row, COL_ERROR_LOG, note)

    def write_story(self, row: int, story: dict) -> None:
        """Store the generated copy in columns C-K and N-P for later reference."""
        scenes = story.get("scenes", [])
        caption = f"{story.get('social_caption', '')}\n\n{story.get('hashtags', '')}".strip()
        content = [
            story.get("category", ""),
            scenes[0]["headline"] if scenes else "",
            scenes[0]["tts_text"] if scenes else "",
            json.dumps([{"headline": s["headline"], "description": s["description"]} for s in scenes], ensure_ascii=False),
            story.get("social_title", ""),
            story.get("social_caption", ""),
            story.get("hashtags", ""),
            caption,
            "remotion",
        ]
        self.sheet.update(range_name=f"C{row}:K{row}", values=[content])
        self.sheet.update(
            range_name=f"N{row}:P{row}",
            values=[
                [
                    story.get("source", {}).get("url", ""),
                    story.get("visual_theme", ""),
                    summary_5w1h_text(story.get("five_w_one_h", {})),
                ]
            ],
        )

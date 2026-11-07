"""iCalendar export, for people who'd rather not connect Google."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

DEFAULT_LENGTH = timedelta(minutes=30)


@dataclass(frozen=True)
class IcsEvent:
    uid: str
    title: str
    starts_at: datetime
    ends_at: datetime | None = None


def _escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r", "")
        .replace("\n", "\\n")
    )


def _stamp(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _fold(line: str) -> list[str]:
    """RFC 5545 limits lines to 75 octets, with continuations starting with a space."""
    pieces: list[str] = []
    while len(line.encode()) > 75:
        cut = 75
        while len(line[:cut].encode()) > 75:
            cut -= 1
        pieces.append(line[:cut])
        line = " " + line[cut:]
    pieces.append(line)
    return pieces


def build_ics(events: Iterable[IcsEvent], now: datetime) -> str:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Recall//Tasks//EN", "CALSCALE:GREGORIAN"]
    for event in events:
        lines += [
            "BEGIN:VEVENT",
            f"UID:{event.uid}@recall",
            f"DTSTAMP:{_stamp(now)}",
            f"DTSTART:{_stamp(event.starts_at)}",
            f"DTEND:{_stamp(event.ends_at or event.starts_at + DEFAULT_LENGTH)}",
            f"SUMMARY:{_escape(event.title)}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(part for line in lines for part in _fold(line)) + "\r\n"

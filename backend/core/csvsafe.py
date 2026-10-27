"""CSV export that cannot be turned into a spreadsheet formula.

A cell that begins with ``=``, ``+``, ``-`` or ``@`` (or a tab or carriage return) is
run as a formula by Excel and LibreOffice when the file is opened. Village names,
vehicle numbers and notes are typed by officers, so every export goes through this
module, which prefixes such a cell with an apostrophe: the spreadsheet then shows the
text as typed and runs nothing (OWASP "CSV injection").

A value that is a plain number, such as a negative variance ``-3.25``, is left as it is,
so numeric columns stay numeric.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Iterable
from typing import Any, TextIO

TRIGGERS = ("=", "+", "-", "@", "\t", "\r")
_PLAIN_NUMBER = re.compile(r"^[+-]?\d+(\.\d+)?$")


def safe_cell(value: Any) -> Any:
    """The value to write: text that could start a formula is neutralised."""
    if value is None:
        return ""
    if not isinstance(value, str):
        return value
    if value.startswith(TRIGGERS) and not _PLAIN_NUMBER.match(value):
        return "'" + value
    return value


class SafeWriter:
    """``csv.writer`` with every cell passed through :func:`safe_cell`."""

    def __init__(self, stream: TextIO, *, lineterminator: str = "\r\n") -> None:
        self._writer = csv.writer(stream, lineterminator=lineterminator)

    def writerow(self, row: Iterable[Any]) -> None:
        self._writer.writerow([safe_cell(v) for v in row])

    def writerows(self, rows: Iterable[Iterable[Any]]) -> None:
        for row in rows:
            self.writerow(row)


def writer(stream: TextIO, *, lineterminator: str = "\r\n") -> SafeWriter:
    return SafeWriter(stream, lineterminator=lineterminator)


__all__ = ["TRIGGERS", "SafeWriter", "safe_cell", "writer"]

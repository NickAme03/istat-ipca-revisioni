#!/usr/bin/env python3
"""Scarica e normalizza una singola serie mensile IPCA da ISTAT."""

from __future__ import annotations

import csv
import io
import os
import sys
import tempfile
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SOURCE_URL = (
    "https://esploradati.istat.it/SDMXWS/rest/data/"
    "168_761/M.IT.87.4.00"
)
OUTPUT_PATH = Path(__file__).resolve().parent / "data" / "ipca.csv"
ACCEPT = "application/vnd.sdmx.data+csv;version=1.0.0"
EXPECTED_DIMENSIONS = {
    "FREQ": "M",
    "REF_AREA": "IT",
    "DATA_TYPE": "87",
    "MEASURE": "4",
    "ECOICOP_2": "00",
}
REQUIRED_COLUMNS = {
    *EXPECTED_DIMENSIONS,
    "TIME_PERIOD",
    "OBS_VALUE",
    "OBS_STATUS",
}


@dataclass
class IstatRateLimiter:
    """Mantiene almeno 12,5 secondi tra due query nello stesso processo."""

    minimum_interval_seconds: float = 12.5
    _last_query_started: float | None = None

    def wait(self) -> None:
        if self._last_query_started is not None:
            elapsed = time.monotonic() - self._last_query_started
            remaining = self.minimum_interval_seconds - elapsed
            if remaining > 0:
                time.sleep(remaining)
        self._last_query_started = time.monotonic()


def fetch_csv(rate_limiter: IstatRateLimiter, attempts: int = 3) -> str:
    request = Request(
        SOURCE_URL,
        headers={
            "Accept": ACCEPT,
            "User-Agent": "dataset-vivo-ipca/0.1",
        },
    )

    for attempt in range(1, attempts + 1):
        rate_limiter.wait()
        try:
            with urlopen(request, timeout=60) as response:
                return response.read().decode("utf-8-sig")
        except HTTPError as error:
            if error.code < 500 or attempt == attempts:
                raise RuntimeError(f"ISTAT ha risposto HTTP {error.code}") from error
        except (TimeoutError, URLError) as error:
            if attempt == attempts:
                raise RuntimeError(f"Query ISTAT fallita: {error}") from error

    raise RuntimeError("Query ISTAT fallita senza una risposta")


def canonical_decimal(value: str) -> str:
    try:
        number = Decimal(value)
    except InvalidOperation as error:
        raise ValueError(f"Valore non numerico: {value!r}") from error

    rendered = format(number, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def normalize(source: str) -> bytes:
    reader = csv.DictReader(io.StringIO(source, newline=""))
    if reader.fieldnames is None:
        raise ValueError("La risposta ISTAT non contiene un'intestazione CSV")

    missing = REQUIRED_COLUMNS.difference(reader.fieldnames)
    if missing:
        raise ValueError(f"Colonne ISTAT mancanti: {', '.join(sorted(missing))}")

    observations: dict[str, tuple[str, str]] = {}
    for line_number, row in enumerate(reader, start=2):
        for column, expected in EXPECTED_DIMENSIONS.items():
            if row[column] != expected:
                raise ValueError(
                    f"Riga {line_number}: {column}={row[column]!r}, atteso {expected!r}"
                )

        period = row["TIME_PERIOD"].strip()
        if len(period) != 7 or period[4] != "-" or not period.replace("-", "").isdigit():
            raise ValueError(f"Riga {line_number}: periodo non valido {period!r}")

        value = canonical_decimal(row["OBS_VALUE"].strip())
        status = row["OBS_STATUS"].strip()
        observation = (value, status)
        previous = observations.get(period)
        if previous is not None and previous != observation:
            raise ValueError(f"Osservazioni in conflitto per {period}")
        observations[period] = observation

    if not observations:
        raise ValueError("La risposta ISTAT non contiene osservazioni")

    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["period", "index_2025_100", "status"])
    for period in sorted(observations):
        value, status = observations[period]
        writer.writerow([period, value, status])
    return output.getvalue().encode("utf-8")


def write_only_if_changed(path: Path, content: bytes) -> bool:
    if path.exists() and path.read_bytes() == content:
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(file_descriptor, "wb") as temporary_file:
            temporary_file.write(content)
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise
    return True


def main() -> int:
    try:
        source = fetch_csv(IstatRateLimiter())
        normalized = normalize(source)
        changed = write_only_if_changed(OUTPUT_PATH, normalized)
    except (RuntimeError, ValueError) as error:
        print(f"errore: {error}", file=sys.stderr)
        return 1

    state = "aggiornato" if changed else "invariato"
    rows = normalized.count(b"\n") - 1
    print(f"{OUTPUT_PATH}: {state}, {rows} osservazioni")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

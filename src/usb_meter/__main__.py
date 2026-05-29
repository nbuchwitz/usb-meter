# SPDX-FileCopyrightText: 2026 Nicolai Buchwitz <n.buchwitz@kunbus.com>
#
# SPDX-License-Identifier: LGPL-2.1-or-later

"""CLI: read ADC samples from a connected KM003C."""

from __future__ import annotations

import argparse
import csv
import dataclasses
import os
import sys
import time
from datetime import datetime
from typing import IO, Any

from .connection import MeterConnectionError
from .meter import KM003C, AdcSample


def _open_csv(path: str) -> tuple[Any, IO[str]]:
    """Open ``path`` for append and return ``(writer, file_handle)``.

    Writes a header row when the file is freshly created or empty.
    Field order follows the dataclass; if AdcSample grows, the CSV grows.
    """
    is_new = not os.path.exists(path) or os.path.getsize(path) == 0
    file_handle = open(path, "a", newline="")  # noqa: SIM115 - lifetime managed by caller
    writer = csv.writer(file_handle)
    if is_new:
        header = ["timestamp"] + [f.name for f in dataclasses.fields(AdcSample)]
        writer.writerow(header)
        file_handle.flush()
    return writer, file_handle


def main() -> int:
    """Entry point for the ``usb-meter`` console script."""
    parser = argparse.ArgumentParser(
        description="Read ADC samples from a ChargerLAB POWER-Z KM003C.",
    )
    parser.add_argument(
        "-n", "--count", type=int, default=1,
        help="number of samples to print (0 = run forever; default: 1)",
    )
    parser.add_argument(
        "-i", "--interval", type=float, default=0.1,
        help="seconds between samples (default: 0.1)",
    )
    selector = parser.add_mutually_exclusive_group()
    selector.add_argument(
        "-s", "--serial",
        help="USB serial of the meter to open (see --list)",
    )
    selector.add_argument(
        "-p", "--path",
        help="explicit /dev/hidraw* path to open",
    )
    parser.add_argument(
        "-l", "--list", action="store_true",
        help="enumerate attached meters and exit",
    )
    parser.add_argument(
        "-o", "--csv", metavar="FILE",
        help="append samples to this CSV file (writes header on creation)",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true",
        help="suppress stdout output (use with --csv for headless logging)",
    )
    args = parser.parse_args()

    if args.list:
        devices = KM003C.list()
        if not devices:
            print("no KM003C found", file=sys.stderr)
            return 1
        for d in devices:
            print(f"{d.path}  serial={d.serial or '?'}")
        return 0

    csv_writer = None
    csv_file = None
    if args.csv:
        csv_writer, csv_file = _open_csv(args.csv)

    try:
        with KM003C.open(serial=args.serial, path=args.path) as meter:
            i = 0
            while args.count == 0 or i < args.count:
                s = meter.read_adc()
                if csv_writer is not None:
                    row = [datetime.now().astimezone().isoformat(timespec="milliseconds")]
                    row += [getattr(s, f.name) for f in dataclasses.fields(AdcSample)]
                    csv_writer.writerow(row)
                    csv_file.flush()  # type: ignore[union-attr]
                if not args.quiet:
                    print(
                        f"VBUS={s.vbus_v:7.4f} V  IBUS={s.ibus_a:+8.4f} A  "
                        f"VCC1={s.vcc1_v:6.4f} V  VCC2={s.vcc2_v:6.4f} V  "
                        f"VDP={s.vdp_v:6.4f} V  VDM={s.vdm_v:6.4f} V  "
                        f"T={s.temperature_c:5.2f} C"
                    )
                i += 1
                if args.count == 0 or i < args.count:
                    time.sleep(args.interval)
    except MeterConnectionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        pass
    finally:
        if csv_file is not None:
            csv_file.close()  # type: ignore[union-attr]
    return 0


if __name__ == "__main__":
    sys.exit(main())

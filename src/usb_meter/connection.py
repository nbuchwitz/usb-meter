# SPDX-FileCopyrightText: 2026 Nicolai Buchwitz <n.buchwitz@kunbus.com>
#
# SPDX-License-Identifier: LGPL-2.1-or-later

"""Transports for talking to USB-C power meters."""

from __future__ import annotations

import os
import select
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

SYS_HIDRAW = Path("/sys/class/hidraw")


@dataclass(frozen=True)
class HidDevice:
    """A discovered USB HID device on the local machine.

    Attributes
    ----------
    path : Path
        The ``/dev/hidraw*`` node.
    serial : str | None
        USB serial number, if the device exposes one. Stable across
        replug; use it to pin a specific meter when several are
        attached.
    vendor_id : int
    product_id : int
    """

    path: Path
    serial: str | None
    vendor_id: int
    product_id: int


class MeterConnectionError(Exception):
    """Base class for transport errors."""


class MeterNotFoundError(MeterConnectionError):
    """No matching device is plugged in."""


class MeterPermissionError(MeterConnectionError):
    """The caller cannot open the device node."""


class MeterTimeoutError(MeterConnectionError):
    """The device did not respond in time."""


def find_hidraw_devices(vendor_id: int, product_id: int) -> list[HidDevice]:
    """Enumerate every ``/dev/hidraw*`` matching a USB VID/PID.

    Parameters
    ----------
    vendor_id : int
        USB vendor id, e.g. ``0x5FC9`` for ChargerLAB.
    product_id : int
        USB product id, e.g. ``0x0063`` for KM003C.

    Returns
    -------
    list[HidDevice]
        Empty when nothing matches. Order follows the directory listing
        in ``/sys/class/hidraw`` and is *not* guaranteed stable across
        replug; pin to ``HidDevice.serial`` instead.
    """
    if not SYS_HIDRAW.is_dir():
        return []
    devices: list[HidDevice] = []
    for entry in sorted(SYS_HIDRAW.iterdir()):
        try:
            text = (entry / "device" / "uevent").read_text()
        except OSError:
            continue
        hid_id: tuple[int, int] | None = None
        serial: str | None = None
        for line in text.splitlines():
            key, _, value = line.partition("=")
            if key == "HID_ID":
                parts = value.split(":")
                if len(parts) == 3:
                    hid_id = (int(parts[1], 16), int(parts[2], 16))
            elif key == "HID_UNIQ" and value:
                serial = value
        if hid_id == (vendor_id, product_id):
            devices.append(
                HidDevice(
                    path=Path("/dev") / entry.name,
                    serial=serial,
                    vendor_id=vendor_id,
                    product_id=product_id,
                )
            )
    return devices


class Connection(ABC):
    """Abstract transport: a bidirectional byte stream of 64-byte frames."""

    @abstractmethod
    def write(self, data: bytes) -> int:
        """Send one frame. Return bytes written."""

    @abstractmethod
    def read(self, length: int, timeout: float | None = 1.0) -> bytes:
        """Read one frame. Raise MeterTimeoutError on timeout."""

    @abstractmethod
    def close(self) -> None:
        """Release the underlying handle."""

    def __enter__(self) -> Connection:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class ConnectionHID(Connection):
    """``/dev/hidraw`` transport.

    Writes go to the device via SET_REPORT; reads come from the
    interrupt-IN endpoint.
    """

    def __init__(self, path: Path | str) -> None:
        try:
            self._fd = os.open(str(path), os.O_RDWR | os.O_NONBLOCK)
        except PermissionError as exc:
            raise MeterPermissionError(
                f"Cannot open {path}: install the udev rule shipped with "
                "this package, or add the user to the 'plugdev' group."
            ) from exc
        except FileNotFoundError as exc:
            raise MeterNotFoundError(str(exc)) from exc

    def write(self, data: bytes) -> int:
        """Write one report."""
        return os.write(self._fd, data)

    def read(self, length: int, timeout: float | None = 1.0) -> bytes:
        """Read one report, raising on timeout."""
        ready, _, _ = select.select([self._fd], [], [], timeout)
        if not ready:
            raise MeterTimeoutError(f"No response within {timeout} s")
        return os.read(self._fd, length)

    def close(self) -> None:
        """Close the file descriptor."""
        if self._fd >= 0:
            os.close(self._fd)
            self._fd = -1

# SPDX-FileCopyrightText: 2026 Nicolai Buchwitz <n.buchwitz@kunbus.com>
#
# SPDX-License-Identifier: LGPL-2.1-or-later

"""USB-C power meter device classes."""

from __future__ import annotations

import struct
from abc import ABC
from dataclasses import dataclass
from pathlib import Path

from .connection import (
    Connection,
    ConnectionHID,
    HidDevice,
    MeterNotFoundError,
    find_hidraw_devices,
)
from .protocol import (
    Attribute,
    Command,
    DataType,
    ExtHeader,
    MsgHeader,
    encode_request,
)

CHARGERLAB_USB_VENDOR_ID = 0x5FC9


# Two-byte raw temperature -> millidegrees Celsius, per the upstream Linux
# `powerz` driver. The vendor docx oversimplifies this field to int16.
def _decode_temperature_c(t_lo: int, t_hi: int) -> float:
    return (t_hi * 2000 + t_lo * 1000 / 128) / 1000


@dataclass(frozen=True)
class AdcSample:
    """One ADC frame from a KM003C / KM002C.

    All voltages are in volts and all currents in amperes. The ``*_avg``
    fields are smoothed and calibrated; ``*_ori_avg`` are smoothed only.
    """

    vbus_v: float
    ibus_a: float
    vbus_avg_v: float
    ibus_avg_a: float
    vbus_ori_avg_v: float
    ibus_ori_avg_a: float
    temperature_c: float
    vcc1_v: float
    vcc2_v: float
    vdp_v: float
    vdm_v: float
    vdd_v: float

    @classmethod
    def from_payload(cls, payload: bytes) -> AdcSample:
        """Parse a 44-byte ADC payload (header stripped) into an AdcSample."""
        if len(payload) < 36:
            raise ValueError(f"ADC payload too short: {len(payload)} bytes")
        vbus, ibus, vbus_avg, ibus_avg, vbus_ori, ibus_ori = struct.unpack_from("<6i", payload, 0)
        t_lo, t_hi = payload[24], payload[25]
        vcc1, vcc2, vdp, vdm, vdd = struct.unpack_from("<5H", payload, 26)
        return cls(
            vbus_v=vbus / 1e6,
            ibus_a=ibus / 1e6,
            vbus_avg_v=vbus_avg / 1e6,
            ibus_avg_a=ibus_avg / 1e6,
            vbus_ori_avg_v=vbus_ori / 1e6,
            ibus_ori_avg_a=ibus_ori / 1e6,
            temperature_c=_decode_temperature_c(t_lo, t_hi),
            vcc1_v=vcc1 / 1e4,
            vcc2_v=vcc2 / 1e4,
            vdp_v=vdp / 1e4,
            vdm_v=vdm / 1e4,
            vdd_v=vdd / 1e4,
        )


class UsbMeter(ABC):
    """Common base for USB-C power meters."""

    USB_VENDOR_ID: int
    USB_PRODUCT_ID: int

    def __init__(self, connection: Connection) -> None:
        self.conn = connection
        self._msg_id = 0

    def _next_id(self) -> int:
        self._msg_id = (self._msg_id + 1) & 0xFF
        return self._msg_id

    def close(self) -> None:
        """Release the underlying transport."""
        self.conn.close()

    def __enter__(self) -> UsbMeter:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class KM003C(UsbMeter):
    """ChargerLAB POWER-Z KM003C.

    Talks to the device over its HID interface (``/dev/hidraw*``). The
    vendor-bulk interface is normally claimed by the upstream Linux
    ``powerz`` kernel driver; HID avoids that conflict and works on any
    distribution without driver gymnastics.

    Examples
    --------
    >>> with KM003C.open() as meter:
    ...     sample = meter.read_adc()
    ...     print(f"{sample.vbus_v:.3f} V  {sample.ibus_a:.3f} A")
    """

    USB_VENDOR_ID = CHARGERLAB_USB_VENDOR_ID
    USB_PRODUCT_ID = 0x0063

    @classmethod
    def list(cls) -> list[HidDevice]:
        """Enumerate every attached meter of this device class."""
        return find_hidraw_devices(cls.USB_VENDOR_ID, cls.USB_PRODUCT_ID)

    @classmethod
    def open(
        cls,
        *,
        serial: str | None = None,
        path: Path | str | None = None,
    ) -> KM003C:
        """Open one meter. With no selector, opens the first one found.

        Parameters
        ----------
        serial : str | None
            USB serial number to pin to. Survives replug; preferred for
            multi-meter setups.
        path : Path | str | None
            Explicit ``/dev/hidraw*`` path. Mutually exclusive with
            ``serial``.

        Raises
        ------
        ValueError
            If both ``serial`` and ``path`` are given.
        MeterNotFoundError
            If no device matches the selector.
        """
        if serial is not None and path is not None:
            raise ValueError("Pass at most one of 'serial' or 'path'")
        if path is not None:
            return cls(ConnectionHID(path))

        devices = cls.list()
        if not devices:
            raise MeterNotFoundError(
                f"No {cls.__name__} found (USB {cls.USB_VENDOR_ID:04x}:{cls.USB_PRODUCT_ID:04x})"
            )
        if serial is None:
            chosen = devices[0]
        else:
            chosen = next((d for d in devices if d.serial == serial), None)
            if chosen is None:
                available = ", ".join(repr(d.serial) for d in devices)
                raise MeterNotFoundError(
                    f"No {cls.__name__} with serial {serial!r} (available: {available})"
                )
        return cls(ConnectionHID(chosen.path))

    def read_adc(self, timeout: float = 1.0) -> AdcSample:
        """Request a single ADC sample and parse the response.

        Parameters
        ----------
        timeout : float
            Seconds to wait for the response. Default 1.0.

        Returns
        -------
        AdcSample
            The decoded sample.
        """
        req = encode_request(Command.GET_DATA, Attribute.ADC, self._next_id())
        self.conn.write(req)
        frame = self.conn.read(64, timeout=timeout)
        if len(frame) < 8:
            raise OSError(f"Short frame: {len(frame)} bytes")
        msg = MsgHeader.unpack(frame)
        if msg.type != int(DataType.PUT_DATA):
            raise OSError(f"Unexpected response type {msg.type}")
        ext = ExtHeader.unpack(frame, 4)
        if ext.attribute != int(Attribute.ADC):
            raise OSError(f"Unexpected response attribute 0x{ext.attribute:x}")
        if ext.size < 36 or 8 + ext.size > len(frame):
            raise OSError(f"Bad payload size {ext.size} in frame of {len(frame)} bytes")
        return AdcSample.from_payload(frame[8 : 8 + ext.size])

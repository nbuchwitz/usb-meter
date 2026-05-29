# SPDX-FileCopyrightText: 2026 Nicolai Buchwitz <n.buchwitz@kunbus.com>
#
# SPDX-License-Identifier: LGPL-2.1-or-later

"""Python library for USB-C power meters.

Currently supports the ChargerLAB POWER-Z KM003C over the HID transport
(``/dev/hidraw``). The wire format is shared with the KM002C, so adding
that device is mostly a matter of a new USB product id.

Example
-------
>>> from usb_meter import KM003C
>>> with KM003C.open() as meter:
...     s = meter.read_adc()
...     print(f"{s.vbus_v:.3f} V  {s.ibus_a:.3f} A")
"""

from .connection import (
    Connection,
    ConnectionHID,
    HidDevice,
    MeterConnectionError,
    MeterNotFoundError,
    MeterPermissionError,
    MeterTimeoutError,
    find_hidraw_devices,
)
from .meter import KM003C, AdcSample, UsbMeter
from .protocol import (
    Attribute,
    Command,
    DataType,
    ExtHeader,
    MsgHeader,
    encode_request,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # Devices
    "KM003C",
    "UsbMeter",
    # Data
    "AdcSample",
    # Transports
    "Connection",
    "ConnectionHID",
    "HidDevice",
    "find_hidraw_devices",
    # Errors
    "MeterConnectionError",
    "MeterNotFoundError",
    "MeterPermissionError",
    "MeterTimeoutError",
    # Protocol primitives
    "Attribute",
    "Command",
    "DataType",
    "ExtHeader",
    "MsgHeader",
    "encode_request",
]

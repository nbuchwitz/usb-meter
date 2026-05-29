# SPDX-FileCopyrightText: 2026 Nicolai Buchwitz <n.buchwitz@kunbus.com>
#
# SPDX-License-Identifier: LGPL-2.1-or-later

"""Wire-protocol primitives for ChargerLAB POWER-Z meters (KM002C, KM003C).

Every frame on the USER (vendor-bulk), CDC, and HID transports starts with
a 32-bit little-endian header. A request packs ``(type, id, attribute)``;
a response packs ``(type, id, obj count)`` and is followed by an extension
header carrying ``(attribute, size)`` before the actual payload.

Reference: KM002C/3C API description (ChargerLAB).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import IntEnum, IntFlag


class Command(IntEnum):
    """Control-message opcodes (type field is in 1..63)."""

    SYNC = 1
    CONNECT = 2
    DISCONNECT = 3
    RESET = 4
    ACCEPT = 5
    REJECT = 6
    FINISHED = 7
    JUMP_APROM = 8
    JUMP_DFU = 9
    GET_STATUS = 10
    ERROR = 11
    GET_DATA = 12
    GET_FILE = 13


class DataType(IntEnum):
    """Data-message opcodes (type field >= 64)."""

    HEAD = 64
    PUT_DATA = 65


class Attribute(IntFlag):
    """What the device should return.

    The protocol treats this as a 15-bit bitmask, but in practice
    requests carry a single attribute at a time.
    """

    ADC = 0x001
    ADC_QUEUE = 0x002
    ADC_QUEUE_10K = 0x004
    SETTINGS = 0x008
    PD_PACKET = 0x010
    PD_STATUS = 0x020
    QC_PACKET = 0x040
    TICK = 0x080


HEADER_LEN = 4


def encode_request(command: Command, attribute: Attribute, msg_id: int = 0) -> bytes:
    """Pack a control header into 4 little-endian bytes.

    Layout (32-bit LE): ``type:7  extend:1  id:8  encode:1  att:15``.

    Parameters
    ----------
    command : Command
        Opcode (1..63).
    attribute : Attribute
        Attribute code (15-bit).
    msg_id : int
        Sequence id, 0..255. The meter echoes this in the response.

    Returns
    -------
    bytes
        4-byte little-endian header.
    """
    if not 0 <= msg_id <= 0xFF:
        raise ValueError(f"msg_id {msg_id} out of range 0..255")
    if not 0 <= int(attribute) <= 0x7FFF:
        raise ValueError(f"attribute {attribute!r} out of 15-bit range")
    word = (int(command) & 0x7F) | ((msg_id & 0xFF) << 8) | ((int(attribute) & 0x7FFF) << 17)
    return struct.pack("<I", word)


@dataclass(frozen=True)
class MsgHeader:
    """Decoded first 4 bytes of a response (data-message layout)."""

    type: int
    msg_id: int
    obj_words: int

    @classmethod
    def unpack(cls, buf: bytes, offset: int = 0) -> MsgHeader:
        """Decode a 4-byte LE header at ``offset``."""
        word = struct.unpack_from("<I", buf, offset)[0]
        return cls(
            type=word & 0x7F,
            msg_id=(word >> 8) & 0xFF,
            obj_words=(word >> 22) & 0x3FF,
        )


@dataclass(frozen=True)
class ExtHeader:
    """Decoded extension header that follows a PUT_DATA message header."""

    attribute: int
    chunk: int
    size: int

    @classmethod
    def unpack(cls, buf: bytes, offset: int = 0) -> ExtHeader:
        """Decode a 4-byte LE extension header at ``offset``."""
        word = struct.unpack_from("<I", buf, offset)[0]
        return cls(
            attribute=word & 0x7FFF,
            chunk=(word >> 16) & 0x3F,
            size=(word >> 22) & 0x3FF,
        )

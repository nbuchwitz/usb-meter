# SPDX-FileCopyrightText: 2026 Nicolai Buchwitz <n.buchwitz@kunbus.com>
#
# SPDX-License-Identifier: LGPL-2.1-or-later

"""Wire-protocol round-trip tests. Hardware-free."""

from usb_meter.meter import AdcSample
from usb_meter.protocol import Attribute, Command, ExtHeader, MsgHeader, encode_request

# Real PUT_DATA + ADC frame captured from a KM003C powered at ~5 V.
# Layout: 4-byte msg header, 4-byte ext header, 44-byte ADC payload, padding.
CAPTURED_FRAME = bytes.fromhex(
    "41008002"  # msg header
    "0100000b"  # ext header
    "15504e00422ff8ff7b504e00f241f8ff34524e002642f8ff"  # 6 int32 V/I fields
    "c00e"  # raw temperature bytes
    "2c00b13f7c035c04497c"  # VCC1 VCC2 VDP VDM VDD
    "00805c0659006f00"  # rate/n + reserved
    "0000000000000000000000000000"  # padding to 64 bytes
)


def test_encode_adc_request_matches_vendor_example():
    """Vendor docx: CMD_GET_DATA + ATT_ADC encodes as 0c 00 02 00."""
    assert encode_request(Command.GET_DATA, Attribute.ADC, msg_id=0) == bytes.fromhex("0c000200")


def test_encode_request_carries_msg_id_in_bits_8_15():
    """msg_id=9 should appear in the second byte."""
    assert encode_request(Command.GET_DATA, Attribute.ADC, msg_id=9) == bytes.fromhex("0c090200")


def test_unpack_known_message_header():
    msg = MsgHeader.unpack(CAPTURED_FRAME)
    assert msg.type == 65  # CMD_PUT_DATA
    assert msg.msg_id == 0
    assert msg.obj_words == 10  # 10 * 4 = 40 documented payload bytes


def test_unpack_known_ext_header():
    ext = ExtHeader.unpack(CAPTURED_FRAME, 4)
    assert ext.attribute == int(Attribute.ADC)
    assert ext.chunk == 0
    # size is in bytes (44 = 40 documented + 4 reserved trailer)
    assert ext.size == 44


def test_decode_known_adc_payload():
    payload = CAPTURED_FRAME[8 : 8 + 44]
    sample = AdcSample.from_payload(payload)
    # Values cross-checked against the kernel `powerz` hwmon driver at
    # the same moment on the same device.
    assert sample.vbus_v == 5.132309
    assert sample.ibus_a == -0.51219
    assert round(sample.vcc1_v, 4) == 0.0044
    assert round(sample.vcc2_v, 4) == 1.6305
    assert round(sample.vdp_v, 4) == 0.0892
    assert round(sample.vdm_v, 4) == 0.1116
    assert round(sample.vdd_v, 4) == 3.1817
    # temperature: 14 * 2000 + 192 * 1000 / 128 = 29500 m C -> 29.5 C
    assert round(sample.temperature_c, 3) == 29.5

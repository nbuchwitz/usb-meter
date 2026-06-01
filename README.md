<!--
SPDX-FileCopyrightText: 2026 Nicolai Buchwitz <n.buchwitz@kunbus.com>
SPDX-License-Identifier: LGPL-2.1-or-later
-->

# usb-meter

[![Tests](https://github.com/nbuchwitz/usb-meter/actions/workflows/pytest.yml/badge.svg)](https://github.com/nbuchwitz/usb-meter/actions/workflows/pytest.yml)
[![License: LGPL v2.1+](https://img.shields.io/badge/License-LGPL_v2.1+-blue.svg)](https://www.gnu.org/licenses/lgpl-2.1)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

Python library for USB-C power meters. Initial support: ChargerLAB
POWER-Z **KM003C** over its HID transport.

The library talks directly to `/dev/hidraw*`, so it does not fight with
the upstream Linux `powerz` kernel driver (which binds to the device's
vendor-bulk interface and exposes a small subset of values via hwmon).
It also has no third-party dependencies.

## Features

- Find a connected meter by USB vendor/product id.
- Read ADC samples (VBUS, IBUS, VCC1/2, VDP/M, VDD, temperature).
- Compact wire-protocol primitives (message + extension header, opcode
  and attribute enums) shared with the KM002C.
- `usb-meter` CLI for one-shot and streaming reads.

## Installation

Directly from GitHub:

```bash
pip install git+https://github.com/nbuchwitz/usb-meter.git
```

Or from a local checkout:

```bash
pip install .
```

Install the udev rule so non-root users in the `plugdev` group can
access the device:

```bash
sudo install -m 644 etc/udev/rules.d/60-chargerlab-km003c.rules /etc/udev/rules.d/
sudo udevadm control --reload && sudo udevadm trigger
```

## Usage

```python
from usb_meter import KM003C

with KM003C.open() as meter:
    sample = meter.read_adc()
    print(f"{sample.vbus_v:.3f} V, {sample.ibus_a:.3f} A, {sample.temperature_c:.1f} C")
```

Or from the shell:

```bash
usb-meter -n 10 -i 0.2     # 10 samples, 200 ms apart
usb-meter -n 0             # stream forever
```

## Status

Alpha. Only ADC reading is implemented today. The vendor protocol
documents more attributes (`PD_PACKET`, `ADC_QUEUE_10K`, `SETTINGS`,
etc.) that map to the same request/response shape and will land here
incrementally.

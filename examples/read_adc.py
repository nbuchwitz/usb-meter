#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Nicolai Buchwitz <n.buchwitz@kunbus.com>
#
# SPDX-License-Identifier: LGPL-2.1-or-later

"""Read one ADC sample from a connected KM003C and print every field."""

from usb_meter import KM003C


def main() -> None:
    """Open the first KM003C found and print one frame."""
    with KM003C.open() as meter:
        s = meter.read_adc()
    for name, value in vars(s).items():
        if name.endswith("_v"):
            unit = "V"
        elif name.endswith("_a"):
            unit = "A"
        else:
            unit = "C"
        print(f"{name:20s} = {value:>10.4f} {unit}")


if __name__ == "__main__":
    main()

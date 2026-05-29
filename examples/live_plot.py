#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Nicolai Buchwitz <n.buchwitz@kunbus.com>
#
# SPDX-License-Identifier: LGPL-2.1-or-later

"""Live-plot VBUS and IBUS from a connected KM003C.

Requires matplotlib (``pip install usb-meter[plot]`` or ``pip install matplotlib``).
Over SSH, run with X-forwarding (``ssh -X ...``) or set ``MPLBACKEND=TkAgg``
on a host with a display.
"""

import argparse
import sys
import time
from collections import deque

import matplotlib.pyplot as plt

from usb_meter import KM003C, MeterConnectionError


def main() -> int:
    """Open a KM003C and stream samples into a rolling-window plot."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-s", "--serial", help="USB serial of the meter (see usb-meter --list)")
    parser.add_argument("-w", "--window", type=int, default=300,
                        help="samples to keep on screen (default: 300)")
    parser.add_argument("-i", "--interval", type=float, default=0.05,
                        help="seconds between samples (default: 0.05)")
    args = parser.parse_args()

    times: deque[float] = deque(maxlen=args.window)
    vbus: deque[float] = deque(maxlen=args.window)
    ibus: deque[float] = deque(maxlen=args.window)

    plt.ion()
    fig, (ax_v, ax_i) = plt.subplots(2, 1, sharex=True, figsize=(9, 6))
    line_v, = ax_v.plot([], [], color="C0")
    line_i, = ax_i.plot([], [], color="C1")
    ax_v.set_ylabel("VBUS (V)")
    ax_i.set_ylabel("IBUS (A)")
    ax_i.set_xlabel("time (s)")
    ax_v.grid(True)
    ax_i.grid(True)
    fig.suptitle("ChargerLAB POWER-Z KM003C - live")
    fig.tight_layout()

    try:
        meter = KM003C.open(serial=args.serial)
    except MeterConnectionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    t0 = time.monotonic()
    try:
        with meter:
            while plt.fignum_exists(fig.number):
                sample = meter.read_adc()
                times.append(time.monotonic() - t0)
                vbus.append(sample.vbus_v)
                ibus.append(sample.ibus_a)
                line_v.set_data(times, vbus)
                line_i.set_data(times, ibus)
                ax_v.relim()
                ax_v.autoscale_view()
                ax_i.relim()
                ax_i.autoscale_view()
                fig.canvas.draw_idle()
                plt.pause(args.interval)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3

import ctypes
import os
import sys

I2C_RDWR = 0x0707
I2C_M_RD = 0x0001

AXP221_ADDR = 0x34

# AXP221 charge-control register 1; bit 7 enables battery charging.
CHARGE_CONTROL_REG = 0x33
CHARGE_ENABLE_BIT = 0x80


class I2CMsg(ctypes.Structure):
    _fields_ = [
        ("addr", ctypes.c_uint16),
        ("flags", ctypes.c_uint16),
        ("len", ctypes.c_uint16),
        ("buf", ctypes.POINTER(ctypes.c_uint8)),
    ]


class I2CRdwrData(ctypes.Structure):
    _fields_ = [
        ("msgs", ctypes.POINTER(I2CMsg)),
        ("nmsgs", ctypes.c_uint32),
    ]


libc = ctypes.CDLL(None, use_errno=True)
libc.ioctl.restype = ctypes.c_int


def rdwr(fd, messages):
    transaction = I2CRdwrData(messages, len(messages))

    if libc.ioctl(fd, I2C_RDWR, ctypes.byref(transaction)) < 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


def read_register(fd, register):
    register_buffer = (ctypes.c_uint8 * 1)(register)
    value_buffer = (ctypes.c_uint8 * 1)()

    messages = (I2CMsg * 2)(
        I2CMsg(
            AXP221_ADDR,
            0,
            1,
            ctypes.cast(
                register_buffer,
                ctypes.POINTER(ctypes.c_uint8),
            ),
        ),
        I2CMsg(
            AXP221_ADDR,
            I2C_M_RD,
            1,
            ctypes.cast(
                value_buffer,
                ctypes.POINTER(ctypes.c_uint8),
            ),
        ),
    )

    rdwr(fd, messages)
    return value_buffer[0]


def write_register(fd, register, value):
    buffer = (ctypes.c_uint8 * 2)(register, value)

    messages = (I2CMsg * 1)(
        I2CMsg(
            AXP221_ADDR,
            0,
            2,
            ctypes.cast(
                buffer,
                ctypes.POINTER(ctypes.c_uint8),
            ),
        ),
    )

    rdwr(fd, messages)


def set_charging_enabled(fd, enabled):
    current = read_register(fd, CHARGE_CONTROL_REG)

    if enabled:
        target = current | CHARGE_ENABLE_BIT
    else:
        target = current & ~CHARGE_ENABLE_BIT

    if target != current:
        write_register(fd, CHARGE_CONTROL_REG, target)

    readback = read_register(fd, CHARGE_CONTROL_REG)
    actual_enabled = bool(readback & CHARGE_ENABLE_BIT)

    if actual_enabled != enabled:
        raise RuntimeError(
            f"charge-control verification failed: 0x{readback:02x}"
        )


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in {
        "status",
        "enable",
        "disable",
    }:
        print(
            f"usage: {sys.argv[0]} status|enable|disable",
            file=sys.stderr,
        )
        return 2

    if not os.path.exists("/customer/app/axp_test"):
        print("AXP charging interface unavailable", file=sys.stderr)
        return 1

    fd = os.open("/dev/i2c-1", os.O_RDWR)

    try:
        action = sys.argv[1]

        if action == "status":
            value = read_register(fd, CHARGE_CONTROL_REG)
            print(
                "enabled"
                if value & CHARGE_ENABLE_BIT
                else "disabled"
            )
        else:
            set_charging_enabled(fd, action == "enable")
    finally:
        os.close(fd)

    return 0


if __name__ == "__main__":
    sys.exit(main())

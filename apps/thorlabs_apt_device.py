from __future__ import annotations

from thorlabs_apt.kbd101 import KBD101

MGMSG_MOD_IDENTIFY = 0x0223

MGMSG_HW_REQ_INFO = 0x0005
MGMSG_HW_GET_INFO = 0x0006

# K-Cube Position Aligner

if __name__ == "__main__":
    dev = KBD101(serial_number="28251738")
    print(dev._hw_info)

    dev.enable_channel(1)
    print(dev.get_velocity_params())
    d = dev.get_stage_params()

    print(dev.get_homing_params())
    # dev.home()
    # print(dev.position())
    # dev.move_relative(1.0)

    # print(dev.position())
    # dev.move_relative(1.0)
    # print(dev.position())

    # dev.move_absolute(10.0)

    # print(dev.position())

    # kpa = KPA101(serial_number="69252738")

    # print(kpa.position_demand_params)

    # kpa.operation_mode = OperationMode.OPEN_LOOP
    # print(kpa.operation_mode)
    # print(kpa.status_bits)
    # print(kpa.display_settings)
    # print(kpa.position)
    # kpa.position = (1.0, 1.0)
    # print(kpa.position)
    # print(kpa.readings)
    # # while True:
    # #     print(kpa.readings)

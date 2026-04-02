import math
from enum import IntEnum
from functools import partial

from thorlabs_apt.device import APTDevice, find_device
from thorlabs_apt.packet import APTPacket, Buffer, field

MGMSG_QUAD_SET_PARAMS = 0x0870
MGMSG_QUAD_REQ_PARAMS = 0x0871
MGMSG_QUAD_GET_PARAMS = 0x0872

SUB_MSG_ID_LOOP_PARAMS = 0x01
SUB_MSG_ID_READINGS = 0x03
SUB_MSG_ID_POSITION_DEMAND_PARAMS = 0x05
SUB_MSG_ID_OPERATION_MODE = 0x07
SUB_MSG_ID_STATUS_BITS = 0x09
SUB_MSG_ID_DISPLAY_SETTINGS = 0x0B
SUB_MSG_ID_POSITION_DEMAND_OUTPUTS = 0x0D
SUB_MSG_ID_LOOP_PARAMS_2 = 0x0E
SUB_MSG_ID_KPA_TRIG_IO_CONFIG = 0x0F


def dig2volt(dig: int, r: tuple[float, float], res=2**16) -> float:
    range_val = abs(max(r) - min(r))
    voltage = dig * range_val / (res - 1)
    step_size = range_val / (res - 1)
    # Round to the minimum resolution determined by the DAC/ADC step size
    decimals = max(0, -int(math.floor(math.log10(step_size)))) if step_size > 0 else 0
    return round(voltage, decimals)


def volt2dig(dig: float, r: tuple[float, float], res=2**16, signed: bool = True) -> int:
    bit = round(dig * (res - 1) / abs(max(r) - min(r)))
    if signed:
        return max(-(res // 2), min((res // 2) - 1, bit))
    return max(0, min(res - 1, bit))


def gain2percent(gain: int) -> float:
    return round(gain * 100 / 32767, 6)


def percent2gain(gain: float) -> int:
    bit = round(gain * 32767 / 100)
    return max(0, min(32767, bit))


class QuadReadings(Buffer):
    sub_msg_id = field[int](0, "<H", default=SUB_MSG_ID_READINGS)
    x_diff = field[float](
        2, "<h", decode=partial(dig2volt, r=(-10, 10)), encode=partial(volt2dig, r=(-10, 10), signed=True)
    )
    y_diff = field[float](
        4, "<h", decode=partial(dig2volt, r=(-10, 10)), encode=partial(volt2dig, r=(-10, 10), signed=True)
    )
    _sum = field[float](6, "<H", decode=partial(dig2volt, r=(0, 10)), encode=partial(volt2dig, r=(0, 10), signed=False))
    x_pos = field[float](
        8, "<h", decode=partial(dig2volt, r=(-10, 10)), encode=partial(volt2dig, r=(-10, 10), signed=True)
    )
    y_pos = field[float](
        10, "<h", decode=partial(dig2volt, r=(-10, 10)), encode=partial(volt2dig, r=(-10, 10), signed=True)
    )


class QuadLoopParams(Buffer):
    sub_msg_id = field[int](0, "<H", default=SUB_MSG_ID_LOOP_PARAMS)
    p_gain = field[float](2, "<H", decode=gain2percent, encode=percent2gain)
    i_gain = field[float](4, "<H", decode=gain2percent, encode=percent2gain)
    d_gain = field[float](6, "<H", decode=gain2percent, encode=percent2gain)


class QuadPositionDemandParams(Buffer):
    sub_msg_id = field[int](0, "<H", default=SUB_MSG_ID_POSITION_DEMAND_PARAMS)
    x_pos_dem_min = field[float](
        2, "<h", decode=partial(dig2volt, r=(-10, 10)), encode=partial(volt2dig, r=(-10, 10), signed=True)
    )
    y_pos_dem_min = field[float](
        4, "<h", decode=partial(dig2volt, r=(-10, 10)), encode=partial(volt2dig, r=(-10, 10), signed=True)
    )
    x_pos_dem_max = field[float](
        6, "<h", decode=partial(dig2volt, r=(-10, 10)), encode=partial(volt2dig, r=(-10, 10), signed=True)
    )
    y_pos_dem_max = field[float](
        8, "<h", decode=partial(dig2volt, r=(-10, 10)), encode=partial(volt2dig, r=(-10, 10), signed=True)
    )
    lv_out_route = field[int](10, "<H")
    ol_pos_dem = field[int](12, "<H")
    x_pos_fb_sense = field[float](
        14, "<h", decode=partial(dig2volt, r=(-10, 10)), encode=partial(volt2dig, r=(-10, 10), signed=True)
    )
    y_pos_fb_sense = field[float](
        16, "<h", decode=partial(dig2volt, r=(-10, 10)), encode=partial(volt2dig, r=(-10, 10), signed=True)
    )


class OperationMode(IntEnum):
    MONITOR_MODE = 1
    OPEN_LOOP = 2
    CLOSED_LOOP = 3
    AUTO = 4


class QuadOperationMode(Buffer):
    sub_msg_id = field[int](0, "<H", default=SUB_MSG_ID_OPERATION_MODE)
    mode = field[OperationMode](2, "<H", decode=lambda x: OperationMode(x))


class QuadStatusBits(Buffer):
    sub_msg_id = field[int](0, "<H", default=SUB_MSG_ID_STATUS_BITS)
    status_bits = field[int](2, "<L")


class QuadDisplaySettings(Buffer):
    sub_msg_id = field[int](0, "<H", default=SUB_MSG_ID_DISPLAY_SETTINGS)
    display_intensity = field[int](2, "<H", int)
    display_mode = field[int](4, "<H")
    display_dim_timeout = field[int](6, "<H")


class QuadPositionOutputs(Buffer):
    sub_msg_id = field[int](0, "<H", default=SUB_MSG_ID_POSITION_DEMAND_OUTPUTS)
    x_pos = field[float](
        2, "<h", decode=partial(dig2volt, r=(-10, 10)), encode=partial(volt2dig, r=(-10, 10), signed=True)
    )
    y_pos = field[float](
        4, "<h", decode=partial(dig2volt, r=(-10, 10)), encode=partial(volt2dig, r=(-10, 10), signed=True)
    )


class QuadKPATrigIOConfig(Buffer):
    sub_msg_id = field[int](0, "<H", default=SUB_MSG_ID_KPA_TRIG_IO_CONFIG)
    trig_io_config = field[int](2, "<H")


class KPA101(APTDevice):
    def __init__(self, serial_number: str) -> None:
        super().__init__(find_device(serial_number=serial_number))

    @property
    def readings(self) -> QuadReadings:
        packet = APTPacket(MGMSG_QUAD_REQ_PARAMS, SUB_MSG_ID_READINGS, 0x00, 0x50, 0x01)
        data = self.request(packet)
        return QuadReadings.unpack(data)

    @property
    def closed_loop_position(self): ...

    @closed_loop_position.setter
    def closed_loop_position(self, pos: tuple[float, float]): ...

    @property
    def loop_params(self) -> QuadLoopParams:
        packet = APTPacket(MGMSG_QUAD_REQ_PARAMS, SUB_MSG_ID_LOOP_PARAMS, 0x00, 0x50, 0x01)
        data = self.request(packet)
        return QuadLoopParams.unpack(data)

    @loop_params.setter
    def loop_params(self, params: QuadLoopParams):
        packet = APTPacket(MGMSG_QUAD_SET_PARAMS, SUB_MSG_ID_LOOP_PARAMS, 0x00, 0x50, 0x01)
        data = params.tobytes()
        self.set(packet, data)

    @property
    def position_demand_params(self) -> QuadPositionDemandParams:
        packet = APTPacket(MGMSG_QUAD_REQ_PARAMS, SUB_MSG_ID_POSITION_DEMAND_PARAMS, 0x00, 0x50, 0x01)
        data = self.request(packet)
        return QuadPositionDemandParams.unpack(data)

    @property
    def operation_mode(self) -> QuadOperationMode:
        packet = APTPacket(MGMSG_QUAD_REQ_PARAMS, SUB_MSG_ID_OPERATION_MODE, 0x00, 0x50, 0x01)
        data = self.request(packet)
        return QuadOperationMode.unpack(data)

    @operation_mode.setter
    def operation_mode(self, mode: OperationMode):
        packet = APTPacket(MGMSG_QUAD_SET_PARAMS, SUB_MSG_ID_OPERATION_MODE, 0x00, 0x50, 0x01)
        data = QuadOperationMode(mode=mode).tobytes()
        self.set(packet, data)

    @property
    def status_bits(self) -> QuadStatusBits:
        packet = APTPacket(MGMSG_QUAD_REQ_PARAMS, SUB_MSG_ID_STATUS_BITS, 0x00, 0x50, 0x01)
        data = self.request(packet)
        return QuadStatusBits.unpack(data)

    @property
    def display_settings(self) -> QuadDisplaySettings:
        packet = APTPacket(MGMSG_QUAD_REQ_PARAMS, SUB_MSG_ID_DISPLAY_SETTINGS, 0x00, 0x50, 0x01)
        data = self.request(packet)
        return QuadDisplaySettings.unpack(data)

    @property
    def position(self) -> QuadPositionOutputs:
        packet = APTPacket(MGMSG_QUAD_REQ_PARAMS, SUB_MSG_ID_POSITION_DEMAND_OUTPUTS, 0x00, 0x50, 0x01)
        data = self.request(packet)
        return QuadPositionOutputs.unpack(data)

    @position.setter
    def position(self, pos: tuple[float, float]):
        packet = APTPacket(MGMSG_QUAD_SET_PARAMS, SUB_MSG_ID_POSITION_DEMAND_OUTPUTS, 0x00, 0x50, 0x01)
        data = QuadPositionOutputs(x_pos=pos[0], y_pos=pos[1]).tobytes()
        self.set(packet, data)

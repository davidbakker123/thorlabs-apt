from abc import abstractmethod
from enum import IntEnum
from typing import Any

from thorlabs_apt.device import APTDevice
from thorlabs_apt.packet import APTPacket, Buffer, field

MSGMSG_MOT_REQ_POSCOUNTER = 0x0411

MGMSG_MOT_REQ_STAGEAXISPARAMS = 0x04F1
MGMSG_MOT_REQ_HOMEPARAMS = 0x0441

MGMSG_MOT_SET_VELPARAMS = 0x0413
MGMSG_MOT_REQ_VELPARAMS = 0x0414
MGMSG_MOT_GET_VELPARAMS = 0x0415

MGMSG_MOT_MOVE_HOME = 0x0443
MGMSG_MOT_MOVE_HOMED = 0x0444

MGMSG_MOT_MOVE_RELATIVE = 0x0448
MGMSG_MOT_MOVE_ABSOLUTE = 0x0453
MGMSG_MOT_MOVE_COMPLETED = 0x0464


def request_velocity_params_packet(channel: int = 0x01, source: int = 0x01, destination: int = 0x50) -> APTPacket:
    return APTPacket(MGMSG_MOT_REQ_VELPARAMS, channel, 0x00, destination, source)


def set_velocity_params_packet(source: int = 0x01, destination: int = 0x50) -> APTPacket:
    return APTPacket(MGMSG_MOT_SET_VELPARAMS, 0x00, 0x00, destination, source)


class HomeDirection(IntEnum):
    FORWARD = 0x01
    REVERSE = 0x02


class LimitSwitch(IntEnum):
    REVERSE = 0x01
    FORWARD = 0x04


class MotorVelocityParams(Buffer):
    channel = field[int](0, "<H")
    min_velocity = field[float](2, "<l")
    acceleration = field[float](6, "<l")
    max_velocity = field[float](10, "<l")


class MotorMoveRelativeParams(Buffer):
    channel = field[int](0, "<H")
    distance = field[int](2, "<l")


class MotorMoveAbsoluteParams(Buffer):
    channel = field[int](0, "<H")
    distance = field[int](2, "<l")


class MotorPositionCounter(Buffer):
    channel = field[int](0, "<H")
    position = field[int](2, "<l")


class MotorStageAxisParams(Buffer):
    channel = field[int](0, "<H")
    stage_id = field[int](2, "<H")
    axis_id = field[int](4, "<H")
    part_no_axis = field[str](6, "16c", decode=lambda c: "".join(i.decode("ascii") for i in c).strip())
    serial_number = field[int](22, "<I", decode=int)
    counts_per_unit = field[float](26, "<I", decode=int)
    min_position = field[float](30, "<i", decode=int)
    max_position = field[float](34, "<i", decode=int)
    max_acceleration = field[float](38, "<i", decode=int)
    max_decceleration = field[float](42, "<i", decode=int)
    max_velocity = field[float](46, "<i", decode=int)


class MotorHomingParams(Buffer):
    channel = field[int](0, "<H")
    homing_direction = field[HomeDirection](2, "<H", decode=lambda x: HomeDirection(x))
    limit_switch = field[LimitSwitch](4, "<H", decode=lambda x: LimitSwitch(x))
    home_velocity = field[float](6, "<i", decode=int)
    offset_distance = field[float](10, "<i", decode=int)


class APTMotorController(APTDevice):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._stage_params = self.get_stage_params()

    def get_velocity_params(self, channel: int = 0x01) -> MotorVelocityParams:
        packet = request_velocity_params_packet(channel=channel)
        data = self.request(packet)
        return MotorVelocityParams.unpack(data)

    def set_velocity_params(self, velocity_params: MotorVelocityParams) -> None:
        packet = set_velocity_params_packet()
        self.set(packet, velocity_params)

    def home(self, channel: int = 0x01, destination: int = 0x50) -> None:
        packet = APTPacket(MGMSG_MOT_MOVE_HOME, channel, 0x00, destination, 0x01)
        self._write(packet.tobytes())

        max_iter = 100
        i = 0
        while i < max_iter:
            try:
                packet, _ = self._read()
                if packet.message_id == MGMSG_MOT_MOVE_HOMED and packet.param1 == channel:
                    return
            except ValueError:
                i += 1

    def move_relative(self, distance: float, channel: int = 0x01, destination: int = 0x50) -> None:
        packet = APTPacket(MGMSG_MOT_MOVE_RELATIVE, 0x00, 0x00, destination, 0x01)
        params = MotorMoveRelativeParams(channel=channel, distance=self.encode_position(distance))
        self.set(packet, params)

        max_iter = 100
        i = 0
        while i < max_iter:
            try:
                packet, _ = self._read()
                if packet.message_id == MGMSG_MOT_MOVE_COMPLETED:
                    return
            except ValueError:
                i += 1

    def move_absolute(self, distance: float, channel: int = 0x01, destination: int = 0x50) -> None:
        packet = APTPacket(MGMSG_MOT_MOVE_ABSOLUTE, 0x00, 0x00, destination, 0x01)
        params = MotorMoveAbsoluteParams(channel=channel, distance=self.encode_position(distance))
        self.set(packet, params)

        max_iter = 100
        i = 0
        while i < max_iter:
            try:
                packet, _ = self._read()
                if packet.message_id == MGMSG_MOT_MOVE_COMPLETED:
                    return
            except ValueError:
                i += 1

    def position(self, channel: int = 0x01, destination: int = 0x50) -> float:
        packet = APTPacket(MSGMSG_MOT_REQ_POSCOUNTER, channel, 0x00, destination, 0x01)
        data = self.request(packet)
        position_counter = MotorPositionCounter.unpack(data)
        return self.decode_position(position_counter.position)

    def get_stage_params(self, channel: int = 0x01, destination: int = 0x50) -> MotorStageAxisParams:
        packet = APTPacket(MGMSG_MOT_REQ_STAGEAXISPARAMS, channel, 0x00, destination, 0x01)
        data = self.request(packet)
        return MotorStageAxisParams.unpack(data)

    def get_homing_params(self, channel: int = 0x01, destination: int = 0x50) -> MotorHomingParams:
        packet = APTPacket(MGMSG_MOT_REQ_HOMEPARAMS, channel, 0x00, destination, 0x01)
        data = self.request(packet)
        return MotorHomingParams.unpack(data)

    @abstractmethod
    def encode_position(self, decoder_position: float) -> int: ...

    @abstractmethod
    def decode_position(self, encoder_position: int) -> float: ...

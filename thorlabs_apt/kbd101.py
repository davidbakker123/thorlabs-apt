import math

from thorlabs_apt.device import find_device
from thorlabs_apt.motor_controller import APTMotorController

T = 102.4e-6


class KBD101(APTMotorController):
    def __init__(self, serial_number: str) -> None:
        super().__init__(find_device(serial_number=serial_number))
        self._decimals = math.ceil(abs(math.log10(360 / self._stage_params.counts_per_unit)))

    def encode_position(self, decoder_position: float) -> int:
        return int(decoder_position * self._stage_params.counts_per_unit)

    def decode_position(self, encoder_position: int) -> float:
        return round(encoder_position / self._stage_params.counts_per_unit, self._decimals)

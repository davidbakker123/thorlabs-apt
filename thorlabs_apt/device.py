import serial
import serial.tools.list_ports

from thorlabs_apt.packet import (
    APTPacket,
    Buffer,
    HardwareInfo,
    get_identify_packet,
    request_channel_enable_state_packet,
    request_hardware_info_packet,
    set_channel_enable_state_packet,
)


def find_device(vid: int | None = None, pid: int | None = None, serial_number: str | None = None):
    for p in serial.tools.list_ports.comports():
        if serial_number and p.serial_number == serial_number:
            return p.device


def list_devices():
    result = ""
    for p in serial.tools.list_ports.comports():
        if pid := p.pid:
            pid = f"{pid:#06x}"
        if vid := p.vid:
            vid = f"{vid:#06x}"
        result += f"device={p.device}, manufacturer={p.manufacturer}, product={p.product}, vid={vid}, pid={pid}, serial_number={p.serial_number}\n"
    return result.rstrip()


class APTDevice:
    def __init__(self, port_name: str) -> None:
        self.port = serial.Serial(
            port=port_name,
            baudrate=115200,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            rtscts=True,
            timeout=1.0,
        )
        self.port.reset_input_buffer()
        self.port.reset_output_buffer()

        resp = self.request(request_hardware_info_packet())
        self._hw_info = HardwareInfo.unpack(resp)

    def _write(self, data: bytes) -> None:
        written = self.port.write(data)
        self.port.flush()

        if written != len(data):
            msg = "not written full packet"
            raise ValueError(msg)

    def _read(self) -> tuple[APTPacket, bytes]:
        if not (response := self.port.read(APTPacket.MESSAGE_HEADER_SIZE)):
            msg = "no response received"
            raise ValueError(msg)
        packet = APTPacket.unpack(response)
        if packet.data_packet_length > 0:
            raw_data = self.port.read(packet.data_packet_length)
            return packet, raw_data
        return packet, b""

    def request(self, packet: APTPacket) -> bytes:
        self._write(packet.tobytes())
        _, data = self._read()
        return bytes(data)

    def set(self, packet: APTPacket, data: bytes | Buffer | None = None) -> None:
        if data is None:
            data = b""
        elif isinstance(data, Buffer):
            data = data.tobytes()

        packet.data_packet_length = len(data)
        self._write(packet.tobytes() + data)

    @property
    def serial_number(self) -> int:
        return self._hw_info.serial_number

    def identify(self, channel: int = 0) -> None:
        packet = get_identify_packet(channel=channel)
        self._write(packet.tobytes())

    def enable_channel(self, channel: int) -> None:
        packet = set_channel_enable_state_packet(channel=channel, enabled=True)
        self._write(packet.tobytes())

    def disable_channel(self, channel: int) -> None:
        packet = set_channel_enable_state_packet(channel=channel, enabled=False)
        self._write(packet.tobytes())

    def get_channel_enable_state(self, channel: int) -> bool:
        packet = request_channel_enable_state_packet(channel=channel)
        self._write(packet.tobytes())
        response, _ = self._read()
        return bool(response.param2 & 0x01)

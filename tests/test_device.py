from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import serial

from thorlabs_apt.device import APTDevice, find_device, list_devices
from thorlabs_apt.packet import (
    MGMSG_HW_GET_INFO,
    APTPacket,
    HardwareInfo,
    get_identify_packet,
    request_hardware_info_packet,
    set_channel_enable_state_packet,
)


@pytest.fixture
def ports(monkeypatch: pytest.MonkeyPatch) -> list[SimpleNamespace]:
    available_ports = [
        SimpleNamespace(
            device="COM3",
            serial_number="12345678",
            manufacturer="Thorlabs",
            product="KDC101",
            vid=0x1313,
            pid=0x2019,
        ),
        SimpleNamespace(
            device="COM4",
            serial_number="87654321",
            manufacturer=None,
            product=None,
            vid=None,
            pid=None,
        ),
    ]
    monkeypatch.setattr("thorlabs_apt.device.serial.tools.list_ports.comports", lambda: available_ports)
    return available_ports


class TestDeviceDiscovery:
    def test_find_device_returns_port_for_matching_serial_number(self, ports: list[SimpleNamespace]) -> None:
        assert find_device("87654321") == "COM4"

    def test_find_device_returns_none_when_serial_number_is_not_found(self, ports: list[SimpleNamespace]) -> None:
        assert find_device("missing") is None

    def test_list_devices_formats_all_enumerated_ports(self, ports: list[SimpleNamespace]) -> None:
        assert list_devices() == (
            "device=COM3, manufacturer=Thorlabs, product=KDC101, vid=0x1313, pid=0x2019,serial_number=12345678\n"
            "device=COM4, manufacturer=None, product=None, vid=None, pid=None,serial_number=87654321"
        )


def data_packet(message_id: int, data: bytes) -> bytes:
    packet = APTPacket(message_id=message_id, destination=0x50, source=0x01)
    packet.data_packet_length = len(data)
    return packet.tobytes()


@pytest.fixture
def serial_port(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    hardware_info = HardwareInfo(serial_number=12345678)
    port = MagicMock()
    port.read.side_effect = [data_packet(MGMSG_HW_GET_INFO, hardware_info.tobytes()), hardware_info.tobytes()]
    port.write.side_effect = lambda data: len(data)
    serial_constructor = MagicMock(return_value=port)
    port.serial_constructor = serial_constructor
    monkeypatch.setattr("thorlabs_apt.device.serial.Serial", serial_constructor)
    return port


@pytest.fixture
def device(serial_port: MagicMock) -> APTDevice:
    return APTDevice("COM3")


class TestAPTDevice:
    def test_initialization_configures_port_and_reads_hardware_info(
        self, device: APTDevice, serial_port: MagicMock
    ) -> None:
        assert device.serial_number == 12345678
        serial_port.serial_constructor.assert_called_once_with(
            port="COM3",
            baudrate=115200,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            rtscts=True,
            timeout=1.0,
        )
        serial_port.reset_input_buffer.assert_called_once()
        serial_port.reset_output_buffer.assert_called_once()
        serial_port.write.assert_called_once_with(request_hardware_info_packet().tobytes())
        serial_port.flush.assert_called_once_with()
        device._hw_info.serial_number = 12345678

    def test_request_writes_packet_and_returns_data_payload(self, device: APTDevice, serial_port: MagicMock) -> None:
        response_data = b"response"
        serial_port.read.side_effect = [data_packet(0x1234, response_data), response_data]
        packet = APTPacket(message_id=0x4321, destination=0x50, source=0x01)

        assert device.request(packet) == response_data
        serial_port.write.assert_called_with(packet.tobytes())

    def test_set_marks_packet_as_data_packet_and_appends_payload(
        self, device: APTDevice, serial_port: MagicMock
    ) -> None:
        packet = APTPacket(message_id=0x4321, destination=0x50, source=0x01)

        device.set(packet, b"data")

        assert serial_port.write.call_args.args == (b"!C\x04\x00\xd0\x01data",)

    @pytest.mark.parametrize(
        ("method_name", "expected_packet"),
        [
            ("identify", get_identify_packet(channel=2)),
            ("enable_channel", set_channel_enable_state_packet(channel=2, enabled=True)),
            ("disable_channel", set_channel_enable_state_packet(channel=2, enabled=False)),
        ],
    )
    def test_channel_commands_write_expected_packets(
        self, device: APTDevice, serial_port: MagicMock, method_name: str, expected_packet: APTPacket
    ) -> None:
        getattr(device, method_name)(2)

        serial_port.write.assert_called_with(expected_packet.tobytes())

    def test_get_channel_enable_state_reads_response_flag(self, device: APTDevice, serial_port: MagicMock) -> None:
        serial_port.read.side_effect = [APTPacket(message_id=0x0212, param2=0x01).tobytes()]

        assert device.get_channel_enable_state(2) is True

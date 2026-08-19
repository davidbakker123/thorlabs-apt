import re
from enum import IntEnum

import pytest

from thorlabs_apt.packet import APTPacket, Buffer, field


class MockBuffer(Buffer):
    value = field[int](0, "<H")
    pair = field[tuple[int, int]](2, "<2H")
    encoded = field[str](
        6,
        "<2H",
        decode=lambda values: "-".join(map(str, values)),
        encode=lambda value: tuple(map(int, value.split("-"))),
    )
    defaulted = field[int](10, "B", default=7)


class Mode(IntEnum):
    READY = 1


class FormattedBuffer(Buffer):
    mode = field[Mode](0, "B", decode=Mode)
    ratio = field[float](1, "<f")
    label = field[str](5, "<3B", decode=lambda _: "label")


@pytest.fixture
def buffer() -> MockBuffer:
    return MockBuffer()


class TestField:
    def test_field_is_returned_when_accessed_on_class(self) -> None:
        assert isinstance(MockBuffer.value, field)

    def test_field_reads_and_writes_scalar_values(self, buffer: MockBuffer) -> None:
        buffer.value = 0x1234

        assert buffer.value == 0x1234
        assert buffer.tobytes()[:2] == b"\x34\x12"

    @pytest.mark.parametrize("value", [(1, 2), [3, 4]])
    def test_field_writes_sequence_values(self, buffer: MockBuffer, value: tuple[int, int] | list[int]) -> None:
        buffer.pair = value

        assert buffer.pair == tuple(value)

    def test_field_applies_decode_and_encode_functions(self, buffer: MockBuffer) -> None:
        buffer.encoded = "12-34"

        assert buffer.encoded == "12-34"
        assert buffer.tobytes()[6:10] == b"\x0c\x00\x22\x00"

    def test_field_applies_default_when_buffer_is_constructed(self, buffer: MockBuffer) -> None:
        assert buffer.defaulted == 7

    def test_field_does_not_override_explicit_value_with_default(self) -> None:
        buffer = MockBuffer(defaulted=9)

        assert buffer.defaulted == 9

    def test_field_wraps_struct_errors_as_value_errors(self, buffer: MockBuffer) -> None:
        with pytest.raises(ValueError, match=r"failed to pack field at offset 0 with format <H: 65536"):
            buffer.value = 65536


class TestBuffer:
    def test_buffer_size_and_length_are_based_on_last_field(self, buffer: MockBuffer) -> None:
        assert buffer.size == 11
        assert len(buffer) == 11

    def test_buffer_accepts_positional_arguments_in_offset_order(self) -> None:
        buffer = MockBuffer(0x1234, (1, 2), "12-34", 9)

        assert buffer.value == 0x1234
        assert buffer.pair == (1, 2)
        assert buffer.encoded == "12-34"
        assert buffer.defaulted == 9

    @pytest.mark.parametrize(
        ("args", "kwargs", "message"),
        [
            ((1, 2, "3-4", 5, 6), {}, "takes at most 4 positional arguments"),
            ((), {"missing": 1}, "unexpected keyword argument(s): missing"),
            ((1,), {"value": 2}, "multiple values for field(s): value"),
        ],
    )
    def test_buffer_rejects_invalid_constructor_arguments(
        self, args: tuple[object, ...], kwargs: dict[str, object], message: str
    ) -> None:
        with pytest.raises(TypeError, match=re.escape(message)):
            MockBuffer(*args, **kwargs)

    def test_buffer_serializes_to_bytes(self) -> None:
        buffer = MockBuffer(value=0x1234, pair=(1, 2), encoded="12-34", defaulted=9)

        assert buffer.tobytes() == b"\x34\x12\x01\x00\x02\x00\x0c\x00\x22\x00\x09"

    def test_buffer_unpack_copies_the_buffer_length_and_ignores_extra_data(self) -> None:
        buffer = MockBuffer.unpack(bytes(range(20)))

        assert len(buffer) == 11
        assert buffer.value == 0x0100
        assert buffer.pair == (0x0302, 0x0504)
        assert buffer.encoded == "1798-2312"
        assert buffer.defaulted == 10

    def test_buffer_unpack_rejects_insufficient_data(self) -> None:
        with pytest.raises(ValueError, match="insufficient data to unpack buffer"):
            MockBuffer.unpack(bytes(10))

    def test_buffer_string_representation_formats_values(self) -> None:
        buffer = FormattedBuffer(Mode.READY, 1.25)

        assert str(buffer) == "FormattedBuffer(mode=Mode<READY:1>, ratio=1.2500, label=label)"


class TestAPTPacket:
    def test_packet_serializes_message_header_fields(self) -> None:
        packet = APTPacket(message_id=0x1234, param1=0x56, param2=0x78, destination=0x50, source=0x01)

        assert len(packet) == APTPacket.MESSAGE_HEADER_SIZE
        assert packet.tobytes() == b"\x34\x12\x56\x78\x50\x01"

    def test_data_packet_length_is_zero_when_destination_data_flag_is_clear(self) -> None:
        packet = APTPacket(param1=0x34, param2=0x12, destination=0x50)

        assert packet.data_packet_length == 0

    def test_data_packet_length_reads_little_endian_parameter_bytes(self) -> None:
        packet = APTPacket(param1=0x34, param2=0x12, destination=0xD0)

        assert packet.data_packet_length == 0x1234

    def test_setting_data_packet_length_marks_destination_and_serializes_value(self) -> None:
        packet = APTPacket(destination=0x50)

        packet.data_packet_length = 0x1234

        assert packet.destination == 0xD0
        assert packet.param1 == 0x34
        assert packet.param2 == 0x12
        assert packet.data_packet_length == 0x1234

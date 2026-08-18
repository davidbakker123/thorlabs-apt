from __future__ import annotations

import inspect
import struct
from enum import IntEnum
from operator import itemgetter
from typing import TYPE_CHECKING, Any, Self, TypeVar, overload

if TYPE_CHECKING:
    from collections.abc import Callable

T = TypeVar("T")


class Buffer:
    __slots__ = ("buff",)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls._mapping = {}
        for name, t in inspect.getmembers(cls, lambda x: isinstance(x, field)):
            cls._mapping[name] = (t.format, t.offset, t.decode, t.default)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.buff = bytearray(self.size)

        ordered_fields = [name for name, _ in sorted(self._mapping.items(), key=lambda item: item[1][1])]

        if len(args) > len(ordered_fields):
            msg = (
                f"{self.__class__.__name__}() takes at most {len(ordered_fields)} "
                f"positional arguments ({len(args)} given)"
            )
            raise TypeError(msg)

        unknown_kwargs = set(kwargs) - set(self._mapping)
        if unknown_kwargs:
            names = ", ".join(sorted(unknown_kwargs))
            msg = f"unexpected keyword argument(s): {names}"
            raise TypeError(msg)

        positional_names = set(ordered_fields[: len(args)])
        duplicate_names = positional_names & set(kwargs)
        if duplicate_names:
            names = ", ".join(sorted(duplicate_names))
            msg = f"multiple values for field(s): {names}"
            raise TypeError(msg)

        for arg, name in zip(args, ordered_fields, strict=False):
            setattr(self, name, arg)

        for name, value in kwargs.items():
            setattr(self, name, value)

        # Set defaults for fields that weren't explicitly provided
        for name, (_, _, _, default) in self._mapping.items():
            if default is not None and name not in kwargs and name not in ordered_fields[: len(args)]:
                setattr(self, name, default)

    def __len__(self) -> int:
        return len(self.buff)

    def __str__(self) -> str:
        attrs = []
        for name, (format, _, decode, _) in sorted(self._mapping.items(), key=lambda item: item[1][1]):
            value = getattr(self, name)
            hex_width = struct.calcsize(format) * 2
            if isinstance(value, IntEnum):
                attrs += [f"{name}={value.__class__.__name__}<{value.name}:{value.value}>"]
            elif isinstance(value, str) or decode:
                attrs += [f"{name}={value}"]
            elif isinstance(value, float):
                attrs += [f"{name}={value:.4f}"]
            else:
                attrs += [f"{name}=0x{value:0{hex_width}x}"]
        attrs_str = ", ".join(attrs)
        return f"{self.__class__.__name__}({attrs_str})"

    @classmethod
    def unpack(cls, data: bytes | bytearray) -> Self:
        instance = cls()
        if len(data) < len(instance):
            msg = "insufficient data to unpack buffer"
            raise ValueError(msg)
        instance.buff[:] = data[: len(instance)]
        return instance

    def tobytes(self) -> bytes:
        return bytes(self.buff)

    @property
    def size(self) -> int:
        if not self._mapping:
            return 0
        vals = self._mapping.values()
        format, offset, _, _ = max(vals, key=itemgetter(1))
        return offset + struct.calcsize(format)


class field[T]:
    def __init__(
        self,
        offset: int,
        format: str,
        decode: Callable[[Any], T] | None = None,
        encode: Callable[[Any], Any] | None = None,
        default: Any = None,
    ) -> None:
        self.offset = offset
        self.format = format
        self.decode = decode
        self.encode = encode
        self.default = default

    @overload
    def __get__(self, instance: None, owner: type) -> field[T]: ...

    @overload
    def __get__(self, instance: Any, owner: type) -> T: ...

    def __get__(self, instance: Buffer | None, owner):
        if instance is None:
            return self

        raw_data = struct.unpack_from(self.format, instance.buff, self.offset)

        if len(raw_data) == 1:
            raw_data = raw_data[0]

        if self.decode:
            return self.decode(raw_data)
        return raw_data

    def __set__(self, instance: Buffer, value: Any) -> None:
        if self.encode:
            value = self.encode(value)
        try:
            if isinstance(value, (tuple, list)):
                struct.pack_into(self.format, instance.buff, self.offset, *value)
                return

            struct.pack_into(self.format, instance.buff, self.offset, value)
        except struct.error as exc:
            msg = f"failed to pack field at offset {self.offset} with format {self.format}: {value!r}"
            raise ValueError(msg) from exc


class APTPacket(Buffer):
    MESSAGE_HEADER_SIZE = 6

    message_id = field[int](0, "<H")
    param1 = field[int](2, "B")
    param2 = field[int](3, "B")
    destination = field[int](4, "B")
    source = field[int](5, "B")

    @property
    def data_packet_length(self) -> int:
        if self.destination & 0x80:
            return struct.unpack_from("<H", self.buff, 2)[0]
        return 0

    @data_packet_length.setter
    def data_packet_length(self, value: int) -> None:
        self.destination = self.destination | 0x80
        struct.pack_into("<H", self.buff, 2, value)


class HardwareInfo(Buffer):
    serial_number = field[int](0, "<i", int)
    model_number = field[str](4, "8c", decode=lambda c: "".join(i.decode("ascii") for i in c).strip())
    hw_type = field[int](12, "<H")
    firmware_version = field[str](14, "4B", decode=lambda b: ".".join(map(str, b)))
    hardware_version = field[int](78, "<H")
    mod_state = field[int](80, "<H")
    n_channels = field[int](82, "<H")


MGMSG_HW_REQ_INFO = 0x0005
MGMSG_HW_GET_INFO = 0x0006
MGMSG_MOD_IDENTIFY = 0x0223

MGMSG_MOD_SET_CHANENABLESTATE = 0x0210
MGMSG_MOD_REQ_CHANENABLESTATE = 0x0211


def request_hardware_info_packet(source: int = 0x01, destination: int = 0x50) -> APTPacket:
    return APTPacket(MGMSG_HW_REQ_INFO, 0x00, 0x00, destination, source)


def get_identify_packet(channel: int = 0x01, source: int = 0x01, destination: int = 0x50) -> APTPacket:
    return APTPacket(MGMSG_MOD_IDENTIFY, channel, 0x00, destination, source)


def request_channel_enable_state_packet(channel: int = 0x01, source: int = 0x01, destination: int = 0x50) -> APTPacket:
    return APTPacket(MGMSG_MOD_REQ_CHANENABLESTATE, channel, 0x00, destination, source)


def set_channel_enable_state_packet(
    channel: int, enabled: bool, source: int = 0x01, destination: int = 0x50
) -> APTPacket:
    enable_value = 0x01 if enabled else 0x02
    return APTPacket(MGMSG_MOD_SET_CHANENABLESTATE, channel, enable_value, destination, source)

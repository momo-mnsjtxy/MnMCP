"""Offline framing fixtures for the exported Minecraft packet handler."""

import asyncio

import pytest

from mcp_mc.packet_handler import MCPPocketHandler


@pytest.fixture
def handler():
    return MCPPocketHandler(client=None)


def parse(handler, data):
    return asyncio.run(handler.parse_packet(data))


@pytest.mark.parametrize(
    ("wire", "packet_id", "payload"),
    [
        (b"\x01\x00", 0, b""),
        (b"\x04\x01abc", 1, b"abc"),
        (b"\x05\x80\x01abc", 128, b"abc"),
        (b"\x80\x01\x7f" + b"x" * 127, 127, b"x" * 127),
        (b"\x05\xff\xff\xff\xff\x07", 2**31 - 1, b""),
    ],
)
def test_golden_frames_preserve_complete_payload(handler, wire, packet_id, payload):
    packet = parse(handler, wire)
    assert packet is not None
    assert packet.packet_id == packet_id
    assert packet.data == payload
    assert packet.direction == "in"
    assert handler.encode_packet(packet_id, payload) == wire


@pytest.mark.parametrize("packet_id", [0, 1, 127, 128, 16383, 16384, 2**31 - 1])
@pytest.mark.parametrize("size", [0, 1, 126, 127, 128, 255, 4096])
def test_round_trip_across_varint_boundaries(handler, packet_id, size):
    payload = (bytes(range(256)) * (size // 256 + 1))[:size]
    packet = parse(handler, handler.encode_packet(packet_id, payload))
    assert packet is not None
    assert (packet.packet_id, packet.data) == (packet_id, payload)


@pytest.mark.parametrize(
    "wire",
    [
        b"",
        b"\x80",
        b"\x00",
        b"\x02\x01",
        b"\x01\x80",
        b"\x01\x01x",
        b"\x01\x01\x01\x02",
        b"\x80\x80\x80\x80\x80\x00",
        b"\x01\xff\xff\xff\xff\x07",
        b"\xff\xff\xff\xff\x0f",
        b"\x05\xff\xff\xff\xff\x0f",
        b"\x05\x80\x80\x80\x80\x10",
    ],
)
def test_incomplete_empty_trailing_and_invalid_frames_are_rejected(handler, wire):
    assert parse(handler, wire) is None


def test_packet_limit_is_inclusive_and_applies_both_directions(handler):
    # A small fixture limit exercises the production check without large buffers.
    handler.MAX_PACKET_SIZE = 8
    good = handler.encode_packet(128, b"123456")
    assert parse(handler, good).data == b"123456"
    with pytest.raises(ValueError, match="large"):
        handler.encode_packet(128, b"1234567")
    assert parse(handler, b"\x09\x80\x011234567") is None
    assert parse(handler, b"\x09") is None


@pytest.mark.parametrize(
    "wire", [b"\xff\xff\xff\xff\x0f", b"\x80\x80\x80\x80\x10", b"\x80" * 5, b"\x80"]
)
def test_invalid_unsigned_varints_are_rejected(handler, wire):
    with pytest.raises(ValueError):
        handler._read_varint(wire, 0)


@pytest.mark.parametrize("offset", [-1, 1, 99])
def test_invalid_varint_offsets_are_rejected(handler, offset):
    with pytest.raises(ValueError):
        handler._read_varint(b"\x00", offset)


@pytest.mark.parametrize("value", [2**31, 2**35, 1.5, True])
def test_invalid_varint_encoder_inputs_are_rejected(handler, value):
    with pytest.raises(ValueError):
        handler._write_varint(value)


def test_negative_varint_encoder_input_is_rejected(handler):
    # The old loop never terminated for negative values. Run this regression
    # only after implementing the bound, rather than hang a baseline test run.
    with pytest.raises(ValueError):
        handler._write_varint(-1)


def test_negative_packet_id_is_rejected(handler):
    with pytest.raises(ValueError):
        handler.encode_packet(-1, b"payload")


@pytest.mark.parametrize("text", ["", "hello", "中文🙂", "x" * 128])
def test_string_round_trip_counts_bytes(handler, text):
    encoded = handler._write_string(text)
    decoded, offset = handler._read_string(b"prefix" + encoded + b"suffix", 6)
    assert decoded == text
    assert offset == 6 + len(encoded)


@pytest.mark.parametrize(
    "wire", [b"\x04abc", b"\x02\xe4", b"\x01\xff", b"\xff\xff\xff\xff\x0f"]
)
def test_truncated_or_invalid_strings_are_rejected(handler, wire):
    with pytest.raises((ValueError, UnicodeDecodeError)):
        handler._read_string(wire, 0)

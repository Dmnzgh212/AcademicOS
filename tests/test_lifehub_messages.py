import pytest

from academicos.lifehub.messages import MAX_IO_BYTES, decode_message, encode_message


def test_message_byte_limits_apply_to_raw_and_canonical_json():
    assert decode_message(b'"' + b'x' * (MAX_IO_BYTES - 2) + b'"') == 'x' * (MAX_IO_BYTES - 2)
    with pytest.raises(ValueError, match="IO limit"):
        decode_message(b' ' * MAX_IO_BYTES + b'0')
    # Compact exponent syntax can expand into a longer canonical float spelling.
    with pytest.raises(ValueError, match="IO limit"):
        decode_message(b'[' + b'1e100,' * 10000 + b'0]')


def test_host_message_depth_boundary_and_cycles():
    value = 0
    for _ in range(64):
        value = [value]
    assert decode_message(encode_message(value)) == value
    with pytest.raises(ValueError, match="depth limit"):
        encode_message([value])
    cycle = []
    cycle.append(cycle)
    with pytest.raises(ValueError, match="depth limit"):
        encode_message(cycle)

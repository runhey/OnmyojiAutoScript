"""
The encoder of the bit2 format: the C encoder when the accelerator of
oas_speedup is installed, the pure Python encoder otherwise.

Importing this module is what looks for the accelerator (see
oas.speedup): it scans the site-packages, loads the installed
oas_speedup, builds its library on first use and checks its interface
version. Anything that fails on the way, a machine without a compiler
included, falls back to bit2coding_encode_python, so a caller always gets
an encoder. The reason of a fallback is in oas.speedup.ERRORS['bit2'].

The two implementations do not emit the same bytes (the parse of the C one
is never larger), both decode back with decode_bit2() of
bit2coding_decode.py, which is the reference of the format.
"""
from oas.ext.algorithm.bit2coding.bit2coding_encode_python import (
    _encode_value_check, encode_bit2 as encode_bit2_python
)
from oas.ext.algorithm.vint import encode_vint
try:
    from oas.speedup import accelerator
except ImportError:
    def accelerator(_name):
        return None

_bit2 = accelerator('bit2')

if _bit2 is not None:
    def encode_bit2(data, ext8=False):
        """
        Encode data to bit2 format with a vint count prefix (see encode_vint):
        [count]: number of values
        [stream]: bit2 compressed values, written by the C encoder

        Args:
            data (list[int] | deque[int]): Data to encode
            ext8 (bool): True to enable ext8 support to allow 4/5/6/7 as literal values

        Returns:
            bytes: Encoded data
        """
        _encode_value_check(data, ext8)
        return encode_vint(len(data)) + bytes(_bit2.encode_bit2_stream(data, ext8=ext8))
else:
    # no accelerator, the pure Python encoder is the implementation of the
    # very same contract
    encode_bit2 = encode_bit2_python

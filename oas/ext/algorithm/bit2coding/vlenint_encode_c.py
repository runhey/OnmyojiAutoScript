"""
The vlenint encoder: the C one when the accelerator of oas_speedup is
installed, the pure Python one otherwise.

Importing this module looks for the accelerator, like
bit2coding_encode_c.py. The vlenint encoding is the bit2 encoding of the
byte lengths of the values plus the values themselves, so the two encoders
share the library of the bit2 module, see oas_speedup/README.md. The
format itself is documented in vlenint_encode_python.py.
"""
from oas.ext.algorithm.bit2coding.vlenint_encode_python import (
    encode_vlenint as encode_vlenint_python, vlenint_value_check
)
try:
    from oas.speedup import accelerator
except ImportError:
    def accelerator(_name):
        return None

_bit2 = accelerator('bit2')

if _bit2 is not None:
    def encode_vlenint(data):
        """
        Encode numbers to variable length int, the sections of the format
        are documented in vlenint_encode_python.py

        Args:
            data (Iterable[int]): list of values to encode, 0 ~ 2^32 - 1

        Returns:
            bytes: vlenint encoded data

        Raises:
            ValueError: If a value is out of range, or the encoder rejects the input
        """
        data = list(data)
        vlenint_value_check(data)
        return _bit2.encode_vlenint(data)
else:
    # no accelerator, the pure Python encoder is the implementation of the
    # very same contract
    encode_vlenint = encode_vlenint_python

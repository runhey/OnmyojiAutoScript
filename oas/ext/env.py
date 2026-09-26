"""Environment constants shared across the OAS project.

Counterpart of ``alasio/ext/env.py`` (Alasio): the project root constant.
Only ``OAS_ROOT`` is provided here so far; the Alasio module also carries
OS detection flags and ``PROJECT_ROOT``, which can be added when a
migrated module needs them.
"""
import os

# Project root: the directory that contains the oas/ package.
# ``__file__`` is <root>/oas/ext/env.py, so three dirname() hops
# land on <root> (matches Alasio's PathStr.new(__file__).uppath(3)).
OAS_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""
Tests for alasio/ext/path/validate.py.

validate_filename() is pure string validation, validate_resolve_filepath()
runs on the in-memory fake filesystem.
"""
import os
import re

import pytest

from oas.ext.path.validate import validate_filename, validate_filepath, validate_resolve_filepath
from oas.testing.filesystem import fs  # noqa: F401


class TestValidateFilename:
    """Tests for validate_filename()."""

    # --- Check 1: Basic sanity ---
    @pytest.mark.parametrize("invalid_name", [
        None,
        123,
        [],
        {},
    ])
    def test_non_string_names_raise_value_error(self, invalid_name):
        """Non-string names should be rejected with the type error message."""
        with pytest.raises(ValueError, match="Filename should be a string"):
            validate_filename(invalid_name)

    def test_empty_name_raises_value_error(self):
        """Empty names should be rejected with the emptiness error message."""
        with pytest.raises(ValueError, match="Filename cannot be empty"):
            validate_filename("")

    # --- Check 2: Length ---
    def test_name_too_long_raises_value_error(self):
        """Names longer than 255 chars should be rejected."""
        with pytest.raises(ValueError, match="Filename is too long, length should <= 255"):
            validate_filename("a" * 256)

    # --- Check 3: Illegal characters ---
    @pytest.mark.parametrize("char", ['\\', '/', ':', '*', '?', '"', '<', '>', '|'])
    def test_illegal_characters_raise_value_error(self, char):
        """Names containing illegal characters should be rejected."""
        message = f'Filename should not contain character: "{char}"'
        with pytest.raises(ValueError, match=re.escape(message)):
            validate_filename(f"my{char}file.txt")

    # --- Check 3: Control characters ---
    @pytest.mark.parametrize("char_ord", [0, 1, 9, 10, 127])
    def test_control_characters_raise_value_error(self, char_ord):
        """Names containing control characters should be rejected."""
        char = chr(char_ord)
        message = f"Filename should not contain control character (ASCII: {char_ord})"
        with pytest.raises(ValueError, match=re.escape(message)):
            validate_filename(f"file-with-{char}-name.txt")

    # --- Check 4: Directory pointers ---
    @pytest.mark.parametrize("invalid_name", [".", ".."])
    def test_directory_pointers_raise_value_error(self, invalid_name):
        """`.` and `..` should be reported as directory pointers."""
        with pytest.raises(ValueError, match="Filename cannot be directory pointer"):
            validate_filename(invalid_name)

    # --- Check 5: Start/end characters ---
    @pytest.mark.parametrize("invalid_name", [
        " CON",
        " LPT1.txt",
        " LPT1.abc.txt",
        " starts-with-space.txt",
    ])
    def test_name_starting_with_space_raises_value_error(self, invalid_name):
        """Names starting with a space should be rejected."""
        with pytest.raises(ValueError, match="Filename cannot start with a <space>"):
            validate_filename(invalid_name)

    @pytest.mark.parametrize("invalid_name", [
        "CON ",
        "CON. ",
        "ends-with-space.txt ",
    ])
    def test_name_ending_with_space_raises_value_error(self, invalid_name):
        """Names ending with a space should be rejected."""
        with pytest.raises(ValueError, match="Filename cannot end with a <space>"):
            validate_filename(invalid_name)

    @pytest.mark.parametrize("invalid_name", [
        "CON.",
        "CON .",
        "LPT1.txt.",
        "ends-with-dot.txt.",
    ])
    def test_name_ending_with_dot_raises_value_error(self, invalid_name):
        """Names ending with a dot should be rejected."""
        with pytest.raises(ValueError, match="Filename cannot end with a <dot>"):
            validate_filename(invalid_name)

    # --- Check 6: NTFS metadata names ---
    @pytest.mark.parametrize("invalid_name", ["$MFT", "$logfile"])
    def test_ntfs_metadata_names_raise_value_error(self, invalid_name):
        """NTFS metadata names should be rejected case-insensitively."""
        with pytest.raises(ValueError, match="Filename cannot be NTFS metadata name"):
            validate_filename(invalid_name)

    # --- Check 6: Reserved system names ---
    @pytest.mark.parametrize("invalid_name", [
        "CON",
        "con",
        "PRN.txt",
        "lpt1.doc",
        "COM5.zip",
        "NUL",
        "aux.json",
        "LPT1.txt",
        "LPT1..txt",
        "LPT1.abc.txt",
        # Windows strips trailing dots and spaces when resolving device names
        "LPT1 .txt",
        "LPT1 .abc.txt",
    ])
    def test_reserved_system_names_raise_value_error(self, invalid_name):
        """Reserved system names like `CON` or `LPT1` should be rejected."""
        with pytest.raises(ValueError, match="Filename cannot be reserved system name"):
            validate_filename(invalid_name)

    # --- Check 7: Byte length and encoding ---
    def test_byte_length_too_long_raises_value_error(self):
        """Names exceeding 255 UTF-8 bytes should be rejected."""
        with pytest.raises(ValueError, match="Filename is too long, byte_length should <= 255"):
            validate_filename("a" * 253 + "€")

    def test_invalid_encoding_raises_value_error(self):
        """Names that cannot be UTF-8 encoded should be rejected."""
        with pytest.raises(ValueError, match="Filename contains invalid characters that cannot be UTF-8 encoded"):
            validate_filename(f"malformed-{chr(0xD800)}-string.txt")

    # --- Valid names ---
    @pytest.mark.parametrize("valid_name", [
        "file.txt",
        "document-1.docx",
        "image.jpg",
        "a" * 255,  # Max length
        "€" * 85,  # 255 bytes in UTF-8, multibyte name
        "中文ファイル名.txt",
        # Names that merely look like reserved names are still valid
        "CON2.txt",  # Only exact basenames are reserved
        "COM10.zip",  # Only COM1-COM9 are reserved
        "$MFT2",  # Only exact NTFS metadata names are reserved
        ".gitignore",  # Dotfiles are valid
        "..git",
    ])
    def test_valid_names_do_not_raise_exception(self, valid_name):
        """
        Verifies that valid names pass through validation without exception.
        """
        try:
            validate_filename(valid_name)
        except ValueError:
            pytest.fail(f"validate_filename('{valid_name}') raised an unexpected ValueError.")


class TestValidateFilepath:
    """Tests for validate_filepath()."""

    # --- Check 1: Basic sanity ---
    @pytest.mark.parametrize("invalid_path", [
        None,
        123,
        [],
        {},
    ])
    def test_non_string_paths_raise_value_error(self, invalid_path):
        """Non-string paths should be rejected with the type error message."""
        with pytest.raises(ValueError, match="Path should be a string"):
            validate_filepath(invalid_path)

    def test_empty_path_raises_value_error(self):
        """Empty paths should be rejected with the emptiness error message."""
        with pytest.raises(ValueError, match="Path cannot be empty"):
            validate_filepath("")

    # --- Check 2: Overall structure ---
    @pytest.mark.parametrize("invalid_path", [
        "/absolute.txt",
        "\\absolute.txt",
    ])
    def test_absolute_paths_raise_value_error(self, invalid_path):
        """Paths starting with a slash should be rejected on all platforms."""
        with pytest.raises(ValueError, match="Path cannot be absolute or start with a slash"):
            validate_filepath(invalid_path)

    def test_drive_absolute_path_raises_value_error(self):
        """
        Drive-absolute paths should be rejected on all platforms.

        On Windows they are detected as absolute, on POSIX the drive
        component is rejected for containing a colon.
        """
        with pytest.raises(ValueError):
            validate_filepath("C:\\absolute.txt")

    def test_overall_length_raises_value_error(self):
        """Paths longer than 4096 chars should be rejected."""
        with pytest.raises(ValueError, match="Path is too long, length should <= 4096"):
            validate_filepath("/".join(["a"] * 2049))

    # --- Check 3: Empty components ---
    @pytest.mark.parametrize("invalid_path", [
        "a//b.txt",
        "a/",
        "a/b/",
        "a///b",
    ])
    def test_empty_components_raise_value_error(self, invalid_path):
        """Empty components from repeated or trailing slashes should be rejected."""
        with pytest.raises(ValueError, match="Path component cannot be empty"):
            validate_filepath(invalid_path)

    # --- Check 3: Component length ---
    @pytest.mark.parametrize("invalid_path", [
        "a/" + "b" * 256,
        "b" * 256,
    ])
    def test_component_too_long_raises_value_error(self, invalid_path):
        """Components longer than 255 chars should be rejected."""
        with pytest.raises(ValueError, match="Path component is too long, length should <= 255"):
            validate_filepath(invalid_path)

    # --- Check 3: Illegal characters ---
    @pytest.mark.parametrize("char", [':', '*', '?', '"', '<', '>', '|'])
    def test_illegal_characters_raise_value_error(self, char):
        """Components containing illegal characters should be rejected."""
        message = f'Path component should not contain character: "{char}"'
        with pytest.raises(ValueError, match=re.escape(message)):
            validate_filepath(f"a/b{char}file.txt")

    # --- Check 3: Control characters ---
    @pytest.mark.parametrize("char_ord", [0, 1, 9, 10, 127])
    def test_control_characters_raise_value_error(self, char_ord):
        """Components containing control characters should be rejected."""
        char = chr(char_ord)
        message = f"Path component should not contain control character (ASCII: {char_ord})"
        with pytest.raises(ValueError, match=re.escape(message)):
            validate_filepath(f"a/b{char}c.txt")

    # --- Check 4: Directory pointers ---
    @pytest.mark.parametrize("invalid_path", [
        ".",
        "..",
        "a/.",
        "a/..",
    ])
    def test_directory_pointers_raise_value_error(self, invalid_path):
        """`.` and `..` components should be reported as directory pointers."""
        with pytest.raises(ValueError, match="Path component cannot be directory pointer"):
            validate_filepath(invalid_path)

    # --- Check 5: Start/end characters ---
    @pytest.mark.parametrize("invalid_path", [
        " starts-with-space.txt",
        " CON",
        " LPT1.txt",
        " LPT1.abc.txt",
    ])
    def test_component_starting_with_space_raises_value_error(self, invalid_path):
        """Components starting with a space should be rejected."""
        with pytest.raises(ValueError, match="Path component cannot start with a <space>"):
            validate_filepath(invalid_path)

    @pytest.mark.parametrize("invalid_path", [
        "dir/ends-with-space.txt ",
        "CON ",
        "CON. ",
    ])
    def test_component_ending_with_space_raises_value_error(self, invalid_path):
        """Components ending with a space should be rejected."""
        with pytest.raises(ValueError, match="Path component cannot end with a <space>"):
            validate_filepath(invalid_path)

    @pytest.mark.parametrize("invalid_path", [
        "dir/ends-with-dot.txt.",
        "CON.",
        "CON .",
        "LPT1.txt.",
    ])
    def test_component_ending_with_dot_raises_value_error(self, invalid_path):
        """Components ending with a dot should be rejected."""
        with pytest.raises(ValueError, match="Path component cannot end with a <dot>"):
            validate_filepath(invalid_path)

    # --- Check 6: NTFS metadata names ---
    @pytest.mark.parametrize("invalid_path", [
        "$MFT",
        "dir/$LogFile",
    ])
    def test_ntfs_metadata_names_raise_value_error(self, invalid_path):
        """NTFS metadata names should be rejected case-insensitively."""
        with pytest.raises(ValueError, match="Path component cannot be NTFS metadata name"):
            validate_filepath(invalid_path)

    # --- Check 6: Reserved system names ---
    @pytest.mark.parametrize("invalid_path", [
        "CON",
        "con.txt",
        "a/LPT1.doc",
        "COM5.zip",
        "NUL",
        "aux.json",
        "LPT1.txt",
        "LPT1..txt",
        "LPT1.abc.txt",
        # Windows strips trailing dots and spaces when resolving device names
        "LPT1 .txt",
        "LPT1 .abc.txt",
    ])
    def test_reserved_system_names_raise_value_error(self, invalid_path):
        """Reserved system names like `CON` or `LPT1` should be rejected."""
        with pytest.raises(ValueError, match="Path component cannot be reserved system name"):
            validate_filepath(invalid_path)

    # --- Check 7: Byte length and encoding ---
    @pytest.mark.parametrize("invalid_path", [
        "dir/" + "a" * 253 + "€",  # Char length is 254, but byte length is 256
        "€" * 86,  # Char length is 86, but byte length is 258
    ])
    def test_component_byte_length_too_long_raises_value_error(self, invalid_path):
        """Components exceeding 255 UTF-8 bytes should be rejected."""
        with pytest.raises(ValueError, match="Path component is too long, byte_length should <= 255"):
            validate_filepath(invalid_path)

    def test_invalid_encoding_raises_value_error(self):
        """Components that cannot be UTF-8 encoded should be rejected."""
        with pytest.raises(ValueError, match="Path component contains invalid characters that cannot be UTF-8 encoded"):
            validate_filepath(f"malformed-{chr(0xD800)}-string.txt")
        with pytest.raises(ValueError, match="Path component contains invalid characters that cannot be UTF-8 encoded"):
            validate_filepath(f"dir/malformed-{chr(0xD800)}.txt")

    # --- Valid paths ---
    @pytest.mark.parametrize("valid_path", [
        "file.txt",
        "dir/file.txt",
        "dir/sub/file.tar.gz",
        "dir\\sub\\file.txt",  # Backslash is treated as a separator
        "a" * 255,  # Max component length
        "€" * 85,  # 255 bytes in UTF-8, multibyte component
        "中文/ファイル.txt",
        "/".join(["a" * 255] * 16),  # 4095 chars, max overall length
        # Names that merely look like reserved names are still valid
        "CON2.txt",  # Only exact basenames are reserved
        "COM10.zip",  # Only COM1-COM9 are reserved
        "$MFT2",  # Only exact NTFS metadata names are reserved
        ".gitignore",  # Dotfiles are valid
        "..git",
    ])
    def test_valid_paths_do_not_raise_exception(self, valid_path):
        """
        Verifies that valid paths pass through validation without exception.
        """
        try:
            validate_filepath(valid_path)
        except ValueError:
            pytest.fail(f"validate_filepath('{valid_path}') raised an unexpected ValueError.")


class TestValidateResolveFilepath:
    """Tests for validate_resolve_filepath() on the in-memory fake filesystem."""

    @pytest.fixture
    def temp_fs(self, fs):
        """
        Create a controlled in-memory filesystem environment for testing
        path resolution and traversal.

        Structure created:
        {root}/
        ├── safe_dir/
        │   ├── existing_file.txt
        │   └── link_to_secret -> ../outside_dir/secret.txt
        └── outside_dir/
            └── secret.txt

        Yields:
            dict[str, str]: safe_dir, outside_dir and symlink_path
        """
        root = 'C:/test_root' if os.name == 'nt' else '/test_root'
        safe_dir = f'{root}/safe_dir'
        outside_dir = f'{root}/outside_dir'
        fs.create_file(f'{safe_dir}/existing_file.txt', contents='safe content')
        fs.create_file(f'{outside_dir}/secret.txt', contents='secret content')
        os.symlink(f'{outside_dir}/secret.txt', f'{safe_dir}/link_to_secret')

        yield {
            'safe_dir': safe_dir,
            'outside_dir': outside_dir,
            'symlink_path': f'{safe_dir}/link_to_secret',
        }

    @pytest.mark.parametrize("invalid_path", [
        # --- Advanced Traversal & Obfuscation ---
        "a/b/c/../../../..",  # Resolves to one level above safe_dir root
        "a/./b/../c/../../..",  # Mixed '.' and '..'
        "a\\b/..\\../..",  # Mixed path separators (Windows/Linux)

        # --- URL Encoding (Simulated) ---
        # In a real web app, these would be decoded before hitting the function,
        # so we test the decoded form.
        # "..%2f..%2fetc%2fpasswd",  # Simulating decoded URL-encoded slash
        # "..%5c..%5cboot.ini",  # Simulating decoded URL-encoded backslash

        # --- Null Byte Injection ---
        # Our string-level validation should catch this.
        "a/b/c\0/real_file.txt",
        "a/b/c.txt\0.log",

        # --- Filename & Extension Obfuscation (Windows-specific behavior) ---
        "CON.txt",  # Reserved name with extension
        "LPT1.anything",  # Reserved name with extension
        "file.txt.",  # Trailing dot
        "file.txt ",  # Trailing space
        " file.txt",  # Leading space

        # --- Deeply Nested Paths (within character limits) ---
        # This tests for potential performance issues or recursion limits,
        # though our function is iterative.
        "/".join(["d"] * 50) + "/../../" + "../outside_dir/secret.txt",

        # --- Path Normalization Edge Cases ---
        "safe_dir/../safe_dir/../outside_dir/secret.txt",  # Weaving in and out

        # --- Non-standard but potentially problematic ---
        # "a/b~1.txt",  # Short filename notation (should be valid but good check)
        "a::$DATA",  # NTFS Alternate Data Streams (colon is blocked)

        # --- Unicode Homoglyph/Lookalike Attacks ---
        # Simulating a user trying to create a file that looks like another.
        # Our function allows unicode, but this is a reminder of this attack class.
        # The validation should still pass if the characters are valid.
        # e.g., "ｓcript.js" (full-width) vs "script.js" (half-width)
        # No direct test here as our validator correctly allows valid Unicode,
        # but it's an important attack vector to be aware of at a higher level.
    ])
    def test_invalid_paths_raise_value_error(self, temp_fs, invalid_path):
        """A comprehensive test for a wide range of invalid and malicious paths."""
        with pytest.raises(ValueError):
            validate_resolve_filepath(temp_fs["safe_dir"], invalid_path)

    def test_symlink_traversal_raises_value_error(self, temp_fs):
        """A symlink pointing outside the safe directory should be rejected."""
        with pytest.raises(ValueError, match="Path traversal detected"):
            validate_resolve_filepath(temp_fs["safe_dir"], "link_to_secret")

    def test_a_root_reached_through_a_link(self, fs):
        """A root that is itself reached through a link is not a traversal.

        The combined path is resolved, so the root has to be resolved as well:
        a temporary directory of macOS lives under the "/var" link and a
        junction of Windows may hold anything, and every path of such a root
        used to be reported as a traversal of the directory it really is.
        """
        root = 'C:/test_root' if os.name == 'nt' else '/test_root'
        fs.create_dir(f'{root}/real/safe_dir')
        fs.create_file(f'{root}/real/safe_dir/file.txt', contents='content')
        fs.create_file(f'{root}/outside/secret.txt', contents='secret')
        os.symlink(f'{root}/real', f'{root}/junction')
        # the root is named through the link, the resolved path is inside the
        # directory the root really is
        assert validate_resolve_filepath(
            f'{root}/junction/safe_dir', 'file.txt'
        ) == f'{root}/real/safe_dir/file.txt'
        # a link of the tree that points outside of it is still refused
        os.symlink(f'{root}/outside/secret.txt', f'{root}/real/safe_dir/link_to_secret')
        with pytest.raises(ValueError, match="Path traversal detected"):
            validate_resolve_filepath(f'{root}/junction/safe_dir', 'link_to_secret')

    @pytest.mark.parametrize("valid_path, expected_suffix", [
        ("file.txt", "file.txt"),
        ("new_dir/new_file.txt", "new_dir/new_file.txt"),
        # ("a/b/../c/file.txt", "a/c/file.txt"),
        # ("./a/./b/file.txt", "a/b/file.txt"),
    ])
    def test_valid_paths_return_correct_absolute_path(self, temp_fs, valid_path, expected_suffix):
        """Valid paths should resolve to the absolute path inside the safe dir."""
        safe_dir = temp_fs["safe_dir"]
        try:
            resolved_path = validate_resolve_filepath(safe_dir, valid_path)
            assert os.path.isabs(resolved_path)
            assert resolved_path.startswith(safe_dir)
            expected_path = f'{safe_dir}/{expected_suffix}'
            assert resolved_path == expected_path
        except ValueError as e:
            pytest.fail(f"validate_and_resolve_path('{valid_path}') raised an unexpected ValueError: {e}")

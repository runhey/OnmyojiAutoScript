"""
Tests for oas/testing/preview/parse_unittest.py.

The parser returns the full test source and the UnittestImage bindings; it never
imports the test module. Function-level errors live on UnittestImage.error,
file-level errors live on ParsedUnittest.errors.
"""

from oas.testing.filesystem import fs  # noqa: F401
from oas.testing.preview.parse_unittest import (
    ParsedUnittest,
    UnittestImage,
    parse_test_file,
    parse_test_source,
)


class TestParseImages:
    def test_class_images(self):
        source = '''\
"""Module docstring."""

from oas.testing.screenshot import image


class TestFoo:
    """Class docstring."""

    @image("a.webp")
    def test_one(self):
        print("draft")
        assert 1 == 1

    def helper(self):
        return 1

    @image("b.webp")
    def test_two(self):
        assert 2 == 2
'''
        assert parse_test_source(source, filename='test_sample.py') == ParsedUnittest(
            source=source,
            images=[
                UnittestImage(
                    class_name='TestFoo',
                    func_name='test_one',
                    start_line=9,
                    end_line=12,
                    image='a.webp',
                    error='',
                ),
                UnittestImage(
                    class_name='TestFoo',
                    func_name='test_two',
                    start_line=17,
                    end_line=19,
                    image='b.webp',
                    error='',
                ),
            ],
            errors=[],
        )

    def test_module_level_test_has_no_class_name(self):
        source = """\
from oas.testing.screenshot import image

@image("a.webp")
def test_a():
    assert True
"""
        assert parse_test_source(source) == ParsedUnittest(
            source=source,
            images=[
                UnittestImage(
                    class_name='',
                    func_name='test_a',
                    start_line=3,
                    end_line=5,
                    image='a.webp',
                    error='',
                ),
            ],
            errors=[],
        )

    def test_test_without_image_is_not_listed(self):
        source = """\
def test_a():
    pass
"""
        assert parse_test_source(source) == ParsedUnittest(
            source=source, images=[], errors=[]
        )

    def test_helper_function_is_not_listed(self):
        source = """\
def helper():
    pass
"""
        assert parse_test_source(source) == ParsedUnittest(
            source=source, images=[], errors=[]
        )

    def test_class_without_tests_has_no_images(self):
        source = '''\
class TestEmpty:
    """doc"""
    value = 1
'''
        assert parse_test_source(source) == ParsedUnittest(
            source=source, images=[], errors=[]
        )

    def test_images_are_sorted_by_start_line(self):
        source = """\
class TestA:
    @image("a.webp")
    def test_a(self):
        pass


@image("b.webp")
def test_b():
    pass
"""
        assert parse_test_source(source) == ParsedUnittest(
            source=source,
            images=[
                UnittestImage(
                    class_name='TestA',
                    func_name='test_a',
                    start_line=2,
                    end_line=4,
                    image='a.webp',
                    error='',
                ),
                UnittestImage(
                    class_name='',
                    func_name='test_b',
                    start_line=7,
                    end_line=9,
                    image='b.webp',
                    error='',
                ),
            ],
            errors=[],
        )

    def test_decorated_test_starts_at_the_first_decorator(self):
        source = """\
from oas.testing.screenshot import image

@decorator
@image(
    "a.webp"
)
def test_a():
    pass
"""
        assert parse_test_source(source) == ParsedUnittest(
            source=source,
            images=[
                UnittestImage(
                    class_name='',
                    func_name='test_a',
                    start_line=3,
                    end_line=8,
                    image='a.webp',
                    error='',
                ),
            ],
            errors=[],
        )

    def test_class_method_decorator_anchors_at_the_first_decorator(self):
        source = """\
from oas.testing.screenshot import image

class TestFoo:
    @slow
    @image(
        "a.webp"
    )
    def test_one(self):
        pass
"""
        assert parse_test_source(source) == ParsedUnittest(
            source=source,
            images=[
                UnittestImage(
                    class_name='TestFoo',
                    func_name='test_one',
                    start_line=4,
                    end_line=9,
                    image='a.webp',
                    error='',
                ),
            ],
            errors=[],
        )

    def test_multiple_images_still_anchor_at_the_first_decorator(self):
        source = """\
from oas.testing.screenshot import image

@slow
@image("a.webp")
@image("b.webp")
def test_a():
    pass
"""
        assert parse_test_source(source) == ParsedUnittest(
            source=source,
            images=[
                UnittestImage(
                    class_name='',
                    func_name='test_a',
                    start_line=3,
                    end_line=7,
                    image='a.webp',
                    error='line 4: multiple @image decorators, using the first one',
                ),
            ],
            errors=[],
        )


class TestImageDecorator:
    def test_plain_import(self):
        source = """\
from oas.testing.screenshot import image

@image("a.webp")
def test_a():
    pass
"""
        assert parse_test_source(source) == ParsedUnittest(
            source=source,
            images=[
                UnittestImage(
                    class_name='',
                    func_name='test_a',
                    start_line=3,
                    end_line=5,
                    image='a.webp',
                    error='',
                ),
            ],
            errors=[],
        )

    def test_alias_import(self):
        source = """\
from oas.testing.screenshot import image as shot

@shot("a.webp")
def test_a():
    pass
"""
        assert parse_test_source(source) == ParsedUnittest(
            source=source,
            images=[
                UnittestImage(
                    class_name='',
                    func_name='test_a',
                    start_line=3,
                    end_line=5,
                    image='a.webp',
                    error='',
                ),
            ],
            errors=[],
        )

    def test_module_import(self):
        source = """\
import oas.testing.screenshot as screenshot

@screenshot.image("a.webp")
def test_a():
    pass
"""
        assert parse_test_source(source) == ParsedUnittest(
            source=source,
            images=[
                UnittestImage(
                    class_name='',
                    func_name='test_a',
                    start_line=3,
                    end_line=5,
                    image='a.webp',
                    error='',
                ),
            ],
            errors=[],
        )

    def test_from_testing_import_screenshot(self):
        source = """\
from oas.testing import screenshot

@screenshot.image("a.webp")
def test_a():
    pass
"""
        assert parse_test_source(source) == ParsedUnittest(
            source=source,
            images=[
                UnittestImage(
                    class_name='',
                    func_name='test_a',
                    start_line=3,
                    end_line=5,
                    image='a.webp',
                    error='',
                ),
            ],
            errors=[],
        )

    def test_full_dotted_decorator(self):
        source = """\
import oas.testing.screenshot

@oas.testing.screenshot.image("a.webp")
def test_a():
    pass
"""
        assert parse_test_source(source) == ParsedUnittest(
            source=source,
            images=[
                UnittestImage(
                    class_name='',
                    func_name='test_a',
                    start_line=3,
                    end_line=5,
                    image='a.webp',
                    error='',
                ),
            ],
            errors=[],
        )

    def test_star_import(self):
        source = """\
from oas.testing.screenshot import *

@image("a.webp")
def test_a():
    pass
"""
        assert parse_test_source(source) == ParsedUnittest(
            source=source,
            images=[
                UnittestImage(
                    class_name='',
                    func_name='test_a',
                    start_line=3,
                    end_line=5,
                    image='a.webp',
                    error='',
                ),
            ],
            errors=[],
        )

    def test_keyword_path(self):
        source = """\
from oas.testing.screenshot import image

@image(path="a.webp")
def test_a():
    pass
"""
        assert parse_test_source(source) == ParsedUnittest(
            source=source,
            images=[
                UnittestImage(
                    class_name='',
                    func_name='test_a',
                    start_line=3,
                    end_line=5,
                    image='a.webp',
                    error='',
                ),
            ],
            errors=[],
        )

    def test_multiple_images_use_the_topmost(self):
        source = """\
from oas.testing.screenshot import image

@image("a.webp")
@image("b.webp")
def test_a():
    pass
"""
        assert parse_test_source(source) == ParsedUnittest(
            source=source,
            images=[
                UnittestImage(
                    class_name='',
                    func_name='test_a',
                    start_line=3,
                    end_line=6,
                    image='a.webp',
                    error='line 3: multiple @image decorators, using the first one',
                ),
            ],
            errors=[],
        )

    def test_dynamic_path_is_a_function_level_error(self):
        source = """\
from oas.testing.screenshot import image

@image(f"a{1}.webp")
def test_a():
    pass
"""
        assert parse_test_source(source) == ParsedUnittest(
            source=source,
            images=[
                UnittestImage(
                    class_name='',
                    func_name='test_a',
                    start_line=3,
                    end_line=5,
                    image='',
                    error='line 3: @image path is not a string literal',
                ),
            ],
            errors=[],
        )

    def test_missing_path_is_a_function_level_error(self):
        source = """\
from oas.testing.screenshot import image

@image
def test_a():
    pass
"""
        assert parse_test_source(source) == ParsedUnittest(
            source=source,
            images=[
                UnittestImage(
                    class_name='',
                    func_name='test_a',
                    start_line=3,
                    end_line=5,
                    image='',
                    error='line 3: @image is missing its path argument',
                ),
            ],
            errors=[],
        )

    def test_empty_path_is_a_function_level_error(self):
        source = """\
from oas.testing.screenshot import image

@image("")
def test_a():
    pass
"""
        assert parse_test_source(source) == ParsedUnittest(
            source=source,
            images=[
                UnittestImage(
                    class_name='',
                    func_name='test_a',
                    start_line=3,
                    end_line=5,
                    image='',
                    error='line 3: @image path is empty',
                ),
            ],
            errors=[],
        )

    def test_image_on_a_non_test_function_is_a_function_level_error(self):
        source = """\
from oas.testing.screenshot import image

@image("a.webp")
def helper():
    pass
"""
        assert parse_test_source(source) == ParsedUnittest(
            source=source,
            images=[
                UnittestImage(
                    class_name='',
                    func_name='helper',
                    start_line=3,
                    end_line=5,
                    image='a.webp',
                    error='line 3: @image on a non-test function',
                ),
            ],
            errors=[],
        )

    def test_async_test_keeps_the_image_and_reports_a_function_error(self):
        source = """\
from oas.testing.screenshot import image

@image("a.webp")
async def test_a():
    pass
"""
        assert parse_test_source(source) == ParsedUnittest(
            source=source,
            images=[
                UnittestImage(
                    class_name='',
                    func_name='test_a',
                    start_line=3,
                    end_line=5,
                    image='a.webp',
                    error='line 4: async test is not supported',
                ),
            ],
            errors=[],
        )

    def test_async_test_without_image_is_a_file_level_error(self):
        source = """\
async def test_a():
    pass
"""
        assert parse_test_source(source, filename='test.py') == ParsedUnittest(
            source=source,
            images=[],
            errors=['test.py:1: async test is not supported'],
        )

    def test_multiple_function_errors_are_joined(self):
        source = """\
from oas.testing.screenshot import image

@image(f"a{1}.webp")
async def helper():
    pass
"""
        assert parse_test_source(source) == ParsedUnittest(
            source=source,
            images=[
                UnittestImage(
                    class_name='',
                    func_name='helper',
                    start_line=3,
                    end_line=5,
                    image='',
                    error=(
                        'line 3: @image path is not a string literal\n'
                        'line 3: @image on a non-test function\n'
                        'line 4: async test is not supported'
                    ),
                ),
            ],
            errors=[],
        )


class TestSyntaxErrors:
    def test_syntax_error_is_a_file_level_error(self):
        source = 'def broken(:\n'
        assert parse_test_source(source, filename='broken.py') == ParsedUnittest(
            source=source,
            images=[],
            errors=['broken.py:1: invalid syntax'],
        )

    def test_null_byte_is_a_file_level_error(self):
        source = '\x00'
        assert parse_test_source(source, filename='null.py') == ParsedUnittest(
            source=source,
            images=[],
            errors=['null.py: source code string cannot contain null bytes'],
        )


class TestParseTestFile:
    def test_reads_utf8_bom(self, fs):
        source = """\
from oas.testing.screenshot import image

@image("a.webp")
def test_a():
    pass
"""
        fs.create_file(
            '/tests/test_a.py', contents=b'\xef\xbb\xbf' + source.encode('utf-8')
        )

        assert parse_test_file('/tests/test_a.py') == ParsedUnittest(
            source=source,
            images=[
                UnittestImage(
                    class_name='',
                    func_name='test_a',
                    start_line=3,
                    end_line=5,
                    image='a.webp',
                    error='',
                ),
            ],
            errors=[],
        )

    def test_reads_crlf(self, fs):
        source = 'def test_a():\n    pass\n'.replace('\n', '\r\n')
        fs.create_file('/test_a.py', contents=source.encode('utf-8'))

        assert parse_test_file('/test_a.py') == ParsedUnittest(
            source=source, images=[], errors=[]
        )

    def test_missing_file(self, fs):
        assert parse_test_file('/missing.py') == ParsedUnittest(
            source='',
            images=[],
            errors=[
                f"/missing.py: [Errno 2] No such file or directory: '{fs.root_dir.path.rstrip('/')}/missing.py'"
            ],
        )

    def test_empty_file(self, fs):
        fs.create_file('/empty.py', contents=b'')

        assert parse_test_file('/empty.py') == ParsedUnittest(
            source='', images=[], errors=[]
        )

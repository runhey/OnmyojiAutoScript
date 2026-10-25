"""
Parse a golden test file into its full source and its image bindings.

The preview page shows the complete test source in the middle and anchors the
screenshot bound by `@image` on the right. The backend returns the whole source
so the frontend can run its Python syntax highlighter over the complete file;
splitting the source into blocks on the backend would break tokens that span
lines (multi-line strings, brackets, comments).

Each test function bound by `@image` becomes an `UnittestImage`:

    class_name: enclosing class name, empty for a module-level test
    func_name:  test function name
    start_line: first decorator line, the anchor of the image
    end_line:   last line of the function
    image:      path from @image, relative to collection/

The parser never imports the test module. A screenshot test imports the game
script modules, pytest plugins and fixtures, which the backend process does not
have; importing it would execute code for a page that only reads the source.
`ast` is read-only and enough to find the test functions and their decorators.

Usage:

    from oas.testing.preview.parse_unittest import parse_test_source

    parsed = parse_test_source(source, filename='tests/map/test_a.py')

    print(parsed.source)
    for image in parsed.images:
        print(image.class_name, image.func_name, image.start_line, image.image)
"""

import ast
import tokenize
from io import BytesIO
from typing import List

from msgspec import Struct

from oas.ext.path.atomic import atomic_read_bytes

__all__ = [
    'IMAGE_DECORATOR',
    'ParsedUnittest',
    'UnittestImage',
    'parse_test_file',
    'parse_test_source',
]

# The decorator that binds a screenshot to a test
IMAGE_DECORATOR = 'oas.testing.screenshot.image'


class UnittestImage(Struct, omit_defaults=True):
    """
    An image bound to a test function by @image

    Attributes:
        class_name (str): Enclosing class name, empty for a module-level test
        func_name (str): Test function name
        start_line (int): First decorator line, 1-based; the image top is
            aligned to this line
        end_line (int): Last line of the function, 1-based and inclusive
        image (str): Path from @image, relative to collection/, empty when the
            path is invalid
        error (str): Function-level errors, one per line; empty when the
            binding is valid
    """

    class_name: str = ''
    func_name: str = ''
    start_line: int = 1
    end_line: int = 1
    image: str = ''
    error: str = ''


class ParsedUnittest(Struct):
    """
    A parsed test file

    Attributes:
        source (str): Full source of the test file
        images (List[UnittestImage]): Image bindings in source order
        errors (List[str]): File-level errors and read errors
    """

    source: str
    images: List[UnittestImage] = []
    errors: List[str] = []


def parse_test_file(file):
    """
    Read and parse a test file

    Args:
        file (str): Path of the test file

    Returns:
        ParsedUnittest: The full source and the image bindings
    """
    try:
        data = atomic_read_bytes(str(file))
        encoding, _ = tokenize.detect_encoding(BytesIO(data).readline)
        source = data.decode(encoding)
    except (OSError, UnicodeDecodeError, SyntaxError, LookupError) as e:
        return ParsedUnittest(source='', errors=[f'{file}: {e}'])

    return parse_test_source(source, filename=str(file))


def parse_test_source(source, filename='<test>'):
    """
    Parse a test file into its full source and its image bindings

    The parser never imports the test module, it only reads the syntax tree.
    The returned source is exactly the input source; the frontend highlights
    it and anchors the images to `UnittestImage.start_line`.

    Args:
        source (str): Source code of the test file
        filename (str): Name reported in error messages

    Returns:
        ParsedUnittest: The full source and the image bindings
    """
    try:
        tree = ast.parse(source, filename=filename)
    except (SyntaxError, ValueError) as e:
        return ParsedUnittest(source=source, errors=[_format_parse_error(filename, e)])

    aliases = _collect_image_aliases(tree)
    images = []
    errors = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    _handle_function(
                        images, errors, child, node.name, aliases, filename
                    )
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _handle_function(images, errors, node, '', aliases, filename)

    images.sort(key=lambda image: (image.start_line, image.func_name))
    return ParsedUnittest(source=source, images=images, errors=errors)


def _format_parse_error(filename, error):
    """
    Format a SyntaxError/ValueError from ast.parse()

    Args:
        filename (str): Name reported in the error
        error (Exception): SyntaxError or ValueError

    Returns:
        str: Error message
    """
    lineno = getattr(error, 'lineno', None)
    message = getattr(error, 'msg', None) or str(error)
    return f'{filename}:{lineno}: {message}' if lineno else f'{filename}: {message}'


def _handle_function(images, errors, node, class_name, aliases, filename):
    """
    Handle one top-level function or class method

    Args:
        images (List[UnittestImage]): Image binding collector
        errors (List[str]): File-level error collector
        node (ast.FunctionDef | ast.AsyncFunctionDef): Function node
        class_name (str): Enclosing class name, empty for a module-level test
        aliases (dict[str, str]): Image decorator aliases
        filename (str): Name reported in file-level errors
    """
    matched = _matched_image_decorators(node, aliases)
    is_test = node.name.startswith('test')
    is_async = isinstance(node, ast.AsyncFunctionDef)

    if not matched:
        # Without @image there is no image anchor. An async test without an
        # image still needs to be reported, but it has no UnittestImage to
        # attach the error to, so it goes to the file-level errors.
        if is_test and is_async:
            errors.append(f'{filename}:{node.lineno}: async test is not supported')
        return

    messages = []
    if len(matched) > 1:
        messages.append(
            f'line {matched[0][0].lineno}: '
            f'multiple @image decorators, using the first one'
        )
    for decorator, _, error in matched:
        if error:
            messages.append(f'line {decorator.lineno}: @image {error}')
    if not is_test:
        messages.append(f'line {matched[0][0].lineno}: @image on a non-test function')
    if is_async:
        messages.append(f'line {node.lineno}: async test is not supported')

    _, image, error = matched[0]
    if error:
        image = ''
    elif not image:
        messages.append(f'line {matched[0][0].lineno}: @image path is empty')
        image = ''

    images.append(
        UnittestImage(
            class_name=class_name,
            func_name=node.name,
            start_line=_node_start(node),
            end_line=_node_end(node),
            image=image,
            error='\n'.join(messages),
        )
    )


def _matched_image_decorators(node, aliases):
    """
    Collect the @image decorators of a function, topmost first

    Args:
        node (ast.FunctionDef | ast.AsyncFunctionDef): Function node
        aliases (dict[str, str]): Image decorator aliases

    Returns:
        list[tuple[ast.AST, str | None, str | None]]: (decorator, path, error)
            for every @image decorator, in decorator_list order. The first one
            is the effective image: decorators are applied bottom-up, so the
            topmost one runs last and wins.
    """
    matched = []
    for decorator in node.decorator_list:
        is_image, image, error = _image_decorator_path(decorator, aliases)
        if is_image:
            matched.append((decorator, image, error))
    return matched


def _collect_image_aliases(tree):
    """
    Collect the local names that may refer to the image decorator

    Both forms are supported:

        from oas.testing.screenshot import image
        from oas.testing.screenshot import image as shot
        import oas.testing.screenshot as screenshot
        from oas.testing import screenshot
        from oas.testing.screenshot import *

    Args:
        tree (ast.Module): Parsed module

    Returns:
        dict[str, str]: Local name -> dotted name
    """
    aliases = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            module = node.module or ''
            for alias in node.names:
                if alias.name == '*':
                    if module == 'oas.testing.screenshot':
                        aliases.setdefault('image', IMAGE_DECORATOR)
                    continue
                local = alias.asname or alias.name
                aliases[local] = f'{module}.{alias.name}' if module else alias.name
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    aliases[alias.asname] = alias.name
                else:
                    # import a.b.c binds the top-level name "a"
                    root = alias.name.partition('.')[0]
                    aliases[root] = root
    return aliases


def _node_start(node):
    """
    First line of a function, including its decorators

    Args:
        node (ast.FunctionDef | ast.AsyncFunctionDef): Function node

    Returns:
        int: 1-based line number
    """
    decorators = getattr(node, 'decorator_list', ())
    return min([node.lineno] + [decorator.lineno for decorator in decorators])


def _node_end(node):
    """
    Last line of a function

    Args:
        node (ast.FunctionDef | ast.AsyncFunctionDef): Function node

    Returns:
        int: 1-based line number
    """
    end = getattr(node, 'end_lineno', None)
    return end if end is not None else node.lineno


def _image_decorator_path(decorator, aliases):
    """
    Resolve one decorator as an @image decorator

    Args:
        decorator (ast.AST): Decorator expression
        aliases (dict[str, str]): Image decorator aliases

    Returns:
        tuple[bool, str | None, str | None]: (matched, image path, error)
            matched is False when the decorator is not @image; when matched is
            True, image is None if the path is missing or not a string literal
            and error describes why.
    """
    if isinstance(decorator, ast.Call):
        if not _is_image_decorator(decorator.func, aliases):
            return False, None, None
        path_node = decorator.args[0] if decorator.args else None
        if path_node is None:
            for keyword in decorator.keywords:
                if keyword.arg == 'path':
                    path_node = keyword.value
                    break
        if path_node is None:
            return True, None, 'is missing its path argument'
        if isinstance(path_node, ast.Constant) and isinstance(path_node.value, str):
            return True, path_node.value, None
        return True, None, 'path is not a string literal'

    if _is_image_decorator(decorator, aliases):
        return True, None, 'is missing its path argument'
    return False, None, None


def _is_image_decorator(node, aliases):
    """
    Check if a decorator expression refers to the screenshot image decorator

    Args:
        node (ast.AST): Decorator expression or its func
        aliases (dict[str, str]): Image decorator aliases

    Returns:
        bool:
    """
    name = _render_dotted(node, aliases)
    if name is None:
        return False
    # A bare "image" is the documented fallback for a test file that imports
    # the decorator in a way the alias collector does not understand.
    return name == IMAGE_DECORATOR or name == 'image'


def _render_dotted(node, aliases):
    """
    Render a Name/Attribute expression as a dotted name

    Args:
        node (ast.AST): Expression
        aliases (dict[str, str]): Image decorator aliases

    Returns:
        str | None: Dotted name, None for unsupported expressions
    """
    if isinstance(node, ast.Name):
        return aliases.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        base = _render_dotted(node.value, aliases)
        if base is None:
            return None
        return f'{base}.{node.attr}'
    return None

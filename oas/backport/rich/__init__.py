# Trimmed from alasio/backport/rich/__init__.py for OAS (Python 3.14)
# Kept: patch_rich_traceback_links (IDE-clickable tracebacks, version-independent)
# Dropped: patch_rich_traceback_extract (only needed for python<3.11 + rich<14.3 exceptiongroup)
from oas.backport.once import patch_once


def parse_rich_traceback_header(line):
    """
    Parse rich traceback header like "E:\\path\\to\\file.py:5 in cause_error"
    to (path, line_num, function_name).

    Args:
        line (str): Rich header string.

    Returns:
        tuple[str, str, str]: path, line_num, function_name
    """
    # Header format: "{path}:{line} in {func}"
    # Python function name cannot have spaces.
    header_part, sep, function_name = line.rpartition(' in ')
    if not sep:
        header_part = line
        function_name = ''

    # Line number is always after the last colon
    path, sep, line_num = header_part.rpartition(':')
    if not sep:
        path = header_part
        line_num = ''

    return path, line_num, function_name


@patch_once
def patch_rich_traceback_links():
    """
    Patch rich.traceback to format header like python builtin traceback,
    so it can be clickable in IDE (IDEs will parse them as clickable)
    """
    try:
        from rich.text import Text
        from rich.traceback import Traceback
    except ImportError:
        # no rich, no need to patch
        return True

    original_render_stack = Traceback._render_stack

    def render_stack_patched(self, stack):
        # Call original to get the Group of renderables
        renderable_group = original_render_stack(self, stack)

        # In rich, @group() makes it return a Group object with a .renderables attribute
        for i, item in enumerate(renderable_group.renderables):
            if isinstance(item, Text):
                plain = item.plain
                # Traceback frame header normally contains " in " or at least a colon
                if ':' in plain:
                    try:
                        path, line_num, function_name = parse_rich_traceback_header(plain)
                        if not path or not line_num:
                            continue

                        # PERFORMANCE & AESTHETICS:
                        # Use standard Python traceback format which IDEs recognize natively.
                        # Format:   File "path", line line_num, in function_name
                        new_text = Text()
                        new_text.append('  File "', style='pygments.text')
                        new_text.append(path, style='pygments.string')
                        new_text.append('", line ', style='pygments.text')
                        new_text.append(line_num, style='pygments.number')
                        if function_name:
                            new_text.append(', in ', style='pygments.text')
                            new_text.append(function_name, style='pygments.function')

                        renderable_group.renderables[i] = new_text
                    except Exception:
                        pass
        return renderable_group

    Traceback._render_stack = render_stack_patched
# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import re
from html import escape

def replace_newline_with_br(input_text):
    replaced_text = input_text.replace('\n', '<br>')
    return replaced_text

def highlight_text(input_text):
    color_mapping = {
        r'\d{2}:\d{2}:\d{2}\.\d{3}': 'cyan',
        r'\bTrue\b': 'lime',
        r'\bFalse\b': 'red',
        r'DEBUG': 'cyan',
        r'INFO': 'green',
        r'WARNING': 'yellow',
        r'ERROR': 'red',
        r'CRITICAL': 'darkred'
    }

    for pattern, color in color_mapping.items():
        input_text = re.sub(pattern, f'<span style="color: {color}">\\g<0></span>', input_text)

    return replace_newline_with_br(input_text)

# 测试
# input_string = 'The time is 13:20:36.411. Is it True or False? DEBUG: This is a debug message. INFO: This is an info message. WARNING: This is a warning message. ERROR: This is an error message. CRITICAL: This is a critical message.'
# highlighted_text = highlight_text(input_string)
# html_text = f'<html><body>{highlighted_text}</body></html>'
# print(html_text)



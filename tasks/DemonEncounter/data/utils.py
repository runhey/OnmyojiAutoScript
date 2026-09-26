import re


def remove_symbols(text):
    return re.sub(r'[^\w\s]', '', text)

# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import re


def remove_symbols(text):
    return re.sub(r'[^\w\s]', '', text)

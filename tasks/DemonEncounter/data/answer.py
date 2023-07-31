# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import csv

from datetime import datetime
from pathlib import Path


def answer_one(question: str, options: list[str]) -> int:
    """

    每一个问题有四个选项， 返回选项的序号(1、2、3)
    :param question:
    :param options:
    :return:
    """
    file = str(Path(__file__).parent / 'data.csv')
    with open(file, newline='', encoding='utf-8-sig') as csvfile:
        reader = csv.reader(csvfile)
        next(reader)
        for row in reader:
            if row[0] == question:
                try:
                    return options.index(row[1]) + 1
                except ValueError:
                    return 1
        return 1


if __name__ == "__main__":
    question = '以下式神中，手持折扇的是'
    options = ['生命上限', '鬼王', '荒川之主']
    start_time = datetime.now()
    print(answer_one(question, options))
    print(datetime.now() - start_time)
    print(answer_one(question, options))

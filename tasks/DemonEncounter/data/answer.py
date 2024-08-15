# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import csv
import re

from datetime import datetime
from pathlib import Path

from module.logger import logger

def count_intersection(str1, str2):
    set1 = set(str1)
    set2 = set(str2)
    intersection = set1.intersection(set2)
    return len(intersection)

def remove_symbols(text):
    return re.sub(r'[^\w\s]', '', text)

class Answer:
    def __init__(self):
        self.data: dict[str, list] = {}
        self.data_options: dict[str, list] = {}
        file = str(Path(__file__).parent / 'data.csv')
        with open(file, newline='', encoding='utf-8-sig') as csvfile:
            reader = csv.reader(csvfile)
            next(reader)
            for row in reader:
                key = remove_symbols(row[0])
                value = remove_symbols(row[1])
                if key not in self.data:
                    self.data[key] = []
                self.data[key].append(value)
                if value not in self.data_options:
                    self.data_options[value] = []
                self.data_options[value].append(key)

    def answer_one(self, question: str, options: list[str]) -> int|None:
        """

        每一个问题有三个选项， 返回选项的序号(1、2、3)
        :param question:
        :param options:
        :return:
        """
        def decide_by_options(question: str, option: list[str]):
            # 瞎猫当死耗子
            opts = {}
            for index, option in enumerate(options):
                if option in self.data_options.keys():
                    cnts = [count_intersection(question, ques) for ques in self.data_options[option] ]
                    cnts.sort(reverse=True)
                    opts[index + 1] = cnts[0]
            #
            if opts:
                opts = sorted(opts.items(), key=lambda x: x[1], reverse=True)
            if opts:
                return opts[0][0]
            else:
                return None


        question = question.replace('「', '').replace('」', '').replace('?', '')
        question = remove_symbols(question)
        options = [remove_symbols(option) for option in options]

        for index, option in enumerate(options):
            if option == '其余选项皆对':
                return index + 1

        question_matches: list = []
        try:
            question_matches = self.data[question]
        except Exception as e:
            # 没有出现题目，从选项反入手
            logger.error('Exception: %s', e)
            return decide_by_options(question=question, option=options)
        # 出现了题目，开始对答案
        for index, option in enumerate(options):
            for match in question_matches:
                if match == option:
                    return index + 1
        # 可能选项识别某一个字错误
        if options[0] != '' and options[1] != '' and options[2] != '' and options[3] != '':
            for index, option in enumerate(options):
                for match in question_matches:
                    if len(match) != len(option):
                        continue
                    if len(match) - count_intersection(match, option) <= 1 :
                        logger.warning('Option is not match: %s, %s', match, option)
                        return index + 1
        # 选项一个都对不上可能是，识别的选项异常
        for index, option in enumerate(options):
            if option == '':
                logger.error('Option is empty: %s', options)
                return index + 1
        return None


if __name__ == "__main__":
    answer = Answer()
    question = '以下式神中，谁从小就是孤'
    options = ['生命上限', '小鹿男', '荒川之主']
    start_time = datetime.now()
    print(answer.answer_one(question, options))
    print(answer.answer_one(question, options))
    print(datetime.now() - start_time)

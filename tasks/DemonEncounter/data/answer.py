# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import csv
import re
import difflib

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
        # 添加缓存以确保相同问题的答案一致性
        # 修改：缓存存储答案字符串而不是索引，避免选项顺序变化的影响
        self.question_cache: dict[str, str] = {}
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
        
        # 检查缓存，如果已经处理过类似问题，直接返回结果
        # 修改：现在缓存的是答案字符串，需要在选项中查找对应的索引
        for cached_q, cached_answer_str in self.question_cache.items():
            similarity = difflib.SequenceMatcher(None, question, cached_q).ratio()
            if similarity >= 0.9:  # 如果问题相似度超过90%，直接返回缓存的答案
                # 在当前选项中查找缓存的答案字符串
                for idx, option in enumerate(options):
                    if option == cached_answer_str:
                        return idx + 1  # 返回选项索引（从1开始）
                # 如果缓存的答案在当前选项中不存在，则尝试模糊匹配
                for idx, option in enumerate(options):
                    if difflib.SequenceMatcher(None, option, cached_answer_str).ratio() >= 0.9:
                        logger.info(f"Fuzzy match cache: '{cached_answer_str}' ~ '{option}'")
                        return idx + 1
        def decide_by_question_foreach(ques: str, ops: list[str]):
            # 这个是最耗时的操作，遍历数据库中的所有题目，找到最相识的题目和选项
            for key, values in self.data.items():
                question_match_ratio = difflib.SequenceMatcher(None, ques, key).ratio()
                if question_match_ratio < 0.7:
                    continue
                for value in values:
                    for index, option in enumerate(ops):
                        option_match_ratio = difflib.SequenceMatcher(None, option, value).ratio()
                        if option_match_ratio >= 0.5:
                            logger.warning('The worst case: no match found for question and option')
                            logger.warning('Now traversing the entire database to find the most similar question and option')
                            logger.warning(f'Most similar question: {key} and most similar option: {value}')
                            result_index = index + 1
                            # 修改：缓存问题和答案字符串
                            self.question_cache[ques] = ops[index]
                            return result_index
            return None

        def decide_by_options(question: str, ops: list[str]):
            # 瞎猫当死耗子
            matches = {}
            for index, option in enumerate(ops):
                if option not in self.data_options.keys():
                    continue
                for ques in self.data_options[option]:
                    ques_match_ratio = difflib.SequenceMatcher(None, ques, question).ratio()
                    if ques_match_ratio > 0.8:
                        matches[index + 1] = ques_match_ratio
            if matches:
                opts = sorted(matches.items(), key=lambda x: x[1], reverse=True)
                logger.warning('No match found for question,\n Now traversing the entire database to find the most similar question')
                logger.warning(f'Most similar answer: {opts[0][0]}, and similarity char number is {opts[0][1]}')
                result_index = opts[0][0]
                # 修改：缓存问题和答案字符串
                self.question_cache[question] = ops[result_index - 1]
                return result_index
            index = decide_by_question_foreach(question, ops)
            return index if index else None


        question = question.replace('「', '').replace('」', '').replace('?', '')
        question = remove_symbols(question)
        options = [remove_symbols(option) for option in options]

        for index, option in enumerate(options):
            if option == '其余选项皆对':
                result_index = index + 1
                # 特殊选项才缓存
                # 修改：缓存问题和答案字符串
                self.question_cache[question] = option
                return result_index

        question_matches: list = []
        try:
            question_matches = self.data[question]
        except Exception as e:
            # 没有出现题目，从选项反入手
            logger.error('Exception: %s', e)
            result = decide_by_options(question=question, ops=options)
            if result is not None:
                # 只有在使用模糊匹配的情况下才缓存结果
                # 修改：缓存问题和答案字符串
                self.question_cache[question] = options[result - 1]
            return result
        # 出现了题目，开始对答案
        for index, option in enumerate(options):
            for match in question_matches:
                if match == option:
                    return index + 1  # 精确匹配，不缓存，直接返回
        # 可能选项识别某一个字错误
        if all(options):
            for index, option in enumerate(options):
                for match in question_matches:
                    if len(match) != len(option):
                        continue
                    if len(match) - count_intersection(match, option) <= 1 :
                        logger.warning('Option is not match: %s, %s', match, option)
                        return index + 1  # 这也是精确匹配的一种，不缓存，直接返回
        # 最保守策略，答案匹配度最高
        opts = {}
        for index, option in enumerate(options):
            item_match_ratio = 0
            for match in question_matches:
                match_ratio = difflib.SequenceMatcher(None, match, option).ratio()
                if match_ratio >= 0.33 and match_ratio > item_match_ratio:
                    item_match_ratio = match_ratio
            if item_match_ratio > 0:
                opts[index + 1] = item_match_ratio
        if opts:
            opts = sorted(opts.items(), key=lambda x: x[1], reverse=True)
            logger.warning(f'Use SequenceMatcher and get answers: {opts[0][0]}, score: {opts[0][1]}')
            result_index = opts[0][0]
            # 只有在这种情况下才缓存
            # 修改：缓存问题和答案字符串
            self.question_cache[question] = options[result_index - 1]
            return result_index

        # 选项一个都对不上可能是，正确答案检测为空
        for index, option in enumerate(options):
            if option == '':
                logger.error('Option is empty: %s', options)
                result_index = index + 1
                # 只有在这种情况下才缓存
                # 修改：缓存问题和答案字符串
                self.question_cache[question] = option
                return result_index
                
        # 如果所有方法都失败，尝试使用decide_by_options
        result = decide_by_options(question=question, ops=options)
        if result is not None:
            # 只有在使用模糊匹配的情况下才缓存结果
            # 修改：缓存问题和答案字符串
            self.question_cache[question] = options[result - 1]
        return result


if __name__ == "__main__":
    answer = Answer()
    question = '冥界中谁拥阁魔之目一双审善度恶'
    options = ['判官', '孟婆', '荒川之主', '阁魔']
    start_time = datetime.now()
    print(answer.answer_one(question, options))
    print(datetime.now() - start_time)

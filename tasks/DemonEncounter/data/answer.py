# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import csv
import re
import difflib

from datetime import datetime
from pathlib import Path

from module.logger import logger


def remove_symbols(text):
    return re.sub(r'[^\w\s]', '', text)


def _tokenize_question(text: str) -> list[str]:
    # 2-gram 题目切词，长度不足时退化为 1-gram
    text = text.replace(' ', '')
    if len(text) < 2:
        return list(text)
    return [text[i:i + 2] for i in range(len(text) - 1)]


def _normalize(q: str, opts: list[str]) -> tuple[str, list[str]]:
    # 统一清洗 OCR 字符
    q = q.replace('「', '').replace('」', '').replace('?', '')
    q = remove_symbols(q)
    opts = [remove_symbols(opt) for opt in opts]
    return q, opts


class Answer:
    question_sim_threshold = 0.8
    answer_sim_threshold = 0.5
    data_file = Path(__file__).parent / 'data.csv'
    question_answer: dict[str, set[str]] = {}  # 题目: {标准答案
    answer_question: dict[str, set[str]] = {}  # 标准答案: {题目}
    question_index: dict[str, set[str]] = {}  # 倒排索引
    question_cache: dict[str, set[str]] = {}  # 缓存：识别到的问题 -> {标准答案, 选项答案}

    def __init__(self, top_n: int = 30):
        self.top_n = top_n
        with open(self.data_file, newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            next(reader)
            for row in reader:
                key = remove_symbols(row[0])
                value = remove_symbols(row[1])
                self.question_answer.setdefault(key, set()).add(value)
                self.answer_question.setdefault(value, set()).add(key)
                for token in _tokenize_question(key):
                    self.question_index.setdefault(token, set()).add(key)

    def answer_one(self, question: str, options: list[str]) -> int | None:
        """
        每一个问题有三个选项， 返回选项的序号(1、2、3)
        :param question:
        :param options:
        :return:
        """
        question, options = _normalize(question, options)
        for index, option in enumerate(options):
            if option == '其余选项皆对':
                result_index = index + 1
                # 缓存问题和答案字符串
                self._cache_store(question, option, option)
                logger.debug('Answer strategy: special option hit.')
                return result_index
        # 1) 优先命中缓存
        cached_index = self._cache_hit(question, options)
        if cached_index is not None:
            return cached_index
        # 2) 题目命中：精确或相似选项匹配
        if question in self.question_answer:
            return self._handle_known_question(question, options)
        # 3) 相似题：先精确，再相似匹配
        result = self._handle_similar_questions(question, options)
        if result is not None:
            return result
        # 4) 选项是否存在于答案集合
        result = self._handle_answer_option_match(question, options)
        if result is not None:
            return result
        # 5) 完全未知：返回 None
        logger.error('Unknown question: %s', question)
        return None

    def _cache_store(self, question: str, std_answer: str, chosen: str) -> None:
        # 更新缓存，便于下一次直接命中
        cache = self.question_cache.setdefault(question, set())
        if std_answer:
            cache.add(std_answer)
        if chosen:
            cache.add(chosen)

    def _find_option_index(self, opts: list[str], target: str) -> int | None:
        # 精确查找选项索引
        for idx, option in enumerate(opts):
            if option == target:
                return idx + 1
        return None

    def _cache_hit(self, question: str, opts: list[str]) -> int | None:
        # 优先命中缓存答案
        cached = self.question_cache.get(question)
        if not cached:
            return None
        for ans in cached:
            idx = self._find_option_index(opts, ans)
            if idx is not None:
                logger.info('Hit cache.')
                return idx
        return None

    def _best_similarity_option(self, options: list[str], answer: str) -> tuple[int | None, float]:
        # 从选项中找与答案最相似的项
        best_idx = None
        best_score = 0.0
        for idx, option in enumerate(options):
            score = difflib.SequenceMatcher(None, option, answer).ratio()
            if score > best_score:
                best_score = score
                best_idx = idx + 1
        return best_idx, best_score

    def _get_similar_questions(self, question: str) -> list[tuple[str, float]]:
        # 倒排索引过滤候选问题，再按相似度排序
        tokens = _tokenize_question(question)
        if not tokens:
            return []
        candidate_scores: dict[str, int] = {}
        for token in tokens:
            for key in self.question_index.get(token, []):
                candidate_scores[key] = candidate_scores.get(key, 0) + 1
        if not candidate_scores:
            return []
        candidates = sorted(candidate_scores.items(), key=lambda x: x[1], reverse=True)
        if self.top_n and len(candidates) > self.top_n:
            candidates = candidates[:self.top_n]
        scored = []
        for key, _ in candidates:
            score = difflib.SequenceMatcher(None, question, key).ratio()
            if score >= self.question_sim_threshold:
                scored.append((key, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    def _handle_known_question(self, question: str, options: list[str]) -> int | None:
        # 题目命中时，优先精确匹配答案
        for answer in self.question_answer[question]:
            idx = self._find_option_index(options, answer)
            if idx is not None:
                logger.info('Hit question, correct answer.')
                self._cache_store(question, answer, options[idx - 1])
                return idx
        # 题目命中但选项不一致：按相似度选最接近答案
        best_idx, best_score, best_answer = None, 0.0, ""
        for answer in self.question_answer[question]:
            idx, score = self._best_similarity_option(options, answer)
            if idx is not None and score > best_score:
                best_idx, best_score, best_answer = idx, score, answer
        if best_idx is not None:
            logger.info('Hit question, similar answer.')
            self._cache_store(question, best_answer, options[best_idx - 1])
        return best_idx

    def _handle_similar_questions(self, question: str, options: list[str]) -> int | None:
        # 相似题优先：逐题匹配答案是否在选项中
        similar_questions = self._get_similar_questions(question)
        for key, _ in similar_questions:
            for answer in self.question_answer.get(key, []):
                idx = self._find_option_index(options, answer)
                if idx is not None:
                    logger.info('Hit similar question, correct answer')
                    self._cache_store(question, answer, options[idx - 1])
                    return idx
        # 相似题答案不在选项中：做相似度匹配
        best_idx, best_score, best_answer = None, 0.0, ""
        for key, _ in similar_questions:
            for answer in self.question_answer.get(key, []):
                idx, score = self._best_similarity_option(options, answer)
                if idx is not None and score > best_score:
                    best_idx, best_score, best_answer = idx, score, answer
        if best_idx is not None and best_score >= self.answer_sim_threshold:
            logger.info('Hit similar question, similar answer')
            self._cache_store(question, best_answer, options[best_idx - 1])
            return best_idx
        return None

    def _handle_answer_option_match(self, question: str, options: list[str]) -> int | None:
        # 选项命中答案集合时，根据题目相似度校验
        for idx, option in enumerate(options):
            if option in self.answer_question:
                questions = self.answer_question.get(option, set())
                best_question, best_score = None, 0.0
                for candidate in questions:
                    score = difflib.SequenceMatcher(None, question, candidate).ratio()
                    if score > best_score:
                        best_score = score
                        best_question = candidate
                # 选项在答案中, 则问题相似度降级处理
                if best_question is not None and best_score >= self.answer_sim_threshold:
                    self._cache_store(question, option, option)
                    logger.info('Hit correct answer, lower similar question')
                    return idx + 1
        return None


if __name__ == "__main__":
    answer = Answer()
    test_cases = [
        # 精确命中
        ('冥界中谁拥阁魔之目一双审善度恶', ['判官', '孟婆', '荒川之主', '阁魔']),
        # 相似题命中（缺尾）
        ('冥界中谁拥阁魔之目一双', ['判官', '孟婆', '荒川之主', '阁魔']),
        # 相似题命中（字形误差）
        ('冥界中谁用阎魔之日一双审善渡恶', ['判官', '孟婆', '荒川之主', '阁魔']),
        # 选项存在于答案集合
        ('冥界中谁拥阁魔', ['六百六十六', '七百七十七', '八百八十八', '阁魔']),
        # 完全未知
        ('这是一条完全未知的问题', ['甲', '乙', '丙', '丁']),
    ]
    for question, options in test_cases:
        start_time = datetime.now()
        result = answer.answer_one(question, options)
        cost_ms = (datetime.now() - start_time).microseconds / 1000
        print(f'Q: {question} -> {result}, cost: {cost_ms:.2f}ms')

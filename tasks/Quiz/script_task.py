# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import random
from cached_property import cached_property

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_realm_raid, page_main
from tasks.Quiz.assets import QuizAssets
from tasks.ActivityShikigami.assets import ActivityShikigamiAssets
from tasks.DemonEncounter.data.answer import Answer
from tasks.Quiz.debug import Debugger, remove_symbols

from module.logger import logger
from module.exception import TaskEnd
from module.base.timer import Timer
from module.atom.image_grid import ImageGrid
from module.atom.image import RuleImage
from module.atom.click import RuleClick

class NoTicket(Exception):
    pass

class ScriptTask(GameUi, QuizAssets, ActivityShikigamiAssets, Debugger):

    answer_cnt = 0
    last_select_1 = ''
    last_select_2 = ''
    last_select_3 = ''
    last_select_4 = ''

    @cached_property
    def anwser(self) -> Answer:
        # Misspelling
        return Answer()

    @cached_property
    def click_options(self) -> list:
        return [self.O_ANSWER1, self.O_ANSWER2, self.O_ANSWER3, self.O_ANSWER4]

    @cached_property
    def _config(self):
        return self.config.model.quiz.quiz_config

    def run(self):
        self.ui_get_current_page()
        self.ui_goto(page_main)
        _config = self.config.model.quiz.quiz_config
        self.enter()

        quiz_cnt = 0
        while 1:
            if quiz_cnt >= _config.quiz_cnt:
                break
            try:
                self.once()
                quiz_cnt += 1
            except NoTicket:
                break

        self.ui_click(self.I_UI_BACK_YELLOW, self.I_CHECK_MAIN, interval=2)
        self.set_next_run(task='Quiz', success=True, finish=True)
        raise TaskEnd('Quiz')

    def enter(self):
        while 1:
            self.screenshot()
            if self.appear(self.I_START):
                break
            if self.appear_then_click(self.I_SHI, interval=1):
                continue
            if self.appear_then_click(self.I_ENTRY, interval=1):
                continue
        logger.info('Quiz start')

    def once(self) -> bool:
        logger.hr('Quiz', 3)
        start_cnt = 0
        self.answer_cnt = 0
        while 1:
            self.screenshot()
            if self.appear(self.I_MESSAGE):
                break
            if start_cnt >= 4:
                logger.error('No ticket')
                raise NoTicket('No ticket')
            if self.appear_then_click(self.I_START, interval=1.5):
                start_cnt += 1
                continue
        self.last_select_1, self.last_select_2, self.last_select_3, self.last_select_4 = '', '', '', ''

        quiz_timer = Timer(1.4)
        quiz_timer.start()
        while 1:
            self.screenshot()

            if self.ui_reward_appear_click():
                continue
            if self.appear(self.I_FAIL_QUIT):
                # 失败
                logger.info('Quiz Fail and exit')
                self.ui_click(self.I_FAIL_QUIT, self.I_START)
                break
            if self.appear(self.I_SHARE):
                # 结算
                logger.info('Quiz Victory and exit')
                self.ui_click(self.I_UI_BACK_RED, self.I_START)
                break
            if quiz_timer.reached():
                quiz_timer.reset()
                self._deal_quiz()
                continue
        self.close_fn()

    def detect_new(self, select_1, select_2, select_3, select_4) -> bool:
        new = True if self.last_select_1 != select_1 or \
                self.last_select_2 != select_2 or \
                self.last_select_3 != select_3 or \
                self.last_select_4 != select_4 else False
        self.last_select_1, self.last_select_2, self.last_select_3, self.last_select_4 = \
            select_1, select_2, select_3, select_4
        return new

    def _deal_quiz(self):
        countdown = self.O_COUNTDOWN.ocr(self.device.image)
        if countdown < 2 or countdown > 5:
            # 最后两秒钟的时候 进行选择
            return False
        question, answer_1, answer_2, answer_3, answer_4 = self.detect_question_and_answers()
        if answer_1 == '' and answer_2 == '' and answer_3 == '' and answer_4 == '':
            return False
        question = remove_symbols(question)

        new_question = self.detect_new(answer_1, answer_2, answer_3, answer_4)
        if new_question:
            self.answer_cnt += 1
            logger.info(f'Question count: {self.answer_cnt}')

        # questions = self.O_QUESTION.detect_and_ocr(self.device.image)
        # question = ''.join([q.ocr_text for q in questions])
        # question = question.replace('?', '').replace('？', '').replace(' ', '').replace(',', '，')
        # question = remove_symbols(question)

        index = self.anwser.answer_one(question=question,  options=[answer_1, answer_2, answer_3, answer_4])
        if index is None:
            logger.error('Now question has no answer, please check')
            self.append_one(question=question, options=[answer_1, answer_2, answer_3, answer_4])
            self.config.notifier.push(title='Quiz',
                                      content=f"New question: \n{question} \n{[answer_1, answer_2, answer_3, answer_4]}")
            index = 1

        if self._config.quiz_per_round < 150 and self.answer_cnt > self._config.quiz_per_round:
            index_options = {1, 2, 3, 4}
            index_options.remove(index)
            index = random.choice(list(index_options))
        logger.info(f'Question: {question}, Answer: {index}')
        self.click(self.click_options[index-1], interval=1)
        self.device.click_record_clear()
        return True

    def detect_question_and_answers(self) -> tuple:
        results = self.O_QUESTION_AND_ANSWER.detect_and_ocr(self.device.image)
        question = ''
        answer_1 = ''
        answer_2 = ''
        answer_3 = ''
        answer_4 = ''
        for result in results:
            # box 是四个点坐标 左上， 右上， 右下， 左下
            # x1, y1, x2, y2 = result.box[0][0], result.box[0][1], result.box[2][0], result.box[2][1]
            # w, h = x2 - x1, y2 - y1
            y_start = result.box[0][1]
            y_end = result.box[2][1]
            text = result.ocr_text
            if y_start >= 0 and y_end <= 150:
                question += text
            elif y_start > 150 and y_end <= 240:
                answer_1 += text
            elif y_start > 240 and y_end <= 370:
                answer_2 += text
            elif y_start > 370 and y_end <= 470:
                answer_3 += text
            elif y_start > 470 and y_end <= 600:
                answer_4 += text
        return question, answer_1, answer_2, answer_3, answer_4






if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.screenshot()

    t.run()

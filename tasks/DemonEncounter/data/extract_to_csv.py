# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import re
import rich
import csv
import pandas as pd

from utils import remove_symbols

class Extracter:
    def __init__(self, data_file: str='data.csv'):
        self.data_file = data_file
        self.df = pd.read_csv(self.data_file)

    @staticmethod
    def parse_one(value: str) -> tuple:
        """
        解析原始的一行数据，变成OAS使用的格式: question,answer
        :param value:
        :return:
        """
        if not value:
            print(f'value is None {value}')
            return None, None
        if not isinstance(value, str):
            print(f'-----------------------------------------------------------value is not str {value}')
            return None, None
        # 标点符号
        value = value.replace(' ', '').replace('?', '？').replace('!', '！').replace(',', '，').replace('—', '-')

        # 正则匹配
        result = re.search(r"(.*)？-(.*)", value)
        if result:
            return result[1], result[2]
        result = re.search(r"(.*)？--(.*)", value)
        if result:
            return result[1], result[2]
        result = re.search(r"(.*)？-------(.*)", value)
        if result:
            return result[1], result[2]
        result = re.search(r"(.*)？------(.*)", value)
        if result:
            return result[1], result[2]
        result = re.search(r"(.*)？-----(.*)", value)
        if result:
            return result[1], result[2]
        result = re.search(r"(.*)？----(.*)", value)
        if result:
            return result[1], result[2]
        result = re.search(r"(.*)------(.*)", value)
        if result:
            return result[1], result[2]
        result = re.search(r"(.*)-----(.*)", value)
        if result:
            return result[1], result[2]
        result = re.search(r"(.*)----(.*)", value)
        if result:
            return result[1], result[2]
        return None, None


    def xlsx2csv(self, input_file: str='data.xlsx'):
        """
        将xlsx文件的数据添加到csv文件
        :param input_file:
        :return:
        """
        df_source = pd.read_excel(input_file, usecols='A')
        for index, row in df_source.iterrows():
            item_value = row[0]
            question, answer = self.parse_one(item_value)
            if question is None and answer is None:
                continue
            if len(question) < 3:
                continue
            # print(index, question, answer)
            # 非常重要，去除标点符号
            question = remove_symbols(question)
            answer = remove_symbols(answer)
            if self.appear_in_df(question, answer):
                continue
            print('New', index, question, answer)
            self.df.loc[len(self.df)] = [question, answer]
        self.df.to_csv(self.data_file, index=False, encoding='utf-8-sig')

    def appear_in_df(self, question: str, answer: str) -> bool:
        for index, row in self.df.iterrows():
            if row['question'] == question and row['answer'] == answer:
                return True
        return False

    def clear_symbols(self):
        for index, row in self.df.iterrows():
            row['question'] = remove_symbols(row['question'])
            row['answer'] = remove_symbols(row['answer'])
        self.df.to_csv(self.data_file, index=False, encoding='utf-8-sig')




if __name__ == "__main__":
    Extracter().xlsx2csv()









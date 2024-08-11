# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import re
import csv
import pandas as pd

def parse_one(value: str) -> tuple:
    if not value:
        print(f'value is None {value}')
        return None
    result = re.search(r"(.*)？——(.*)", value)
    if result:
        return result[1], result[2]
    else:
        print(f'parse error {value}')
        return None, None


if __name__ == "__main__":
    file = 'data.xlsx'
    df_read = pd.read_excel(file, usecols='A')
    df_wirte = pd.DataFrame(columns=['question', 'answer'])
    print(df_read.columns)
    for index, row in df_read.iterrows():
        question, answer = parse_one(row['question answering'])
        df_wirte.loc[index] = [question, answer]
    df_wirte.to_csv('data.csv', index=False, encoding='utf-8-sig')









# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import argparse
import subprocess

from module.logger import logger

def generate(qml: bool=False):
    content = ''
    if not qml:
        with open("requirements-in.txt", "r", encoding="utf-8") as f:
            content = f.read()
            content = content.replace("pyside6==6.4.3\n", "")
        with open("requirements-in.txt", "w", encoding="utf-8") as f:
            f.write(content)
        logger.info("requirements-in.txt generated")
    else:
        with open("requirements-in.txt", "r", encoding="utf-8") as f:
            content = f.read()
            if content.find("pyside6==6.4.3\n") == -1:
                content.index("pyside6==6.4.3\n")
        with open("requirements-in.txt", "w", encoding="utf-8") as f:
            f.write(content)
        logger.info("requirements-in.txt generated")


    # 执行命令 pip-compile --annotation-style=line --output-file=requirements.txt requirements-in.txt
    subprocess.run(["pip-compile", "--annotation-style=line", "--output-file=requirements.txt", "requirements-in.txt"])

    content = ''
    with open("requirements.txt", "r", encoding="utf-8") as f:
        content = f.read()
        content = content.replace('''--index-url https://pypi.tuna.tsinghua.edu.cn/simple
--trusted-host pypi.tuna.tsinghua.edu.cn''', '')
    with open("requirements.txt", "w", encoding="utf-8") as f:
        f.write(content)
    logger.info("requirements.txt generated")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate requirements.txt")
    parser.add_argument(
        "--qml",
        action="store_true",
        help="Use qml",
    )
    args, _ = parser.parse_known_args()
    qml = True if args.qml else False
    logger.attr("QML", qml)

    generate(qml)



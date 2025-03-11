import cv2
import json
from module.ocr.sub_ocr import Single
from pathlib import Path
from enum import Enum
MODULE_FOLDER = 'tasks'

# 定义图像文件扩展名
IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.bmp', '.tiff']

# 定义 OCR 规则模板
OCR_RULE_TEMPLATE = """
    # OCR Rule for {image_path}
    O_{rule_name} = RuleOcr(
        roi={roi},
        area={area},
        mode="Single",
        method="Default",
        keyword="{text}",
        name="{image_name}"
    )
"""

class OcrMode(Enum):
    FULL = 1  # str: "Full"
    SINGLE = 2  # str: "Single"
    DIGIT = 3  # str: "Digit"
    DIGITCOUNTER = 4  # str: "DigitCounter"
    DURATION = 5  # str: "Duration"
    QUANTITY = 6  # str: "Quantity"

class OcrMethod(Enum):
    DEFAULT = 1  # str: "Default"

def perform_ocr(image_path):
    """
    对指定图片进行 OCR 识别
    :param image_path: 图片文件路径
    :return: 识别到的文字
    """
    try:
        # 读取图片
        image = cv2.imread(image_path)
        if image is None:
            print(f"Error: Unable to load image from {image_path}")
            return None

        # 初始化 BaseCor
        ocr = Single(
            name="ocr",
            mode="SINGLE",
            method="DEFAULT",
            roi=(0, 0, image.shape[1], image.shape[0]),
            area=(0, 0, image.shape[1], image.shape[0]),
            keyword=""
        )

        # 进行 OCR 识别
        text = ocr.ocr_single_line(image)
        if text:
            return text.strip()
    except Exception as e:
        print(f"Error performing OCR on {image_path}: {e}")
    return None

def generate_ocr_rule(image_path, text):
    """
    生成 OCR 规则
    :param image_path: 图片文件路径
    :param text: 识别到的文字
    :return: 生成的 OCR 规则字符串
    """
    image_name = Path(image_path).stem
    image = cv2.imread(image_path)
    height, width, _ = image.shape
    rule_name = image_name.upper().replace(" ", "_")
    return OCR_RULE_TEMPLATE.format(
        image_path=image_path,
        rule_name=rule_name,
        roi=(0, 0, width, height),
        area=(0, 0, width, height),
        text=text,
        image_name=image_name
    )

def process_images_in_directory(directory):
    """
    处理指定目录下的所有图像文件
    :param directory: 目录路径
    :return: 成功提取到文字的图像清单和生成的 OCR 规则
    """
    image_list = []
    ocr_rules = []
    directory = Path(directory)

    # 遍历目录下的所有文件
    for image_path in directory.rglob("*"):
        if image_path.suffix.lower() in IMAGE_EXTENSIONS:
            print(f"Processing {image_path}...")
            # 进行 OCR 操作
            text = perform_ocr(str(image_path))
            if text:
                print(f"Text extracted: {text}")
                # 记录图像信息
                image_list.append({
                    "path": str(image_path),
                    "file_name": image_path.name,
                    "text": text
                })
                # 生成 OCR 规则
                ocr_rule = generate_ocr_rule(str(image_path), text)
                ocr_rules.append(ocr_rule)

    return image_list, ocr_rules

def save_results(image_list, ocr_rules, output_dir):
    """
    保存结果到文件
    :param image_list: 图像清单
    :param ocr_rules: OCR 规则
    :param output_dir: 输出目录
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    # 保存图像清单
    with open(output_dir / "image_list.json", "w", encoding="utf-8") as f:
        json.dump(image_list, f, indent=4, ensure_ascii=False)

    # 保存 OCR 规则
    with open(output_dir / "ocr_rules.py", "w", encoding="utf-8") as f:
        f.write("# Generated OCR Rules\n")
        f.write("from module.atom.ocr import RuleOcr\n\n")
        f.write("class Img2Ocr: \n")
        for rule in ocr_rules:
            f.write(rule + "\n")

def main():
    # 输入目录和输出目录
    input_directory = Path.cwd() / MODULE_FOLDER # 替换为你的图像目录
    output_directory = Path.cwd() / "dev_tools" /"output"  # 输出目录

    # 处理图像文件
    image_list, ocr_rules = process_images_in_directory(input_directory)

    # 保存结果
    save_results(image_list, ocr_rules, output_directory)

    print("Processing completed. Results saved to:", output_directory)

if __name__ == "__main__":
    main()

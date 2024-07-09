import cv2
import numpy as np

from module.logger import logger


def detect_safe_area(image, target_gray_value=255, tolerance=0):
    """
    在灰度图片中查找与目标灰度值在容差范围内的纯色区块，并返回这些区块的坐标。

    :param image_path: 图片路径
    :param target_gray_value: 目标灰度值，默认为255（最亮）
    :param tolerance: 灰度差异容忍度，默认为0（即完全匹配）
    :return: 包含找到的纯色区块坐标元组的列表
    """
    # 加载图片并转换为灰度图
    # img = Image.open(image_path).convert('L')  # 'L' 表示转换为灰度图
    # img_arr = np.array(img)  # 转换为numpy数组以便高效处理

    # 将图片转换为灰度图
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, img_arr = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)

    # 初始化结果列表
    solid_regions = []

    # 遍历图片的每个像素
    for y in range(img_arr.shape[0]):  # 高度
        for x in range(img_arr.shape[1]):  # 宽度
            pixel_gray_value = img_arr[y, x]

            # 检查当前像素灰度值是否与目标灰度值在容差范围内匹配
            if abs(pixel_gray_value - target_gray_value) <= tolerance:
                # 检查周围是否也是同样的灰度值，以确定这是一个区块而非单个像素
                is_solid_region = True
                for dy in range(-1, 2):  # 检查3x3区域
                    for dx in range(-1, 2):
                        if dy == 0 and dx == 0:
                            continue  # 跳过中心点
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < img_arr.shape[0] and 0 <= nx < img_arr.shape[1]:
                            if abs(img_arr[ny, nx] - target_gray_value) > tolerance:
                                is_solid_region = False
                                break
                    if not is_solid_region:
                        break

                if is_solid_region:
                    # 记录纯色区块的左上角坐标和右下角坐标
                    start_x, start_y = x, y
                    while start_y > 0 and abs(img_arr[start_y - 1, x] - target_gray_value) <= tolerance:
                        start_y -= 1
                    while start_x > 0 and abs(img_arr[y, start_x - 1] - target_gray_value) <= tolerance:
                        start_x -= 1
                    end_x, end_y = x, y
                    while end_y < img_arr.shape[0] - 1 and abs(img_arr[end_y + 1, x] - target_gray_value) <= tolerance:
                        end_y += 1
                    while end_x < img_arr.shape[1] - 1 and abs(img_arr[y, end_x + 1] - target_gray_value) <= tolerance:
                        end_x += 1

                    solid_regions.append(((start_x, start_y), (end_x + 1, end_y + 1)))

    return solid_regions


def detect_safe_area2(image, safe_color_lower, safe_color_upper, num_areas=3, debug=False):
    """
    找出当前截图里最大的纯色区域，找出来的这个区域将被用于随机点击的区域。
    :note:          注意拿到这个区域后要马上点击，不要sleep！
    :param image:   截图图像
    :return:        最大纯色区域的坐标
    """
    # 将图片从BGR转换到HSV色彩空间
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    # 定义颜色范围
    # 注意：这里的颜色范围需要根据实际图片中的安全区域颜色进行调整
    mask = cv2.inRange(hsv, safe_color_lower, safe_color_upper)

    # 应用形态学操作来消除噪点和填补小的孔洞
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.dilate(mask, kernel, iterations=1)
    mask = cv2.erode(mask, kernel, iterations=1)

    # 查找轮廓
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # 计算每个轮廓的面积并排序
    # areas = [(cv2.contourArea(contour), contour) for contour in contours]
    areas = []
    for contour in contours:
        area = cv2.contourArea(contour)
        print(f"area={area}")
        areas.append((area, contour))

    # areas.sort(reverse=True)
    # 按面积降序排序
    areas_sorted = sorted(areas, key=lambda x: x[0], reverse=True)

    if debug:
        # 绘制面积排名前3的区域
        for area, contour in areas_sorted[:num_areas]:
            x1, y1, w1, h1 = cv2.boundingRect(contour)
            # 使用蓝色边框，线宽为4
            cv2.rectangle(image, (x1, y1), (x1 + w1, y1 + h1), (255, 0, 0), 4)
            # 使用红色边框，线宽为3
            cv2.drawContours(image, [contour], -1, (0, 0, 255), 3)

    # 假设最大的轮廓是安全区域
    if contours:
        safe_area = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(safe_area)

        if debug:
            # 绘制安全区域
            cv2.drawContours(image, [safe_area], -1, (0, 255, 0), 3)

        return (x, y, w, h)

    return (0, 0, 0, 0)


def test_ocr_locate_dokan_target():
    import cv2
    from module.atom.ocr import RuleOcr

    logger.info("========================================>>test 2")
    O_DOKAN_MAP = RuleOcr(roi=(270, 130, 740, 460), area=(270, 130, 740, 460), mode="Full", method="Default",
                          keyword="万", name="dokan_map")

    image = cv2.imread("g:/yys/oas/tests/1.png")
    pos = O_DOKAN_MAP.ocr_full(image)
    print(f"image1: {pos}")

    image = cv2.imread("g:/yys/oas/tests/2.png")
    pos = O_DOKAN_MAP.ocr_full(image)
    print(f"image2: {pos}")

    image = cv2.imread("g:/yys/oas/tests/3.png")
    pos = O_DOKAN_MAP.ocr_full(image)
    print(f"image3: {pos}")

    image = cv2.imread("g:/yys/oas/tests/4.png")
    pos = O_DOKAN_MAP.ocr_full(image)
    print(f"image4: {pos}")
    if pos == (0, 0, 0, 0):
        logger.info("failed to find {self.O_DOKAN_MAP.keyword}")
    else:
        # 取中间
        x = pos[0] + pos[2] / 2
        # 往上偏移20
        y = pos[1] - 20

        logger.info(f"ocr detect result pos={pos}, try click pos, x={x}, y={y}")


def test_anti_detect_random_click():
    import cv2

    # image_list = ['g:/yys/oas/tests/1.png', 'g:/yys/oas/tests/2.png', 'g:/yys/oas/tests/3.png', 'g:/yys/oas/tests/4.png', 'g:/yys/oas/tests/5.png']
    image_list = ['g:/yys/oas/tests/a.png', 'g:/yys/oas/tests/b.png', 'g:/yys/oas/tests/c.png']

    for item in image_list:
        print(f"item: {item}")
        image = cv2.imread(item)

        # 注意：这里的颜色范围需要根据实际图片进行调整
        # http://kb.rg4.net/docs/omassistant/omassistant-1fnirpstkhdnh
        # 0<=h<20， 红色
        # 30<=h<45，黄色
        # 45<=h<90，绿色
        # 90<=h<125，青色
        # 125<=h<150，蓝色
        # 150<=h<175，紫色
        # 175<=h<200，粉红色
        # 200<=h<220，砖红色
        # 220<=h<255，品红色

        # 示例使用：假设安全区域是绿色的
        safe_color_lower = np.array([45, 25, 25])  # HSV颜色空间的绿色下界
        safe_color_upper = np.array([90, 255, 255])  # HSV颜色空间的绿色上界

        # 读取图片
        image = cv2.imread('c.png')
        if image is None:
            print("Error: Image not found.")
        else:
            # 调用函数
            pos = detect_safe_area2(image, safe_color_lower, safe_color_upper, 3, True)
            print(f"pos={pos}")

            # 显示结果
            cv2.imshow('Safe Area', image)
            cv2.waitKey(0)
            cv2.destroyAllWindows()



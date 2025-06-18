import cv2

def match_template(main_image_path, template_image_path, threshold=0.8):
    # 读取主图像和模板图像
    main_image = cv2.imread(main_image_path)
    template_image = cv2.imread(template_image_path)

    if main_image is None or template_image is None:
        raise ValueError("One or both images could not be read. Please check the file paths.")

    # 获取模板图像的高度和宽度
    h, w = template_image.shape[:2]

    # 使用模板匹配方法进行匹配
    result = cv2.matchTemplate(main_image, template_image, cv2.TM_CCOEFF_NORMED)

    # 找到最佳匹配的位置
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    

    # 检查匹配值是否高于阈值
    if max_val >= threshold:
        # 计算最佳匹配位置的左上角坐标
        top_left = max_loc
        x, y = top_left
        return x, y
    else:
        return None, None
# 示例用法
if __name__ == "__main__":
    main_image_path = r"C:\Users\MG\Desktop\4.png"
    template_image_path =  r"C:\Users\MG\Desktop\11.png"

    best_x, best_y = match_template(main_image_path, template_image_path)
    if best_x is not None and best_y is not None:
        print(f"Best match position: ({best_x}, {best_y})")
    else:
        print("No match found with confidence above 0.8.")


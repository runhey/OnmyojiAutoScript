import cv2
# import pytesseract

def find_image(image, pattern, threshold: float = 0.9, top1_only: bool = True, draw_result: bool = False):
    '''
    以图搜图
    使用全图进行模板匹配，来匹配当前画面中有没有输入的pattern
    :return 匹配到的数量
    '''
    results = cv2.matchTemplate(image, pattern, cv2.TM_CCOEFF_NORMED)

    count = 0
    img_disp = None
    pos = []

    if draw_result:
        img_disp = image.copy()

    if top1_only:
        _, max_val, _, max_loc = cv2.minMaxLoc(results)
        # 找到最佳匹配位置的坐标
        if max_val >= threshold:
            top_left = max_loc
            bottom_right = (top_left[0] + pattern.shape[1], top_left[1] + pattern.shape[0])
            count = 1
            # print(f'top_left={top_left}, similiar={max_val}')

            pos.append((top_left[0], top_left[1], bottom_right[0], bottom_right[1]))

            if draw_result:
                # 在原始图像上绘制矩形框来突出显示匹配出的图案
                cv2.rectangle(img_disp, top_left, bottom_right, (0, 255, 0), 2)
        else:
            count = 0
    else:
        #筛选大于一定匹配值的点
        val,result = cv2.threshold(results,threshold,1.0,cv2.THRESH_BINARY)
        match_locs = cv2.findNonZero(result)
        # print('match_locs.shape:',match_locs.shape) 
        # print('match_locs:\n',match_locs)

        count = len(match_locs)

        # 找到最佳匹配位置的坐标
        for match_loc_t in match_locs:
            #match_locs是一个3维数组，第2维固定长度为1，取其下标0对应数组
            top_left = match_loc_t[0]
            bottom_right = (top_left[0] + pattern.shape[1], top_left[1] + pattern.shape[0])
            # print(f'top_left={top_left}, similar={results[top_left[1],top_left[0]]}')

            pos.append((top_left[0], top_left[1], bottom_right[0], bottom_right[1]))

            if draw_result:
                # 在原始图像上绘制矩形框来突出显示匹配出的图案
                cv2.rectangle(img_disp, top_left, bottom_right, (0,255,0), 5, 8, 0 )
                cv2.circle(result, top_left, 10, (255,0,0), 3 )

        # TODO 去除重叠的区域，只留该区域里相似度最高的
        

    if draw_result:
        cv2.imshow('Matched Result', img_disp)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    return count, pos
 
# def find_text(image, text) -> int:
#     '''
#     以文搜图
#     使用图像识别库进行图像识别和文字检测
#     使用全图进行模板匹配，来匹配当前画面中有没有输入的文字
#     :return 匹配到的数量
#     '''
#     # 
#     extracted_text = pytesseract.image_to_string(image)
    
#     match_indices = [i for i, item in enumerate(extracted_text) if text in item]
 
#     count = len(match_indices)
#     if count > 0:
#         print(f'Found {count} locations matches the input pattern.')
#         # 可以根据需求输出或显示匹配的结果
#     else:
#         print('Pattern not found.')

#     return count

if __name__ == '__main__':

    # 读取待搜索的图像和目标图像
    image_path = "tests/toppa_scrolls/test.png"
    pattern_path = "tests/toppa_scrolls/res_toppa_scroll.png"

    image = cv2.imread(image_path)
    pattern = cv2.imread(pattern_path)
    if image is None or pattern is None:
        print(f"image file not exists? {image_path}, patter image file: {pattern_path}")
    else:
        # find_text(image, "突破")
        count, pos = find_image(image, pattern, 0.9, False, False)
        print(f"count={count}, pos={pos}")

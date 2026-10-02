# image 迁移

`alasio/base/image/` 6 文件 1510 行 → `script/misc/image/`（只改 import）。

## A 类：Alasio 为准，换掉 `oas/base/utils/utils.py` 的重复

| 函数 | 变化 |
|---|---|
| `rgb2gray` `color_similarity` `color_similar` | `dst=` 就地复用，去 numpy |
| `color_similarity_2d` `extract_letters` | 双路径：<30000px 走 3 通道 |
| `extract_white_letters` | 反色域算 |
| `rgb2hsv` | 修 `np.float` |
| `rgb2luma` | 加 `fast=True` |
| `get_color` | `area` 变可选 |
| `image_channel` | 灰度 `0`→`1` |

本来就一样没动：`crop` `image_size` `resize` `color_similar_1d`

Alasio 版在 `script/misc/image/color.py` 里把 OAS 原码逐字注释留作对照（7 处）。

## B 类：Alasio 独有 32 个

原样保留在 `script/misc/image/`，含 `color_mask` `rgbmax` `rgbmin` `rgbminmax` `rgb565_to_rgb888`。

## C-image：5 个 OAS 独有 → `script/misc/image/extra.py`

`rgb2yuv` `color_mapping` `color_bar_percentage` `image_left_strip` `red_overlay_transparency`，全部 0 调用方。

## 没搬

| 项 | 原因 |
|---|---|
| `get_bbox` | 要中层的 `ImageNotSupported`，会反向依赖。0 调用 |
| `load_image` `save_image` | 被 `image_load` `image_save` 取代，参数顺序相反。有活调用方 |

## 验证

9 个函数与 Alasio 逐字节一致；`4789 passed, 63 skipped`；`oas/`+`script/` 零 numpy 已删别名。
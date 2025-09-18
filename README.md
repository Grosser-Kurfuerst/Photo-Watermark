# Photo-Watermark

一个命令行工具：读取图片 EXIF 拍摄时间 (年-月-日) 并生成文字水印，支持单文件或整目录批量处理，输出到“原目录名_watermark”子目录，不修改原图。

---
## 功能特性
- 自动提取 EXIF 拍摄日期 (DateTimeOriginal / DateTimeDigitized / DateTime)
- 未找到日期则跳过并提示
- 支持输入：单个图片文件 或 包含多张图片的目录
- 支持格式：JPG / JPEG / PNG / TIFF / BMP
- 可自定义：字体大小、颜色、位置（九宫格）
- 半透明黑色底框提高可读性
- 覆盖已存在的同名输出文件

---
## 环境要求
- Python 3.6+
- 系统已安装常见中文或西文字体（工具会尝试：simhei.ttf、msyh.ttc、arial.ttf）

---
## 安装
### 克隆或下载代码后安装依赖
```bash
pip install -r requirements.txt
```
或手动：
```bash
pip install Pillow piexif click
```
> PowerShell 请逐条执行，不要使用 `&&`。

---
## 快速开始
处理目录：
```bash
python watermark.py /path/to/photos
```
处理单个文件：
```bash
python watermark.py /path/to/photos/IMG_0001.jpg
```

---
## 命令参数
| 参数 | 必填 | 默认 | 说明 |
|------|------|------|------|
| input_path | 是 | - | 图片文件或目录路径 |
| -s / --font-size | 否 | 36 | 字体大小（像素） |
| -c / --color | 否 | white | 字体颜色（颜色名或 #RRGGBB） |
| -p / --position | 否 | bottom-right | 水印位置（九宫格） |

支持位置值：
```
 top-left     top-center     top-right
 center-left  center         center-right
 bottom-left  bottom-center  bottom-right
```

---
## 示例
1) 目录批量：
```bash
python watermark.py "C:/Photos/Trip2024"
```
2) 单文件：
```bash
python watermark.py "C:/Photos/Trip2024/IMG_1234.JPG"
```
3) 指定红色中央：
```bash
python watermark.py ./album -c red -p center
```
4) 指定大小与颜色（十六进制）：
```bash
python watermark.py ./album -s 54 -c #FFAA33 -p top-left
```

---
## 输出目录规则
| 输入类型 | 示例输入 | 输出目录 |
|----------|----------|----------|
| 目录 | C:/Photos/Trip2024 | C:/Photos/Trip2024/Trip2024_watermark |
| 单文件 | C:/Photos/Trip2024/IMG_0001.JPG | C:/Photos/Trip2024/Trip2024_watermark |

水印图片文件名与原文件名相同。

---
## EXIF 日期获取逻辑
优先顺序：
1. Exif: DateTimeOriginal
2. Exif: DateTimeDigitized
3. 0th: DateTime

日期格式解析：`YYYY:MM:DD HH:MM:SS` → 输出 `YYYY-MM-DD`

若图片缺失 EXIF 或字段损坏：该图片跳过。

---
## 常见问题 (FAQ)
**Q1: 输出目录为什么为空？**  
A: 可能所有图片都缺少 EXIF 拍摄时间；用图片查看器验证是否存在拍摄时间。

**Q2: PNG 没有 EXIF 怎么办？**  
A: 大多数 PNG 没有拍摄时间，会被跳过，可手动添加或改代码自定义文本。

**Q3: 想去掉水印背景框？**  
A: 编辑 `watermark.py`，删除 `overlay_draw.rectangle(...)` 和 `alpha_composite` 相关几行。

**Q4: 想自定义文字内容？**  
A: 修改 `add_watermark` 中 `date_text` 变量，或新增参数。

**Q5: 颜色怎么写？**  
A: 支持如 `white`, `red`, `#1122CC`, `#FFAA00`。

**Q6: 字体锯齿明显？**  
A: 增大字体或换更清晰的字体（在 font_paths 中添加路径）。

---
## 代码关键点
`PhotoWatermark` 类：
- `get_exif_date()` 解析并返回日期字符串
- `add_watermark()` 渲染半透明背景 + 绘制文字
- `process_directory()` 批量处理
- `process_single_file()` 单文件模式

---
## 可能的改进方向（未实现）
- 递归子目录处理
- 自定义水印文字模板（如：`{date} 我的水印`）
- 去重检查（防止重复处理）
- 添加并保留 EXIF 到输出文件
- 多语言 CLI

---
## 依赖说明
| 库 | 作用 |
|----|------|
| Pillow | 图像读写与绘制 |
| piexif | 解析 EXIF 信息 |
| click | 构建命令行界面 |

安装：`pip install -r requirements.txt`

---
## 简易调试建议
```bash
# 查看脚本帮助
python watermark.py --help

# 仅测试一张含 EXIF 的图片
python watermark.py tests/sample.jpg -p center -c yellow -s 40
```

---
## 许可证
MIT License

---
## 快速问题定位表
| 现象 | 可能原因 | 建议 |
|------|----------|------|
| 全部跳过 | 无 EXIF 或无日期字段 | 用 exif 查看工具确认；改为自定义文本 | 
| 中文字体不生效 | 系统缺字体文件 | 放置 ttf 并修改 font_paths |
| 颜色不正确 | 十六进制错误 | 使用 `#RRGGBB` 格式 |
| 输出过暗 | 半透明背景遮挡 | 去除背景矩形 |

---
如需新增功能（递归、文本模板、LOG输出）可继续提出。

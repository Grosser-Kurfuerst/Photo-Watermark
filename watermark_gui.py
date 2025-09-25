#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Photo Watermark GUI Tool
基于GUI的图片水印工具，支持拖拽导入、批量处理和缩略图预览
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
from PIL import Image, ImageTk, ImageDraw, ImageFont, ImageEnhance
import piexif
from pathlib import Path
from datetime import datetime
import threading


class ImageItem:
    """图片项目类，存储图片信息"""

    def __init__(self, file_path):
        self.file_path = Path(file_path)
        self.thumbnail = None
        self.exif_date = None
        self.processed = False
        self._load_thumbnail()
        self._extract_exif_date()

    def _load_thumbnail(self):
        """加载缩略图"""
        try:
            with Image.open(self.file_path) as img:
                img.thumbnail((100, 100), Image.Resampling.LANCZOS)
                self.thumbnail = ImageTk.PhotoImage(img)
        except Exception as e:
            print(f"无法加载缩略图: {e}")
            self.thumbnail = None

    def _extract_exif_date(self):
        """提取EXIF拍摄时间"""
        try:
            with Image.open(self.file_path) as image:
                exif_bytes = image.info.get('exif', b'')
                if not exif_bytes:
                    return

                exif_data = piexif.load(exif_bytes)
                date_fields = [
                    piexif.ExifIFD.DateTimeOriginal,
                    piexif.ExifIFD.DateTimeDigitized,
                ]

                for field in date_fields:
                    if field in exif_data.get('Exif', {}):
                        try:
                            date_str = exif_data['Exif'][field].decode('utf-8')
                            date_obj = datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
                            self.exif_date = date_obj.strftime('%Y-%m-%d')
                            return
                        except Exception:
                            continue

                if piexif.ImageIFD.DateTime in exif_data.get('0th', {}):
                    try:
                        date_str = exif_data['0th'][piexif.ImageIFD.DateTime].decode('utf-8')
                        date_obj = datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
                        self.exif_date = date_obj.strftime('%Y-%m-%d')
                    except Exception:
                        pass
        except Exception as e:
            print(f"无法提取EXIF信息: {e}")


class WatermarkGUI:
    """图片水印GUI应用程序"""

    def __init__(self, root):
        self.root = root
        self.root.title("Photo Watermark Tool - GUI版本")
        self.root.geometry("1000x700")

        # 支持的图片格式
        self.supported_formats = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}
        self.image_items = []

        # --- 设置变量 ---
        # 水印类型
        self.watermark_type = tk.StringVar(value="Text")

        # 文本水印变量
        self.font_size = tk.IntVar(value=36)
        self.color = tk.StringVar(value="white")
        self.text_opacity = tk.IntVar(value=100)
        self.watermark_text_source = tk.StringVar(value="EXIF Date")
        self.custom_watermark_text = tk.StringVar(value="自定义水印")

        # 图片水印变量
        self.image_watermark_path = tk.StringVar()
        self.image_opacity = tk.IntVar(value=100)
        self.image_scale = tk.IntVar(value=20) # 默认缩放为原图的20%

        # 通用变量
        self.position = tk.StringVar(value="bottom-right")

        # 输出变量
        self.output_format = tk.StringVar(value="JPEG")
        self.output_quality = tk.IntVar(value=95)
        self.output_dir = tk.StringVar()
        self.filename_prefix = tk.StringVar()
        self.filename_suffix = tk.StringVar(value="_watermarked")
        self.resize_option = tk.StringVar(value="不缩放")
        self.resize_value = tk.IntVar(value=100)

        self.create_widgets()
        self.setup_drag_drop()

    def create_widgets(self):
        """创建GUI组件"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")

        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(1, weight=1)

        # 导入区域
        import_frame = ttk.LabelFrame(main_frame, text="图片导入", padding="5")
        import_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        ttk.Button(import_frame, text="选择文件", command=self.select_files).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(import_frame, text="选择文件夹", command=self.select_folder).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(import_frame, text="清空列表", command=self.clear_list).pack(side=tk.LEFT, padx=(0, 5))

        # 拖拽提示
        drag_label = ttk.Label(import_frame, text="或直接拖拽图片文件到下方列表", foreground="gray")
        drag_label.pack(side=tk.RIGHT)

        # --- 设置区域 ---
        settings_frame = ttk.LabelFrame(main_frame, text="水印设置", padding="5")
        settings_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        settings_frame.columnconfigure(1, weight=1)

        # --- 水印类型选择 ---
        ttk.Label(settings_frame, text="水印类型:").grid(row=0, column=0, sticky="w", pady=2)
        watermark_type_frame = ttk.Frame(settings_frame)
        watermark_type_frame.grid(row=0, column=1, columnspan=2, sticky="ew", pady=2, padx=(5, 0))

        text_watermark_frame = ttk.LabelFrame(settings_frame, text="文本水印设置", padding="10")
        image_watermark_frame = ttk.LabelFrame(settings_frame, text="图片水印设置", padding="10")

        def on_watermark_type_change():
            if self.watermark_type.get() == "Text":
                text_watermark_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=5)
                image_watermark_frame.grid_remove()
            else:
                image_watermark_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=5)
                text_watermark_frame.grid_remove()

        ttk.Radiobutton(
            watermark_type_frame, text="文本", variable=self.watermark_type,
            value="Text", command=on_watermark_type_change
        ).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(
            watermark_type_frame, text="图片", variable=self.watermark_type,
            value="Image", command=on_watermark_type_change
        ).pack(side=tk.LEFT)

        # --- 文本水印设置框架 ---
        text_watermark_frame.columnconfigure(1, weight=1)

        # 字体大小
        ttk.Label(text_watermark_frame, text="字体大小:").grid(row=0, column=0, sticky="w", pady=2)
        font_size_display = tk.StringVar(value=str(self.font_size.get()))
        def update_font_size_display(value):
            int_value = int(float(value))
            self.font_size.set(int_value)
            font_size_display.set(str(int_value))
        font_scale = ttk.Scale(text_watermark_frame, from_=12, to=100, variable=self.font_size, orient=tk.HORIZONTAL, command=update_font_size_display)
        font_scale.grid(row=0, column=1, sticky="ew", pady=2, padx=(5, 0))
        ttk.Label(text_watermark_frame, textvariable=font_size_display).grid(row=0, column=2, pady=2, padx=(5, 0))

        # 颜色选择
        ttk.Label(text_watermark_frame, text="字体颜色:").grid(row=1, column=0, sticky="w", pady=2)
        color_frame = ttk.Frame(text_watermark_frame)
        color_frame.grid(row=1, column=1, columnspan=2, sticky="ew", pady=2, padx=(5, 0))
        ttk.Entry(color_frame, textvariable=self.color, width=10).pack(side=tk.LEFT)
        ttk.Button(color_frame, text="选择颜色", command=self.choose_color).pack(side=tk.LEFT, padx=(5, 0))

        # 文本透明度
        ttk.Label(text_watermark_frame, text="文本透明度:").grid(row=2, column=0, sticky="w", pady=2)
        opacity_display = tk.StringVar(value=f"{self.text_opacity.get()}%")
        def update_opacity_display(value):
            int_value = int(float(value))
            self.text_opacity.set(int_value)
            opacity_display.set(f"{int_value}%")
        opacity_scale = ttk.Scale(text_watermark_frame, from_=0, to=100, variable=self.text_opacity, orient=tk.HORIZONTAL, command=update_opacity_display)
        opacity_scale.grid(row=2, column=1, sticky="ew", pady=2, padx=(5, 0))
        ttk.Label(text_watermark_frame, textvariable=opacity_display).grid(row=2, column=2, pady=2, padx=(5, 0))

        # 水印文本来源
        ttk.Label(text_watermark_frame, text="水印内容:").grid(row=3, column=0, sticky="w", pady=2)
        text_source_frame = ttk.Frame(text_watermark_frame)
        text_source_frame.grid(row=3, column=1, columnspan=2, sticky="ew", pady=2, padx=(5, 0))
        custom_text_entry = ttk.Entry(text_watermark_frame, textvariable=self.custom_watermark_text)
        def on_text_source_change():
            if self.watermark_text_source.get() == "Custom Text":
                custom_text_entry.grid(row=4, column=1, columnspan=2, sticky="ew", pady=2, padx=(5, 0))
            else:
                custom_text_entry.grid_remove()
        ttk.Radiobutton(text_source_frame, text="EXIF日期", variable=self.watermark_text_source, value="EXIF Date", command=on_text_source_change).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(text_source_frame, text="自定义文本", variable=self.watermark_text_source, value="Custom Text", command=on_text_source_change).pack(side=tk.LEFT)
        on_text_source_change()

        # --- 图片水印设置框架 ---
        image_watermark_frame.columnconfigure(1, weight=1)

        # 图片选择
        ttk.Label(image_watermark_frame, text="水印图片:").grid(row=0, column=0, sticky="w", pady=2)
        image_path_frame = ttk.Frame(image_watermark_frame)
        image_path_frame.grid(row=0, column=1, columnspan=2, sticky="ew", pady=2, padx=(5, 0))
        ttk.Entry(image_path_frame, textvariable=self.image_watermark_path, state="readonly").pack(side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Button(image_path_frame, text="选择图片...", command=self.select_watermark_image).pack(side=tk.LEFT, padx=(5, 0))

        # 图片缩放
        ttk.Label(image_watermark_frame, text="水印缩放(%):").grid(row=1, column=0, sticky="w", pady=2)
        image_scale_display = tk.StringVar(value=f"{self.image_scale.get()}%")
        def update_image_scale_display(value):
            int_value = int(float(value))
            self.image_scale.set(int_value)
            image_scale_display.set(f"{int_value}%")
        image_scale_slider = ttk.Scale(image_watermark_frame, from_=1, to=100, variable=self.image_scale, orient=tk.HORIZONTAL, command=update_image_scale_display)
        image_scale_slider.grid(row=1, column=1, sticky="ew", pady=2, padx=(5, 0))
        ttk.Label(image_watermark_frame, textvariable=image_scale_display).grid(row=1, column=2, pady=2, padx=(5, 0))

        # 图片透明度
        ttk.Label(image_watermark_frame, text="图片透明度:").grid(row=2, column=0, sticky="w", pady=2)
        image_opacity_display = tk.StringVar(value=f"{self.image_opacity.get()}%")
        def update_image_opacity_display(value):
            int_value = int(float(value))
            self.image_opacity.set(int_value)
            image_opacity_display.set(f"{int_value}%")
        image_opacity_slider = ttk.Scale(image_watermark_frame, from_=0, to=100, variable=self.image_opacity, orient=tk.HORIZONTAL, command=update_image_opacity_display)
        image_opacity_slider.grid(row=2, column=1, sticky="ew", pady=2, padx=(5, 0))
        ttk.Label(image_watermark_frame, textvariable=image_opacity_display).grid(row=2, column=2, pady=2, padx=(5, 0))

        # --- 通用设置 ---
        common_settings_frame = ttk.LabelFrame(settings_frame, text="通用与输出设置", padding="10")
        common_settings_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=5)
        common_settings_frame.columnconfigure(1, weight=1)

        # 位置选择
        ttk.Label(common_settings_frame, text="水印位置:").grid(row=0, column=0, sticky="w", pady=2)
        position_combo = ttk.Combobox(common_settings_frame, textvariable=self.position, state="readonly")
        position_combo['values'] = ('top-left', 'top-center', 'top-right', 'center-left', 'center', 'center-right', 'bottom-left', 'bottom-center', 'bottom-right')
        position_combo.grid(row=0, column=1, columnspan=2, sticky="ew", pady=2, padx=(5, 0))

        # 输出格式
        ttk.Label(common_settings_frame, text="输出格式:").grid(row=1, column=0, sticky="w", pady=2)
        format_combo = ttk.Combobox(common_settings_frame, textvariable=self.output_format, state="readonly")
        format_combo['values'] = ('JPEG', 'PNG')
        format_combo.grid(row=1, column=1, columnspan=2, sticky="ew", pady=2, padx=(5, 0))

        # 输出质量（仅JPEG）
        ttk.Label(common_settings_frame, text="JPEG质量:").grid(row=2, column=0, sticky="w", pady=2)
        quality_display = tk.StringVar(value=str(self.output_quality.get()))
        def update_quality_display(value):
            int_value = int(float(value))
            self.output_quality.set(int_value)
            quality_display.set(str(int_value))
        quality_scale = ttk.Scale(common_settings_frame, from_=1, to=100, variable=self.output_quality, orient=tk.HORIZONTAL, command=update_quality_display)
        quality_scale.grid(row=2, column=1, sticky="ew", pady=2, padx=(5, 0))
        ttk.Label(common_settings_frame, textvariable=quality_display).grid(row=2, column=2, pady=2, padx=(5, 0))

        # 输出文件夹
        ttk.Label(common_settings_frame, text="输出文件夹:").grid(row=3, column=0, sticky="w", pady=2)
        output_dir_frame = ttk.Frame(common_settings_frame)
        output_dir_frame.grid(row=3, column=1, columnspan=2, sticky="ew", pady=2, padx=(5, 0))
        ttk.Entry(output_dir_frame, textvariable=self.output_dir).pack(side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Button(output_dir_frame, text="选择...", command=self.select_output_dir).pack(side=tk.LEFT, padx=(5, 0))

        # 文件名前缀
        ttk.Label(common_settings_frame, text="文件名前缀:").grid(row=4, column=0, sticky="w", pady=2)
        ttk.Entry(common_settings_frame, textvariable=self.filename_prefix).grid(row=4, column=1, columnspan=2, sticky="ew", pady=2, padx=(5, 0))

        # 文件名后缀
        ttk.Label(common_settings_frame, text="文件名后缀:").grid(row=5, column=0, sticky="w", pady=2)
        ttk.Entry(common_settings_frame, textvariable=self.filename_suffix).grid(row=5, column=1, columnspan=2, sticky="ew", pady=2, padx=(5, 0))

        # 缩放选项
        ttk.Label(common_settings_frame, text="调整尺寸:").grid(row=6, column=0, sticky="w", pady=2)
        resize_frame = ttk.Frame(common_settings_frame)
        resize_frame.grid(row=6, column=1, columnspan=2, sticky="ew", pady=2, padx=(5, 0))
        resize_combo = ttk.Combobox(resize_frame, textvariable=self.resize_option, state="readonly", width=10)
        resize_combo['values'] = ('不缩放', '按宽度', '按高度', '按百分比')
        resize_combo.pack(side=tk.LEFT, padx=(0, 5))
        ttk.Entry(resize_frame, textvariable=self.resize_value, width=8).pack(side=tk.LEFT)

        # 处理按钮
        ttk.Button(settings_frame, text="开始处理", command=self.process_images).grid(row=3, column=0, columnspan=3, pady=10)

        # 初始状态
        on_watermark_type_change()
        # 图片列表区域
        list_frame = ttk.LabelFrame(main_frame, text="图片列表", padding="5")
        list_frame.grid(row=1, column=1, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        # 创建带滚动条的Canvas
        self.canvas = tk.Canvas(list_frame)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        # 进度条
        self.progress = ttk.Progressbar(main_frame, mode='determinate')
        self.progress.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        # 状态标签
        self.status_label = ttk.Label(main_frame, text="就绪")
        self.status_label.grid(row=3, column=0, columnspan=2, pady=(5, 0))

    def setup_drag_drop(self):
        """设置拖拽功能"""
        try:
            # 检查 root 是否支持拖拽
            if hasattr(self.root, 'drop_target_register'):
                from tkinterdnd2 import DND_FILES
                self.root.drop_target_register(DND_FILES)
                self.root.dnd_bind('<<Drop>>', self.on_drop)
        except ImportError:
            # 如果 tkinterdnd2 未安装，此代码块不会执行，因为 main 函数会处理
            pass

    def on_drop(self, event):
        """处理拖拽事件"""
        files = self.root.tk.splitlist(event.data)
        self.add_files(files)

    def select_files(self):
        """选择文件"""
        filetypes = [
            ('图片文件', '*.jpg *.jpeg *.png *.bmp *.tiff *.tif'),
            ('JPEG文件', '*.jpg *.jpeg'),
            ('PNG文件', '*.png'),
            ('BMP文件', '*.bmp'),
            ('TIFF文件', '*.tiff *.tif'),
            ('所有文件', '*.*')
        ]

        files = filedialog.askopenfilenames(
            title="选择图片文件",
            filetypes=filetypes
        )

        if files:
            self.add_files(files)

    def select_folder(self):
        """选择文件夹"""
        folder = filedialog.askdirectory(title="选择包含图片的文件夹")
        if folder:
            folder_path = Path(folder)
            image_files = []
            for ext in self.supported_formats:
                image_files.extend(folder_path.glob(f"*{ext}"))
                image_files.extend(folder_path.glob(f"*{ext.upper()}"))

            if image_files:
                self.add_files([str(f) for f in image_files])
            else:
                messagebox.showinfo("提示", "所选文件夹中没有找到支持的图片文件")

    def add_files(self, file_paths):
        """添加文件到列表"""
        added_count = 0
        for file_path in file_paths:
            path = Path(file_path)

            # 检查文件是否存在且为支持的格式
            if path.exists() and path.suffix.lower() in self.supported_formats:
                # 检查是否已经添加
                if not any(item.file_path == path for item in self.image_items):
                    try:
                        image_item = ImageItem(path)
                        self.image_items.append(image_item)
                        added_count += 1
                    except Exception as e:
                        print(f"无法添加文件 {path}: {e}")

        if added_count > 0:
            self.update_image_list()
            self.status_label.config(text=f"已添加 {added_count} 个文件，总计 {len(self.image_items)} 个")
        else:
            messagebox.showwarning("警告", "没有找到可添加的有效图片文件")

    def update_image_list(self):
        """更新图片列表显示"""
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        for i, item in enumerate(self.image_items):
            item_frame = ttk.Frame(self.scrollable_frame, padding=5)
            item_frame.grid(row=i, column=0, sticky="ew", pady=2)

            if item.thumbnail:
                thumb_label = ttk.Label(item_frame, image=item.thumbnail)
                thumb_label.grid(row=0, column=0, rowspan=2, padx=(0, 10))

            filename_label = ttk.Label(item_frame, text=item.file_path.name, font=("Segoe UI", 10, "bold"))
            filename_label.grid(row=0, column=1, sticky="w")

            exif_info = f"拍摄时间: {item.exif_date}" if item.exif_date else "无EXIF时间"
            exif_label = ttk.Label(item_frame, text=exif_info, foreground="gray")
            exif_label.grid(row=1, column=1, sticky="w")

    def select_output_dir(self):
        """选择输出文件夹"""
        directory = filedialog.askdirectory(title="选择输出文件夹")
        if directory:
            self.output_dir.set(directory)

    def clear_list(self):
        """清空图片列表"""
        self.image_items.clear()
        self.update_image_list()
        self.status_label.config(text="列表已清空")

    def choose_color(self):
        """选择颜色"""
        color_code = colorchooser.askcolor(title="选择字体颜色")
        if color_code[1]:
            self.color.set(color_code[1])

    def select_watermark_image(self):
        """选择水印图片"""
        filetypes = [('PNG图片', '*.png'), ('所有文件', '*.*')]
        filepath = filedialog.askopenfilename(title="选择水印图片", filetypes=filetypes)
        if filepath:
            self.image_watermark_path.set(filepath)

    def get_position_coordinates(self, image_size, watermark_size, position):
        """根据位置参数计算水印坐标"""
        img_width, img_height = image_size
        wm_width, wm_height = watermark_size

        positions = {
            'top-left': (10, 10),
            'top-center': ((img_width - wm_width) // 2, 10),
            'top-right': (img_width - wm_width - 10, 10),
            'center-left': (10, (img_height - wm_height) // 2),
            'center': ((img_width - wm_width) // 2, (img_height - wm_height) // 2),
            'center-right': (img_width - wm_width - 10, (img_height - wm_height) // 2),
            'bottom-left': (10, img_height - wm_height - 10),
            'bottom-center': ((img_width - wm_width) // 2, img_height - wm_height - 10),
            'bottom-right': (img_width - wm_width - 10, img_height - wm_height - 10)
        }
        return positions.get(position, positions['bottom-right'])

    def apply_text_watermark(self, image, params):
        """应用文本水印"""
        watermark_text = ""
        if params["watermark_text_source"] == "EXIF Date":
            if not params["image_item"].exif_date:
                return None, "无EXIF拍摄时间"
            watermark_text = params["image_item"].exif_date
        else:  # Custom Text
            if not params["custom_watermark_text"]:
                return None, "自定义文本为空"
            watermark_text = params["custom_watermark_text"]

        draw = ImageDraw.Draw(image)
        try:
            font_paths = ["C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/arial.ttf"]
            font = next((ImageFont.truetype(fp, params["font_size"]) for fp in font_paths if os.path.exists(fp)), ImageFont.load_default())
        except Exception:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), watermark_text, font=font)
        text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x, y = self.get_position_coordinates(image.size, (text_width, text_height), params["position"])

        try:
            rgb_color = Image.new("RGB", (1, 1), params["color"]).getpixel((0, 0))
        except ValueError:
            from PIL import ImageColor
            rgb_color = ImageColor.getrgb(params["color"])

        alpha = int(255 * (params["text_opacity"] / 100))
        final_color = rgb_color + (alpha,)

        overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        padding = 5
        overlay_draw.rectangle(
            [x - padding, y - padding, x + text_width + padding, y + text_height + padding],
            fill=(0, 0, 0, int(128 * (params["text_opacity"] / 100)))
        )
        image = Image.alpha_composite(image, overlay)

        final_draw = ImageDraw.Draw(image)
        final_draw.text((x, y), watermark_text, fill=final_color, font=font)
        return image, "成功"

    def apply_image_watermark(self, image, params):
        """应用图片水印"""
        watermark_path = params["image_watermark_path"]
        if not watermark_path or not Path(watermark_path).exists():
            return None, "水印图片路径无效"

        with Image.open(watermark_path).convert("RGBA") as watermark:
            # 调整水印透明度
            if params["image_opacity"] < 100:
                alpha = watermark.split()[3]
                alpha = ImageEnhance.Brightness(alpha).enhance(params["image_opacity"] / 100)
                watermark.putalpha(alpha)

            # 调整水印大小
            scale_percent = params["image_scale"]
            base_width = image.size[0]
            w_width, w_height = watermark.size
            target_width = int(base_width * (scale_percent / 100))
            w_ratio = w_height / w_width
            target_height = int(target_width * w_ratio)
            watermark = watermark.resize((target_width, target_height), Image.Resampling.LANCZOS)

            # 计算位置并粘贴
            x, y = self.get_position_coordinates(image.size, watermark.size, params["position"])

            # 创建一个透明层来粘贴水印
            overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
            overlay.paste(watermark, (x, y), watermark)

            # 合成
            image = Image.alpha_composite(image, overlay)

        return image, "成功"


    def process_single_image(self, image_item, output_dir, **params):
        """处理单张图片"""
        try:
            with Image.open(image_item.file_path) as image:
                original_mode = image.mode

                # 调整尺寸
                if params["resize_option"] != '不缩放':
                    w, h = image.size
                    if params["resize_option"] == '按宽度':
                        new_w = params["resize_value"]
                        new_h = int(h * (new_w / w))
                    elif params["resize_option"] == '按高度':
                        new_h = params["resize_value"]
                        new_w = int(w * (new_h / h))
                    elif params["resize_option"] == '按百分比':
                        new_w = int(w * params["resize_value"] / 100)
                        new_h = int(h * params["resize_value"] / 100)
                    else:
                        new_w, new_h = w, h
                    image = image.resize((new_w, new_h), Image.Resampling.LANCZOS)

                # 统一转换为RGBA进行处理
                if image.mode != 'RGBA':
                    image = image.convert('RGBA')

                # 应用水印
                params["image_item"] = image_item
                if params["watermark_type"] == "Text":
                    image, message = self.apply_text_watermark(image, params)
                else: # Image
                    image, message = self.apply_image_watermark(image, params)

                if image is None:
                    return False, message

                # 根据输出格式进行转换和保存
                output_ext = '.jpg' if params["output_format"] == 'JPEG' else '.png'
                new_filename = f"{params['prefix']}{image_item.file_path.stem}{params['suffix']}{output_ext}"
                output_path = output_dir / new_filename

                if params["output_format"] == 'JPEG':
                    if image.mode in ('RGBA', 'LA'):
                        background = Image.new('RGB', image.size, (255, 255, 255))
                        background.paste(image, mask=image.split()[-1])
                        image = background
                    else:
                        image = image.convert('RGB')
                    image.save(output_path, 'JPEG', quality=params["quality"], optimize=True)
                else: # PNG
                    image.save(output_path, 'PNG', optimize=True)

                return True, "成功"

        except Exception as e:
            return False, str(e)

    def process_images(self):
        """处理所有图片"""
        if not self.image_items:
            messagebox.showwarning("警告", "请先添加图片文件")
            return

        output_dir_str = self.output_dir.get()
        if not output_dir_str:
            messagebox.showwarning("警告", "请选择一个输出文件夹")
            return

        output_dir = Path(output_dir_str)
        if not output_dir.exists():
            output_dir.mkdir(parents=True, exist_ok=True)

        # 检查是否与原图文件夹相同
        source_dirs = {item.file_path.parent for item in self.image_items}
        if output_dir in source_dirs:
            if not messagebox.askyesno("警告", "输出文件夹与原图文件夹相同，可能覆盖原文件，是否继续?"):
                return

        params = {
            # 水印类型
            "watermark_type": self.watermark_type.get(),
            # 文本水印
            "font_size": self.font_size.get(),
            "color": self.color.get(),
            "text_opacity": self.text_opacity.get(),
            "watermark_text_source": self.watermark_text_source.get(),
            "custom_watermark_text": self.custom_watermark_text.get(),
            # 图片水印
            "image_watermark_path": self.image_watermark_path.get(),
            "image_opacity": self.image_opacity.get(),
            "image_scale": self.image_scale.get(),
            # 通用
            "position": self.position.get(),
            # 输出
            "output_format": self.output_format.get(),
            "quality": self.output_quality.get(),
            "prefix": self.filename_prefix.get(),
            "suffix": self.filename_suffix.get(),
            "resize_option": self.resize_option.get(),
            "resize_value": self.resize_value.get(),
        }

        def process_thread():
            success_count = 0
            total_count = len(self.image_items)
            self.progress.config(maximum=total_count)

            for i, item in enumerate(self.image_items):
                self.root.after(0, lambda i=i: self.status_label.config(text=f"正在处理 {i+1}/{total_count}: {item.file_path.name}"))

                success, message = self.process_single_image(item, output_dir, **params)

                if success:
                    success_count += 1
                else:
                    print(f"处理 {item.file_path.name} 失败: {message}")

                self.root.after(0, lambda v=i+1: self.progress.config(value=v))

            self.root.after(0, lambda: self.status_label.config(
                text=f"处理完成: 成功 {success_count}/{total_count} 个文件，输出到: {output_dir}"
            ))
            self.root.after(0, lambda: messagebox.showinfo(
                "完成", f"处理完成!\n成功: {success_count}/{total_count}\n输出目录: {output_dir}"
            ))

        threading.Thread(target=process_thread, daemon=True).start()


def main():
    """主函数"""
    try:
        from tkinterdnd2 import TkinterDnD
        # 如果支持，则创建支持拖拽的根窗口
        root = TkinterDnD.Tk()
    except ImportError:
        # 否则，创建标准窗口并打印警告
        root = tk.Tk()
        print("tkinterdnd2 未安装，拖拽功能将不可用。请运行 'pip install tkinterdnd2'")

    app = WatermarkGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()


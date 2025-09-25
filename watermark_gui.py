#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Photo Watermark GUI Tool
基于GUI的图片水印工具，支持拖拽导入、批量处理和缩略图预览
"""

import os
import json
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
        self.root.geometry("1200x800")  # 增大窗口以容纳预览区域

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
        self.rotation_angle = tk.IntVar(value=0)  # 新增：旋转角度

        # 输出变量
        self.output_format = tk.StringVar(value="JPEG")
        self.output_quality = tk.IntVar(value=95)
        self.output_dir = tk.StringVar()
        self.filename_prefix = tk.StringVar()
        self.filename_suffix = tk.StringVar(value="_watermarked")
        self.resize_option = tk.StringVar(value="不缩放")
        self.resize_value = tk.IntVar(value=100)

        # 预览相关变量
        self.current_preview_item = None
        self.preview_image = None
        self.preview_photo = None
        self.preview_scale = 1.0

        # 拖拽相关变量
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.is_dragging = False
        self.watermark_x_offset = 0
        self.watermark_y_offset = 0
        self.manual_position = False  # 是否使用手动位置

        # 模板相关变量
        self.templates_dir = Path("templates")
        self.templates_dir.mkdir(exist_ok=True)
        self.settings_file = self.templates_dir / "last_settings.json"
        self.current_template_name = tk.StringVar()

        self.create_widgets()
        self.setup_drag_drop()

        # 绑定变量变化事件，用于实时预览
        self.bind_preview_events()

        # 加载上次的设置
        self.load_last_settings()

        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

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

        # 模板管理按钮
        template_frame = ttk.Frame(import_frame)
        template_frame.pack(side=tk.LEFT, padx=(20, 0))

        ttk.Button(template_frame, text="保存模板", command=self.save_template_dialog).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(template_frame, text="加载模板", command=self.load_template_dialog).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(template_frame, text="管理模板", command=self.manage_templates_dialog).pack(side=tk.LEFT, padx=(0, 5))

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

        # 绑定位置选择变化事件
        position_combo.bind("<<ComboboxSelected>>", self.on_position_changed)

        # 旋转角度控制
        ttk.Label(common_settings_frame, text="旋转角度:").grid(row=1, column=0, sticky="w", pady=2)
        rotation_frame = ttk.Frame(common_settings_frame)
        rotation_frame.grid(row=1, column=1, columnspan=2, sticky="ew", pady=2, padx=(5, 0))

        rotation_display = tk.StringVar(value=f"{self.rotation_angle.get()}°")
        def update_rotation_display(value):
            int_value = int(float(value))
            self.rotation_angle.set(int_value)
            rotation_display.set(f"{int_value}°")

        rotation_scale = ttk.Scale(rotation_frame, from_=-180, to=180, variable=self.rotation_angle,
                                 orient=tk.HORIZONTAL, command=update_rotation_display)
        rotation_scale.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
        ttk.Label(rotation_frame, textvariable=rotation_display, width=6).pack(side=tk.LEFT)
        ttk.Button(rotation_frame, text="重置", command=lambda: self.rotation_angle.set(0), width=6).pack(side=tk.LEFT, padx=(5, 0))

        # 输出格式
        ttk.Label(common_settings_frame, text="输出格式:").grid(row=2, column=0, sticky="w", pady=2)
        format_combo = ttk.Combobox(common_settings_frame, textvariable=self.output_format, state="readonly")
        format_combo['values'] = ('JPEG', 'PNG')
        format_combo.grid(row=2, column=1, columnspan=2, sticky="ew", pady=2, padx=(5, 0))

        # 输出质量（仅JPEG）
        ttk.Label(common_settings_frame, text="JPEG质量:").grid(row=3, column=0, sticky="w", pady=2)
        quality_display = tk.StringVar(value=str(self.output_quality.get()))
        def update_quality_display(value):
            int_value = int(float(value))
            self.output_quality.set(int_value)
            quality_display.set(str(int_value))
        quality_scale = ttk.Scale(common_settings_frame, from_=1, to=100, variable=self.output_quality, orient=tk.HORIZONTAL, command=update_quality_display)
        quality_scale.grid(row=3, column=1, sticky="ew", pady=2, padx=(5, 0))
        ttk.Label(common_settings_frame, textvariable=quality_display).grid(row=3, column=2, pady=2, padx=(5, 0))

        # 输出文件夹
        ttk.Label(common_settings_frame, text="输出文件夹:").grid(row=4, column=0, sticky="w", pady=2)
        output_dir_frame = ttk.Frame(common_settings_frame)
        output_dir_frame.grid(row=4, column=1, columnspan=2, sticky="ew", pady=2, padx=(5, 0))
        ttk.Entry(output_dir_frame, textvariable=self.output_dir).pack(side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Button(output_dir_frame, text="选择...", command=self.select_output_dir).pack(side=tk.LEFT, padx=(5, 0))

        # 文件名前缀
        ttk.Label(common_settings_frame, text="文件名前缀:").grid(row=5, column=0, sticky="w", pady=2)
        ttk.Entry(common_settings_frame, textvariable=self.filename_prefix).grid(row=5, column=1, columnspan=2, sticky="ew", pady=2, padx=(5, 0))

        # 文件名后缀
        ttk.Label(common_settings_frame, text="文件名后缀:").grid(row=6, column=0, sticky="w", pady=2)
        ttk.Entry(common_settings_frame, textvariable=self.filename_suffix).grid(row=6, column=1, columnspan=2, sticky="ew", pady=2, padx=(5, 0))

        # 缩放选项
        ttk.Label(common_settings_frame, text="调整尺寸:").grid(row=7, column=0, sticky="w", pady=2)
        resize_frame = ttk.Frame(common_settings_frame)
        resize_frame.grid(row=7, column=1, columnspan=2, sticky="ew", pady=2, padx=(5, 0))
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

        # 预览区域
        preview_frame = ttk.LabelFrame(main_frame, text="水印预览", padding="5")
        preview_frame.grid(row=0, column=2, rowspan=2, sticky="nsew", padx=(10, 0))

        # 预览画布
        self.preview_canvas = tk.Canvas(preview_frame, bg="gray")
        self.preview_canvas.grid(row=0, column=0, sticky="nsew")

        # 预览滚动条
        preview_scrollbar = ttk.Scrollbar(preview_frame, orient="vertical", command=self.preview_canvas.yview)
        preview_scrollbar.grid(row=0, column=1, sticky="ns")
        self.preview_canvas.configure(yscrollcommand=preview_scrollbar.set)

        # 绑定画布滚动事件
        self.preview_canvas.bind_all("<MouseWheel>", self.on_mouse_wheel)

        # 预览状态标签
        self.preview_status_label = ttk.Label(preview_frame, text="请添加图片以查看预览", foreground="gray")
        self.preview_status_label.grid(row=1, column=0, pady=(5, 0))

        # 预览图像信息
        self.preview_image_label = ttk.Label(preview_frame, text="", foreground="blue")
        self.preview_image_label.grid(row=2, column=0, pady=(0, 5))

        # 绑定画布点击事件
        self.preview_canvas.bind("<Button-1>", self.on_preview_click)
        self.preview_canvas.bind("<ButtonRelease-1>", self.on_preview_release)
        self.preview_canvas.bind("<B1-Motion>", self.on_preview_drag)

        # 绑定双击事件重置预览
        self.preview_canvas.bind("<Double-1>", self.reset_preview)

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
        """更新图片列表显示，增加点击选择功能"""
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        for i, item in enumerate(self.image_items):
            item_frame = ttk.Frame(self.scrollable_frame, padding=5)
            item_frame.grid(row=i, column=0, sticky="ew", pady=2)

            # 添加选择状态指示
            if item == self.current_preview_item:
                item_frame.configure(style="Selected.TFrame")

            if item.thumbnail:
                thumb_label = ttk.Label(item_frame, image=item.thumbnail)
                thumb_label.grid(row=0, column=0, rowspan=2, padx=(0, 10))
                # 绑定点击事件
                thumb_label.bind("<Button-1>", lambda e, idx=i: self.select_image_for_preview(idx))

            filename_label = ttk.Label(item_frame, text=item.file_path.name, font=("Segoe UI", 10, "bold"))
            filename_label.grid(row=0, column=1, sticky="w")
            # 绑定点击事件
            filename_label.bind("<Button-1>", lambda e, idx=i: self.select_image_for_preview(idx))

            exif_info = f"拍摄时间: {item.exif_date}" if item.exif_date else "无EXIF时间"
            exif_label = ttk.Label(item_frame, text=exif_info, foreground="gray")
            exif_label.grid(row=1, column=1, sticky="w")
            # 绑定点击事件
            exif_label.bind("<Button-1>", lambda e, idx=i: self.select_image_for_preview(idx))

            # 为整个框架绑定点击事件
            item_frame.bind("<Button-1>", lambda e, idx=i: self.select_image_for_preview(idx))

    def select_image_for_preview(self, index):
        """选择图片进行预览"""
        if 0 <= index < len(self.image_items):
            self.current_preview_item = self.image_items[index]
            self.preview_scale = 1.0  # 重置缩放
            self.manual_position = False  # 重置手动位置
            self.watermark_x_offset = 0
            self.watermark_y_offset = 0
            self.update_image_list()  # 更新列表显示选中状态
            self.update_preview_image()

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

    def show_position_grid(self):
        """显示九宫格位置选择窗口"""
        grid_window = tk.Toplevel(self.root)
        grid_window.title("选择水印位置")
        grid_window.geometry("300x300")
        grid_window.resizable(False, False)
        grid_window.transient(self.root)
        grid_window.grab_set()

        # 居中显示窗口
        grid_window.update_idletasks()
        x = (grid_window.winfo_screenwidth() // 2) - (300 // 2)
        y = (grid_window.winfo_screenheight() // 2) - (300 // 2)
        grid_window.geometry(f"300x300+{x}+{y}")

        # 创建九宫格按钮
        positions = [
            ('top-left', '左上'), ('top-center', '上中'), ('top-right', '右上'),
            ('center-left', '左中'), ('center', '正中'), ('center-right', '右中'),
            ('bottom-left', '左下'), ('bottom-center', '下中'), ('bottom-right', '右下')
        ]

        for i, (pos_key, pos_name) in enumerate(positions):
            row = i // 3
            col = i % 3

            btn = tk.Button(
                grid_window,
                text=pos_name,
                font=("Segoe UI", 12),
                width=8,
                height=3,
                command=lambda p=pos_key: self.select_position(p, grid_window)
            )
            btn.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")

            # 高亮当前选中的位置
            if pos_key == self.position.get():
                btn.config(bg="lightblue")

        # 配置网格权重
        for i in range(3):
            grid_window.columnconfigure(i, weight=1)
            grid_window.rowconfigure(i, weight=1)

    def select_position(self, position, window):
        """选择位置并关闭窗口"""
        self.position.set(position)
        self.manual_position = False  # 重置为预设位置
        window.destroy()
        if self.current_preview_item:
            self.update_preview_image()

    def get_position_coordinates(self, image_size, watermark_size, position, manual_x=0, manual_y=0):
        """根据位置参数计算水印坐标，支持手动位置"""
        if position == "manual":
            return (int(manual_x), int(manual_y))

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

        # 计算位置（支持手动位置）
        manual_x = params.get("manual_x", 0)
        manual_y = params.get("manual_y", 0)
        x, y = self.get_position_coordinates(image.size, (text_width, text_height), params["position"], manual_x, manual_y)

        try:
            rgb_color = Image.new("RGB", (1, 1), params["color"]).getpixel((0, 0))
        except ValueError:
            from PIL import ImageColor
            rgb_color = ImageColor.getrgb(params["color"])

        alpha = int(255 * (params["text_opacity"] / 100))
        final_color = rgb_color + (alpha,)

        # 创建文本水印图像
        rotation_angle = params.get("rotation_angle", 0)
        if rotation_angle != 0:
            # 为旋转创建足够大的画布
            max_dim = max(text_width, text_height) * 2
            text_img = Image.new('RGBA', (max_dim, max_dim), (0, 0, 0, 0))
            text_draw = ImageDraw.Draw(text_img)

            # 在中心绘制文本
            center_x = (max_dim - text_width) // 2
            center_y = (max_dim - text_height) // 2

            # 添加背景
            padding = 5
            text_draw.rectangle(
                [center_x - padding, center_y - padding, center_x + text_width + padding, center_y + text_height + padding],
                fill=(0, 0, 0, int(128 * (params["text_opacity"] / 100)))
            )
            text_draw.text((center_x, center_y), watermark_text, fill=final_color, font=font)

            # 旋转文本图像
            text_img = text_img.rotate(rotation_angle, expand=True)

            # 计算旋转后的位置调整
            rotated_width, rotated_height = text_img.size
            paste_x = x - (rotated_width - text_width) // 2
            paste_y = y - (rotated_height - text_height) // 2

            # 粘贴到原图像
            image.paste(text_img, (paste_x, paste_y), text_img)
        else:
            # 无旋转的情况
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

            # 应用旋转
            rotation_angle = params.get("rotation_angle", 0)
            if rotation_angle != 0:
                watermark = watermark.rotate(rotation_angle, expand=True)

            # 计算位置并粘贴（支持手动位置）
            manual_x = params.get("manual_x", 0)
            manual_y = params.get("manual_y", 0)
            x, y = self.get_position_coordinates(image.size, watermark.size, params["position"], manual_x, manual_y)

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
            # 通用 - 修复：包含手动位置信息
            "position": self.position.get() if not self.manual_position else "manual",
            "manual_x": self.watermark_x_offset if self.manual_position else 0,
            "manual_y": self.watermark_y_offset if self.manual_position else 0,
            "rotation_angle": self.rotation_angle.get(),
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

    def on_mouse_wheel(self, event):
        """处理鼠标滚轮事件"""
        if self.preview_canvas.winfo_height() > 0:
            # 计算缩放因子
            scale_factor = 1.1 if event.delta > 0 else 0.9
            new_scale = self.preview_scale * scale_factor

            # 限制缩放范围
            if 0.1 <= new_scale <= 10:
                self.preview_scale = new_scale
                self.update_preview_image()

    def update_preview_image(self):
        """更新预览图像"""
        if not self.current_preview_item:
            self.preview_canvas.delete("all")
            self.preview_status_label.config(text="请选择图片以查看预览")
            self.preview_image_label.config(text="")
            return

        try:
            with Image.open(self.current_preview_item.file_path) as img:
                img = img.convert("RGBA")
                original_size = img.size

                # 应用水印
                params = {
                    "watermark_type": self.watermark_type.get(),
                    "font_size": self.font_size.get(),
                    "color": self.color.get(),
                    "text_opacity": self.text_opacity.get(),
                    "watermark_text_source": self.watermark_text_source.get(),
                    "custom_watermark_text": self.custom_watermark_text.get(),
                    "image_watermark_path": self.image_watermark_path.get(),
                    "image_opacity": self.image_opacity.get(),
                    "image_scale": self.image_scale.get(),
                    "position": self.position.get() if not self.manual_position else "manual",
                    "rotation_angle": self.rotation_angle.get(),
                    "image_item": self.current_preview_item,
                    "manual_x": self.watermark_x_offset if self.manual_position else 0,
                    "manual_y": self.watermark_y_offset if self.manual_position else 0,
                }

                if params["watermark_type"] == "Text":
                    img, message = self.apply_text_watermark(img, params)
                else:
                    img, message = self.apply_image_watermark(img, params)

                if img is None:
                    self.preview_status_label.config(text=f"预览错误: {message}")
                    return

                # 不对整个图像进行旋转，旋转只应用于水印

                # 自适应画布大小
                canvas_width = self.preview_canvas.winfo_width()
                canvas_height = self.preview_canvas.winfo_height()

                if canvas_width > 1 and canvas_height > 1:
                    # 计算适合画布的缩放比例
                    scale_x = canvas_width / img.size[0]
                    scale_y = canvas_height / img.size[1]
                    auto_scale = min(scale_x, scale_y, 1.0)  # 不放大，只缩小

                    # 应用用户缩放
                    final_scale = auto_scale * self.preview_scale

                    if final_scale != 1.0:
                        new_size = (int(img.size[0] * final_scale), int(img.size[1] * final_scale))
                        img = img.resize(new_size, Image.Resampling.LANCZOS)

                self.preview_image = img
                self.preview_photo = ImageTk.PhotoImage(img)

                # 更新画布
                self.preview_canvas.delete("all")
                self.preview_canvas.create_image(
                    canvas_width // 2 if canvas_width > 1 else 0,
                    canvas_height // 2 if canvas_height > 1 else 0,
                    image=self.preview_photo,
                    anchor="center"
                )
                self.preview_canvas.config(scrollregion=self.preview_canvas.bbox("all"))

                # 更新状态标签
                self.preview_status_label.config(text=f"预览: {self.current_preview_item.file_path.name}")
                scale_info = f"缩放: {self.preview_scale:.1f}x" if self.preview_scale != 1.0 else ""
                rotation_info = f"旋转: {self.rotation_angle.get()}°" if self.rotation_angle.get() != 0 else ""
                position_info = "手动位置" if self.manual_position else f"预设位置: {self.position.get()}"
                info_parts = [f"原始: {original_size[0]}x{original_size[1]}"]
                if scale_info:
                    info_parts.append(scale_info)
                if rotation_info:
                    info_parts.append(rotation_info)
                info_parts.append(position_info)
                self.preview_image_label.config(text=" | ".join(info_parts))

        except Exception as e:
            print(f"更新预览图像时出错: {e}")
            self.preview_status_label.config(text=f"预览错误: {str(e)}")

    def on_preview_click(self, event):
        """处理预览区域点击事件"""
        if self.current_preview_item:
            self.is_dragging = True
            self.drag_start_x = event.x
            self.drag_start_y = event.y

            # 计算画布中心和图像位置
            canvas_width = self.preview_canvas.winfo_width()
            canvas_height = self.preview_canvas.winfo_height()

            # 获取实际图像大小（考虑缩放）
            if self.preview_image:
                img_width, img_height = self.preview_image.size

                # 计算图像在画布中的位置
                image_start_x = (canvas_width - img_width) // 2
                image_start_y = (canvas_height - img_height) // 2

                # 计算点击位置相对于图像的坐标
                relative_x = event.x - image_start_x
                relative_y = event.y - image_start_y

                # 确保点击在图像内部
                if 0 <= relative_x <= img_width and 0 <= relative_y <= img_height:
                    # 转换为原始图像坐标（考虑预览缩放）
                    canvas_width_orig = self.preview_canvas.winfo_width()
                    canvas_height_orig = self.preview_canvas.winfo_height()

                    if canvas_width_orig > 1 and canvas_height_orig > 1:
                        # 计算原始图像大小
                        with Image.open(self.current_preview_item.file_path) as orig_img:
                            orig_width, orig_height = orig_img.size

                            # 计算缩放比例
                            scale_x = canvas_width_orig / orig_width
                            scale_y = canvas_height_orig / orig_height
                            auto_scale = min(scale_x, scale_y, 1.0)
                            final_scale = auto_scale * self.preview_scale

                            # 转换坐标到原始图像
                            orig_x = int(relative_x / final_scale)
                            orig_y = int(relative_y / final_scale)

                            # 设置水印位置
                            self.watermark_x_offset = orig_x
                            self.watermark_y_offset = orig_y
                            self.manual_position = True

                            # 更新预览
                            self.update_preview_image()

    def on_preview_release(self, event):
        """处理预览区域释放事件"""
        self.is_dragging = False

    def on_preview_drag(self, event):
        """处理预览区域拖拽事件"""
        if self.is_dragging and self.current_preview_item:
            # 计算拖拽距离
            dx = event.x - self.drag_start_x
            dy = event.y - self.drag_start_y

            # 计算缩放比例
            canvas_width = self.preview_canvas.winfo_width()
            canvas_height = self.preview_canvas.winfo_height()

            if canvas_width > 1 and canvas_height > 1:
                with Image.open(self.current_preview_item.file_path) as orig_img:
                    orig_width, orig_height = orig_img.size

                    # 计算缩放比例
                    scale_x = canvas_width / orig_width
                    scale_y = canvas_height / orig_height
                    auto_scale = min(scale_x, scale_y, 1.0)
                    final_scale = auto_scale * self.preview_scale

                    # 转换拖拽距离到原始图像坐标
                    orig_dx = dx / final_scale
                    orig_dy = dy / final_scale

                    # 更新水印位置
                    self.watermark_x_offset += orig_dx
                    self.watermark_y_offset += orig_dy
                    self.manual_position = True

            # 更新拖拽起始点
            self.drag_start_x = event.x
            self.drag_start_y = event.y

            # 更新预览图像
            self.update_preview_image()

    def reset_preview(self, event=None):
        """重置预览为原始状态"""
        self.watermark_x_offset = 0
        self.watermark_y_offset = 0
        self.manual_position = False

        if self.current_preview_item:
            self.update_preview_image()

    def on_position_changed(self, event=None):
        """处理位置选择变化事件"""
        # 当用户从下拉框选择新位置时，重置手动位置标志
        self.manual_position = False
        self.watermark_x_offset = 0
        self.watermark_y_offset = 0

        # 更新预览
        if self.current_preview_item:
            self.update_preview_image()

    def bind_preview_events(self):
        """绑定预览相关变量的变化事件"""
        self.watermark_type.trace_add("write", lambda *args: self.update_preview_image())
        self.font_size.trace_add("write", lambda *args: self.update_preview_image())
        self.color.trace_add("write", lambda *args: self.update_preview_image())
        self.text_opacity.trace_add("write", lambda *args: self.update_preview_image())
        self.watermark_text_source.trace_add("write", lambda *args: self.update_preview_image())
        self.custom_watermark_text.trace_add("write", lambda *args: self.update_preview_image())
        self.image_watermark_path.trace_add("write", lambda *args: self.update_preview_image())
        self.image_opacity.trace_add("write", lambda *args: self.update_preview_image())
        self.image_scale.trace_add("write", lambda *args: self.update_preview_image())
        # 注意：position的变化事件已经在ComboboxSelected中处理，这里不需要重复绑定
        self.rotation_angle.trace_add("write", lambda *args: self.update_preview_image())

        # 绑定选择图片后更新预览
        self.scrollable_frame.bind("<ButtonRelease-1>", self.on_image_select)

    def on_image_select(self, event):
        """处理图片选择"""
        widget = event.widget
        if isinstance(widget, ttk.Label) and widget.winfo_parent():
            parent_frame = widget.winfo_parent()
            index = int(parent_frame.grid_info()["row"])

            if 0 <= index < len(self.image_items):
                self.current_preview_item = self.image_items[index]
                self.update_preview_image()

    def load_last_settings(self):
        """加载上次的设置"""
        if not self.settings_file.exists():
            return

        try:
            with open(self.settings_file, "r", encoding="utf-8") as f:
                settings = json.load(f)

            # 恢复所有设置参数
            self.watermark_type.set(settings.get("watermark_type", "Text"))

            # 文本水印设置
            self.font_size.set(settings.get("font_size", 36))
            self.color.set(settings.get("color", "white"))
            self.text_opacity.set(settings.get("text_opacity", 100))
            self.watermark_text_source.set(settings.get("watermark_text_source", "EXIF Date"))
            self.custom_watermark_text.set(settings.get("custom_watermark_text", "自定义水印"))

            # 图片水印设置
            self.image_watermark_path.set(settings.get("image_watermark_path", ""))
            self.image_opacity.set(settings.get("image_opacity", 100))
            self.image_scale.set(settings.get("image_scale", 20))

            # 通用与输出设置
            self.position.set(settings.get("position", "bottom-right"))
            self.rotation_angle.set(settings.get("rotation_angle", 0))
            self.output_format.set(settings.get("output_format", "JPEG"))
            self.output_quality.set(settings.get("output_quality", 95))
            self.output_dir.set(settings.get("output_dir", ""))
            self.filename_prefix.set(settings.get("filename_prefix", ""))
            self.filename_suffix.set(settings.get("filename_suffix", "_watermarked"))
            self.resize_option.set(settings.get("resize_option", "不缩放"))
            self.resize_value.set(settings.get("resize_value", 100))

            # 手动位置
            self.manual_position = settings.get("manual_position", False)
            self.watermark_x_offset = settings.get("watermark_x_offset", 0)
            self.watermark_y_offset = settings.get("watermark_y_offset", 0)

        except Exception as e:
            print(f"加载设置时出错: {e}")

    def save_settings(self):
        """保存当前设置为模板"""
        try:
            settings = {
                "watermark_type": self.watermark_type.get(),
                "font_size": self.font_size.get(),
                "color": self.color.get(),
                "text_opacity": self.text_opacity.get(),
                "watermark_text_source": self.watermark_text_source.get(),
                "custom_watermark_text": self.custom_watermark_text.get(),
                "image_watermark_path": self.image_watermark_path.get(),
                "image_opacity": self.image_opacity.get(),
                "image_scale": self.image_scale.get(),
                "position": self.position.get(),
                "rotation_angle": self.rotation_angle.get(),
                # 添加手动位置信息
                "manual_position": self.manual_position,
                "watermark_x_offset": self.watermark_x_offset,
                "watermark_y_offset": self.watermark_y_offset,
                "output_format": self.output_format.get(),
                "output_quality": self.output_quality.get(),
                "output_dir": self.output_dir.get(),
                "filename_prefix": self.filename_prefix.get(),
                "filename_suffix": self.filename_suffix.get(),
                "resize_option": self.resize_option.get(),
                "resize_value": self.resize_value.get(),
            }

            # 使用当前时间戳作为模板文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            template_file = self.templates_dir / f"template_{timestamp}.json"

            with open(template_file, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=4)

            messagebox.showinfo("保存模板", f"设置已保存为模板: {template_file.name}")
        except Exception as e:
            messagebox.showerror("保存模板", f"保存设置时出错: {e}")

    def apply_template(self, template_path):
        """应用模板设置"""
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                settings = json.load(f)

            # 应用所有设置参数，不论水印类型
            self.watermark_type.set(settings.get("watermark_type", "Text"))

            # 文本水印设置
            self.font_size.set(settings.get("font_size", 36))
            self.color.set(settings.get("color", "white"))
            self.text_opacity.set(settings.get("text_opacity", 100))
            self.watermark_text_source.set(settings.get("watermark_text_source", "EXIF Date"))
            self.custom_watermark_text.set(settings.get("custom_watermark_text", "自定义水印"))

            # 图片水印设置
            self.image_watermark_path.set(settings.get("image_watermark_path", ""))
            self.image_opacity.set(settings.get("image_opacity", 100))
            self.image_scale.set(settings.get("image_scale", 20))

            # 通用与输出设置
            self.position.set(settings.get("position", "bottom-right"))
            self.rotation_angle.set(settings.get("rotation_angle", 0))
            self.output_format.set(settings.get("output_format", "JPEG"))
            self.output_quality.set(settings.get("output_quality", 95))
            self.output_dir.set(settings.get("output_dir", ""))
            self.filename_prefix.set(settings.get("filename_prefix", ""))
            self.filename_suffix.set(settings.get("filename_suffix", "_watermarked"))
            self.resize_option.set(settings.get("resize_option", "不缩放"))
            self.resize_value.set(settings.get("resize_value", 100))

            # 恢复手动位置信息
            self.manual_position = settings.get("manual_position", False)
            self.watermark_x_offset = settings.get("watermark_x_offset", 0)
            self.watermark_y_offset = settings.get("watermark_y_offset", 0)

            # 更新预览如果有选中的图片
            if self.current_preview_item:
                self.update_preview_image()

            messagebox.showinfo("应用模板", f"模板 '{Path(template_path).name}' 已加载")
        except Exception as e:
            messagebox.showerror("应用模板", f"加载模板时出错: {e}")

    def load_templates(self):
        """加载模板列表"""
        try:
            templates = sorted(self.templates_dir.glob("template_*.json"), key=os.path.getmtime)
            return [t.name for t in templates]
        except Exception as e:
            print(f"加载模板时出错: {e}")
            return []

    def create_template_menu(self, menu):
        """创建模板菜单"""
        templates = self.load_templates()

        def on_template_select(template_name):
            if template_name == "新建模板":
                self.save_settings()
            else:
                template_path = self.templates_dir / template_name
                self.apply_template(template_path)

        menu.add_command(label="保存设置为模板", command=lambda: self.save_settings())
        menu.add_separator()

        for template in templates:
            menu.add_command(label=template.name, command=lambda t=template: on_template_select(t))
        menu.add_separator()
        menu.add_command(label="新建模板", command=lambda: on_template_select("新建模板"))

    def save_template_dialog(self):
        """保存模板对话框"""
        self.save_settings()

    def load_template_dialog(self):
        """加载模板对话框"""
        filetypes = [("JSON文件", "*.json"), ("所有文件", "*.*")]
        filepath = filedialog.askopenfilename(title="加载模板", filetypes=filetypes)
        if filepath:
            self.apply_template(filepath)

    def manage_templates_dialog(self):
        """管理模板对话框"""
        try:
            # 获取模板文件列表（返回Path对象而不是文件名）
            template_files = sorted(self.templates_dir.glob("template_*.json"), key=os.path.getmtime, reverse=True)
        except Exception as e:
            print(f"加载模板时出错: {e}")
            template_files = []

        if not template_files:
            messagebox.showinfo("管理模板", "没有找到可用的模板")
            return

        manage_window = tk.Toplevel(self.root)
        manage_window.title("管理模板")
        manage_window.geometry("500x400")
        manage_window.resizable(False, False)
        manage_window.transient(self.root)
        manage_window.grab_set()

        # 居中显示窗口
        manage_window.update_idletasks()
        x = (manage_window.winfo_screenwidth() // 2) - (250)
        y = (manage_window.winfo_screenheight() // 2) - (200)
        manage_window.geometry(f"500x400+{x}+{y}")

        # 说明标签
        info_label = ttk.Label(manage_window, text="双击模板名称可以加载模板，或使用下方按钮进行操作", foreground="gray")
        info_label.pack(pady=(10, 5))

        # 列表框架
        list_frame = ttk.Frame(manage_window)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 滚动条
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical")
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 模板列表框
        template_listbox = tk.Listbox(list_frame, selectmode=tk.SINGLE, yscrollcommand=scrollbar.set)
        template_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=template_listbox.yview)

        # 绑定双击事件加载模板
        def on_template_double_click(event):
            selection = template_listbox.curselection()
            if selection:
                index = selection[0]
                template_file = template_files[index]
                self.apply_template(template_file)
                manage_window.destroy()

        template_listbox.bind("<Double-Button-1>", on_template_double_click)

        # 填充模板列表，显示更友好的名称
        for template_file in template_files:
            # 从文件名提取时间戳
            try:
                timestamp_str = template_file.stem.replace("template_", "")
                timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                display_name = f"{timestamp.strftime('%Y-%m-%d %H:%M:%S')} - {template_file.name}"
            except:
                display_name = template_file.name
            template_listbox.insert(tk.END, display_name)

        # 按钮框架
        button_frame = ttk.Frame(manage_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        # 加载按钮
        def load_template():
            selection = template_listbox.curselection()
            if not selection:
                messagebox.showwarning("请选择", "请先选择一个模板")
                return

            index = selection[0]
            template_file = template_files[index]
            self.apply_template(template_file)
            manage_window.destroy()

        load_button = ttk.Button(button_frame, text="加载模板", command=load_template)
        load_button.pack(side=tk.LEFT, padx=(0, 5))

        # 删除按钮
        def delete_template():
            selection = template_listbox.curselection()
            if not selection:
                messagebox.showwarning("请选择", "请先选择一个模板")
                return

            index = selection[0]
            template_file = template_files[index]

            if messagebox.askyesno("确认删除", f"确定要删除模板 '{template_file.name}' 吗?"):
                try:
                    template_file.unlink()
                    template_listbox.delete(index)
                    template_files.pop(index)
                    messagebox.showinfo("删除成功", "模板已删除")
                except Exception as e:
                    messagebox.showerror("删除失败", f"删除模板时出错: {e}")

        delete_button = ttk.Button(button_frame, text="删除模板", command=delete_template)
        delete_button.pack(side=tk.LEFT, padx=(0, 5))

        # 关闭按钮
        close_button = ttk.Button(button_frame, text="关闭", command=manage_window.destroy)
        close_button.pack(side=tk.RIGHT)

    def save_last_settings(self):
        """保存当前设置到最后设置文件"""
        try:
            settings = {
                "watermark_type": self.watermark_type.get(),
                "font_size": self.font_size.get(),
                "color": self.color.get(),
                "text_opacity": self.text_opacity.get(),
                "watermark_text_source": self.watermark_text_source.get(),
                "custom_watermark_text": self.custom_watermark_text.get(),
                "image_watermark_path": self.image_watermark_path.get(),
                "image_opacity": self.image_opacity.get(),
                "image_scale": self.image_scale.get(),
                "position": self.position.get(),
                "rotation_angle": self.rotation_angle.get(),
                # 添加手动位置信息
                "manual_position": self.manual_position,
                "watermark_x_offset": self.watermark_x_offset,
                "watermark_y_offset": self.watermark_y_offset,
                "output_format": self.output_format.get(),
                "output_quality": self.output_quality.get(),
                "output_dir": self.output_dir.get(),
                "filename_prefix": self.filename_prefix.get(),
                "filename_suffix": self.filename_suffix.get(),
                "resize_option": self.resize_option.get(),
                "resize_value": self.resize_value.get(),
            }

            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"保存最后设置时出错: {e}")

    def on_closing(self):
        """处理窗口关闭事件"""
        # 保存最后的设置
        self.save_last_settings()
        # 直接关闭程序
        self.root.destroy()

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

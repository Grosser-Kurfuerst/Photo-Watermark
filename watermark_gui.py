#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Photo Watermark GUI Tool
基于GUI的图片水印工具，支持拖拽导入、批量处理和缩略图预览
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
from PIL import Image, ImageTk, ImageDraw, ImageFont
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

        # 设置变量
        self.font_size = tk.IntVar(value=36)
        self.color = tk.StringVar(value="white")
        self.position = tk.StringVar(value="bottom-right")
        self.output_format = tk.StringVar(value="JPEG")
        self.output_quality = tk.IntVar(value=95)

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

        # 设置区域
        settings_frame = ttk.LabelFrame(main_frame, text="水印设置", padding="5")
        settings_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 10))

        # 字体大小
        ttk.Label(settings_frame, text="字体大小:").grid(row=0, column=0, sticky="w", pady=2)

        font_size_display = tk.StringVar(value=str(self.font_size.get()))

        def update_font_size_display(value):
            int_value = int(float(value))
            self.font_size.set(int_value)
            font_size_display.set(str(int_value))

        font_scale = ttk.Scale(
            settings_frame,
            from_=12,
            to=100,
            variable=self.font_size,
            orient=tk.HORIZONTAL,
            command=update_font_size_display
        )
        font_scale.grid(row=0, column=1, sticky="ew", pady=2, padx=(5, 0))
        ttk.Label(settings_frame, textvariable=font_size_display).grid(row=0, column=2, pady=2, padx=(5, 0))

        # 颜色选择
        ttk.Label(settings_frame, text="字体颜色:").grid(row=1, column=0, sticky="w", pady=2)
        color_frame = ttk.Frame(settings_frame)
        color_frame.grid(row=1, column=1, columnspan=2, sticky="ew", pady=2, padx=(5, 0))
        ttk.Entry(color_frame, textvariable=self.color, width=10).pack(side=tk.LEFT)
        ttk.Button(color_frame, text="选择颜色", command=self.choose_color).pack(side=tk.LEFT, padx=(5, 0))

        # 位置选择
        ttk.Label(settings_frame, text="水印位置:").grid(row=2, column=0, sticky="w", pady=2)
        position_combo = ttk.Combobox(settings_frame, textvariable=self.position, state="readonly")
        position_combo['values'] = (
            'top-left', 'top-center', 'top-right',
            'center-left', 'center', 'center-right',
            'bottom-left', 'bottom-center', 'bottom-right'
        )
        position_combo.grid(row=2, column=1, columnspan=2, sticky="ew", pady=2, padx=(5, 0))

        # 输出格式
        ttk.Label(settings_frame, text="输出格式:").grid(row=3, column=0, sticky="w", pady=2)
        format_combo = ttk.Combobox(settings_frame, textvariable=self.output_format, state="readonly")
        format_combo['values'] = ('JPEG', 'PNG')
        format_combo.grid(row=3, column=1, columnspan=2, sticky="ew", pady=2, padx=(5, 0))

        # 输出质量（仅JPEG）
        ttk.Label(settings_frame, text="JPEG质量:").grid(row=4, column=0, sticky="w", pady=2)
        quality_scale = ttk.Scale(settings_frame, from_=1, to=100, variable=self.output_quality, orient=tk.HORIZONTAL)
        quality_scale.grid(row=4, column=1, sticky="ew", pady=2, padx=(5, 0))
        ttk.Label(settings_frame, textvariable=self.output_quality).grid(row=4, column=2, pady=2, padx=(5, 0))

        # 处理按钮
        ttk.Button(settings_frame, text="开始处理", command=self.process_images).grid(row=5, column=0, columnspan=3, pady=10)

        # 配置网格权重
        settings_frame.columnconfigure(1, weight=1)

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

    def get_position_coordinates(self, image_size, text_size, position):
        """根据位置参数计算文字坐标"""
        img_width, img_height = image_size
        text_width, text_height = text_size

        positions = {
            'top-left': (10, 10),
            'top-center': ((img_width - text_width) // 2, 10),
            'top-right': (img_width - text_width - 10, 10),
            'center-left': (10, (img_height - text_height) // 2),
            'center': ((img_width - text_width) // 2, (img_height - text_height) // 2),
            'center-right': (img_width - text_width - 10, (img_height - text_height) // 2),
            'bottom-left': (10, img_height - text_height - 10),
            'bottom-center': ((img_width - text_width) // 2, img_height - text_height - 10),
            'bottom-right': (img_width - text_width - 10, img_height - text_height - 10)
        }
        return positions.get(position, positions['bottom-right'])

    def process_single_image(self, image_item, output_dir, font_size, color, position, output_format, quality):
        """处理单张图片"""
        try:
            if not image_item.exif_date:
                return False, "无EXIF拍摄时间"

            with Image.open(image_item.file_path) as image:
                original_mode = image.mode

                # 统一转换为RGBA进行处理，以支持透明度
                if original_mode not in ('RGBA', 'RGB'):
                    image = image.convert('RGBA')
                elif original_mode == 'RGB':
                    image = image.convert('RGBA')

                draw = ImageDraw.Draw(image)

                try:
                    font_paths = ["C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/arial.ttf"]
                    font = next((ImageFont.truetype(fp, font_size) for fp in font_paths if os.path.exists(fp)), ImageFont.load_default())
                except Exception:
                    font = ImageFont.load_default()

                bbox = draw.textbbox((0, 0), image_item.exif_date, font=font)
                text_width, text_height = bbox[2] - bbox[0], bbox[3] - bbox[1]
                x, y = self.get_position_coordinates(image.size, (text_width, text_height), position)

                # 创建半透明背景
                overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
                overlay_draw = ImageDraw.Draw(overlay)
                padding = 5
                overlay_draw.rectangle(
                    [x - padding, y - padding, x + text_width + padding, y + text_height + padding],
                    fill=(0, 0, 0, 128)
                )
                image = Image.alpha_composite(image, overlay)

                # 在合并后的图像上绘制文字
                final_draw = ImageDraw.Draw(image)
                final_draw.text((x, y), image_item.exif_date, fill=color, font=font)

                # 根据输出格式进行转换和保存
                output_ext = '.jpg' if output_format == 'JPEG' else '.png'
                output_path = output_dir / f"{image_item.file_path.stem}{output_ext}"

                if output_format == 'JPEG':
                    # 如果原始图片有透明度，需要填充背景色
                    if image.mode in ('RGBA', 'LA'):
                        background = Image.new('RGB', image.size, (255, 255, 255))
                        background.paste(image, mask=image.split()[-1])
                        image = background
                    else:
                        image = image.convert('RGB')
                    image.save(output_path, 'JPEG', quality=quality, optimize=True)
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

        first_image_dir = self.image_items[0].file_path.parent
        output_dir = first_image_dir / f"{first_image_dir.name}_watermark"
        output_dir.mkdir(exist_ok=True)

        params = {
            "font_size": self.font_size.get(), "color": self.color.get(),
            "position": self.position.get(), "output_format": self.output_format.get(),
            "quality": self.output_quality.get()
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

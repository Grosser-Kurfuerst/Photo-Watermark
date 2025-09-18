#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Photo Watermark Tool
在图片上添加基于EXIF拍摄时间的水印
"""

import os
from datetime import datetime
from pathlib import Path
import click
from PIL import Image, ImageDraw, ImageFont
import piexif


class PhotoWatermark:
    """图片水印处理类"""

    def __init__(self):
        self.supported_formats = ('.jpg', '.jpeg', '.png', '.tiff', '.bmp')

    def is_supported_image(self, path: Path) -> bool:
        return path.suffix.lower() in self.supported_formats

    def get_exif_date(self, image_path):
        """从图片EXIF信息中提取拍摄时间，返回 YYYY-MM-DD 或 None"""
        try:
            image = Image.open(image_path)
            exif_bytes = image.info.get('exif', b'')
            if not exif_bytes:
                return None
            exif_data = piexif.load(exif_bytes)

            date_fields = [
                piexif.ExifIFD.DateTimeOriginal,  # 拍摄时间
                piexif.ExifIFD.DateTimeDigitized, # 数字化时间
            ]
            # 0th IFD 中的 DateTime 也可能存在
            for field in date_fields:
                if field in exif_data.get('Exif', {}):
                    try:
                        date_str = exif_data['Exif'][field].decode('utf-8')
                        date_obj = datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
                        return date_obj.strftime('%Y-%m-%d')
                    except Exception:
                        continue
            if piexif.ImageIFD.DateTime in exif_data.get('0th', {}):
                try:
                    date_str = exif_data['0th'][piexif.ImageIFD.DateTime].decode('utf-8')
                    date_obj = datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
                    return date_obj.strftime('%Y-%m-%d')
                except Exception:
                    return None
            return None
        except Exception as e:
            click.echo(f"警告: 无法读取 {image_path} 的EXIF信息: {e}", err=True)
            return None

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

    def add_watermark(self, image_path, font_size, color, position, output_dir):
        """为单张图片添加水印，返回是否成功"""
        try:
            date_text = self.get_exif_date(image_path)
            if not date_text:
                click.echo(f"跳过 {image_path.name}: 无EXIF拍摄时间")
                return False
            image = Image.open(image_path)
            if image.mode != 'RGB':
                image = image.convert('RGB')
            draw = ImageDraw.Draw(image)
            try:
                font_paths = [
                    "C:/Windows/Fonts/simhei.ttf",
                    "C:/Windows/Fonts/msyh.ttc",
                    "C:/Windows/Fonts/arial.ttf",
                ]
                font = None
                for fp in font_paths:
                    if os.path.exists(fp):
                        font = ImageFont.truetype(fp, font_size)
                        break
                if font is None:
                    font = ImageFont.load_default()
            except Exception:
                font = ImageFont.load_default()
            bbox = draw.textbbox((0, 0), date_text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            x, y = self.get_position_coordinates(image.size, (text_width, text_height), position)
            overlay = Image.new('RGBA', image.size, (0, 0, 0, 0))
            overlay_draw = ImageDraw.Draw(overlay)
            padding = 5
            overlay_draw.rectangle(
                [x - padding, y - padding, x + text_width + padding, y + text_height + padding],
                fill=(0, 0, 0, 128)
            )
            image = Image.alpha_composite(image.convert('RGBA'), overlay).convert('RGB')
            draw = ImageDraw.Draw(image)
            draw.text((x, y), date_text, fill=color, font=font)
            output_path = output_dir / image_path.name
            image.save(output_path, quality=95, optimize=True)
            click.echo(f"已处理: {image_path.name}")
            return True
        except Exception as e:
            click.echo(f"处理 {image_path} 时出错: {e}", err=True)
            return False

    def process_directory(self, input_dir, font_size, color, position):
        """处理目录中的所有图片"""
        input_path = Path(input_dir)
        if not input_path.exists():
            click.echo(f"错误: 目录 {input_dir} 不存在")
            return
        output_dir = input_path / f"{input_path.name}_watermark"
        output_dir.mkdir(exist_ok=True)
        image_files = []
        for ext in self.supported_formats:
            image_files.extend(input_path.glob(f"*{ext}"))
            image_files.extend(input_path.glob(f"*{ext.upper()}"))
        if not image_files:
            click.echo(f"在目录 {input_dir} 中没有找到支持的图片文件")
            return
        click.echo(f"找到 {len(image_files)} 个图片文件，开始处理...")
        success = 0
        for img in image_files:
            if self.add_watermark(img, font_size, color, position, output_dir):
                success += 1
        click.echo(f"完成: 成功 {success}/{len(image_files)}")

    def process_single_file(self, file_path, font_size, color, position):
        """处理单个文件"""
        file_path = Path(file_path)
        if not file_path.exists():
            click.echo(f"错误: 文件 {file_path} 不存在")
            return
        if not self.is_supported_image(file_path):
            click.echo("错误: 不支持的图片格式")
            return
        parent = file_path.parent
        output_dir = parent / f"{parent.name}_watermark"
        output_dir.mkdir(exist_ok=True)
        click.echo(f"处理单个文件: {file_path.name}")
        self.add_watermark(file_path, font_size, color, position, output_dir)

@click.command()
@click.argument('input_path', type=click.Path(exists=True, path_type=Path))
@click.option('--font-size', '-s', default=36, show_default=True, help='字体大小')
@click.option('--color', '-c', default='white', show_default=True, help='字体颜色(名称或#RRGGBB)')
@click.option('--position', '-p',
              type=click.Choice([
                  'top-left', 'top-center', 'top-right',
                  'center-left', 'center', 'center-right',
                  'bottom-left', 'bottom-center', 'bottom-right'
              ]),
              default='bottom-right', show_default=True,
              help='水印位置')
def main(input_path: Path, font_size, color, position):
    """输入路径可以是 单个图片文件 或 包含图片的目录。"""
    click.echo("=== Photo Watermark Tool ===")
    click.echo(f"输入路径: {input_path}")
    click.echo(f"字体: {font_size}px 颜色: {color} 位置: {position}")
    click.echo("--------------------------------")
    wm = PhotoWatermark()
    if input_path.is_file():
        wm.process_single_file(input_path, font_size, color, position)
    else:
        wm.process_directory(input_path, font_size, color, position)

if __name__ == '__main__':
    main()

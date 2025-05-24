# ===============================
# utils/image_processor.py - 图像处理工具
# ===============================
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import base64
import io
from typing import Tuple, Optional, Dict, Any
import logging

from config.settings import settings
from .exceptions import ImageProcessingError

logger = logging.getLogger(__name__)

class ImageProcessor:
    """图像处理工具类"""

    @staticmethod
    def preprocess_image(image_data: bytes) -> str:
        """
        预处理图像数据

        Args:
            image_data: 原始图像数据

        Returns:
            处理后的Base64编码图像
        """
        try:
            # 将字节数据转换为PIL图像
            image = Image.open(io.BytesIO(image_data))

            # 检查图像格式
            if image.format not in ['JPEG', 'PNG', 'JPG']:
                image = image.convert('RGB')

            # 图像增强
            enhanced_image = ImageProcessor._enhance_image(image)

            # 调整大小
            resized_image = ImageProcessor._resize_image(enhanced_image)

            # 转换为Base64
            buffered = io.BytesIO()
            resized_image.save(buffered, format="JPEG", quality=95)
            image_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

            logger.info(f"图像预处理完成，大小: {len(image_base64)} 字符")
            return image_base64

        except Exception as e:
            logger.error(f"图像预处理失败: {e}")
            raise ImageProcessingError(f"图像预处理失败: {e}")

    @staticmethod
    def _enhance_image(image: Image.Image) -> Image.Image:
        """图像增强处理"""
        try:
            # 对比度增强
            contrast_enhancer = ImageEnhance.Contrast(image)
            enhanced = contrast_enhancer.enhance(1.2)

            # 锐度增强
            sharpness_enhancer = ImageEnhance.Sharpness(enhanced)
            enhanced = sharpness_enhancer.enhance(1.1)

            # 亮度调整
            brightness_enhancer = ImageEnhance.Brightness(enhanced)
            enhanced = brightness_enhancer.enhance(1.05)

            return enhanced

        except Exception as e:
            logger.warning(f"图像增强失败，使用原图: {e}")
            return image

    @staticmethod
    def _resize_image(image: Image.Image) -> Image.Image:
        """调整图像大小"""
        max_size = settings.get("image.resize_threshold", 1920)

        width, height = image.size

        if width > max_size or height > max_size:
            # 计算缩放比例
            ratio = min(max_size / width, max_size / height)
            new_width = int(width * ratio)
            new_height = int(height * ratio)

            # 使用高质量重采样
            resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            logger.info(f"图像已调整大小: {width}x{height} -> {new_width}x{new_height}")
            return resized

        return image

    @staticmethod
    def extract_text_regions(image_data: bytes) -> Dict[str, Any]:
        """
        使用OpenCV提取文本区域

        Args:
            image_data: 图像数据

        Returns:
            文本区域信息
        """
        try:
            # 转换为OpenCV格式
            nparr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if image is None:
                raise ImageProcessingError("无法解码图像")

            # 转换为灰度图
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

            # 自适应阈值处理
            thresh = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
            )

            # 查找轮廓
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # 提取文本区域
            text_regions = []
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)

                # 过滤太小的区域
                if w > 20 and h > 10:
                    text_regions.append({
                        "x": int(x),
                        "y": int(y),
                        "width": int(w),
                        "height": int(h),
                        "area": int(w * h)
                    })

            # 按面积排序
            text_regions.sort(key=lambda r: r["area"], reverse=True)

            return {
                "success": True,
                "regions": text_regions[:20],  # 最多返回20个区域
                "total_regions": len(text_regions)
            }

        except Exception as e:
            logger.error(f"文本区域提取失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "regions": []
            }

    @staticmethod
    def validate_image(image_data: bytes) -> Dict[str, Any]:
        """
        验证图像数据

        Args:
            image_data: 图像数据

        Returns:
            验证结果
        """
        try:
            # 检查文件大小
            max_size = settings.get("image.max_size", 10 * 1024 * 1024)
            if len(image_data) > max_size:
                return {
                    "valid": False,
                    "error": f"图像文件过大: {len(image_data)} bytes > {max_size} bytes"
                }

            # 尝试打开图像
            image = Image.open(io.BytesIO(image_data))

            # 检查格式
            allowed_formats = settings.get("image.allowed_formats", ["jpg", "jpeg", "png", "bmp"])
            if image.format.lower() not in allowed_formats:
                return {
                    "valid": False,
                    "error": f"不支持的图像格式: {image.format}"
                }

            # 检查尺寸
            width, height = image.size
            if width < 100 or height < 100:
                return {
                    "valid": False,
                    "error": f"图像尺寸过小: {width}x{height}"
                }

            return {
                "valid": True,
                "format": image.format,
                "size": (width, height),
                "file_size": len(image_data)
            }

        except Exception as e:
            return {
                "valid": False,
                "error": f"图像验证失败: {e}"
            }

    @staticmethod
    def create_thumbnail(image_data: bytes, size: Tuple[int, int] = (200, 200)) -> Optional[str]:
        """
        创建缩略图

        Args:
            image_data: 原始图像数据
            size: 缩略图尺寸

        Returns:
            Base64编码的缩略图
        """
        try:
            image = Image.open(io.BytesIO(image_data))

            # 创建缩略图
            image.thumbnail(size, Image.Resampling.LANCZOS)

            # 转换为Base64
            buffered = io.BytesIO()
            image.save(buffered, format="JPEG", quality=85)
            thumbnail_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

            return thumbnail_base64

        except Exception as e:
            logger.error(f"缩略图创建失败: {e}")
            return None
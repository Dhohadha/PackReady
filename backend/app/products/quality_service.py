import io
from typing import Dict, Any, List
from PIL import Image, ImageStat, ImageFilter


class QualityStatus:
    GOOD = "GOOD"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    REJECTED = "REJECTED"


class ImageQualityConfig:
    MIN_WIDTH: int = 100
    MIN_HEIGHT: int = 100
    MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10MB
    DARK_BRIGHTNESS_THRESHOLD: float = 15.0
    BRIGHT_BRIGHTNESS_THRESHOLD: float = 240.0
    EXTREME_ASPECT_MIN: float = 0.2
    EXTREME_ASPECT_MAX: float = 5.0
    MIN_BLUR_SCORE: float = 10.0


class ImageQualityService:
    @staticmethod
    def analyze_image_bytes(contents: bytes) -> Dict[str, Any]:
        file_size = len(contents)
        if file_size > ImageQualityConfig.MAX_FILE_SIZE_BYTES:
            return {
                "status": QualityStatus.REJECTED,
                "warnings": ["File size exceeds maximum allowed limit."],
                "width": 0,
                "height": 0,
                "file_size_bytes": file_size,
                "aspect_ratio": 0.0,
                "mean_brightness": 0.0,
                "blur_score": 0.0,
                "format": None,
            }

        try:
            img = Image.open(io.BytesIO(contents))
            img.verify()
            img = Image.open(io.BytesIO(contents))
        except Exception:
            return {
                "status": QualityStatus.REJECTED,
                "warnings": ["Corrupt or unreadable image file."],
                "width": 0,
                "height": 0,
                "file_size_bytes": file_size,
                "aspect_ratio": 0.0,
                "mean_brightness": 0.0,
                "blur_score": 0.0,
                "format": None,
            }

        width, height = img.size
        aspect_ratio = round(width / height, 2) if height > 0 else 0.0
        warnings: List[str] = []

        # 1. Check dimensions
        if width < ImageQualityConfig.MIN_WIDTH or height < ImageQualityConfig.MIN_HEIGHT:
            warnings.append(
                f"Image dimensions ({width}x{height}) are smaller than minimum ({ImageQualityConfig.MIN_WIDTH}x{ImageQualityConfig.MIN_HEIGHT})."
            )

        # 2. Check aspect ratio
        if aspect_ratio < ImageQualityConfig.EXTREME_ASPECT_MIN or aspect_ratio > ImageQualityConfig.EXTREME_ASPECT_MAX:
            warnings.append(f"Extreme aspect ratio ({aspect_ratio}).")

        # 3. Brightness estimation
        gray_img = img.convert("L")
        stat = ImageStat.Stat(gray_img)
        mean_brightness = round(stat.mean[0], 2)

        if mean_brightness < ImageQualityConfig.DARK_BRIGHTNESS_THRESHOLD:
            warnings.append(f"Image is extremely dark (brightness: {mean_brightness}).")
        elif mean_brightness > ImageQualityConfig.BRIGHT_BRIGHTNESS_THRESHOLD:
            warnings.append(f"Image is extremely bright / overexposed (brightness: {mean_brightness}).")

        # 4. Blur / Sharpness estimation using Laplacian edge variance
        edges = gray_img.filter(ImageFilter.FIND_EDGES)
        edge_stat = ImageStat.Stat(edges)
        blur_score = round(edge_stat.var[0], 2)

        if blur_score < ImageQualityConfig.MIN_BLUR_SCORE:
            warnings.append(f"Image appears blurry (sharpness score: {blur_score}).")

        # Determine overall quality status
        if width < ImageQualityConfig.MIN_WIDTH or height < ImageQualityConfig.MIN_HEIGHT or aspect_ratio < ImageQualityConfig.EXTREME_ASPECT_MIN or aspect_ratio > ImageQualityConfig.EXTREME_ASPECT_MAX:
            status = QualityStatus.REJECTED
        elif warnings:
            status = QualityStatus.NEEDS_REVIEW
        else:
            status = QualityStatus.GOOD

        return {
            "status": status,
            "warnings": warnings,
            "width": width,
            "height": height,
            "file_size_bytes": file_size,
            "aspect_ratio": aspect_ratio,
            "mean_brightness": mean_brightness,
            "blur_score": blur_score,
            "format": img.format,
        }

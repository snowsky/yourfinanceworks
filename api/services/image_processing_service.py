"""
Image Processing Service for Inventory Attachments

Handles image-specific operations including thumbnail generation,
optimization, and metadata extraction for inventory attachments.
"""
import logging
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any
from dataclasses import dataclass
from PIL import Image
import io
import os

from config import config

logger = logging.getLogger(__name__)


@dataclass
class ThumbnailInfo:
    """Information about a generated thumbnail"""
    path: str
    size: Tuple[int, int]
    file_size: int


@dataclass
class ImageProcessingResult:
    """Result of image processing operation"""
    success: bool
    original_dimensions: Optional[Tuple[int, int]] = None
    thumbnails: Optional[List[ThumbnailInfo]] = None
    optimized_path: Optional[str] = None
    error_message: Optional[str] = None


class ImageProcessingService:
    """
    Service for image processing operations including thumbnails,
    optimization, and metadata extraction.
    """

    def __init__(self):
        self.thumbnail_sizes = [(150, 150), (300, 300)]  # Small and medium thumbnails
        self.max_image_size = (2048, 2048)  # Max dimensions for originals
        self.quality_settings = {
            'high': 95,
            'medium': 85,
            'low': 75
        }

    async def process_image(
        self,
        file_path: Path,
        attachment_id: int,
        tenant_id: str
    ) -> ImageProcessingResult:
        """
        Process uploaded image: validate, resize, generate thumbnails

        Args:
            file_path: Path to the uploaded image
            attachment_id: Attachment ID for naming
            tenant_id: Tenant ID for storage organization

        Returns:
            ImageProcessingResult with processing details
        """
        try:
            # Open and validate image
            with Image.open(file_path) as img:
                # Get original dimensions
                original_dimensions = img.size

                # Validate image
                if not self._is_valid_image(img):
                    return ImageProcessingResult(
                        success=False,
                        error_message="Invalid or corrupted image file"
                    )

                # Generate thumbnails
                thumbnails = await self.generate_thumbnails(file_path, attachment_id, tenant_id)

                # Optimize original image if needed
                optimized_path = await self.optimize_image(file_path, tenant_id)

                return ImageProcessingResult(
                    success=True,
                    original_dimensions=original_dimensions,
                    thumbnails=thumbnails,
                    optimized_path=optimized_path
                )

        except Exception as e:
            logger.error(f"Failed to process image {file_path}: {e}")
            return ImageProcessingResult(
                success=False,
                error_message=f"Image processing failed: {str(e)}"
            )

    async def generate_thumbnails(
        self,
        source_path: Path,
        attachment_id: int,
        tenant_id: str
    ) -> List[ThumbnailInfo]:
        """
        Generate multiple thumbnail sizes

        Args:
            source_path: Path to source image
            attachment_id: Attachment ID
            tenant_id: Tenant ID

        Returns:
            List of ThumbnailInfo objects
        """
        thumbnails = []

        try:
            with Image.open(source_path) as img:
                # Convert to RGB if necessary (for PNG with transparency)
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')

                for size in self.thumbnail_sizes:
                    thumbnail = await self._generate_single_thumbnail(
                        img, size, attachment_id, tenant_id
                    )
                    if thumbnail:
                        thumbnails.append(thumbnail)

        except Exception as e:
            logger.error(f"Failed to generate thumbnails for {source_path}: {e}")

        return thumbnails

    async def _generate_single_thumbnail(
        self,
        img: Image.Image,
        size: Tuple[int, int],
        attachment_id: int,
        tenant_id: str
    ) -> Optional[ThumbnailInfo]:
        """
        Generate a single thumbnail

        Args:
            img: PIL Image object
            size: Target size (width, height)
            attachment_id: Attachment ID
            tenant_id: Tenant ID

        Returns:
            ThumbnailInfo if successful, None otherwise
        """
        try:
            # Create thumbnail
            img_copy = img.copy()
            img_copy.thumbnail(size, Image.Resampling.LANCZOS)

            # Create thumbnail directory path
            from services.file_storage_service import file_storage_service
            thumbnail_dir = file_storage_service.get_storage_path(tenant_id, 'images') / 'thumbnails' / f"{size[0]}x{size[1]}"
            thumbnail_dir.mkdir(parents=True, exist_ok=True)

            # Generate thumbnail filename
            source_name = Path(img.filename).stem if img.filename else f"attachment_{attachment_id}"
            thumbnail_filename = f"{source_name}_thumb_{size[0]}x{size[1]}.jpg"
            thumbnail_path = thumbnail_dir / thumbnail_filename

            # Save thumbnail
            img_copy.save(thumbnail_path, 'JPEG', quality=self.quality_settings['high'])

            # Get file size
            file_size = thumbnail_path.stat().st_size

            return ThumbnailInfo(
                path=str(thumbnail_path),
                size=size,
                file_size=file_size
            )

        except Exception as e:
            logger.error(f"Failed to generate {size} thumbnail: {e}")
            return None

    async def optimize_image(
        self,
        file_path: Path,
        tenant_id: str,
        max_size: Optional[Tuple[int, int]] = None
    ) -> Optional[str]:
        """
        Optimize image size and quality for web display

        Args:
            file_path: Path to image file
            tenant_id: Tenant ID
            max_size: Maximum dimensions (optional)

        Returns:
            Path to optimized image, or None if optimization failed
        """
        try:
            max_size = max_size or self.max_image_size

            with Image.open(file_path) as img:
                # Check if resizing is needed
                if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
                    # Calculate new size maintaining aspect ratio
                    img_ratio = img.size[0] / img.size[1]
                    max_ratio = max_size[0] / max_size[1]

                    if img_ratio > max_ratio:
                        # Image is wider than max ratio
                        new_width = max_size[0]
                        new_height = int(max_size[0] / img_ratio)
                    else:
                        # Image is taller than max ratio
                        new_height = max_size[1]
                        new_width = int(max_size[1] * img_ratio)

                    # Resize image
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')

                # Create optimized version path
                from services.file_storage_service import file_storage_service
                optimized_dir = file_storage_service.get_storage_path(tenant_id, 'images') / 'optimized'
                optimized_dir.mkdir(parents=True, exist_ok=True)

                # Generate optimized filename
                source_name = file_path.stem
                optimized_filename = f"{source_name}_optimized.jpg"
                optimized_path = optimized_dir / optimized_filename

                # Save optimized image
                img.save(optimized_path, 'JPEG', quality=self.quality_settings['high'])

                logger.info(f"Optimized image saved: {optimized_path}")
                return str(optimized_path)

        except Exception as e:
            logger.error(f"Failed to optimize image {file_path}: {e}")
            return None

    def get_image_dimensions(self, file_path: Path) -> Optional[Tuple[int, int]]:
        """
        Get image width and height

        Args:
            file_path: Path to image file

        Returns:
            Tuple of (width, height) or None if failed
        """
        try:
            with Image.open(file_path) as img:
                return img.size
        except Exception as e:
            logger.error(f"Failed to get dimensions for {file_path}: {e}")
            return None

    def is_valid_image(self, file_path: Path) -> bool:
        """
        Validate image file integrity

        Args:
            file_path: Path to image file

        Returns:
            True if valid image, False otherwise
        """
        try:
            with Image.open(file_path) as img:
                # Try to load the image data
                img.verify()
                return True
        except Exception as e:
            logger.error(f"Image validation failed for {file_path}: {e}")
            return False

    def _is_valid_image(self, img: Image.Image) -> bool:
        """
        Validate PIL Image object

        Args:
            img: PIL Image object

        Returns:
            True if valid, False otherwise
        """
        try:
            # Check if image can be processed
            img.verify()
            return True
        except Exception:
            return False

    def extract_image_metadata(self, file_path: Path) -> Dict[str, Any]:
        """
        Extract metadata from image file

        Args:
            file_path: Path to image file

        Returns:
            Dictionary with metadata
        """
        metadata = {
            'dimensions': None,
            'format': None,
            'mode': None,
            'has_transparency': False,
            'file_size': None
        }

        try:
            with Image.open(file_path) as img:
                metadata.update({
                    'dimensions': img.size,
                    'format': img.format,
                    'mode': img.mode,
                    'has_transparency': img.mode in ('RGBA', 'LA', 'P'),
                    'file_size': file_path.stat().st_size
                })

                # Extract EXIF data if available
                if hasattr(img, '_getexif') and img._getexif():
                    exif_data = img._getexif()
                    metadata['exif'] = exif_data

        except Exception as e:
            logger.error(f"Failed to extract metadata from {file_path}: {e}")

        return metadata

    async def cleanup_thumbnails(self, attachment_id: int, tenant_id: str) -> bool:
        """
        Clean up thumbnail files for an attachment

        Args:
            attachment_id: Attachment ID
            tenant_id: Tenant ID

        Returns:
            True if cleanup successful, False otherwise
        """
        try:
            from services.file_storage_service import file_storage_service

            # Get thumbnails directory
            thumbnails_base = file_storage_service.get_storage_path(tenant_id, 'images') / 'thumbnails'

            if not thumbnails_base.exists():
                return True

            # Remove all thumbnails for this attachment
            deleted_count = 0
            for size_dir in thumbnails_base.iterdir():
                if size_dir.is_dir():
                    for thumb_file in size_dir.iterdir():
                        if f"attachment_{attachment_id}" in thumb_file.name:
                            thumb_file.unlink()
                            deleted_count += 1

            logger.info(f"Cleaned up {deleted_count} thumbnail files for attachment {attachment_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to cleanup thumbnails for attachment {attachment_id}: {e}")
            return False


# Global instance
image_processing_service = ImageProcessingService()

"""
Bank Statement Analytics Service

This module provides comprehensive analytics and monitoring capabilities for
bank statement processing, including extraction method tracking, performance
metrics, and document characteristics analysis.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

from sqlalchemy.orm import Session
from core.services.ocr_service import track_ai_usage, publish_ocr_usage_metrics

logger = logging.getLogger(__name__)


@dataclass
class ExtractionMethodMetrics:
    """Metrics for a specific extraction method."""
    method: str
    total_attempts: int = 0
    successful_attempts: int = 0
    failed_attempts: int = 0
    total_processing_time: float = 0.0
    average_processing_time: float = 0.0
    min_processing_time: float = float('inf')
    max_processing_time: float = 0.0
    total_text_length: int = 0
    average_text_length: float = 0.0
    total_word_count: int = 0
    average_word_count: float = 0.0
    
    def update_metrics(self, processing_time: float, text_length: int, word_count: int, success: bool):
        """Update metrics with new processing result."""
        self.total_attempts += 1
        if success:
            self.successful_attempts += 1
        else:
            self.failed_attempts += 1
        
        self.total_processing_time += processing_time
        self.average_processing_time = self.total_processing_time / self.total_attempts
        
        self.min_processing_time = min(self.min_processing_time, processing_time)
        self.max_processing_time = max(self.max_processing_time, processing_time)
        
        self.total_text_length += text_length
        self.average_text_length = self.total_text_length / self.total_attempts
        
        self.total_word_count += word_count
        self.average_word_count = self.total_word_count / self.total_attempts


@dataclass
class DocumentCharacteristics:
    """Characteristics of a document that may influence extraction method selection."""
    file_path: str
    file_size_bytes: int
    file_extension: str
    is_scanned: Optional[bool] = None
    has_tables: Optional[bool] = None
    text_density: Optional[float] = None  # Characters per page
    page_count: Optional[int] = None
    contains_bank_keywords: Optional[bool] = None
    estimated_complexity: Optional[str] = None  # "low", "medium", "high"


class BankStatementAnalyticsService:
    """
    Service for tracking and analyzing bank statement processing metrics.
    
    This service provides comprehensive analytics for extraction method usage,
    processing performance, and document characteristics that influence
    extraction method selection.
    """
    
    def __init__(self):
        """Initialize the analytics service."""
        self.session_metrics: Dict[str, ExtractionMethodMetrics] = {}
        self.document_characteristics: List[DocumentCharacteristics] = []
        
        logger.info("BankStatementAnalyticsService initialized")
    
    def track_extraction_attempt(
        self,
        db: Session,
        method: str,
        pdf_path: str,
        processing_time: float,
        text_length: int = 0,
        word_count: int = 0,
        success: bool = True,
        ai_config: Optional[Dict[str, Any]] = None,
        error_details: Optional[str] = None
    ) -> None:
        """
        Track an extraction method attempt with comprehensive metrics.
        
        Args:
            db: Database session
            method: Extraction method used ("pdf_loader" or "ocr")
            pdf_path: Path to the processed file
            processing_time: Time taken for extraction in seconds
            text_length: Length of extracted text
            word_count: Number of words in extracted text
            success: Whether the extraction was successful
            ai_config: AI configuration used (for usage tracking)
            error_details: Error details if extraction failed
        """
        try:
            # Update session metrics
            if method not in self.session_metrics:
                self.session_metrics[method] = ExtractionMethodMetrics(method=method)
            
            self.session_metrics[method].update_metrics(
                processing_time=processing_time,
                text_length=text_length,
                word_count=word_count,
                success=success
            )
            
            # Log extraction attempt with detailed metrics
            file_name = Path(pdf_path).name
            status = "SUCCESS" if success else "FAILED"
            
            logger.info(
                f"📊 Extraction Method Tracking - "
                f"Method: {method}, "
                f"File: {file_name}, "
                f"Status: {status}, "
                f"Time: {processing_time:.2f}s, "
                f"Text Length: {text_length}, "
                f"Word Count: {word_count}"
            )
            
            # Track document characteristics that triggered OCR fallback
            if method == "ocr":
                self._analyze_document_characteristics(pdf_path, text_length, word_count)
            
            # Publish metrics for external monitoring systems
            publish_ocr_usage_metrics(
                db=db,
                operation_type="bank_statement",
                extraction_method=method,
                processing_time=processing_time,
                success=success
            )
            
            # Track AI usage if configuration is provided
            if ai_config and success:
                track_ai_usage(
                    db=db,
                    ai_config=ai_config,
                    operation_type="bank_statement_extraction",
                    metadata={
                        "extraction_method": method,
                        "processing_time": processing_time,
                        "text_length": text_length,
                        "word_count": word_count,
                        "file_name": file_name
                    }
                )
            
            # Log error details for failed attempts
            if not success and error_details:
                logger.warning(
                    f"❌ Extraction Failed - Method: {method}, "
                    f"File: {file_name}, Error: {error_details[:200]}..."
                )
            
        except Exception as e:
            logger.error(f"Failed to track extraction attempt: {e}")
    
    def _analyze_document_characteristics(
        self,
        pdf_path: str,
        text_length: int,
        word_count: int
    ) -> None:
        """
        Analyze document characteristics that may have triggered OCR fallback.
        
        Args:
            pdf_path: Path to the PDF file
            text_length: Length of extracted text
            word_count: Number of words extracted
        """
        try:
            file_path = Path(pdf_path)
            
            # Basic file characteristics
            characteristics = DocumentCharacteristics(
                file_path=str(file_path),
                file_size_bytes=file_path.stat().st_size if file_path.exists() else 0,
                file_extension=file_path.suffix.lower(),
                text_density=text_length / max(1, word_count) if word_count > 0 else 0
            )
            
            # Analyze text content for bank statement indicators
            if text_length > 0:
                # Simple heuristic to detect if document likely contains bank statement content
                bank_keywords = [
                    'balance', 'transaction', 'deposit', 'withdrawal', 'debit', 'credit',
                    'statement', 'account', 'bank', 'date', 'amount', 'description'
                ]
                # This is a simplified check - in practice, we'd analyze the actual text
                characteristics.contains_bank_keywords = True  # Assume true for OCR fallback cases
            
            # Estimate complexity based on file size and text extraction results
            if characteristics.file_size_bytes > 5 * 1024 * 1024:  # > 5MB
                characteristics.estimated_complexity = "high"
            elif characteristics.file_size_bytes > 1 * 1024 * 1024:  # > 1MB
                characteristics.estimated_complexity = "medium"
            else:
                characteristics.estimated_complexity = "low"
            
            # Assume scanned if OCR was needed
            characteristics.is_scanned = True
            
            self.document_characteristics.append(characteristics)
            
            logger.info(
                f"📋 Document Characteristics - "
                f"File: {file_path.name}, "
                f"Size: {characteristics.file_size_bytes} bytes, "
                f"Complexity: {characteristics.estimated_complexity}, "
                f"Text Density: {characteristics.text_density:.1f}"
            )
            
        except Exception as e:
            logger.error(f"Failed to analyze document characteristics: {e}")
    
    def get_extraction_method_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics for all extraction methods.
        
        Returns:
            Dictionary with extraction method statistics
        """
        try:
            stats = {
                "session_start": datetime.now(timezone.utc).isoformat(),
                "total_documents_processed": sum(
                    metrics.total_attempts for metrics in self.session_metrics.values()
                ),
                "methods": {},
                "summary": {
                    "pdf_loader_usage_percent": 0.0,
                    "ocr_usage_percent": 0.0,
                    "overall_success_rate": 0.0,
                    "average_processing_time": 0.0
                }
            }
            
            total_attempts = 0
            total_successful = 0
            total_processing_time = 0.0
            
            for method, metrics in self.session_metrics.items():
                stats["methods"][method] = {
                    "total_attempts": metrics.total_attempts,
                    "successful_attempts": metrics.successful_attempts,
                    "failed_attempts": metrics.failed_attempts,
                    "success_rate": (
                        metrics.successful_attempts / metrics.total_attempts * 100
                        if metrics.total_attempts > 0 else 0.0
                    ),
                    "average_processing_time": metrics.average_processing_time,
                    "min_processing_time": (
                        metrics.min_processing_time 
                        if metrics.min_processing_time != float('inf') else 0.0
                    ),
                    "max_processing_time": metrics.max_processing_time,
                    "average_text_length": metrics.average_text_length,
                    "average_word_count": metrics.average_word_count
                }
                
                total_attempts += metrics.total_attempts
                total_successful += metrics.successful_attempts
                total_processing_time += metrics.total_processing_time
            
            # Calculate summary statistics
            if total_attempts > 0:
                pdf_attempts = self.session_metrics.get("pdf_loader", ExtractionMethodMetrics("pdf_loader")).total_attempts
                ocr_attempts = self.session_metrics.get("ocr", ExtractionMethodMetrics("ocr")).total_attempts
                
                stats["summary"]["pdf_loader_usage_percent"] = (pdf_attempts / total_attempts) * 100
                stats["summary"]["ocr_usage_percent"] = (ocr_attempts / total_attempts) * 100
                stats["summary"]["overall_success_rate"] = (total_successful / total_attempts) * 100
                stats["summary"]["average_processing_time"] = total_processing_time / total_attempts
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get extraction method statistics: {e}")
            return {"error": str(e)}
    
    def get_document_characteristics_analysis(self) -> Dict[str, Any]:
        """
        Get analysis of document characteristics that trigger OCR fallback.
        
        Returns:
            Dictionary with document characteristics analysis
        """
        try:
            if not self.document_characteristics:
                return {
                    "total_documents": 0,
                    "message": "No document characteristics data available"
                }
            
            analysis = {
                "total_documents": len(self.document_characteristics),
                "file_size_distribution": {
                    "small": 0,  # < 1MB
                    "medium": 0,  # 1-5MB
                    "large": 0   # > 5MB
                },
                "complexity_distribution": {
                    "low": 0,
                    "medium": 0,
                    "high": 0
                },
                "file_extensions": {},
                "average_text_density": 0.0,
                "scanned_documents": 0
            }
            
            total_text_density = 0.0
            
            for doc in self.document_characteristics:
                # File size distribution
                if doc.file_size_bytes < 1024 * 1024:  # < 1MB
                    analysis["file_size_distribution"]["small"] += 1
                elif doc.file_size_bytes < 5 * 1024 * 1024:  # < 5MB
                    analysis["file_size_distribution"]["medium"] += 1
                else:
                    analysis["file_size_distribution"]["large"] += 1
                
                # Complexity distribution
                if doc.estimated_complexity:
                    analysis["complexity_distribution"][doc.estimated_complexity] += 1
                
                # File extensions
                ext = doc.file_extension or "unknown"
                analysis["file_extensions"][ext] = analysis["file_extensions"].get(ext, 0) + 1
                
                # Text density
                if doc.text_density:
                    total_text_density += doc.text_density
                
                # Scanned documents
                if doc.is_scanned:
                    analysis["scanned_documents"] += 1
            
            # Calculate averages
            if len(self.document_characteristics) > 0:
                analysis["average_text_density"] = total_text_density / len(self.document_characteristics)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to get document characteristics analysis: {e}")
            return {"error": str(e)}
    
    def log_processing_summary(self) -> None:
        """Log a summary of processing statistics."""
        try:
            stats = self.get_extraction_method_statistics()
            
            logger.info("📈 Bank Statement Processing Summary:")
            logger.info(f"   Total Documents: {stats.get('total_documents_processed', 0)}")
            logger.info(f"   PDF Loader Usage: {stats['summary']['pdf_loader_usage_percent']:.1f}%")
            logger.info(f"   OCR Usage: {stats['summary']['ocr_usage_percent']:.1f}%")
            logger.info(f"   Overall Success Rate: {stats['summary']['overall_success_rate']:.1f}%")
            logger.info(f"   Average Processing Time: {stats['summary']['average_processing_time']:.2f}s")
            
            # Log method-specific details
            for method, method_stats in stats.get("methods", {}).items():
                logger.info(
                    f"   {method.upper()}: "
                    f"{method_stats['total_attempts']} attempts, "
                    f"{method_stats['success_rate']:.1f}% success, "
                    f"{method_stats['average_processing_time']:.2f}s avg"
                )
            
        except Exception as e:
            logger.error(f"Failed to log processing summary: {e}")
    
    def reset_session_metrics(self) -> None:
        """Reset session metrics (useful for testing or periodic resets)."""
        self.session_metrics.clear()
        self.document_characteristics.clear()
        logger.info("Session metrics reset")


# Global analytics service instance
_analytics_service = None


def get_analytics_service() -> BankStatementAnalyticsService:
    """Get the global analytics service instance."""
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = BankStatementAnalyticsService()
    return _analytics_service


def track_bank_statement_extraction(
    db: Session,
    method: str,
    pdf_path: str,
    processing_time: float,
    text_length: int = 0,
    word_count: int = 0,
    success: bool = True,
    ai_config: Optional[Dict[str, Any]] = None,
    error_details: Optional[str] = None
) -> None:
    """
    Convenience function to track bank statement extraction attempts.
    
    Args:
        db: Database session
        method: Extraction method used ("pdf_loader" or "ocr")
        pdf_path: Path to the processed file
        processing_time: Time taken for extraction in seconds
        text_length: Length of extracted text
        word_count: Number of words in extracted text
        success: Whether the extraction was successful
        ai_config: AI configuration used (for usage tracking)
        error_details: Error details if extraction failed
    """
    analytics_service = get_analytics_service()
    analytics_service.track_extraction_attempt(
        db=db,
        method=method,
        pdf_path=pdf_path,
        processing_time=processing_time,
        text_length=text_length,
        word_count=word_count,
        success=success,
        ai_config=ai_config,
        error_details=error_details
    )
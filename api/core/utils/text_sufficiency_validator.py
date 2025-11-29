"""
Text Sufficiency Validation for Bank Statements

This module provides logic to determine if PDF extraction yielded sufficient text
for bank statement processing, with configurable thresholds and bank statement
content detection heuristics.
"""

import re
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from core.settings.ocr_config import get_ocr_config

logger = logging.getLogger(__name__)


@dataclass
class TextQualityMetrics:
    """Metrics for evaluating text quality."""
    text_length: int
    word_count: int
    line_count: int
    bank_indicators_found: int
    numeric_patterns_found: int
    date_patterns_found: int
    currency_patterns_found: int
    quality_score: float
    is_sufficient: bool
    reasons: List[str]


class TextSufficiencyValidator:
    """
    Validator for determining if extracted text is sufficient for bank statement processing.
    
    Uses configurable thresholds and bank statement content detection heuristics
    to evaluate text quality and determine if OCR fallback is needed.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the text sufficiency validator.
        
        Args:
            config: Optional configuration overrides
        """
        self.ocr_config = get_ocr_config()
        
        # Allow config overrides
        if config:
            self.min_text_threshold = config.get('min_text_threshold', self.ocr_config.min_text_threshold)
            self.min_word_threshold = config.get('min_word_threshold', self.ocr_config.min_word_threshold)
        else:
            self.min_text_threshold = self.ocr_config.min_text_threshold
            self.min_word_threshold = self.ocr_config.min_word_threshold
        
        # Bank statement indicators
        self.bank_indicators = [
            # Core banking terms
            'account', 'balance', 'statement', 'bank', 'banking',
            'transaction', 'transactions', 'deposit', 'withdrawal',
            'debit', 'credit', 'payment', 'transfer', 'fee',
            
            # Financial terms
            'amount', 'total', 'subtotal', 'beginning', 'ending',
            'available', 'current', 'previous', 'interest',
            'service charge', 'overdraft', 'minimum',
            
            # Date-related terms
            'date', 'posted', 'effective', 'period', 'from', 'to',
            'statement period', 'closing date', 'cycle',
            
            # Common bank statement sections
            'summary', 'activity', 'details', 'history',
            'deposits and credits', 'withdrawals and debits',
            'checks', 'electronic', 'atm', 'pos',
            
            # Account types
            'checking', 'savings', 'credit card', 'loan',
            'mortgage', 'investment', 'money market'
        ]
        
        # Numeric patterns for financial data
        self.numeric_patterns = [
            r'\$\d+\.?\d*',  # Dollar amounts: $123.45
            r'\d+\.\d{2}',   # Decimal amounts: 123.45
            r'\(\d+\.\d{2}\)',  # Negative amounts in parentheses: (123.45)
            r'-\d+\.\d{2}',  # Negative amounts with minus: -123.45
            r'\d{1,3}(?:,\d{3})*\.\d{2}',  # Formatted amounts: 1,234.56
        ]
        
        # Date patterns
        self.date_patterns = [
            r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',  # MM/DD/YYYY or MM-DD-YYYY
            r'\d{4}[/-]\d{1,2}[/-]\d{1,2}',    # YYYY/MM/DD or YYYY-MM-DD
            r'\d{1,2}/\d{1,2}',                # MM/DD
            r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}',  # Month DD
            r'\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*',  # DD Month
        ]
        
        # Currency patterns
        self.currency_patterns = [
            r'\$',  # Dollar sign
            r'USD', r'CAD', r'EUR', r'GBP',  # Currency codes
            r'cents?', r'dollars?',  # Currency words
        ]
        
        logger.debug(f"TextSufficiencyValidator initialized with thresholds: text={self.min_text_threshold}, words={self.min_word_threshold}")
    
    def validate_text_sufficiency(self, text: str) -> TextQualityMetrics:
        """
        Validate if extracted text is sufficient for bank statement processing.
        
        Args:
            text: Extracted text to validate
            
        Returns:
            TextQualityMetrics with detailed analysis
        """
        if not text:
            return TextQualityMetrics(
                text_length=0,
                word_count=0,
                line_count=0,
                bank_indicators_found=0,
                numeric_patterns_found=0,
                date_patterns_found=0,
                currency_patterns_found=0,
                quality_score=0.0,
                is_sufficient=False,
                reasons=["Text is empty"]
            )
        
        # Basic metrics
        text_length = len(text.strip())
        words = text.split()
        word_count = len(words)
        line_count = len([line for line in text.split('\n') if line.strip()])
        
        # Content analysis
        text_lower = text.lower()
        
        # Count bank indicators
        bank_indicators_found = sum(
            1 for indicator in self.bank_indicators 
            if indicator.lower() in text_lower
        )
        
        # Count numeric patterns
        numeric_patterns_found = sum(
            len(re.findall(pattern, text, re.IGNORECASE))
            for pattern in self.numeric_patterns
        )
        
        # Count date patterns
        date_patterns_found = sum(
            len(re.findall(pattern, text, re.IGNORECASE))
            for pattern in self.date_patterns
        )
        
        # Count currency patterns
        currency_patterns_found = sum(
            len(re.findall(pattern, text, re.IGNORECASE))
            for pattern in self.currency_patterns
        )
        
        # Calculate quality score (0-100)
        quality_score = self._calculate_quality_score(
            text_length, word_count, bank_indicators_found,
            numeric_patterns_found, date_patterns_found, currency_patterns_found
        )
        
        # Determine sufficiency and reasons
        is_sufficient, reasons = self._evaluate_sufficiency(
            text_length, word_count, bank_indicators_found,
            numeric_patterns_found, date_patterns_found, currency_patterns_found
        )
        
        metrics = TextQualityMetrics(
            text_length=text_length,
            word_count=word_count,
            line_count=line_count,
            bank_indicators_found=bank_indicators_found,
            numeric_patterns_found=numeric_patterns_found,
            date_patterns_found=date_patterns_found,
            currency_patterns_found=currency_patterns_found,
            quality_score=quality_score,
            is_sufficient=is_sufficient,
            reasons=reasons
        )
        
        logger.debug(f"Text validation: sufficient={is_sufficient}, score={quality_score:.1f}, reasons={reasons}")
        return metrics
    
    def _calculate_quality_score(
        self,
        text_length: int,
        word_count: int,
        bank_indicators: int,
        numeric_patterns: int,
        date_patterns: int,
        currency_patterns: int
    ) -> float:
        """
        Calculate a quality score (0-100) based on text characteristics.
        
        Args:
            text_length: Length of text in characters
            word_count: Number of words
            bank_indicators: Number of bank-related terms found
            numeric_patterns: Number of numeric patterns found
            date_patterns: Number of date patterns found
            currency_patterns: Number of currency patterns found
            
        Returns:
            Quality score from 0.0 to 100.0
        """
        score = 0.0
        
        # Text length score (0-25 points)
        if text_length >= self.min_text_threshold:
            length_score = min(25, (text_length / (self.min_text_threshold * 4)) * 25)
            score += length_score
        
        # Word count score (0-25 points)
        if word_count >= self.min_word_threshold:
            word_score = min(25, (word_count / (self.min_word_threshold * 4)) * 25)
            score += word_score
        
        # Bank indicators score (0-20 points)
        bank_score = min(20, bank_indicators * 2)
        score += bank_score
        
        # Numeric patterns score (0-15 points)
        numeric_score = min(15, numeric_patterns * 0.5)
        score += numeric_score
        
        # Date patterns score (0-10 points)
        date_score = min(10, date_patterns * 1)
        score += date_score
        
        # Currency patterns score (0-5 points)
        currency_score = min(5, currency_patterns * 1)
        score += currency_score
        
        return min(100.0, score)
    
    def _evaluate_sufficiency(
        self,
        text_length: int,
        word_count: int,
        bank_indicators: int,
        numeric_patterns: int,
        date_patterns: int,
        currency_patterns: int
    ) -> tuple[bool, List[str]]:
        """
        Evaluate if text is sufficient and provide reasons.
        
        Returns:
            Tuple of (is_sufficient, reasons)
        """
        reasons = []
        
        # Check basic thresholds
        if text_length < self.min_text_threshold:
            reasons.append(f"Text too short: {text_length} < {self.min_text_threshold} characters")
        
        if word_count < self.min_word_threshold:
            reasons.append(f"Too few words: {word_count} < {self.min_word_threshold}")
        
        # Check bank statement indicators
        if bank_indicators < 2:
            reasons.append(f"Insufficient bank indicators: {bank_indicators} < 2")
        
        # Check for financial data patterns
        if numeric_patterns < 3:
            reasons.append(f"Insufficient numeric patterns: {numeric_patterns} < 3")
        
        # Check for date patterns (bank statements should have dates)
        if date_patterns < 1:
            reasons.append(f"No date patterns found")
        
        # Text is sufficient if no critical issues found
        is_sufficient = len(reasons) == 0
        
        if is_sufficient:
            reasons.append("Text meets all sufficiency criteria")
        
        return is_sufficient, reasons
    
    def is_text_sufficient(self, text: str) -> bool:
        """
        Simple boolean check for text sufficiency.
        
        Args:
            text: Text to validate
            
        Returns:
            True if text is sufficient
        """
        metrics = self.validate_text_sufficiency(text)
        return metrics.is_sufficient
    
    def get_validation_summary(self, text: str) -> str:
        """
        Get a human-readable summary of text validation.
        
        Args:
            text: Text to validate
            
        Returns:
            Summary string
        """
        metrics = self.validate_text_sufficiency(text)
        
        summary = f"Text Validation Summary:\n"
        summary += f"  Length: {metrics.text_length} characters\n"
        summary += f"  Words: {metrics.word_count}\n"
        summary += f"  Lines: {metrics.line_count}\n"
        summary += f"  Bank indicators: {metrics.bank_indicators_found}\n"
        summary += f"  Numeric patterns: {metrics.numeric_patterns_found}\n"
        summary += f"  Date patterns: {metrics.date_patterns_found}\n"
        summary += f"  Currency patterns: {metrics.currency_patterns_found}\n"
        summary += f"  Quality score: {metrics.quality_score:.1f}/100\n"
        summary += f"  Sufficient: {'Yes' if metrics.is_sufficient else 'No'}\n"
        summary += f"  Reasons: {'; '.join(metrics.reasons)}"
        
        return summary


# Convenience functions for backward compatibility
def is_text_sufficient(text: str, config: Optional[Dict[str, Any]] = None) -> bool:
    """
    Check if text is sufficient for bank statement processing.
    
    Args:
        text: Text to validate
        config: Optional configuration overrides
        
    Returns:
        True if text is sufficient
    """
    validator = TextSufficiencyValidator(config)
    return validator.is_text_sufficient(text)


def validate_text_quality(text: str, config: Optional[Dict[str, Any]] = None) -> TextQualityMetrics:
    """
    Get detailed text quality metrics.
    
    Args:
        text: Text to validate
        config: Optional configuration overrides
        
    Returns:
        TextQualityMetrics with detailed analysis
    """
    validator = TextSufficiencyValidator(config)
    return validator.validate_text_sufficiency(text)
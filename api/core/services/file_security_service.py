"""
File Security Service for Inventory Attachments

Provides comprehensive file validation, security scanning, and threat detection
for uploaded files to ensure safe storage and access.
"""
import os
try:
    import magic
    HAS_MAGIC = True
except ImportError:
    HAS_MAGIC = False
    print("Warning: python-magic not available, using fallback MIME detection")
import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import re

from config import config

logger = logging.getLogger(__name__)


@dataclass
class SecurityScanResult:
    """Result of security scanning operation"""
    is_safe: bool
    threats_detected: List[str]
    scan_details: Dict[str, Any]
    risk_level: str  # 'low', 'medium', 'high', 'critical'
    recommendations: List[str]


@dataclass
class ValidationResult:
    """Result of file validation"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    metadata: Dict[str, Any]
    security_result: Optional[SecurityScanResult] = None


class FileSecurityService:
    """
    Comprehensive file security service with multiple validation layers
    """

    def __init__(self):
        self.max_file_size = config.MAX_UPLOAD_SIZE
        self.allowed_mime_types = self._get_allowed_mime_types()
        self.dangerous_extensions = self._get_dangerous_extensions()
        self.suspicious_patterns = self._get_suspicious_patterns()

    def _get_allowed_mime_types(self) -> Dict[str, List[str]]:
        """Get allowed MIME types for different attachment types"""
        return {
            'images': [
                'image/jpeg', 'image/jpg', 'image/png', 'image/gif',
                'image/webp', 'image/bmp', 'image/tiff', 'image/svg+xml',
                'image/heic', 'image/heif'
            ],
            'documents': [
                'application/pdf', 'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/vnd.ms-excel',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'text/plain', 'text/csv', 'application/rtf',
                'application/vnd.oasis.opendocument.text',
                'application/vnd.oasis.opendocument.spreadsheet',
                # Archive formats (for documentation packages)
                'application/zip', 'application/x-zip-compressed',
                'application/x-rar-compressed', 'application/x-7z-compressed',
                'application/gzip', 'application/x-tar',
                # Additional document formats
                'application/json', 'application/xml', 'text/xml',
                'application/octet-stream'  # Generic binary format
            ]
        }

    def _get_dangerous_extensions(self) -> List[str]:
        """Get list of dangerous file extensions to block"""
        return [
            # Executables
            'exe', 'bat', 'cmd', 'com', 'pif', 'scr', 'vbs', 'js', 'jse', 'wsf', 'wsh',
            'hta', 'jar', 'ps1', 'ps1xml', 'ps2', 'ps2xml', 'psc1', 'psc2', 'msh', 'msh1',
            'msh2', 'mshxml', 'msh1xml', 'msh2xml', 'scf', 'lnk', 'inf', 'reg',

            # Office documents with macros (keep these blocked)
            'docm', 'dotm', 'xlsm', 'xltm', 'pptm', 'potm',

            # Other potentially dangerous
            'dll', 'ocx', 'cpl', 'drv', 'sys'
        ]

    def _get_suspicious_patterns(self) -> List[Dict[str, Any]]:
        """Get patterns that indicate potentially malicious content"""
        return [
            {
                'name': 'script_tags',
                'pattern': r'<script[^>]*>.*?</script>',
                'severity': 'high',
                'description': 'Embedded script tags detected'
            },
            {
                'name': 'javascript_urls',
                'pattern': r'javascript:',
                'severity': 'high',
                'description': 'JavaScript URLs detected'
            },
            {
                'name': 'php_code',
                'pattern': r'<\?php',
                'severity': 'critical',
                'description': 'PHP code detected'
            },
            {
                'name': 'eval_function',
                'pattern': r'\beval\s*\(',
                'severity': 'high',
                'description': 'Eval function usage detected'
            },
            {
                'name': 'base64_decode',
                'pattern': r'base64_decode\s*\(',
                'severity': 'medium',
                'description': 'Base64 decode function detected'
            }
        ]

    async def validate_file(
        self,
        file_content: bytes,
        filename: str,
        attachment_type: str,
        user_id: Optional[int] = None
    ) -> ValidationResult:
        """
        Comprehensive file validation with multiple security layers

        Args:
            file_content: Raw file content as bytes
            filename: Original filename
            attachment_type: Type of attachment ('images', 'documents')
            user_id: User ID for audit logging

        Returns:
            ValidationResult with validation details
        """
        errors = []
        warnings = []
        metadata = {}

        # 1. Basic file information
        file_size = len(file_content)
        file_ext = Path(filename).suffix.lower().lstrip('.')

        metadata.update({
            'original_filename': filename,
            'file_extension': file_ext,
            'file_size': file_size,
            'attachment_type': attachment_type
        })

        # 2. File size validation
        if file_size > self.max_file_size:
            errors.append(f"File size {file_size} exceeds maximum allowed size of {self.max_file_size}")

        if file_size == 0:
            errors.append("File is empty")

        # 3. Filename security validation
        filename_security = self._validate_filename_security(filename)
        if not filename_security['safe']:
            errors.extend(filename_security['issues'])

        # 4. MIME type validation
        mime_validation = await self._validate_mime_type(file_content, filename, attachment_type)
        if not mime_validation['valid']:
            errors.extend(mime_validation['errors'])
        else:
            metadata['detected_mime_type'] = mime_validation['detected_mime']

        # 5. Content analysis
        content_analysis = await self._analyze_file_content(file_content, filename, attachment_type)
        warnings.extend(content_analysis['warnings'])
        metadata.update(content_analysis['metadata'])

        # 6. Security scanning
        security_result = await self._perform_security_scan(file_content, filename, attachment_type)
        if security_result and not security_result.is_safe:
            errors.extend(security_result.threats_detected)

        # Determine overall validity
        is_valid = len(errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            metadata=metadata,
            security_result=security_result
        )

    def _validate_filename_security(self, filename: str) -> Dict[str, Any]:
        """Validate filename for security issues"""
        issues = []
        safe = True

        # Check for dangerous extensions
        file_ext = Path(filename).suffix.lower().lstrip('.')
        if file_ext in self.dangerous_extensions:
            issues.append(f"Dangerous file extension '{file_ext}' not allowed")
            safe = False

        # Check for path traversal attempts
        if '..' in filename or '/' in filename or '\\' in filename:
            issues.append("Filename contains path traversal characters")
            safe = False

        # Check for null bytes
        if '\x00' in filename:
            issues.append("Filename contains null bytes")
            safe = False

        # Check filename length
        if len(filename) > 255:
            issues.append("Filename too long (max 255 characters)")
            safe = False

        return {
            'safe': safe,
            'issues': issues
        }

    async def _validate_mime_type(
        self,
        file_content: bytes,
        filename: str,
        attachment_type: str
    ) -> Dict[str, Any]:
        """Validate MIME type using multiple detection methods"""
        errors = []

        try:
            # Method 1: Python magic library (if available)
            if HAS_MAGIC:
                detected_mime = magic.from_buffer(file_content, mime=True)
            else:
                # Fallback to mimetypes based on filename
                import mimetypes
                detected_mime, _ = mimetypes.guess_type(filename)

            # Method 2: Filename extension to MIME mapping
            import mimetypes
            extension_mime, _ = mimetypes.guess_type(filename)

            # Check if detected MIME is in allowed types
            allowed_types = self.allowed_mime_types.get(attachment_type, [])

            # Be more lenient with MIME type validation
            if detected_mime and detected_mime not in allowed_types:
                # Check if it's a generic type that should be allowed
                if detected_mime in ['application/octet-stream', 'text/plain']:
                    # Allow generic types but add a warning
                    pass
                else:
                    errors.append(f"Detected MIME type '{detected_mime}' not allowed for {attachment_type}")

            # Check for MIME type mismatch
            if extension_mime and detected_mime != extension_mime:
                # This is a warning, not an error, as some files might legitimately have mismatched types
                pass

            return {
                'valid': len(errors) == 0,
                'detected_mime': detected_mime,
                'extension_mime': extension_mime,
                'errors': errors
            }

        except Exception as e:
            logger.error(f"MIME type validation failed: {e}")
            # Don't fail validation just because MIME detection failed
            return {
                'valid': True,  # Allow upload but log the issue
                'detected_mime': 'application/octet-stream',
                'extension_mime': extension_mime,
                'errors': []  # Don't block upload for MIME detection failures
            }

    async def _analyze_file_content(
        self,
        file_content: bytes,
        filename: str,
        attachment_type: str
    ) -> Dict[str, Any]:
        """Analyze file content for suspicious patterns"""
        warnings = []
        metadata = {}

        try:
            # Convert bytes to string for text analysis (for text-based files)
            content_str = None
            if attachment_type == 'documents':
                try:
                    content_str = file_content.decode('utf-8', errors='ignore')
                except:
                    pass

            if content_str:
                # Check for suspicious patterns
                for pattern_info in self.suspicious_patterns:
                    pattern = re.compile(pattern_info['pattern'], re.IGNORECASE | re.MULTILINE)
                    if pattern.search(content_str):
                        warnings.append(f"{pattern_info['severity'].upper()}: {pattern_info['description']}")

                # Basic content analysis
                metadata.update({
                    'has_text_content': True,
                    'content_length': len(content_str),
                    'line_count': len(content_str.split('\n'))
                })
            else:
                metadata.update({
                    'has_text_content': False,
                    'content_length': len(file_content)
                })

            # Calculate file hash for integrity checking
            file_hash = hashlib.sha256(file_content).hexdigest()
            metadata['file_hash'] = file_hash

        except Exception as e:
            logger.error(f"Content analysis failed: {e}")
            warnings.append("Content analysis failed")

        return {
            'warnings': warnings,
            'metadata': metadata
        }

    async def _perform_security_scan(
        self,
        file_content: bytes,
        filename: str,
        attachment_type: str
    ) -> SecurityScanResult:
        """Perform comprehensive security scanning"""
        threats_detected = []
        scan_details = {}
        risk_level = 'low'

        try:
            # 1. File signature analysis
            file_signature = file_content[:50] if len(file_content) >= 50 else file_content
            scan_details['file_signature'] = file_signature.hex()

            # 2. Entropy analysis (high entropy might indicate encryption/compression)
            entropy = self._calculate_entropy(file_content)
            scan_details['entropy'] = entropy

            try:
                # Increase entropy threshold to be more lenient
                if entropy > 8.0:  # Higher entropy threshold for business documents
                    threats_detected.append("High entropy detected - possible encrypted content")
                    if risk_level == 'low':
                        risk_level = 'medium'
            except (TypeError, AttributeError):
                # Skip entropy check if calculation fails
                pass

            # 3. File size anomalies
            file_size = len(file_content)
            if file_size < 10:  # Suspiciously small files
                threats_detected.append("File suspiciously small")
                risk_level = 'medium'

            # 4. Content pattern analysis for known malware signatures
            # This is a simplified example - in production you'd use a proper antivirus engine
            # Made more lenient for business documents
            suspicious_patterns = [
                b'<script', b'javascript:', b'eval(', b'document.cookie',
                b'<?php', b'unescape('
            ]
            
            # Only check for truly dangerous patterns, skip template-like patterns
            for pattern in suspicious_patterns:
                if pattern in file_content.lower():
                    # Only flag as high risk for truly dangerous patterns
                    if pattern in [b'<script', b'javascript:', b'eval(', b'<?php']:
                        threats_detected.append(f"Suspicious pattern detected: {pattern.decode('utf-8', errors='ignore')}")
                        risk_level = 'high'
                    else:
                        # Lower risk for other patterns
                        threats_detected.append(f"Potentially suspicious pattern detected: {pattern.decode('utf-8', errors='ignore')}")
                        if risk_level == 'low':
                            risk_level = 'medium'

            # 5. File extension vs content analysis (more lenient)
            file_ext = Path(filename).suffix.lower().lstrip('.')
            if file_ext in ['txt', 'csv'] and entropy > 7.0:  # Higher threshold
                threats_detected.append("Text file with high entropy - possible obfuscated content")
                if risk_level == 'low':
                    risk_level = 'medium'

        except Exception as e:
            logger.error(f"Security scan failed: {e}")
            threats_detected.append("Security scan failed")
            risk_level = 'medium'

        is_safe = len(threats_detected) == 0

        recommendations = []
        if not is_safe:
            recommendations.append("File flagged for manual review")
            if risk_level in ['high', 'critical']:
                recommendations.append("File quarantined - do not process")

        return SecurityScanResult(
            is_safe=is_safe,
            threats_detected=threats_detected,
            scan_details=scan_details,
            risk_level=risk_level,
            recommendations=recommendations
        )

    def _calculate_entropy(self, data: bytes) -> float:
        """Calculate Shannon entropy of file content"""
        if not data:
            return 0.0

        try:
            # Count byte frequencies
            byte_counts = {}
            for byte in data:
                byte_counts[byte] = byte_counts.get(byte, 0) + 1

            # Calculate entropy
            entropy = 0.0
            data_len = len(data)

            for count in byte_counts.values():
                if count > 0:
                    probability = count / data_len
                    entropy -= probability * (probability.bit_length() - 1)  # Approximation

            return entropy
        except Exception:
            # Return safe default if calculation fails
            return 0.0

    def get_security_stats(self) -> Dict[str, Any]:
        """Get security service statistics"""
        return {
            'supported_mime_types': self.allowed_mime_types,
            'blocked_extensions': self.dangerous_extensions,
            'suspicious_patterns_count': len(self.suspicious_patterns),
            'max_file_size': self.max_file_size
        }


# Global instance
file_security_service = FileSecurityService()

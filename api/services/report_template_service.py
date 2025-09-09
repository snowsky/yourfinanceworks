"""
Report Template Management Service

This service provides comprehensive template management capabilities including
CRUD operations, sharing functionality, validation, and template-based report generation.
"""

from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from pydantic import ValidationError

from models.models_per_tenant import ReportTemplate, User
from schemas.report import (
    ReportTemplateCreate, ReportTemplateUpdate, ReportTemplate as ReportTemplateSchema,
    ReportType, ReportFilters, ReportGenerateRequest, ReportResult
)
from services.report_service import ReportService
from services.report_validation_service import ReportValidationService
from services.report_retry_service import ReportRetryService, retry_on_failure
from exceptions.report_exceptions import (
    ReportTemplateException, ReportValidationException, ReportErrorCode,
    template_not_found_error, validation_error
)


class ReportTemplateService:
    """
    Service for managing report templates with CRUD operations, sharing, and validation.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.validation_service = ReportValidationService(db)
        self.retry_service = ReportRetryService()
        
        # Valid report types for validation
        self.valid_report_types = [rt.value for rt in ReportType]
        
        # Valid filter fields for each report type
        self.valid_filters = {
            ReportType.CLIENT: [
                'date_from', 'date_to', 'client_ids', 'currency', 
                'include_inactive', 'balance_min', 'balance_max'
            ],
            ReportType.INVOICE: [
                'date_from', 'date_to', 'client_ids', 'currency', 'status',
                'amount_min', 'amount_max', 'include_items', 'is_recurring'
            ],
            ReportType.PAYMENT: [
                'date_from', 'date_to', 'client_ids', 'currency', 'payment_methods',
                'include_unmatched', 'amount_min', 'amount_max'
            ],
            ReportType.EXPENSE: [
                'date_from', 'date_to', 'client_ids', 'currency', 'categories',
                'labels', 'include_attachments', 'vendor', 'status'
            ],
            ReportType.STATEMENT: [
                'date_from', 'date_to', 'account_ids', 'transaction_types',
                'include_reconciliation', 'amount_min', 'amount_max'
            ]
        }
        
        # Default columns for each report type
        self.default_columns = {
            ReportType.CLIENT: [
                'name', 'email', 'balance', 'paid_amount', 'total_invoices', 'created_at'
            ],
            ReportType.INVOICE: [
                'number', 'client_name', 'amount', 'status', 'due_date', 'outstanding_amount'
            ],
            ReportType.PAYMENT: [
                'payment_date', 'amount', 'payment_method', 'client_name', 'invoice_number'
            ],
            ReportType.EXPENSE: [
                'expense_date', 'amount', 'category', 'vendor', 'description'
            ],
            ReportType.STATEMENT: [
                'date', 'description', 'amount', 'transaction_type', 'balance'
            ]
        }
    
    def create_template(
        self, 
        template_data: ReportTemplateCreate, 
        user_id: int
    ) -> ReportTemplateSchema:
        """
        Create a new report template.
        
        Args:
            template_data: Template creation data
            user_id: ID of the user creating the template
            
        Returns:
            Created template schema
            
        Raises:
            TemplateValidationError: If validation fails
        """
        try:
            # Validate template data
            self._validate_template_data(template_data)
            
            # Check if template name is unique for this user
            existing_template = self.db.query(ReportTemplate).filter(
                and_(
                    ReportTemplate.user_id == user_id,
                    ReportTemplate.name == template_data.name
                )
            ).first()
            
            if existing_template:
                raise TemplateValidationError(
                    f"Template with name '{template_data.name}' already exists",
                    field="name",
                    code="DUPLICATE_TEMPLATE_NAME"
                )
            
            # Determine columns to use
            columns_to_use = template_data.columns or self.default_columns.get(template_data.report_type, [])
            
            # Create the template
            db_template = ReportTemplate(
                name=template_data.name,
                report_type=template_data.report_type.value,
                filters=template_data.filters,
                columns=columns_to_use,
                formatting=template_data.formatting or {},
                user_id=user_id,
                is_shared=template_data.is_shared or False
            )
            
            self.db.add(db_template)
            self.db.commit()
            self.db.refresh(db_template)
            
            return ReportTemplateSchema.model_validate(db_template)
            
        except TemplateValidationError:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            raise TemplateValidationError(
                f"Failed to create template: {str(e)}",
                code="TEMPLATE_CREATION_ERROR"
            )
    
    def get_template(self, template_id: int, user_id: int) -> ReportTemplateSchema:
        """
        Get a template by ID with access control.
        
        Args:
            template_id: Template ID
            user_id: User ID requesting the template
            
        Returns:
            Template schema
            
        Raises:
            TemplateAccessError: If template not found or access denied
        """
        template = self.db.query(ReportTemplate).filter(
            and_(
                ReportTemplate.id == template_id,
                or_(
                    ReportTemplate.user_id == user_id,  # User owns the template
                    ReportTemplate.is_shared == True    # Template is shared
                )
            )
        ).first()
        
        if not template:
            raise TemplateAccessError(
                f"Template {template_id} not found or access denied",
                template_id=template_id,
                user_id=user_id
            )
        
        return ReportTemplateSchema.model_validate(template)
    
    def update_template(
        self, 
        template_id: int, 
        template_data: ReportTemplateUpdate, 
        user_id: int
    ) -> ReportTemplateSchema:
        """
        Update an existing template.
        
        Args:
            template_id: Template ID to update
            template_data: Updated template data
            user_id: User ID performing the update
            
        Returns:
            Updated template schema
            
        Raises:
            TemplateAccessError: If template not found or user doesn't own it
            TemplateValidationError: If validation fails
        """
        try:
            # Get the template (only owner can update)
            template = self.db.query(ReportTemplate).filter(
                and_(
                    ReportTemplate.id == template_id,
                    ReportTemplate.user_id == user_id  # Only owner can update
                )
            ).first()
            
            if not template:
                raise TemplateAccessError(
                    f"Template {template_id} not found or you don't have permission to update it",
                    template_id=template_id,
                    user_id=user_id
                )
            
            # Validate updated data
            if template_data.name is not None:
                # Check for duplicate name (excluding current template)
                existing_template = self.db.query(ReportTemplate).filter(
                    and_(
                        ReportTemplate.user_id == user_id,
                        ReportTemplate.name == template_data.name,
                        ReportTemplate.id != template_id
                    )
                ).first()
                
                if existing_template:
                    raise TemplateValidationError(
                        f"Template with name '{template_data.name}' already exists",
                        field="name",
                        code="DUPLICATE_TEMPLATE_NAME"
                    )
            
            # Validate filters if provided
            if template_data.filters is not None:
                report_type = ReportType(template.report_type)
                self._validate_template_filters(report_type, template_data.filters)
            
            # Validate columns if provided
            if template_data.columns is not None:
                report_type = ReportType(template.report_type)
                self._validate_template_columns(report_type, template_data.columns)
            
            # Update the template
            update_data = template_data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(template, field, value)
            
            template.updated_at = datetime.now()
            
            self.db.commit()
            self.db.refresh(template)
            
            return ReportTemplateSchema.model_validate(template)
            
        except (TemplateAccessError, TemplateValidationError):
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            raise TemplateValidationError(
                f"Failed to update template: {str(e)}",
                code="TEMPLATE_UPDATE_ERROR"
            )
    
    def delete_template(self, template_id: int, user_id: int) -> bool:
        """
        Delete a template.
        
        Args:
            template_id: Template ID to delete
            user_id: User ID performing the deletion
            
        Returns:
            True if deleted successfully
            
        Raises:
            TemplateAccessError: If template not found or user doesn't own it
        """
        try:
            # Get the template (only owner can delete)
            template = self.db.query(ReportTemplate).filter(
                and_(
                    ReportTemplate.id == template_id,
                    ReportTemplate.user_id == user_id  # Only owner can delete
                )
            ).first()
            
            if not template:
                raise TemplateAccessError(
                    f"Template {template_id} not found or you don't have permission to delete it",
                    template_id=template_id,
                    user_id=user_id
                )
            
            self.db.delete(template)
            self.db.commit()
            
            return True
            
        except TemplateAccessError:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            raise TemplateValidationError(
                f"Failed to delete template: {str(e)}",
                code="TEMPLATE_DELETE_ERROR"
            )
    
    def list_templates(
        self, 
        user_id: int, 
        report_type: Optional[ReportType] = None,
        include_shared: bool = True,
        limit: int = 100,
        offset: int = 0
    ) -> List[ReportTemplateSchema]:
        """
        List templates accessible to a user.
        
        Args:
            user_id: User ID
            report_type: Filter by report type (optional)
            include_shared: Whether to include shared templates
            limit: Maximum number of templates to return
            offset: Number of templates to skip
            
        Returns:
            List of template schemas
        """
        query = self.db.query(ReportTemplate)
        
        # Build access filter
        access_conditions = [ReportTemplate.user_id == user_id]
        if include_shared:
            access_conditions.append(ReportTemplate.is_shared == True)
        
        query = query.filter(or_(*access_conditions))
        
        # Filter by report type if specified
        if report_type:
            query = query.filter(ReportTemplate.report_type == report_type.value)
        
        # Apply pagination
        query = query.offset(offset).limit(limit)
        
        # Order by name
        query = query.order_by(ReportTemplate.name)
        
        templates = query.all()
        return [ReportTemplateSchema.model_validate(template) for template in templates]
    
    def share_template(self, template_id: int, user_id: int, is_shared: bool) -> ReportTemplateSchema:
        """
        Update the sharing status of a template.
        
        Args:
            template_id: Template ID
            user_id: User ID (must be owner)
            is_shared: Whether to share the template
            
        Returns:
            Updated template schema
            
        Raises:
            TemplateAccessError: If template not found or user doesn't own it
        """
        try:
            # Get the template (only owner can change sharing)
            template = self.db.query(ReportTemplate).filter(
                and_(
                    ReportTemplate.id == template_id,
                    ReportTemplate.user_id == user_id  # Only owner can change sharing
                )
            ).first()
            
            if not template:
                raise TemplateAccessError(
                    f"Template {template_id} not found or you don't have permission to modify sharing",
                    template_id=template_id,
                    user_id=user_id
                )
            
            template.is_shared = is_shared
            template.updated_at = datetime.now()
            
            self.db.commit()
            self.db.refresh(template)
            
            return ReportTemplateSchema.model_validate(template)
            
        except TemplateAccessError:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            raise TemplateValidationError(
                f"Failed to update template sharing: {str(e)}",
                code="TEMPLATE_SHARING_ERROR"
            )
    
    def generate_report_from_template(
        self, 
        template_id: int, 
        user_id: int,
        filter_overrides: Optional[Dict[str, Any]] = None,
        export_format: str = "json"
    ) -> ReportResult:
        """
        Generate a report using a template with optional filter overrides.
        
        Args:
            template_id: Template ID to use
            user_id: User ID generating the report
            filter_overrides: Optional filters to override template defaults
            export_format: Export format for the report
            
        Returns:
            Report generation result
            
        Raises:
            TemplateAccessError: If template not found or access denied
        """
        try:
            # Get the template
            template_schema = self.get_template(template_id, user_id)
            
            # Merge template filters with overrides
            final_filters = template_schema.filters.copy() if template_schema.filters else {}
            if filter_overrides:
                final_filters.update(filter_overrides)
            
            # Create report service and generate report
            report_service = ReportService(self.db)
            
            return report_service.generate_report(
                report_type=ReportType(template_schema.report_type),
                filters=final_filters,
                export_format=report_service.validate_export_format(export_format),
                user_id=user_id
            )
            
        except TemplateAccessError:
            raise
        except Exception as e:
            raise TemplateValidationError(
                f"Failed to generate report from template: {str(e)}",
                code="TEMPLATE_REPORT_GENERATION_ERROR"
            )
    
    def validate_template_filters(
        self, 
        report_type: ReportType, 
        filters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate template filters using the report service validation.
        
        Args:
            report_type: Report type
            filters: Filters to validate
            
        Returns:
            Validated filters dictionary
            
        Raises:
            TemplateValidationError: If validation fails
        """
        try:
            report_service = ReportService(self.db)
            validated_filters = report_service.validate_filters(report_type, filters)
            return validated_filters.model_dump(exclude_unset=True)
            
        except ReportValidationError as e:
            raise TemplateValidationError(
                f"Filter validation failed: {e.message}",
                field=e.field,
                code=e.code
            )
    
    def _validate_template_data(self, template_data: ReportTemplateCreate) -> None:
        """Validate template creation data"""
        # Validate report type
        if template_data.report_type.value not in self.valid_report_types:
            raise TemplateValidationError(
                f"Invalid report type: {template_data.report_type}",
                field="report_type",
                code="INVALID_REPORT_TYPE"
            )
        
        # Validate template name
        if not template_data.name or len(template_data.name.strip()) == 0:
            raise TemplateValidationError(
                "Template name cannot be empty",
                field="name",
                code="EMPTY_TEMPLATE_NAME"
            )
        
        if len(template_data.name) > 255:
            raise TemplateValidationError(
                "Template name cannot exceed 255 characters",
                field="name",
                code="TEMPLATE_NAME_TOO_LONG"
            )
        
        # Validate filters
        if template_data.filters:
            self._validate_template_filters(template_data.report_type, template_data.filters)
        
        # Validate columns (including empty list check)
        if template_data.columns is not None:
            self._validate_template_columns(template_data.report_type, template_data.columns)
    
    def _validate_template_filters(self, report_type: ReportType, filters: Dict[str, Any]) -> None:
        """Validate template filters"""
        valid_filters = self.valid_filters.get(report_type, [])
        
        for filter_key in filters.keys():
            if filter_key not in valid_filters:
                raise TemplateValidationError(
                    f"Invalid filter '{filter_key}' for report type '{report_type.value}'",
                    field="filters",
                    code="INVALID_FILTER_KEY"
                )
    
    def _validate_template_columns(self, report_type: ReportType, columns: List[str]) -> None:
        """Validate template columns"""
        if not columns or len(columns) == 0:
            raise TemplateValidationError(
                "At least one column must be specified",
                field="columns",
                code="NO_COLUMNS_SPECIFIED"
            )
        
        # Note: In a real implementation, you might want to validate against
        # available columns for each report type from the database schema
        # For now, we'll just ensure it's not empty
        
        if len(columns) > 50:
            raise TemplateValidationError(
                "Too many columns specified (maximum 50)",
                field="columns",
                code="TOO_MANY_COLUMNS"
            )
    
    def get_template_usage_stats(self, template_id: int, user_id: int) -> Dict[str, Any]:
        """
        Get usage statistics for a template.
        
        Args:
            template_id: Template ID
            user_id: User ID (must have access to template)
            
        Returns:
            Usage statistics dictionary
            
        Raises:
            TemplateAccessError: If template not found or access denied
        """
        # Verify access to template
        self.get_template(template_id, user_id)
        
        # Get usage stats from report history
        from api.models.models_per_tenant import ReportHistory
        
        stats = self.db.query(ReportHistory).filter(
            ReportHistory.template_id == template_id
        )
        
        total_uses = stats.count()
        successful_uses = stats.filter(ReportHistory.status == "completed").count()
        failed_uses = stats.filter(ReportHistory.status == "failed").count()
        
        # Get recent usage
        recent_uses = stats.order_by(ReportHistory.generated_at.desc()).limit(5).all()
        
        return {
            "template_id": template_id,
            "total_uses": total_uses,
            "successful_uses": successful_uses,
            "failed_uses": failed_uses,
            "success_rate": (successful_uses / total_uses * 100) if total_uses > 0 else 0,
            "recent_uses": [
                {
                    "generated_at": use.generated_at,
                    "status": use.status,
                    "generated_by": use.generated_by
                }
                for use in recent_uses
            ]
        }
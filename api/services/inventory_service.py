from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, func, or_, and_
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone
import logging

from models.models_per_tenant import (
    InventoryItem, InventoryCategory, StockMovement,
    User, InvoiceItem, Expense
)
from schemas.inventory import (
    InventoryItemCreate, InventoryItemUpdate, InventoryCategoryCreate,
    InventoryCategoryUpdate, InventorySearchFilters, InventoryAnalytics,
    StockMovementSummary
)
from exceptions.inventory_exceptions import (
    InventoryException, ItemNotFoundException, CategoryNotFoundException,
    DuplicateSKUException, DuplicateCategoryException, ItemInUseException,
    CategoryInUseException, InsufficientStockException, StockNotTrackedException
)

logger = logging.getLogger(__name__)


class InventoryService:
    """Service class for handling inventory operations"""

    def __init__(self, db: Session):
        self.db = db

    # === Category Operations ===

    def create_category(self, category_data: InventoryCategoryCreate) -> InventoryCategory:
        """Create a new inventory category"""
        try:
            category = InventoryCategory(**category_data.model_dump())
            self.db.add(category)
            self.db.commit()
            self.db.refresh(category)
            logger.info(f"Created inventory category: {category.name}")
            return category
        except IntegrityError as e:
            self.db.rollback()
            if "unique constraint" in str(e).lower():
                raise ValueError("Category name already exists")
            raise

    def update_category(self, category_id: int, category_data: InventoryCategoryUpdate) -> InventoryCategory:
        """Update an existing inventory category"""
        category = self.db.query(InventoryCategory).filter(InventoryCategory.id == category_id).first()
        if not category:
            raise CategoryNotFoundException(category_id)

        update_data = category_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(category, field, value)

        try:
            self.db.commit()
            self.db.refresh(category)
            logger.info(f"Updated inventory category: {category.name}")
            return category
        except IntegrityError as e:
            self.db.rollback()
            if "unique constraint" in str(e).lower():
                raise DuplicateCategoryException(update_data.get('name', 'Unknown'))
            raise

    def delete_category(self, category_id: int) -> bool:
        """Delete an inventory category (only if no items are associated)"""
        category = self.db.query(InventoryCategory).filter(InventoryCategory.id == category_id).first()
        if not category:
            raise CategoryNotFoundException(category_id)

        # Check if category has associated items
        item_count = self.db.query(func.count(InventoryItem.id)).filter(
            InventoryItem.category_id == category_id
        ).scalar()

        if item_count > 0:
            raise CategoryInUseException(category_id, item_count)

        self.db.delete(category)
        self.db.commit()
        logger.info(f"Deleted inventory category: {category.name}")
        return True

    def get_categories(self, active_only: bool = True) -> List[InventoryCategory]:
        """Get all inventory categories"""
        query = self.db.query(InventoryCategory)
        if active_only:
            query = query.filter(InventoryCategory.is_active == True)
        return query.order_by(InventoryCategory.name).all()

    def get_category(self, category_id: int) -> Optional[InventoryCategory]:
        """Get a specific category by ID"""
        return self.db.query(InventoryCategory).filter(InventoryCategory.id == category_id).first()

    # === Item Operations ===

    def create_item(self, item_data: InventoryItemCreate, user_id: int) -> InventoryItem:
        """Create a new inventory item"""
        try:
            # Validate category exists if provided
            if item_data.category_id:
                category = self.db.query(InventoryCategory).filter(
                    InventoryCategory.id == item_data.category_id,
                    InventoryCategory.is_active == True
                ).first()
                if not category:
                    raise ValueError("Invalid category")

            # Check for duplicate SKU
            if item_data.sku:
                existing = self.db.query(InventoryItem).filter(
                    InventoryItem.sku == item_data.sku,
                    InventoryItem.is_active == True
                ).first()
                if existing:
                    raise ValueError("SKU already exists")

            item = InventoryItem(**item_data.model_dump())
            self.db.add(item)
            self.db.commit()
            self.db.refresh(item)

            logger.info(f"Created inventory item: {item.name}")
            return item
        except IntegrityError as e:
            self.db.rollback()
            if "unique constraint" in str(e).lower():
                raise ValueError("SKU already exists")
            raise

    def update_item(self, item_id: int, item_data: InventoryItemUpdate, user_id: int) -> InventoryItem:
        """Update an existing inventory item"""
        item = self.db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
        if not item:
            raise ItemNotFoundException(item_id)

        update_data = item_data.model_dump(exclude_unset=True)

        # Validate category if being updated
        if 'category_id' in update_data and update_data['category_id'] is not None:
            category = self.db.query(InventoryCategory).filter(
                InventoryCategory.id == update_data['category_id'],
                InventoryCategory.is_active == True
            ).first()
            if not category:
                raise CategoryNotFoundException(update_data['category_id'])

        # Check for duplicate SKU if being updated
        if 'sku' in update_data and update_data['sku']:
            existing = self.db.query(InventoryItem).filter(
                InventoryItem.sku == update_data['sku'],
                InventoryItem.id != item_id,
                InventoryItem.is_active == True
            ).first()
            if existing:
                raise DuplicateSKUException(update_data['sku'])

        # Update item
        for field, value in update_data.items():
            setattr(item, field, value)

        try:
            self.db.commit()
            self.db.refresh(item)
            logger.info(f"Updated inventory item: {item.name}")
            return item
        except IntegrityError as e:
            self.db.rollback()
            if "unique constraint" in str(e).lower():
                raise DuplicateSKUException(update_data.get('sku', 'Unknown'))
            raise

    def delete_item(self, item_id: int, user_id: int) -> bool:
        """Delete an inventory item (only if not used in invoices or expenses)"""
        item = self.db.query(InventoryItem).filter(InventoryItem.id == item_id).first()
        if not item:
            raise ValueError("Item not found")

        # Check if item is used in invoices
        invoice_usage = self.db.query(func.count(InvoiceItem.id)).filter(
            InvoiceItem.inventory_item_id == item_id
        ).scalar()

        # Check if item is used in expenses
        expense_usage = self.db.query(func.count(Expense.id)).filter(
            func.json_extract(Expense.inventory_items, '$[*].item_id') == str(item_id)
        ).scalar()

        if invoice_usage > 0 or expense_usage > 0:
            raise ValueError("Cannot delete item that is used in invoices or expenses")

        self.db.delete(item)
        self.db.commit()
        logger.info(f"Deleted inventory item: {item.name}")
        return True

    def get_item(self, item_id: int) -> Optional[InventoryItem]:
        """Get a specific inventory item with category"""
        return self.db.query(InventoryItem).options(
            joinedload(InventoryItem.category)
        ).filter(InventoryItem.id == item_id).first()

    def get_items(self, filters: Optional[InventorySearchFilters] = None,
                  skip: int = 0, limit: int = 100) -> List[InventoryItem]:
        """Get inventory items with optional filtering"""
        query = self.db.query(InventoryItem).options(joinedload(InventoryItem.category))

        if filters:
            if filters.query:
                search_term = f"%{filters.query}%"
                query = query.filter(
                    or_(
                        InventoryItem.name.ilike(search_term),
                        InventoryItem.description.ilike(search_term),
                        InventoryItem.sku.ilike(search_term)
                    )
                )

            if filters.category_id:
                query = query.filter(InventoryItem.category_id == filters.category_id)

            if filters.item_type:
                query = query.filter(InventoryItem.item_type == filters.item_type)

            if filters.is_active is not None:
                query = query.filter(InventoryItem.is_active == filters.is_active)

            if filters.track_stock is not None:
                query = query.filter(InventoryItem.track_stock == filters.track_stock)

            if filters.low_stock_only:
                query = query.filter(
                    and_(
                        InventoryItem.track_stock == True,
                        InventoryItem.current_stock <= InventoryItem.minimum_stock
                    )
                )

            if filters.min_price:
                query = query.filter(InventoryItem.unit_price >= filters.min_price)

            if filters.max_price:
                query = query.filter(InventoryItem.unit_price <= filters.max_price)

        return query.order_by(InventoryItem.name).offset(skip).limit(limit).all()

    def search_items(self, query: str, limit: int = 50) -> List[InventoryItem]:
        """Search inventory items by name, description, or SKU"""
        search_term = f"%{query}%"
        return self.db.query(InventoryItem).options(joinedload(InventoryItem.category)).filter(
            or_(
                InventoryItem.name.ilike(search_term),
                InventoryItem.description.ilike(search_term),
                InventoryItem.sku.ilike(search_term)
            ),
            InventoryItem.is_active == True
        ).order_by(InventoryItem.name).limit(limit).all()

    def get_low_stock_items(self) -> List[InventoryItem]:
        """Get items with low stock levels"""
        return self.db.query(InventoryItem).options(joinedload(InventoryItem.category)).filter(
            InventoryItem.track_stock == True,
            InventoryItem.current_stock <= InventoryItem.minimum_stock,
            InventoryItem.is_active == True
        ).order_by(InventoryItem.current_stock).all()

    # === Analytics and Reporting ===

    def get_inventory_analytics(self) -> InventoryAnalytics:
        """Get basic inventory analytics"""
        total_items = self.db.query(func.count(InventoryItem.id)).scalar()
        active_items = self.db.query(func.count(InventoryItem.id)).filter(
            InventoryItem.is_active == True
        ).scalar()

        low_stock_items = self.db.query(func.count(InventoryItem.id)).filter(
            InventoryItem.track_stock == True,
            InventoryItem.current_stock <= InventoryItem.minimum_stock,
            InventoryItem.is_active == True
        ).scalar()

        # Calculate total inventory value
        total_value_result = self.db.query(
            func.sum(InventoryItem.current_stock * InventoryItem.unit_price)
        ).filter(
            InventoryItem.track_stock == True,
            InventoryItem.is_active == True
        ).scalar()

        total_value = total_value_result or 0.0

        return InventoryAnalytics(
            total_items=total_items,
            active_items=active_items,
            low_stock_items=low_stock_items,
            total_value=total_value,
            currency="USD"  # TODO: Get from tenant settings
        )

    def get_stock_movement_summary(self, item_id: Optional[int] = None,
                                  days: int = 30) -> List[StockMovementSummary]:
        """Get stock movement summary for items"""
        from_date = datetime.now(timezone.utc) - timedelta(days=days)

        query = self.db.query(
            InventoryItem.id,
            InventoryItem.name,
            func.count(StockMovement.id).label('total_movements'),
            func.sum(StockMovement.quantity).label('total_quantity_change'),
            func.max(StockMovement.movement_date).label('last_movement_date')
        ).join(StockMovement).filter(
            StockMovement.movement_date >= from_date
        )

        if item_id:
            query = query.filter(InventoryItem.id == item_id)

        query = query.group_by(InventoryItem.id, InventoryItem.name)
        query = query.order_by(desc('total_movements'))

        results = query.all()

        return [
            StockMovementSummary(
                item_id=row[0],
                item_name=row[1],
                total_movements=row[2],
                total_quantity_change=row[3] or 0.0,
                last_movement_date=row[4]
            )
            for row in results
        ]

    # === Utility Methods ===

    def get_inventory_value_report(self) -> Dict[str, Any]:
        """Generate detailed inventory value report"""
        items = self.db.query(InventoryItem).filter(
            InventoryItem.is_active == True
        ).all()

        total_inventory_value = 0.0
        total_cost_value = 0.0
        items_report = []

        for item in items:
            inventory_value = item.current_stock * item.unit_price if item.track_stock else 0.0
            cost_value = item.current_stock * (item.cost_price or 0.0) if item.track_stock else 0.0
            potential_profit = inventory_value - cost_value

            total_inventory_value += inventory_value
            total_cost_value += cost_value

            items_report.append({
                'id': item.id,
                'name': item.name,
                'sku': item.sku,
                'current_stock': item.current_stock,
                'unit_price': item.unit_price,
                'cost_price': item.cost_price,
                'inventory_value': inventory_value,
                'cost_value': cost_value,
                'potential_profit': potential_profit,
                'track_stock': item.track_stock
            })

        return {
            'total_inventory_value': total_inventory_value,
            'total_cost_value': total_cost_value,
            'potential_profit': total_inventory_value - total_cost_value,
            'currency': 'USD',  # TODO: Get from tenant settings
            'items': items_report
        }

    def get_profitability_analysis(self, start_date=None, end_date=None) -> Dict[str, Any]:
        """Generate detailed profitability analysis for inventory items"""
        from datetime import datetime, timezone, timedelta
        from sqlalchemy import func, and_, or_

        # Set default date range (last 30 days)
        if not end_date:
            end_date = datetime.now(timezone.utc)
        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Get sales data from invoices
        sales_query = self.db.query(
            InventoryItem.id.label('item_id'),
            InventoryItem.name.label('item_name'),
            InventoryItem.sku.label('sku'),
            func.sum(InvoiceItem.quantity).label('total_sold'),
            func.sum(InvoiceItem.amount).label('total_sales_revenue'),
            func.count(func.distinct(Invoice.id)).label('invoice_count')
        ).join(InvoiceItem, InventoryItem.id == InvoiceItem.inventory_item_id
        ).join(Invoice, InvoiceItem.invoice_id == Invoice.id
        ).filter(
            InventoryItem.is_active == True,
            Invoice.status.in_(['paid', 'completed']),
            Invoice.created_at.between(start_date, end_date)
        ).group_by(InventoryItem.id, InventoryItem.name, InventoryItem.sku)

        sales_data = {row.item_id: row for row in sales_query.all()}

        # Get purchase data from expenses
        purchase_query = self.db.query(
            func.json_extract(Expense.inventory_items, '$[*].item_id').label('item_ids'),
            func.json_extract(Expense.inventory_items, '$[*].quantity').label('quantities'),
            func.json_extract(Expense.inventory_items, '$[*].unit_cost').label('unit_costs'),
            Expense.expense_date
        ).filter(
            Expense.is_inventory_purchase == True,
            Expense.expense_date.between(start_date, end_date)
        )

        purchase_data = {}
        for row in purchase_query.all():
            if row.item_ids and row.quantities and row.unit_costs:
                for i, item_id in enumerate(row.item_ids):
                    if i < len(row.quantities) and i < len(row.unit_costs):
                        item_id_int = int(item_id)
                        quantity = float(row.quantities[i])
                        unit_cost = float(row.unit_costs[i])

                        if item_id_int not in purchase_data:
                            purchase_data[item_id_int] = {
                                'total_purchased': 0,
                                'total_cost': 0,
                                'purchase_count': 0
                            }

                        purchase_data[item_id_int]['total_purchased'] += quantity
                        purchase_data[item_id_int]['total_cost'] += quantity * unit_cost
                        purchase_data[item_id_int]['purchase_count'] += 1

        # Combine data for profitability analysis
        items = self.db.query(InventoryItem).filter(InventoryItem.is_active == True).all()
        profitability_report = []

        total_revenue = 0
        total_cost = 0
        total_profit = 0

        for item in items:
            sales_info = sales_data.get(item.id)
            purchase_info = purchase_data.get(item.id)

            revenue = sales_info.total_sales_revenue if sales_info else 0
            sold_quantity = sales_info.total_sold if sales_info else 0
            invoice_count = sales_info.invoice_count if sales_info else 0

            purchased_quantity = purchase_info['total_purchased'] if purchase_info else 0
            purchase_cost = purchase_info['total_cost'] if purchase_info else 0
            purchase_count = purchase_info['purchase_count'] if purchase_info else 0

            # Calculate cost of goods sold (COGS)
            avg_cost_per_unit = (item.cost_price or 0) if not purchase_info else (purchase_cost / purchased_quantity if purchased_quantity > 0 else 0)
            cogs = sold_quantity * avg_cost_per_unit
            gross_profit = revenue - cogs

            # Calculate profit margins
            gross_margin = (gross_profit / revenue * 100) if revenue > 0 else 0

            total_revenue += revenue
            total_cost += cogs
            total_profit += gross_profit

            profitability_report.append({
                'item_id': item.id,
                'item_name': item.name,
                'sku': item.sku,
                'category': item.category.name if item.category else None,
                'current_stock': item.current_stock,
                'avg_cost_per_unit': avg_cost_per_unit,
                'unit_price': item.unit_price,
                'sold_quantity': sold_quantity,
                'revenue': revenue,
                'cogs': cogs,
                'gross_profit': gross_profit,
                'gross_margin_percent': gross_margin,
                'invoice_count': invoice_count,
                'purchased_quantity': purchased_quantity,
                'purchase_cost': purchase_cost,
                'purchase_count': purchase_count
            })

        return {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'summary': {
                'total_revenue': total_revenue,
                'total_cost': total_cost,
                'total_profit': total_profit,
                'overall_margin_percent': (total_profit / total_revenue * 100) if total_revenue > 0 else 0
            },
            'items': sorted(profitability_report, key=lambda x: x['gross_profit'], reverse=True)
        }

    def get_inventory_turnover_analysis(self, months: int = 12) -> Dict[str, Any]:
        """Analyze inventory turnover rates"""
        from datetime import datetime, timezone, timedelta
        from sqlalchemy import func

        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=months * 30)

        # Get sales data by item
        sales_query = self.db.query(
            InventoryItem.id,
            InventoryItem.name,
            InventoryItem.sku,
            func.sum(InvoiceItem.quantity).label('total_sold'),
            func.avg(InventoryItem.cost_price).label('avg_cost')
        ).join(InvoiceItem, InventoryItem.id == InvoiceItem.inventory_item_id
        ).join(Invoice, InvoiceItem.invoice_id == Invoice.id
        ).filter(
            InventoryItem.track_stock == True,
            InventoryItem.is_active == True,
            Invoice.status.in_(['paid', 'completed']),
            Invoice.created_at.between(start_date, end_date)
        ).group_by(InventoryItem.id, InventoryItem.name, InventoryItem.sku, InventoryItem.cost_price)

        turnover_data = []
        total_inventory_value = 0
        total_cogs = 0

        for row in sales_query.all():
            item_id, name, sku, total_sold, avg_cost = row

            # Get current inventory value
            item = self.get_item(item_id)
            if item:
                inventory_value = item.current_stock * (item.cost_price or avg_cost or 0)
                total_inventory_value += inventory_value

                # Calculate COGS
                cogs = total_sold * (avg_cost or item.cost_price or 0)
                total_cogs += cogs

                # Calculate turnover ratios
                avg_inventory = inventory_value  # Simplified - using current value as average
                turnover_ratio = (cogs / avg_inventory) if avg_inventory > 0 else 0
                days_to_turnover = (months * 30) / turnover_ratio if turnover_ratio > 0 else 0

                turnover_data.append({
                    'item_id': item_id,
                    'item_name': name,
                    'sku': sku,
                    'current_stock': item.current_stock,
                    'inventory_value': inventory_value,
                    'total_sold': total_sold,
                    'cogs': cogs,
                    'turnover_ratio': turnover_ratio,
                    'days_to_turnover': days_to_turnover,
                    'turnover_category': self._categorize_turnover(turnover_ratio, months)
                })

        # Sort by turnover ratio (descending - faster turnover is better)
        turnover_data.sort(key=lambda x: x['turnover_ratio'], reverse=True)

        return {
            'analysis_period_months': months,
            'summary': {
                'total_inventory_value': total_inventory_value,
                'total_cogs': total_cogs,
                'overall_turnover_ratio': (total_cogs / total_inventory_value) if total_inventory_value > 0 else 0,
                'items_analyzed': len(turnover_data)
            },
            'turnover_categories': {
                'excellent': len([d for d in turnover_data if d['turnover_category'] == 'excellent']),
                'good': len([d for d in turnover_data if d['turnover_category'] == 'good']),
                'fair': len([d for d in turnover_data if d['turnover_category'] == 'fair']),
                'slow': len([d for d in turnover_data if d['turnover_category'] == 'slow']),
                'very_slow': len([d for d in turnover_data if d['turnover_category'] == 'very_slow'])
            },
            'items': turnover_data
        }

    def _categorize_turnover(self, ratio: float, months: int) -> str:
        """Categorize turnover ratio based on period"""
        # Annual turnover benchmarks (adjust based on period)
        annual_ratio = ratio * (12 / months)

        if annual_ratio >= 12:
            return 'excellent'
        elif annual_ratio >= 8:
            return 'good'
        elif annual_ratio >= 4:
            return 'fair'
        elif annual_ratio >= 2:
            return 'slow'
        else:
            return 'very_slow'

    def get_category_performance_report(self, start_date=None, end_date=None) -> Dict[str, Any]:
        """Generate performance report by inventory categories"""
        from datetime import datetime, timezone, timedelta

        # Set default date range
        if not end_date:
            end_date = datetime.now(timezone.utc)
        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Get sales by category
        category_sales = self.db.query(
            InventoryCategory.name.label('category_name'),
            func.count(func.distinct(InventoryItem.id)).label('items_count'),
            func.sum(InvoiceItem.quantity).label('total_sold'),
            func.sum(InvoiceItem.amount).label('total_revenue'),
            func.count(func.distinct(Invoice.id)).label('invoice_count')
        ).join(InventoryItem, InventoryCategory.id == InventoryItem.category_id
        ).join(InvoiceItem, InventoryItem.id == InvoiceItem.inventory_item_id
        ).join(Invoice, InvoiceItem.invoice_id == Invoice.id
        ).filter(
            InventoryCategory.is_active == True,
            InventoryItem.is_active == True,
            Invoice.status.in_(['paid', 'completed']),
            Invoice.created_at.between(start_date, end_date)
        ).group_by(InventoryCategory.id, InventoryCategory.name)

        # Get category inventory values
        category_inventory = self.db.query(
            InventoryCategory.name.label('category_name'),
            func.count(InventoryItem.id).label('total_items'),
            func.sum(InventoryItem.current_stock * InventoryItem.unit_price).label('inventory_value'),
            func.sum(InventoryItem.current_stock * func.coalesce(InventoryItem.cost_price, 0)).label('cost_value'),
            func.avg(InventoryItem.current_stock).label('avg_stock_level')
        ).join(InventoryItem, InventoryCategory.id == InventoryItem.category_id
        ).filter(
            InventoryCategory.is_active == True,
            InventoryItem.is_active == True,
            InventoryItem.track_stock == True
        ).group_by(InventoryCategory.id, InventoryCategory.name)

        # Combine data
        sales_dict = {row.category_name: row for row in category_sales.all()}
        inventory_dict = {row.category_name: row for row in category_inventory.all()}

        all_categories = set(sales_dict.keys()) | set(inventory_dict.keys())
        category_report = []

        for category_name in all_categories:
            sales = sales_dict.get(category_name)
            inventory = inventory_dict.get(category_name)

            revenue = sales.total_revenue if sales else 0
            inventory_value = inventory.inventory_value if inventory else 0
            cost_value = inventory.cost_value if inventory else 0

            category_report.append({
                'category_name': category_name,
                'items_count': sales.items_count if sales else (inventory.total_items if inventory else 0),
                'total_sold': sales.total_sold if sales else 0,
                'total_revenue': revenue,
                'inventory_value': inventory_value,
                'cost_value': cost_value,
                'potential_profit': inventory_value - cost_value,
                'avg_stock_level': inventory.avg_stock_level if inventory else 0,
                'invoice_count': sales.invoice_count if sales else 0,
                'revenue_per_item': revenue / (sales.items_count if sales and sales.items_count > 0 else 1)
            })

        # Sort by revenue (descending)
        category_report.sort(key=lambda x: x['total_revenue'], reverse=True)

        return {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            },
            'categories': category_report,
            'summary': {
                'total_categories': len(category_report),
                'total_revenue': sum(c['total_revenue'] for c in category_report),
                'total_inventory_value': sum(c['inventory_value'] for c in category_report)
            }
        }

    def get_low_stock_alerts(self, threshold_days: int = 30) -> Dict[str, Any]:
        """Generate low stock alerts based on sales velocity"""
        from datetime import datetime, timezone, timedelta

        # Calculate sales velocity for the last 30 days
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=30)

        velocity_query = self.db.query(
            InventoryItem.id,
            InventoryItem.name,
            InventoryItem.sku,
            InventoryItem.current_stock,
            InventoryItem.minimum_stock,
            func.sum(InvoiceItem.quantity).label('sold_last_30_days')
        ).join(InvoiceItem, InventoryItem.id == InvoiceItem.inventory_item_id
        ).join(Invoice, InvoiceItem.invoice_id == Invoice.id
        ).filter(
            InventoryItem.track_stock == True,
            InventoryItem.is_active == True,
            Invoice.status.in_(['paid', 'completed']),
            Invoice.created_at.between(start_date, end_date)
        ).group_by(InventoryItem.id, InventoryItem.name, InventoryItem.sku,
                  InventoryItem.current_stock, InventoryItem.minimum_stock)

        alerts = []
        for row in velocity_query.all():
            item_id, name, sku, current_stock, min_stock, sold_30_days = row

            # Calculate days until stock runs out
            daily_sales_rate = sold_30_days / 30 if sold_30_days > 0 else 0
            days_until_empty = current_stock / daily_sales_rate if daily_sales_rate > 0 else 999

            # Determine alert level
            if current_stock <= min_stock:
                alert_level = 'critical'
                message = f"Stock below minimum level ({current_stock} <= {min_stock})"
            elif days_until_empty <= threshold_days:
                alert_level = 'warning'
                message = f"Stock will run out in {days_until_empty:.1f} days at current sales rate"
            else:
                alert_level = 'normal'
                message = f"Stock level is adequate ({days_until_empty:.1f} days remaining)"

            alerts.append({
                'item_id': item_id,
                'item_name': name,
                'sku': sku,
                'current_stock': current_stock,
                'minimum_stock': min_stock,
                'sold_last_30_days': sold_30_days,
                'daily_sales_rate': daily_sales_rate,
                'days_until_empty': days_until_empty,
                'alert_level': alert_level,
                'message': message
            })

        # Sort by alert level priority
        priority_order = {'critical': 0, 'warning': 1, 'normal': 2}
        alerts.sort(key=lambda x: (priority_order[x['alert_level']], x['days_until_empty']))

        return {
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'threshold_days': threshold_days,
            'alerts': alerts,
            'summary': {
                'total_items': len(alerts),
                'critical_alerts': len([a for a in alerts if a['alert_level'] == 'critical']),
                'warning_alerts': len([a for a in alerts if a['alert_level'] == 'warning']),
                'normal_items': len([a for a in alerts if a['alert_level'] == 'normal'])
            }
        }

    def validate_stock_availability(self, item_id: int, requested_quantity: float) -> bool:
        """Validate if requested quantity is available in stock"""
        item = self.get_item(item_id)
        if not item or not item.track_stock:
            return True  # No stock tracking means always available

        return item.current_stock >= requested_quantity

    def get_item_by_barcode(self, barcode: str) -> Optional[InventoryItem]:
        """Get inventory item by barcode"""
        return self.db.query(InventoryItem).options(
            joinedload(InventoryItem.category)
        ).filter(
            InventoryItem.barcode == barcode,
            InventoryItem.is_active == True
        ).first()

    def update_item_barcode(self, item_id: int, barcode: str, barcode_type: Optional[str] = None, barcode_format: Optional[str] = None) -> InventoryItem:
        """Update barcode information for an inventory item"""
        item = self.get_item(item_id)
        if not item:
            raise ItemNotFoundException(item_id)

        # Check if barcode is already used by another item
        if barcode:
            existing = self.db.query(InventoryItem).filter(
                InventoryItem.barcode == barcode,
                InventoryItem.id != item_id,
                InventoryItem.is_active == True
            ).first()
            if existing:
                raise ValueError(f"Barcode {barcode} is already assigned to item: {existing.name}")

        # Update barcode fields
        item.barcode = barcode
        item.barcode_type = barcode_type
        item.barcode_format = barcode_format
        item.updated_at = datetime.now(timezone.utc)

        try:
            self.db.commit()
            self.db.refresh(item)
            logger.info(f"Updated barcode for item {item.name}: {barcode}")
            return item
        except IntegrityError as e:
            self.db.rollback()
            if "unique constraint" in str(e).lower():
                raise ValueError(f"Barcode {barcode} is already in use")
            raise

    def validate_barcode(self, barcode: str) -> Dict[str, Any]:
        """Validate barcode format and return barcode information"""
        if not barcode:
            return {"valid": False, "error": "Barcode cannot be empty"}

        # Remove any whitespace
        barcode = barcode.strip()

        # Basic length validation
        if len(barcode) < 3:
            return {"valid": False, "error": "Barcode too short"}

        if len(barcode) > 100:
            return {"valid": False, "error": "Barcode too long"}

        # Detect barcode type based on format
        barcode_info = self._detect_barcode_type(barcode)

        return {
            "valid": True,
            "barcode": barcode,
            "detected_type": barcode_info["type"],
            "detected_format": barcode_info["format"],
            "confidence": barcode_info["confidence"]
        }

    def _detect_barcode_type(self, barcode: str) -> Dict[str, Any]:
        """Detect barcode type and format based on content and length"""
        # UPC-A (12 digits)
        if len(barcode) == 12 and barcode.isdigit():
            return {"type": "UPC-A", "format": "1D", "confidence": 0.9}

        # UPC-E (6-8 digits, usually 8)
        if len(barcode) == 8 and barcode.isdigit() and barcode.startswith(('0', '1')):
            return {"type": "UPC-E", "format": "1D", "confidence": 0.8}

        # EAN-13 (13 digits)
        if len(barcode) == 13 and barcode.isdigit():
            return {"type": "EAN-13", "format": "1D", "confidence": 0.9}

        # EAN-8 (8 digits)
        if len(barcode) == 8 and barcode.isdigit():
            return {"type": "EAN-8", "format": "1D", "confidence": 0.8}

        # Code 128 (variable length, alphanumeric)
        if len(barcode) >= 3 and any(c.isalpha() for c in barcode):
            return {"type": "CODE128", "format": "1D", "confidence": 0.7}

        # QR Code detection (if it contains typical QR patterns)
        if len(barcode) > 20 and ('http' in barcode.lower() or barcode.count(':') > 1):
            return {"type": "QR", "format": "2D", "confidence": 0.6}

        # Default to generic
        return {"type": "UNKNOWN", "format": "1D", "confidence": 0.3}

    def generate_barcode_suggestions(self, item_name: str, sku: Optional[str] = None) -> List[str]:
        """Generate barcode suggestions based on item information"""
        suggestions = []

        # Use SKU as barcode if available and valid
        if sku and len(sku) >= 3:
            suggestions.append(sku)

        # Generate variations of item name
        if item_name:
            # Remove spaces and special characters
            clean_name = ''.join(c for c in item_name.upper() if c.isalnum())
            if len(clean_name) >= 3:
                suggestions.append(clean_name[:12])  # Limit length

        # Generate random codes
        import random
        import string

        # Numeric codes (like UPC/EAN)
        for length in [8, 12, 13]:
            numeric_code = ''.join(random.choices(string.digits, k=length))
            suggestions.append(numeric_code)

        # Alphanumeric codes (like Code 128)
        for length in [6, 8, 10]:
            alpha_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
            suggestions.append(alpha_code)

        # Remove duplicates and limit to 10 suggestions
        unique_suggestions = []
        seen = set()
        for suggestion in suggestions:
            if suggestion not in seen and len(suggestion) <= 50:
                unique_suggestions.append(suggestion)
                seen.add(suggestion)
            if len(unique_suggestions) >= 10:
                break

        return unique_suggestions

    def bulk_update_barcodes(self, barcode_updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Bulk update barcodes for multiple items"""
        successful_updates = []
        failed_updates = []

        for update in barcode_updates:
            try:
                item_id = update.get('item_id')
                barcode = update.get('barcode')
                barcode_type = update.get('barcode_type')
                barcode_format = update.get('barcode_format')

                if not item_id or not barcode:
                    failed_updates.append({
                        'item_id': item_id,
                        'error': 'Missing item_id or barcode'
                    })
                    continue

                updated_item = self.update_item_barcode(item_id, barcode, barcode_type, barcode_format)
                successful_updates.append({
                    'item_id': item_id,
                    'item_name': updated_item.name,
                    'barcode': barcode
                })

            except Exception as e:
                failed_updates.append({
                    'item_id': update.get('item_id'),
                    'error': str(e)
                })

        return {
            'successful_updates': successful_updates,
            'failed_updates': failed_updates,
            'total_processed': len(barcode_updates),
            'success_count': len(successful_updates),
            'failure_count': len(failed_updates)
        }

    def get_advanced_inventory_analytics(self, start_date=None, end_date=None) -> Dict[str, Any]:
        """Get advanced inventory analytics with trends and forecasting"""
        from datetime import datetime, timezone, timedelta
        from sqlalchemy import func, extract

        # Set default date range (last 90 days)
        if not end_date:
            end_date = datetime.now(timezone.utc)
        if not start_date:
            start_date = end_date - timedelta(days=90)

        # Get daily sales trends
        daily_sales = self.db.query(
            func.date(Invoice.created_at).label('date'),
            func.sum(InvoiceItem.quantity).label('total_quantity'),
            func.sum(InvoiceItem.amount).label('total_revenue'),
            func.count(func.distinct(Invoice.id)).label('invoice_count')
        ).join(InvoiceItem, Invoice.id == InvoiceItem.invoice_id
        ).join(InventoryItem, InvoiceItem.inventory_item_id == InventoryItem.id
        ).filter(
            Invoice.status.in_(['paid', 'completed']),
            Invoice.created_at.between(start_date, end_date),
            InventoryItem.is_active == True
        ).group_by(func.date(Invoice.created_at)
        ).order_by(func.date(Invoice.created_at)).all()

        # Get top performing items
        top_items = self.db.query(
            InventoryItem.id,
            InventoryItem.name,
            InventoryItem.sku,
            func.sum(InvoiceItem.quantity).label('total_sold'),
            func.sum(InvoiceItem.amount).label('total_revenue'),
            func.count(func.distinct(Invoice.id)).label('invoice_count'),
            func.avg(InvoiceItem.quantity).label('avg_order_quantity')
        ).join(InvoiceItem, InventoryItem.id == InvoiceItem.inventory_item_id
        ).join(Invoice, InvoiceItem.invoice_id == Invoice.id
        ).filter(
            Invoice.status.in_(['paid', 'completed']),
            Invoice.created_at.between(start_date, end_date),
            InventoryItem.is_active == True
        ).group_by(InventoryItem.id, InventoryItem.name, InventoryItem.sku
        ).order_by(func.sum(InvoiceItem.amount).desc()
        ).limit(20).all()

        # Get category performance
        category_performance = self.db.query(
            InventoryCategory.name.label('category'),
            func.count(func.distinct(InventoryItem.id)).label('item_count'),
            func.sum(InvoiceItem.quantity).label('total_sold'),
            func.sum(InvoiceItem.amount).label('total_revenue'),
            func.avg(InventoryItem.unit_price).label('avg_price')
        ).join(InventoryItem, InventoryCategory.id == InventoryItem.category_id
        ).join(InvoiceItem, InventoryItem.id == InvoiceItem.inventory_item_id
        ).join(Invoice, InvoiceItem.invoice_id == Invoice.id
        ).filter(
            InventoryCategory.is_active == True,
            InventoryItem.is_active == True,
            Invoice.status.in_(['paid', 'completed']),
            Invoice.created_at.between(start_date, end_date)
        ).group_by(InventoryCategory.id, InventoryCategory.name
        ).order_by(func.sum(InvoiceItem.amount).desc()).all()

        # Calculate trends and metrics
        daily_sales_list = [
            {
                'date': row[0].isoformat() if row[0] else None,
                'quantity': float(row[1] or 0),
                'revenue': float(row[2] or 0),
                'invoices': row[3] or 0
            }
            for row in daily_sales
        ]

        # Calculate growth rates
        if len(daily_sales_list) >= 2:
            recent_period = daily_sales_list[-30:]  # Last 30 days
            previous_period = daily_sales_list[-60:-30] if len(daily_sales_list) >= 60 else daily_sales_list[:-30]

            if recent_period and previous_period:
                recent_revenue = sum(d['revenue'] for d in recent_period)
                previous_revenue = sum(d['revenue'] for d in previous_period)
                revenue_growth = ((recent_revenue - previous_revenue) / previous_revenue * 100) if previous_revenue > 0 else 0
            else:
                revenue_growth = 0
        else:
            revenue_growth = 0

        return {
            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days': (end_date - start_date).days
            },
            'daily_sales_trends': daily_sales_list,
            'top_performing_items': [
                {
                    'id': row[0],
                    'name': row[1],
                    'sku': row[2],
                    'total_sold': float(row[3] or 0),
                    'total_revenue': float(row[4] or 0),
                    'invoice_count': row[5] or 0,
                    'avg_order_quantity': float(row[6] or 0)
                }
                for row in top_items
            ],
            'category_performance': [
                {
                    'category': row[0],
                    'item_count': row[1] or 0,
                    'total_sold': float(row[2] or 0),
                    'total_revenue': float(row[3] or 0),
                    'avg_price': float(row[4] or 0)
                }
                for row in category_performance
            ],
            'key_metrics': {
                'total_revenue': sum(d['revenue'] for d in daily_sales_list),
                'total_quantity_sold': sum(d['quantity'] for d in daily_sales_list),
                'total_invoices': sum(d['invoices'] for d in daily_sales_list),
                'avg_daily_revenue': sum(d['revenue'] for d in daily_sales_list) / max(len(daily_sales_list), 1),
                'avg_daily_quantity': sum(d['quantity'] for d in daily_sales_list) / max(len(daily_sales_list), 1),
                'revenue_growth_percent': revenue_growth,
                'best_performing_category': category_performance[0][0] if category_performance else None,
                'total_categories': len(category_performance),
                'total_items_sold': len(top_items)
            },
            'insights': self._generate_inventory_insights(daily_sales_list, top_items, category_performance)
        }

    def _generate_inventory_insights(self, daily_sales, top_items, category_performance):
        """Generate AI-powered insights from inventory data"""
        insights = []

        # Sales trend analysis
        if len(daily_sales) >= 7:
            recent_week = daily_sales[-7:]
            previous_week = daily_sales[-14:-7] if len(daily_sales) >= 14 else []

            if previous_week:
                recent_avg = sum(d['revenue'] for d in recent_week) / 7
                previous_avg = sum(d['revenue'] for d in previous_week) / 7

                if recent_avg > previous_avg * 1.2:
                    insights.append({
                        'type': 'positive',
                        'title': 'Sales Growth',
                        'description': 'Revenue increased by {:.1f}% compared to last week'.format(
                            (recent_avg - previous_avg) / previous_avg * 100
                        )
                    })
                elif recent_avg < previous_avg * 0.8:
                    insights.append({
                        'type': 'warning',
                        'title': 'Sales Decline',
                        'description': 'Revenue decreased by {:.1f}% compared to last week'.format(
                            (previous_avg - recent_avg) / previous_avg * 100
                        )
                    })

        # Top performer analysis
        if top_items:
            top_item = top_items[0]
            total_revenue = sum(item['total_revenue'] for item in top_items)
            top_percentage = (top_item['total_revenue'] / total_revenue * 100) if total_revenue > 0 else 0

            if top_percentage > 50:
                insights.append({
                    'type': 'info',
                    'title': 'Top Performer Dominance',
                    'description': f"{top_item['name']} accounts for {top_percentage:.1f}% of total revenue"
                })

        # Category concentration
        if category_performance:
            total_revenue = sum(cat['total_revenue'] for cat in category_performance)
            top_category = category_performance[0]
            concentration = (top_category['total_revenue'] / total_revenue * 100) if total_revenue > 0 else 0

            if concentration > 70:
                insights.append({
                    'type': 'warning',
                    'title': 'Category Concentration Risk',
                    'description': f"{top_category['category']} category represents {concentration:.1f}% of revenue - consider diversification"
                })

        # Low sales days detection
        if daily_sales:
            avg_revenue = sum(d['revenue'] for d in daily_sales) / len(daily_sales)
            low_sales_days = [d for d in daily_sales if d['revenue'] < avg_revenue * 0.5]

            if len(low_sales_days) > len(daily_sales) * 0.3:
                insights.append({
                    'type': 'warning',
                    'title': 'Inconsistent Sales',
                    'description': f"{len(low_sales_days)} out of {len(daily_sales)} days had below-average sales"
                })

        return insights

    def get_sales_velocity_analysis(self, days: int = 30) -> Dict[str, Any]:
        """Analyze sales velocity for inventory forecasting"""
        from datetime import datetime, timezone, timedelta
        from sqlalchemy import func

        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)

        # Get sales velocity data
        velocity_data = self.db.query(
            InventoryItem.id,
            InventoryItem.name,
            InventoryItem.sku,
            InventoryItem.current_stock,
            InventoryItem.minimum_stock,
            func.sum(InvoiceItem.quantity).label('total_sold'),
            func.count(func.distinct(Invoice.id)).label('invoice_count'),
            func.avg(InvoiceItem.quantity).label('avg_order_quantity'),
            func.max(Invoice.created_at).label('last_sale_date'),
            func.min(Invoice.created_at).label('first_sale_date')
        ).join(InvoiceItem, InventoryItem.id == InvoiceItem.inventory_item_id
        ).join(Invoice, InvoiceItem.invoice_id == Invoice.id
        ).filter(
            InventoryItem.is_active == True,
            InventoryItem.track_stock == True,
            Invoice.status.in_(['paid', 'completed']),
            Invoice.created_at.between(start_date, end_date)
        ).group_by(InventoryItem.id, InventoryItem.name, InventoryItem.sku,
                  InventoryItem.current_stock, InventoryItem.minimum_stock)

        results = []
        for row in velocity_data.all():
            item_id, name, sku, current_stock, min_stock, total_sold, invoice_count, avg_order_qty, last_sale, first_sale = row

            # Calculate velocity metrics
            period_days = (last_sale - first_sale).days if first_sale and last_sale else days
            daily_sales_rate = total_sold / period_days if period_days > 0 else 0
            weekly_sales_rate = daily_sales_rate * 7
            monthly_sales_rate = daily_sales_rate * 30

            # Stock coverage calculations
            days_stock_remaining = current_stock / daily_sales_rate if daily_sales_rate > 0 else None
            weeks_stock_remaining = current_stock / weekly_sales_rate if weekly_sales_rate > 0 else None

            # Forecast calculations
            days_since_last_sale = (end_date - last_sale).days if last_sale else None
            forecasted_demand_next_30 = daily_sales_rate * 30
            recommended_stock_level = daily_sales_rate * 45  # 45 days coverage recommended

            results.append({
                'item_id': item_id,
                'item_name': name,
                'sku': sku,
                'current_stock': current_stock,
                'minimum_stock': min_stock,
                'total_sold_period': total_sold,
                'invoice_count': invoice_count,
                'avg_order_quantity': avg_order_qty or 0,
                'daily_sales_rate': daily_sales_rate,
                'weekly_sales_rate': weekly_sales_rate,
                'monthly_sales_rate': monthly_sales_rate,
                'days_since_last_sale': days_since_last_sale,
                'days_stock_remaining': days_stock_remaining,
                'weeks_stock_remaining': weeks_stock_remaining,
                'forecasted_demand_next_30': forecasted_demand_next_30,
                'recommended_stock_level': recommended_stock_level,
                'stock_status': self._calculate_stock_status(current_stock, min_stock, days_stock_remaining),
                'last_sale_date': last_sale.isoformat() if last_sale else None,
                'first_sale_date': first_sale.isoformat() if first_sale else None
            })

        # Sort by sales velocity (descending)
        results.sort(key=lambda x: x['daily_sales_rate'], reverse=True)

        return {
            'analysis_period_days': days,
            'period_start': start_date.isoformat(),
            'period_end': end_date.isoformat(),
            'items': results,
            'summary': {
                'total_items': len(results),
                'high_velocity_items': len([r for r in results if r['daily_sales_rate'] > 1]),
                'low_velocity_items': len([r for r in results if r['daily_sales_rate'] < 0.1]),
                'out_of_stock_risk': len([r for r in results if r['days_stock_remaining'] and r['days_stock_remaining'] < 7]),
                'overstocked_items': len([r for r in results if r['current_stock'] > r['recommended_stock_level'] * 1.5]),
                'avg_daily_sales_rate': sum(r['daily_sales_rate'] for r in results) / max(len(results), 1),
                'total_forecasted_demand': sum(r['forecasted_demand_next_30'] for r in results)
            }
        }

    def _calculate_stock_status(self, current_stock, min_stock, days_remaining):
        """Calculate stock status based on multiple factors"""
        if current_stock <= min_stock:
            return 'critical'
        elif days_remaining and days_remaining < 7:
            return 'low'
        elif days_remaining and days_remaining < 14:
            return 'warning'
        elif current_stock > min_stock * 3:
            return 'overstocked'
        else:
            return 'optimal'

    def get_inventory_forecasting(self, forecast_days: int = 90) -> Dict[str, Any]:
        """Generate inventory forecasting based on historical data"""
        from datetime import datetime, timezone, timedelta
        from statistics import mean, stdev

        # Get historical sales data (last 6 months)
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=180)

        historical_data = self.db.query(
            func.date(Invoice.created_at).label('date'),
            func.sum(InvoiceItem.quantity).label('total_quantity'),
            InventoryItem.id.label('item_id'),
            InventoryItem.name.label('item_name')
        ).join(InvoiceItem, Invoice.id == InvoiceItem.invoice_id
        ).join(InventoryItem, InvoiceItem.inventory_item_id == InventoryItem.id
        ).filter(
            Invoice.status.in_(['paid', 'completed']),
            Invoice.created_at.between(start_date, end_date),
            InventoryItem.is_active == True,
            InventoryItem.track_stock == True
        ).group_by(func.date(Invoice.created_at), InventoryItem.id, InventoryItem.name
        ).order_by(InventoryItem.id, func.date(Invoice.created_at)).all()

        # Process data by item
        item_forecasts = {}
        for row in historical_data:
            date, quantity, item_id, item_name = row

            if item_id not in item_forecasts:
                item_forecasts[item_id] = {
                    'item_name': item_name,
                    'daily_sales': [],
                    'dates': []
                }

            item_forecasts[item_id]['daily_sales'].append(float(quantity))
            item_forecasts[item_id]['dates'].append(date)

        # Generate forecasts
        forecasts = []
        for item_id, data in item_forecasts.items():
            if len(data['daily_sales']) < 30:  # Need at least 30 days of data
                continue

            # Calculate moving averages and trends
            sales_data = data['daily_sales']

            # Simple exponential smoothing forecast
            alpha = 0.3  # Smoothing factor
            forecast = []

            # Start with the last actual value
            last_value = sales_data[-1]
            forecast.append(last_value)

            # Generate forecast
            for _ in range(forecast_days):
                last_value = alpha * last_value + (1 - alpha) * mean(sales_data[-7:])  # Blend with recent average
                forecast.append(last_value)

            # Calculate forecast accuracy metrics
            if len(sales_data) >= 14:
                recent_actual = sales_data[-7:]
                recent_forecast_baseline = [mean(sales_data[-14:-7])] * 7

                # Calculate MAPE (Mean Absolute Percentage Error) for baseline
                mape = mean([
                    abs((actual - predicted) / actual * 100) if actual > 0 else 0
                    for actual, predicted in zip(recent_actual, recent_forecast_baseline)
                ])

                confidence_level = max(0, 100 - mape)  # Higher MAPE = lower confidence
            else:
                confidence_level = 50  # Default confidence for limited data

            forecasts.append({
                'item_id': item_id,
                'item_name': data['item_name'],
                'historical_days': len(sales_data),
                'avg_daily_sales': mean(sales_data),
                'sales_volatility': stdev(sales_data) if len(sales_data) > 1 else 0,
                'forecast_daily': forecast,
                'forecast_total': sum(forecast),
                'forecast_confidence_percent': confidence_level,
                'trend_direction': 'increasing' if forecast[-1] > forecast[0] else 'decreasing' if forecast[-1] < forecast[0] else 'stable',
                'seasonality_detected': self._detect_seasonality(sales_data)
            })

        # Sort by forecast confidence and total forecast
        forecasts.sort(key=lambda x: (x['forecast_confidence_percent'], x['forecast_total']), reverse=True)

        return {
            'forecast_period_days': forecast_days,
            'forecast_generated_at': datetime.now(timezone.utc).isoformat(),
            'historical_period_days': 180,
            'forecasts': forecasts,
            'summary': {
                'total_items_forecasted': len(forecasts),
                'high_confidence_forecasts': len([f for f in forecasts if f['forecast_confidence_percent'] > 80]),
                'total_forecasted_demand': sum(f['forecast_total'] for f in forecasts),
                'increasing_trend_items': len([f for f in forecasts if f['trend_direction'] == 'increasing']),
                'seasonal_items': len([f for f in forecasts if f['seasonality_detected']])
            }
        }

    def _detect_seasonality(self, sales_data):
        """Simple seasonality detection based on weekly patterns"""
        if len(sales_data) < 14:  # Need at least 2 weeks
            return False

        # Compare weekday patterns (simplified)
        weekdays = sales_data[::7]  # Every 7th day
        weekends = sales_data[1::7] if len(sales_data) > 1 else []

        if weekdays and weekends:
            weekday_avg = mean(weekdays)
            weekend_avg = mean(weekends)

            # If weekend sales are significantly different (>20%), consider seasonal
            return abs(weekend_avg - weekday_avg) / max(weekday_avg, weekend_avg) > 0.2

        return False

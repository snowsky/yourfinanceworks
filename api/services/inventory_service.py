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

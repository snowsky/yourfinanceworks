from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc, func, and_
from datetime import datetime, timezone, timedelta
import logging

from core.models.models_per_tenant import (
    InventoryItem, StockMovement, User,
    Invoice, InvoiceItem, Expense
)
from core.schemas.inventory import StockMovementCreate, StockMovementUpdate

logger = logging.getLogger(__name__)


class StockMovementService:
    """Service class for handling stock movement operations and audit trails"""

    def __init__(self, db: Session):
        self.db = db

    def record_movement(self, movement_data: StockMovementCreate) -> StockMovement:
        """Record a new stock movement"""
        try:
            # Validate item exists
            item = self.db.query(InventoryItem).filter(InventoryItem.id == movement_data.item_id).first()
            if not item:
                raise ValueError("Inventory item not found")

            # Allow stock movements for items linked to invoices, even if they don't normally track stock
            # This enables automatic stock reduction when invoices are paid, as per documentation
            if not item.track_stock:
                # Check if this movement is related to an invoice
                if movement_data.reference_type == "invoice" and movement_data.reference_id:
                    logger.info(f"Allowing stock movement for item {item.name} (ID: {item.id}) "
                               f"that doesn't track stock, because it's linked to invoice {movement_data.reference_id}")
                else:
                    raise ValueError("Item does not track stock")

            # Create movement record
            movement = StockMovement(**movement_data.model_dump())
            self.db.add(movement)

            # Update item stock level
            item.current_stock += movement.quantity

            # Prevent negative stock if it's a reduction
            if movement.quantity < 0 and item.current_stock < 0:
                self.db.rollback()
                raise ValueError(f"Insufficient stock. Current: {item.current_stock - movement.quantity}, Requested: {abs(movement.quantity)}")

            self.db.commit()
            self.db.refresh(movement)
            self.db.refresh(item)

            logger.info(f"Recorded stock movement: {movement.movement_type} {movement.quantity} for item {item.name} "
                       f"(ID: {item.id}). New stock level: {item.current_stock}")
            return movement

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error recording stock movement: {e}")
            raise

    def record_manual_adjustment(self, item_id: int, quantity: float,
                               reason: str, user_id: int) -> StockMovement:
        """Record a manual stock adjustment"""
        movement_data = StockMovementCreate(
            item_id=item_id,
            movement_type="adjustment",
            quantity=quantity,
            reference_type="manual",
            notes=reason,
            user_id=user_id
        )
        return self.record_movement(movement_data)

    def process_invoice_sale(self, invoice: Invoice) -> List[StockMovement]:
        """Process stock reductions for invoice items"""
        movements = []

        for item in invoice.items:
            if item.inventory_item_id and item.quantity > 0:
                try:
                    movement = self.record_movement(StockMovementCreate(
                        item_id=item.inventory_item_id,
                        movement_type="sale",
                        quantity=-item.quantity,  # Negative for reduction
                        reference_type="invoice",
                        reference_id=invoice.id,
                        notes=f"Sale from invoice #{invoice.number}",
                        user_id=getattr(invoice, 'user_id', None) or 1  # Fallback to system user
                    ))
                    movements.append(movement)
                except ValueError as e:
                    logger.error(f"Failed to process stock for invoice item {item.id}: {e}")
                    # Continue processing other items
                    continue

        return movements

    def process_expense_purchase(self, expense: Expense) -> List[StockMovement]:
        """Process stock increases for inventory purchase expenses"""
        movements = []

        if not expense.is_inventory_purchase or not expense.inventory_items:
            return movements

        for purchase_item in expense.inventory_items:
            try:
                item_id = purchase_item.get('item_id')
                quantity = purchase_item.get('quantity', 0)
                unit_cost = purchase_item.get('unit_cost', 0)

                if not item_id or quantity <= 0:
                    continue

                movement = self.record_movement(StockMovementCreate(
                    item_id=item_id,
                    movement_type="purchase",
                    quantity=quantity,
                    unit_cost=unit_cost,
                    reference_type="expense",
                    reference_id=expense.id,
                    notes=f"Purchase from expense #{expense.id}",
                    user_id=expense.user_id or 1
                ))
                movements.append(movement)

            except ValueError as e:
                logger.error(f"Failed to process stock for expense purchase item {purchase_item}: {e}")
                continue

        return movements

    def process_expense_consumption(self, expense: Expense) -> List[StockMovement]:
        """Process stock reductions for inventory consumption expenses"""
        movements = []

        if not expense.is_inventory_consumption or not expense.consumption_items:
            return movements

        for consumption_item in expense.consumption_items:
            try:
                item_id = consumption_item.get('item_id')
                quantity = consumption_item.get('quantity', 0)
                unit_cost = consumption_item.get('unit_cost')

                if not item_id or quantity <= 0:
                    continue

                movement = self.record_movement(StockMovementCreate(
                    item_id=item_id,
                    movement_type="usage",
                    quantity=-quantity,  # Negative for reduction
                    unit_cost=unit_cost,
                    reference_type="expense",
                    reference_id=expense.id,
                    notes=f"Consumption from expense #{expense.id}",
                    user_id=expense.user_id or 1
                ))
                movements.append(movement)

            except ValueError as e:
                logger.error(f"Failed to process stock for expense consumption item {consumption_item}: {e}")
                continue

        return movements

    def reverse_invoice_stock_impact(self, invoice: Invoice) -> List[StockMovement]:
        """Reverse stock impacts when invoice is cancelled or deleted"""
        movements = []

        for item in invoice.items:
            if item.inventory_item_id and item.quantity > 0:
                try:
                    # Create reverse movement (positive quantity to restore stock)
                    movement = self.record_movement(StockMovementCreate(
                        item_id=item.inventory_item_id,
                        movement_type="return",
                        quantity=item.quantity,  # Positive to restore stock
                        reference_type="invoice",
                        reference_id=invoice.id,
                        notes=f"Reversal of sale from cancelled invoice #{invoice.number}",
                        user_id=getattr(invoice, 'user_id', None) or 1
                    ))
                    movements.append(movement)
                except ValueError as e:
                    logger.error(f"Failed to reverse stock for invoice item {item.id}: {e}")
                    continue

        return movements

    def reverse_expense_stock_impact(self, expense: Expense) -> List[StockMovement]:
        """Reverse stock impacts when expense is cancelled or deleted"""
        movements = []

        if not expense.is_inventory_purchase or not expense.inventory_items:
            return movements

        for purchase_item in expense.inventory_items:
            try:
                item_id = purchase_item.get('item_id')
                quantity = purchase_item.get('quantity', 0)

                if not item_id or quantity <= 0:
                    continue

                movement = self.record_movement(StockMovementCreate(
                    item_id=item_id,
                    movement_type="adjustment",
                    quantity=-quantity,  # Negative to reduce stock
                    reference_type="expense",
                    reference_id=expense.id,
                    notes=f"Reversal of purchase from cancelled expense #{expense.id}",
                    user_id=expense.user_id or 1
                ))
                movements.append(movement)

            except ValueError as e:
                logger.error(f"Failed to reverse stock for expense purchase item {purchase_item}: {e}")
                continue

        return movements

    def get_movement_history(self, item_id: int, limit: int = 100,
                           movement_type: Optional[str] = None) -> List[StockMovement]:
        """Get movement history for an item"""
        query = self.db.query(StockMovement).options(
            joinedload(StockMovement.user)
        ).filter(StockMovement.item_id == item_id)

        if movement_type:
            query = query.filter(StockMovement.movement_type == movement_type)

        return query.order_by(desc(StockMovement.movement_date)).limit(limit).all()

    def get_movements_by_reference(self, reference_type: str, reference_id: int) -> List[StockMovement]:
        """Get movements by reference (invoice, expense, etc.)"""
        return self.db.query(StockMovement).options(
            joinedload(StockMovement.item),
            joinedload(StockMovement.user)
        ).filter(
            StockMovement.reference_type == reference_type,
            StockMovement.reference_id == reference_id
        ).order_by(StockMovement.movement_date).all()

    def get_recent_movements(self, days: int = 7, limit: int = 50) -> List[StockMovement]:
        """Get recent stock movements across all items"""
        from_date = datetime.now(timezone.utc) - timedelta(days=days)

        return self.db.query(StockMovement).options(
            joinedload(StockMovement.item),
            joinedload(StockMovement.user)
        ).filter(
            StockMovement.movement_date >= from_date
        ).order_by(desc(StockMovement.movement_date)).limit(limit).all()

    def get_stock_summary(self, item_id: Optional[int] = None,
                         from_date: Optional[datetime] = None,
                         to_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get stock summary with movement totals"""
        query = self.db.query(
            InventoryItem.id,
            InventoryItem.name,
            InventoryItem.sku,
            InventoryItem.current_stock,
            func.sum(StockMovement.quantity).label('total_movement'),
            func.count(StockMovement.id).label('movement_count'),
            func.min(StockMovement.movement_date).label('first_movement'),
            func.max(StockMovement.movement_date).label('last_movement')
        ).join(StockMovement)

        if item_id:
            query = query.filter(InventoryItem.id == item_id)

        if from_date:
            query = query.filter(StockMovement.movement_date >= from_date)

        if to_date:
            query = query.filter(StockMovement.movement_date <= to_date)

        query = query.group_by(
            InventoryItem.id, InventoryItem.name, InventoryItem.sku, InventoryItem.current_stock
        ).order_by(InventoryItem.name)

        results = query.all()

        return [
            {
                'item_id': row[0],
                'item_name': row[1],
                'sku': row[2],
                'current_stock': row[3],
                'total_movement': row[4] or 0.0,
                'movement_count': row[5],
                'first_movement': row[6],
                'last_movement': row[7]
            }
            for row in results
        ]

    def get_movement_summary_by_type(self, item_id: int, days: int = 30) -> Dict[str, Any]:
        """Get movement summary grouped by type for an item"""
        from_date = datetime.now(timezone.utc) - timedelta(days=days)

        query = self.db.query(
            StockMovement.movement_type,
            func.sum(StockMovement.quantity).label('total_quantity'),
            func.count(StockMovement.id).label('count')
        ).filter(
            StockMovement.item_id == item_id,
            StockMovement.movement_date >= from_date
        ).group_by(StockMovement.movement_type)

        results = query.all()

        summary = {}
        for row in results:
            summary[row[0]] = {
                'total_quantity': row[1] or 0.0,
                'count': row[2]
            }

        return summary

    def validate_stock_operation(self, item_id: int, requested_quantity: float,
                               operation: str) -> Dict[str, Any]:
        """Validate if a stock operation is possible"""
        item = self.db.query(InventoryItem).filter(InventoryItem.id == item_id).first()

        if not item:
            return {
                'valid': False,
                'reason': 'Item not found',
                'current_stock': 0,
                'available': 0
            }

        if not item.track_stock:
            return {
                'valid': True,
                'reason': 'Stock not tracked',
                'current_stock': item.current_stock,
                'available': float('inf')
            }

        if operation in ['sale', 'usage'] and requested_quantity > item.current_stock:
            return {
                'valid': False,
                'reason': f'Insufficient stock. Requested: {requested_quantity}, Available: {item.current_stock}',
                'current_stock': item.current_stock,
                'available': item.current_stock
            }

        return {
            'valid': True,
            'reason': 'Operation valid',
            'current_stock': item.current_stock,
            'available': item.current_stock if operation in ['sale', 'usage'] else float('inf')
        }

    def get_audit_trail(self, item_id: int, from_date: Optional[datetime] = None,
                       to_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Get detailed audit trail for an item"""
        query = self.db.query(
            StockMovement,
            InventoryItem.current_stock.label('current_stock_after_movement')
        ).join(InventoryItem).filter(StockMovement.item_id == item_id)

        if from_date:
            query = query.filter(StockMovement.movement_date >= from_date)

        if to_date:
            query = query.filter(StockMovement.movement_date <= to_date)

        movements = query.order_by(StockMovement.movement_date).all()

        audit_trail = []
        running_total = 0.0

        for movement, current_stock in movements:
            running_total += movement.quantity

            audit_trail.append({
                'id': movement.id,
                'movement_type': movement.movement_type,
                'quantity': movement.quantity,
                'running_total': running_total,
                'current_stock': current_stock,
                'unit_cost': movement.unit_cost,
                'reference_type': movement.reference_type,
                'reference_id': movement.reference_id,
                'notes': movement.notes,
                'user_id': movement.user_id,
                'movement_date': movement.movement_date,
                'created_at': movement.created_at
            })

        return audit_trail

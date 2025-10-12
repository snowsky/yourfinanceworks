from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, joinedload
from datetime import datetime, timezone
import logging

from models.models_per_tenant import (
    InventoryItem, StockMovement, Invoice, InvoiceItem, Expense,
    User
)
from schemas.inventory import (
    InventoryItem as InventoryItemSchema,
    StockMovementCreate
)
from services.inventory_service import InventoryService
from services.stock_movement_service import StockMovementService
from exceptions.inventory_exceptions import (
    InsufficientStockException, ItemNotFoundException,
    InventoryException
)

logger = logging.getLogger(__name__)


class InventoryIntegrationService:
    """Service for integrating inventory management with invoices and expenses"""

    def __init__(self, db: Session):
        self.db = db
        self.inventory_service = InventoryService(db)
        self.stock_service = StockMovementService(db)

    def populate_invoice_item_from_inventory(
        self,
        inventory_item_id: int,
        quantity: float = 1.0
    ) -> Dict[str, Any]:
        """
        Populate invoice item data from inventory item
        Returns dictionary with item details for invoice creation
        """
        try:
            inventory_item = self.inventory_service.get_item(inventory_item_id)
            if not inventory_item:
                raise ItemNotFoundException(inventory_item_id)

            # Check stock availability if tracking is enabled
            if inventory_item.track_stock:
                available = self.inventory_service.validate_stock_availability(
                    inventory_item_id, quantity
                )
                if not available:
                    raise InsufficientStockException(
                        inventory_item_id, quantity, inventory_item.current_stock
                    )

            return {
                "inventory_item_id": inventory_item.id,
                "description": inventory_item.name,
                "quantity": quantity,
                "price": inventory_item.unit_price,
                "amount": quantity * inventory_item.unit_price,
                "unit_of_measure": inventory_item.unit_of_measure,
                "inventory_item": inventory_item  # Include full item for reference
            }

        except InventoryException:
            raise
        except Exception as e:
            logger.error(f"Error populating invoice item from inventory {inventory_item_id}: {e}")
            raise InventoryException(
                f"Failed to populate invoice item from inventory",
                "POPULATION_ERROR",
                {"inventory_item_id": inventory_item_id, "error": str(e)}
            )

    def validate_invoice_stock_availability(self, invoice_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Validate stock availability for all invoice items
        Returns list of validation results
        """
        validation_results = []

        for item_data in invoice_items:
            inventory_item_id = item_data.get("inventory_item_id")
            quantity = item_data.get("quantity", 0)

            if inventory_item_id and quantity > 0:
                try:
                    inventory_item = self.inventory_service.get_item(inventory_item_id)
                    if inventory_item and inventory_item.track_stock:
                        available = self.inventory_service.validate_stock_availability(
                            inventory_item_id, quantity
                        )
                        validation_results.append({
                            "inventory_item_id": inventory_item_id,
                            "item_name": inventory_item.name,
                            "requested_quantity": quantity,
                            "current_stock": inventory_item.current_stock,
                            "available": available,
                            "sufficient": inventory_item.current_stock >= quantity
                        })
                    else:
                        validation_results.append({
                            "inventory_item_id": inventory_item_id,
                            "item_name": inventory_item.name if inventory_item else "Unknown",
                            "requested_quantity": quantity,
                            "current_stock": None,
                            "available": True,
                            "sufficient": True
                        })
                except Exception as e:
                    validation_results.append({
                        "inventory_item_id": inventory_item_id,
                        "item_name": "Error",
                        "requested_quantity": quantity,
                        "current_stock": None,
                        "available": False,
                        "sufficient": False,
                        "error": str(e)
                    })

        return validation_results

    def process_invoice_stock_movements(self, invoice: Invoice, user_id: int) -> List[StockMovement]:
        """
        Process stock movements when invoice is completed/paid
        Only processes items that have inventory_item_id set
        """
        movements = []

        try:
            # Only process stock movements for completed/paid invoices
            if invoice.status not in ['paid', 'completed']:
                logger.info(f"Invoice {invoice.id} not in payable status ({invoice.status}), skipping stock movements")
                return movements

            # Get invoice items with inventory information
            invoice_items = self.db.query(InvoiceItem).options(
                joinedload(InvoiceItem.inventory_item)
            ).filter(
                InvoiceItem.invoice_id == invoice.id,
                InvoiceItem.inventory_item_id.isnot(None)
            ).all()

            logger.info(f"Processing {len(invoice_items)} inventory items for invoice {invoice.id}")

            for invoice_item in invoice_items:
                if not invoice_item.inventory_item:
                    continue

                inventory_item = invoice_item.inventory_item

                # Note: We process stock movements for all inventory-linked items,
                # regardless of track_stock setting, as per documentation that states
                # "Automatic stock reduction when invoices are paid"
                if not inventory_item.track_stock:
                    logger.info(f"Processing stock movement for item {inventory_item.name} (ID: {inventory_item.id}) "
                               f"even though track_stock=False, as it's linked to invoice {invoice.id}")
                else:
                    logger.info(f"Processing stock movement for item {inventory_item.name} (ID: {inventory_item.id}) "
                               f"with track_stock=True for invoice {invoice.id}")

                try:
                    # Create stock movement for sale (negative quantity)
                    movement = self.stock_service.record_movement(StockMovementCreate(
                        item_id=inventory_item.id,
                        movement_type="sale",
                        quantity=-invoice_item.quantity,  # Negative for reduction
                        reference_type="invoice",
                        reference_id=invoice.id,
                        notes=f"Sale from invoice #{invoice.number}",
                        user_id=user_id
                    ))
                    movements.append(movement)
                    logger.info(f"Processed stock movement for item {inventory_item.name}: -{invoice_item.quantity}")

                except InsufficientStockException as e:
                    logger.warning(f"Insufficient stock for invoice item {invoice_item.id}: {e.message}")
                    # Continue processing other items - don't fail the whole invoice
                    continue
                except Exception as e:
                    logger.error(f"Error processing stock movement for invoice item {invoice_item.id}: {e}")
                    continue

            logger.info(f"Successfully processed {len(movements)} stock movements for invoice {invoice.id}")
            return movements

        except Exception as e:
            logger.error(f"Error processing invoice stock movements for invoice {invoice.id}: {e}")
            raise InventoryException(
                f"Failed to process stock movements for invoice",
                "STOCK_PROCESSING_ERROR",
                {"invoice_id": invoice.id, "error": str(e)}
            )

    def reverse_invoice_stock_movements(self, invoice: Invoice, user_id: int) -> List[StockMovement]:
        """
        Reverse stock movements when invoice is cancelled or refunded
        """
        movements = []

        try:
            # Get all stock movements for this invoice
            stock_movements = self.stock_service.get_movements_by_reference("invoice", invoice.id)

            for movement in stock_movements:
                try:
                    # Create reverse movement (opposite quantity)
                    reverse_movement = self.stock_service.record_movement(StockMovementCreate(
                        item_id=movement.item_id,
                        movement_type="adjustment",  # Use adjustment for reversals
                        quantity=-movement.quantity,  # Opposite of original movement
                        reference_type="invoice",
                        reference_id=invoice.id,
                        notes=f"Reversal of sale from cancelled invoice #{invoice.number}",
                        user_id=user_id
                    ))
                    movements.append(reverse_movement)
                    logger.info(f"Reversed stock movement for item {movement.item_id}: {reverse_movement.quantity}")

                except Exception as e:
                    logger.error(f"Error reversing stock movement {movement.id}: {e}")
                    continue

            logger.info(f"Successfully reversed {len(movements)} stock movements for invoice {invoice.id}")
            return movements

        except Exception as e:
            logger.error(f"Error reversing invoice stock movements for invoice {invoice.id}: {e}")
            raise InventoryException(
                f"Failed to reverse stock movements for invoice",
                "STOCK_REVERSAL_ERROR",
                {"invoice_id": invoice.id, "error": str(e)}
            )

    def process_expense_inventory_purchase(self, expense: Expense, user_id: int) -> List[StockMovement]:
        """
        Process stock increases for inventory purchase expenses
        """
        movements = []

        try:
            if not expense.is_inventory_purchase or not expense.inventory_items:
                return movements

            logger.info(f"Processing inventory purchase for expense {expense.id}")

            for purchase_item in expense.inventory_items:
                try:
                    item_id = purchase_item.get('item_id')
                    quantity = purchase_item.get('quantity', 0)

                    if not item_id or quantity <= 0:
                        continue

                    # Verify item exists
                    inventory_item = self.inventory_service.get_item(item_id)
                    if not inventory_item:
                        logger.warning(f"Inventory item {item_id} not found for expense purchase")
                        continue

                    # Create stock movement for purchase (positive quantity)
                    movement = self.stock_service.record_movement(StockMovementCreate(
                        item_id=item_id,
                        movement_type="purchase",
                        quantity=quantity,
                        unit_cost=purchase_item.get('unit_cost', 0),
                        reference_type="expense",
                        reference_id=expense.id,
                        notes=f"Purchase from expense #{expense.id}",
                        user_id=user_id
                    ))
                    movements.append(movement)
                    logger.info(f"Processed purchase stock movement for item {inventory_item.name}: +{quantity}")

                except Exception as e:
                    logger.error(f"Error processing purchase item {purchase_item}: {e}")
                    continue

            logger.info(f"Successfully processed {len(movements)} purchase movements for expense {expense.id}")
            return movements

        except Exception as e:
            logger.error(f"Error processing expense inventory purchase for expense {expense.id}: {e}")
            raise InventoryException(
                f"Failed to process inventory purchase for expense",
                "PURCHASE_PROCESSING_ERROR",
                {"expense_id": expense.id, "error": str(e)}
            )

    def process_expense_inventory_consumption(self, expense: Expense, user_id: int) -> List[StockMovement]:
        """
        Process stock decreases for inventory consumption expenses
        """
        movements = []

        try:
            if not expense.is_inventory_consumption or not expense.consumption_items:
                return movements

            logger.info(f"Processing inventory consumption for expense {expense.id}")

            for consumption_item in expense.consumption_items:
                try:
                    item_id = consumption_item.get('item_id')
                    quantity = consumption_item.get('quantity', 0)

                    if not item_id or quantity <= 0:
                        continue

                    # Verify item exists
                    inventory_item = self.inventory_service.get_item(item_id)
                    if not inventory_item:
                        logger.warning(f"Inventory item {item_id} not found for expense consumption")
                        continue

                    # Create stock movement for consumption (negative quantity)
                    movement = self.stock_service.record_movement(StockMovementCreate(
                        item_id=item_id,
                        movement_type="usage",
                        quantity=-quantity,  # Negative for reduction
                        unit_cost=consumption_item.get('unit_cost', inventory_item.cost_price),
                        reference_type="expense",
                        reference_id=expense.id,
                        notes=f"Consumption from expense #{expense.id}",
                        user_id=user_id
                    ))
                    movements.append(movement)
                    logger.info(f"Processed consumption stock movement for item {inventory_item.name}: -{quantity}")

                except Exception as e:
                    logger.error(f"Error processing consumption item {consumption_item}: {e}")
                    continue

            logger.info(f"Successfully processed {len(movements)} consumption movements for expense {expense.id}")
            return movements

        except Exception as e:
            logger.error(f"Error processing expense inventory consumption for expense {expense.id}: {e}")
            raise InventoryException(
                f"Failed to process inventory consumption for expense",
                "CONSUMPTION_PROCESSING_ERROR",
                {"expense_id": expense.id, "error": str(e)}
            )

    def get_invoice_inventory_summary(self, invoice_id: int) -> Dict[str, Any]:
        """
        Get inventory summary for an invoice
        """
        try:
            # Get invoice items with inventory information
            invoice_items = self.db.query(InvoiceItem).options(
                joinedload(InvoiceItem.inventory_item)
            ).filter(InvoiceItem.invoice_id == invoice_id).all()

            inventory_items = []
            total_inventory_value = 0.0

            for item in invoice_items:
                if item.inventory_item:
                    inventory_item = item.inventory_item
                    item_value = item.quantity * item.price
                    total_inventory_value += item_value

                    inventory_items.append({
                        "invoice_item_id": item.id,
                        "inventory_item_id": inventory_item.id,
                        "item_name": inventory_item.name,
                        "sku": inventory_item.sku,
                        "quantity": item.quantity,
                        "unit_price": item.price,
                        "line_total": item_value,
                        "current_stock": inventory_item.current_stock if inventory_item.track_stock else None,
                        "tracks_stock": inventory_item.track_stock
                    })

            return {
                "invoice_id": invoice_id,
                "inventory_items": inventory_items,
                "total_inventory_items": len(inventory_items),
                "total_inventory_value": total_inventory_value
            }

        except Exception as e:
            logger.error(f"Error getting invoice inventory summary for invoice {invoice_id}: {e}")
            return {
                "invoice_id": invoice_id,
                "inventory_items": [],
                "total_inventory_items": 0,
                "total_inventory_value": 0.0,
                "error": str(e)
            }

    def update_invoice_item_inventory_reference(
        self,
        invoice_item_id: int,
        inventory_item_id: Optional[int],
        user_id: int
    ) -> bool:
        """
        Update the inventory item reference for an invoice item
        """
        try:
            invoice_item = self.db.query(InvoiceItem).filter(InvoiceItem.id == invoice_item_id).first()
            if not invoice_item:
                raise ValueError(f"Invoice item {invoice_item_id} not found")

            # If setting inventory reference, validate the item exists
            if inventory_item_id:
                inventory_item = self.inventory_service.get_item(inventory_item_id)
                if not inventory_item:
                    raise ItemNotFoundException(inventory_item_id)

                # Update description and price from inventory if not already set
                if not invoice_item.description or invoice_item.description == "":
                    invoice_item.description = inventory_item.name
                if invoice_item.price == 0:
                    invoice_item.price = inventory_item.unit_price
                if not hasattr(invoice_item, 'unit_of_measure') or not invoice_item.unit_of_measure:
                    invoice_item.unit_of_measure = inventory_item.unit_of_measure

                # Recalculate amount
                invoice_item.amount = invoice_item.quantity * invoice_item.price

            invoice_item.inventory_item_id = inventory_item_id
            self.db.commit()

            logger.info(f"Updated inventory reference for invoice item {invoice_item_id} to {inventory_item_id}")
            return True

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating invoice item inventory reference: {e}")
            raise

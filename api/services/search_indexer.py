import logging
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import event, text

from models.models_per_tenant import Invoice, Client, Payment, Expense, BankStatement
from services.search_service import search_service

logger = logging.getLogger(__name__)

class SearchIndexer:
    """Handles automatic indexing of database changes"""
    
    def __init__(self):
        self.setup_event_listeners()
    
    def setup_event_listeners(self):
        """Set up SQLAlchemy event listeners for automatic indexing"""
        
        # Invoice events
        event.listen(Invoice, 'after_insert', self._index_invoice_after_insert)
        event.listen(Invoice, 'after_update', self._index_invoice_after_update)
        event.listen(Invoice, 'after_delete', self._delete_invoice_from_index)
        
        # Client events
        event.listen(Client, 'after_insert', self._index_client_after_insert)
        event.listen(Client, 'after_update', self._index_client_after_update)
        event.listen(Client, 'after_delete', self._delete_client_from_index)
        
        # Payment events
        event.listen(Payment, 'after_insert', self._index_payment_after_insert)
        event.listen(Payment, 'after_update', self._index_payment_after_update)
        event.listen(Payment, 'after_delete', self._delete_payment_from_index)
        
        logger.info("Search indexer event listeners set up")
    
    def _index_invoice_after_insert(self, mapper, connection, target):
        """Index invoice after insert"""
        try:
            # Get client info
            client = connection.execute(
                text("SELECT * FROM clients WHERE id = :client_id"),
                {"client_id": target.client_id}
            ).fetchone()
            
            if client:
                # Convert row to client-like object
                client_obj = type('Client', (), {
                    'id': client.id,
                    'name': client.name,
                    'email': client.email,
                    'company': client.company
                })()
                search_service.index_invoice(target, client_obj)
            else:
                search_service.index_invoice(target)
                
        except Exception as e:
            logger.error(f"Error indexing invoice after insert: {e}")
    
    def _index_invoice_after_update(self, mapper, connection, target):
        """Index invoice after update"""
        try:
            # Skip if soft deleted
            if hasattr(target, 'is_deleted') and target.is_deleted:
                search_service.delete_document('invoices', str(target.id))
                return
            
            # Get client info
            client = connection.execute(
                text("SELECT * FROM clients WHERE id = :client_id"),
                {"client_id": target.client_id}
            ).fetchone()
            
            if client:
                client_obj = type('Client', (), {
                    'id': client.id,
                    'name': client.name,
                    'email': client.email,
                    'company': client.company
                })()
                search_service.index_invoice(target, client_obj)
            else:
                search_service.index_invoice(target)
                
        except Exception as e:
            logger.error(f"Error indexing invoice after update: {e}")
    
    def _delete_invoice_from_index(self, mapper, connection, target):
        """Remove invoice from index after delete"""
        try:
            search_service.delete_document('invoices', str(target.id))
        except Exception as e:
            logger.error(f"Error deleting invoice from index: {e}")
    
    def _index_client_after_insert(self, mapper, connection, target):
        """Index client after insert"""
        try:
            search_service.index_client(target)
        except Exception as e:
            logger.error(f"Error indexing client after insert: {e}")
    
    def _index_client_after_update(self, mapper, connection, target):
        """Index client after update"""
        try:
            # Skip if soft deleted
            if hasattr(target, 'is_deleted') and target.is_deleted:
                search_service.delete_document('clients', str(target.id))
                return
                
            search_service.index_client(target)
        except Exception as e:
            logger.error(f"Error indexing client after update: {e}")
    
    def _delete_client_from_index(self, mapper, connection, target):
        """Remove client from index after delete"""
        try:
            search_service.delete_document('clients', str(target.id))
        except Exception as e:
            logger.error(f"Error deleting client from index: {e}")
    
    def _index_payment_after_insert(self, mapper, connection, target):
        """Index payment after insert"""
        try:
            # Get invoice and client info
            invoice = connection.execute(
                text("SELECT * FROM invoices WHERE id = :invoice_id"),
                {"invoice_id": target.invoice_id}
            ).fetchone()
            
            client = None
            if invoice:
                client = connection.execute(
                    text("SELECT * FROM clients WHERE id = :client_id"),
                    {"client_id": invoice.client_id}
                ).fetchone()
            
            invoice_obj = None
            client_obj = None
            
            if invoice:
                invoice_obj = type('Invoice', (), {
                    'id': invoice.id,
                    'number': invoice.number,
                    'client_id': invoice.client_id
                })()
            
            if client:
                client_obj = type('Client', (), {
                    'id': client.id,
                    'name': client.name,
                    'email': client.email,
                    'company': client.company
                })()
            
            search_service.index_payment(target, invoice_obj, client_obj)
            
        except Exception as e:
            logger.error(f"Error indexing payment after insert: {e}")
    
    def _index_payment_after_update(self, mapper, connection, target):
        """Index payment after update"""
        try:
            # Get invoice and client info
            invoice = connection.execute(
                text("SELECT * FROM invoices WHERE id = :invoice_id"),
                {"invoice_id": target.invoice_id}
            ).fetchone()
            
            client = None
            if invoice:
                client = connection.execute(
                    text("SELECT * FROM clients WHERE id = :client_id"),
                    {"client_id": invoice.client_id}
                ).fetchone()
            
            invoice_obj = None
            client_obj = None
            
            if invoice:
                invoice_obj = type('Invoice', (), {
                    'id': invoice.id,
                    'number': invoice.number,
                    'client_id': invoice.client_id
                })()
            
            if client:
                client_obj = type('Client', (), {
                    'id': client.id,
                    'name': client.name,
                    'email': client.email,
                    'company': client.company
                })()
            
            search_service.index_payment(target, invoice_obj, client_obj)
            
        except Exception as e:
            logger.error(f"Error indexing payment after update: {e}")
    
    def _delete_payment_from_index(self, mapper, connection, target):
        """Remove payment from index after delete"""
        try:
            search_service.delete_document('payments', str(target.id))
        except Exception as e:
            logger.error(f"Error deleting payment from index: {e}")

# Global indexer instance
search_indexer = SearchIndexer()
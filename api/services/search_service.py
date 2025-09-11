import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from opensearchpy import OpenSearch, RequestsHttpConnection
from opensearchpy.exceptions import NotFoundError, RequestError
from sqlalchemy.orm import Session

from models.models_per_tenant import Invoice, Client, Payment, Expense, BankStatement
from models.database import get_tenant_context
from sqlalchemy.orm import Session
from sqlalchemy import or_

logger = logging.getLogger(__name__)

class SearchService:
    def __init__(self):
        self.host = os.getenv('OPENSEARCH_HOST', 'localhost')
        self.port = int(os.getenv('OPENSEARCH_PORT', '9200'))
        self.enabled = os.getenv('OPENSEARCH_ENABLED', 'true').lower() == 'true'
        self.client = None
        
        if self.enabled:
            try:
                self.client = OpenSearch(
                    hosts=[{'host': self.host, 'port': self.port}],
                    http_compress=True,
                    connection_class=RequestsHttpConnection,
                    use_ssl=False,
                    verify_certs=False,
                    ssl_assert_hostname=False,
                    ssl_show_warn=False,
                    timeout=5,
                    max_retries=1,
                    retry_on_timeout=True
                )
                # Test connection
                self.client.cluster.health()
                self._ensure_indices()
                logger.info(f"OpenSearch connected successfully at {self.host}:{self.port}")
            except Exception as e:
                logger.warning(f"OpenSearch connection failed: {e}. Search functionality will be disabled.")
                self.enabled = False
                self.client = None
    
    def _get_tenant_index(self, entity_type: str) -> str:
        """Get tenant-specific index name"""
        tenant_id = get_tenant_context()
        return f"tenant_{tenant_id}_{entity_type}"
    
    def _ensure_indices(self):
        """Create indices if they don't exist"""
        if not self.enabled or not self.client:
            return
            
        indices = ['invoices', 'clients', 'payments', 'expenses', 'statements', 'attachments']
        
        for entity_type in indices:
            index_name = self._get_tenant_index(entity_type)
            try:
                if not self.client.indices.exists(index=index_name):
                    mapping = self._get_mapping(entity_type)
                    self.client.indices.create(
                        index=index_name,
                        body={'mappings': mapping}
                    )
                    logger.info(f"Created index: {index_name}")
            except Exception as e:
                logger.error(f"Error creating index {index_name}: {e}")
                # Disable search if index creation fails
                self.enabled = False
    
    def _get_mapping(self, entity_type: str) -> Dict[str, Any]:
        """Get mapping configuration for entity type"""
        base_mapping = {
            'properties': {
                'id': {'type': 'keyword'},
                'tenant_id': {'type': 'keyword'},
                'created_at': {'type': 'date'},
                'updated_at': {'type': 'date'},
                'searchable_text': {
                    'type': 'text',
                    'analyzer': 'standard'
                }
            }
        }
        
        entity_mappings = {
            'invoices': {
                'properties': {
                    **base_mapping['properties'],
                    'number': {'type': 'keyword'},
                    'client_name': {'type': 'text'},
                    'client_id': {'type': 'keyword'},
                    'status': {'type': 'keyword'},
                    'total_amount': {'type': 'float'},
                    'currency': {'type': 'keyword'},
                    'description': {'type': 'text'},
                    'attachment_filename': {'type': 'text'},
                    'attachment_content': {'type': 'text'}
                }
            },
            'clients': {
                'properties': {
                    **base_mapping['properties'],
                    'name': {'type': 'text'},
                    'email': {'type': 'keyword'},
                    'phone': {'type': 'keyword'},
                    'address': {'type': 'text'},
                    'company': {'type': 'text'}
                }
            },
            'payments': {
                'properties': {
                    **base_mapping['properties'],
                    'invoice_id': {'type': 'keyword'},
                    'invoice_number': {'type': 'keyword'},
                    'client_name': {'type': 'text'},
                    'amount': {'type': 'float'},
                    'currency': {'type': 'keyword'},
                    'payment_method': {'type': 'keyword'},
                    'notes': {'type': 'text'}
                }
            },
            'expenses': {
                'properties': {
                    **base_mapping['properties'],
                    'vendor': {'type': 'text'},
                    'category': {'type': 'keyword'},
                    'amount': {'type': 'float'},
                    'currency': {'type': 'keyword'},
                    'description': {'type': 'text'},
                    'receipt_filename': {'type': 'text'},
                    'receipt_content': {'type': 'text'}
                }
            },
            'statements': {
                'properties': {
                    **base_mapping['properties'],
                    'original_filename': {'type': 'text'},
                    'bank_name': {'type': 'text'},
                    'account_number': {'type': 'keyword'},
                    'statement_content': {'type': 'text'}
                }
            },
            'attachments': {
                'properties': {
                    **base_mapping['properties'],
                    'filename': {'type': 'text'},
                    'entity_type': {'type': 'keyword'},
                    'entity_id': {'type': 'keyword'},
                    'file_content': {'type': 'text'},
                    'file_path': {'type': 'keyword'}
                }
            }
        }
        
        return entity_mappings.get(entity_type, base_mapping)
    
    def index_invoice(self, invoice: Invoice, client: Client = None):
        """Index an invoice document"""
        if not self.enabled:
            return
            
        try:
            doc = {
                'id': str(invoice.id),
                'tenant_id': get_tenant_context(),
                'number': invoice.number,
                'client_id': str(invoice.client_id),
                'client_name': client.name if client else '',
                'status': invoice.status,
                'total_amount': float(invoice.total_amount or 0),
                'currency': invoice.currency or 'USD',
                'description': invoice.description or '',
                'attachment_filename': invoice.attachment_filename or '',
                'created_at': invoice.created_at.isoformat() if invoice.created_at else None,
                'updated_at': invoice.updated_at.isoformat() if invoice.updated_at else None,
                'searchable_text': f"{invoice.number} {client.name if client else ''} {invoice.description or ''} {invoice.attachment_filename or ''}"
            }
            
            index_name = self._get_tenant_index('invoices')
            self.client.index(
                index=index_name,
                id=str(invoice.id),
                body=doc
            )
            logger.debug(f"Indexed invoice {invoice.id}")
        except Exception as e:
            logger.error(f"Error indexing invoice {invoice.id}: {e}")
    
    def index_client(self, client: Client):
        """Index a client document"""
        if not self.enabled:
            return
            
        try:
            doc = {
                'id': str(client.id),
                'tenant_id': get_tenant_context(),
                'name': client.name,
                'email': client.email or '',
                'phone': client.phone or '',
                'address': client.address or '',
                'company': client.company or '',
                'created_at': client.created_at.isoformat() if client.created_at else None,
                'updated_at': client.updated_at.isoformat() if client.updated_at else None,
                'searchable_text': f"{client.name} {client.email or ''} {client.company or ''} {client.address or ''}"
            }
            
            index_name = self._get_tenant_index('clients')
            self.client.index(
                index=index_name,
                id=str(client.id),
                body=doc
            )
            logger.debug(f"Indexed client {client.id}")
        except Exception as e:
            logger.error(f"Error indexing client {client.id}: {e}")
    
    def index_payment(self, payment: Payment, invoice: Invoice = None, client: Client = None):
        """Index a payment document"""
        if not self.enabled:
            return
            
        try:
            doc = {
                'id': str(payment.id),
                'tenant_id': get_tenant_context(),
                'invoice_id': str(payment.invoice_id),
                'invoice_number': invoice.number if invoice else '',
                'client_name': client.name if client else '',
                'amount': float(payment.amount or 0),
                'currency': payment.currency or 'USD',
                'payment_method': payment.payment_method or '',
                'notes': payment.notes or '',
                'created_at': payment.created_at.isoformat() if payment.created_at else None,
                'updated_at': payment.updated_at.isoformat() if payment.updated_at else None,
                'searchable_text': f"{invoice.number if invoice else ''} {client.name if client else ''} {payment.payment_method or ''} {payment.notes or ''}"
            }
            
            index_name = self._get_tenant_index('payments')
            self.client.index(
                index=index_name,
                id=str(payment.id),
                body=doc
            )
            logger.debug(f"Indexed payment {payment.id}")
        except Exception as e:
            logger.error(f"Error indexing payment {payment.id}: {e}")
    
    def search(self, query: str, entity_types: List[str] = None, limit: int = 50, db: Session = None) -> Dict[str, Any]:
        """Search across all indexed documents with database fallback"""
        if self.enabled and self.client:
            return self._opensearch_search(query, entity_types, limit)
        else:
            return self._database_fallback_search(query, entity_types, limit, db)
    
    def _opensearch_search(self, query: str, entity_types: List[str] = None, limit: int = 50) -> Dict[str, Any]:
        """Search using OpenSearch"""
        try:
            if not entity_types:
                entity_types = ['invoices', 'clients', 'payments', 'expenses', 'statements', 'attachments']
            
            indices = [self._get_tenant_index(et) for et in entity_types]
            
            search_body = {
                'query': {
                    'bool': {
                        'must': [
                            {
                                'multi_match': {
                                    'query': query,
                                    'fields': ['searchable_text^2', 'name', 'number', 'description', 'filename'],
                                    'type': 'best_fields',
                                    'fuzziness': 'AUTO'
                                }
                            }
                        ],
                        'filter': [
                            {'term': {'tenant_id': get_tenant_context()}}
                        ]
                    }
                },
                'highlight': {
                    'fields': {
                        'searchable_text': {},
                        'name': {},
                        'description': {}
                    }
                },
                'sort': [
                    {'_score': {'order': 'desc'}},
                    {'created_at': {'order': 'desc'}}
                ],
                'size': limit
            }
            
            response = self.client.search(
                index=','.join(indices),
                body=search_body
            )
            
            results = []
            for hit in response['hits']['hits']:
                source = hit['_source']
                result = {
                    'id': source['id'],
                    'type': hit['_index'].split('_')[-1],  # Extract entity type from index name
                    'score': hit['_score'],
                    'data': source,
                    'highlights': hit.get('highlight', {})
                }
                results.append(result)
            
            return {
                'results': results,
                'total': response['hits']['total']['value'],
                'query': query
            }
            
        except Exception as e:
            logger.error(f"Error searching with OpenSearch: {e}")
            return {'results': [], 'total': 0, 'error': str(e)}
    
    def _database_fallback_search(self, query: str, entity_types: List[str] = None, limit: int = 50, db: Session = None) -> Dict[str, Any]:
        """Fallback search using database queries when OpenSearch is not available"""
        if not db:
            logger.warning("Database session not provided for fallback search")
            return {'results': [], 'total': 0, 'fallback': True}
        
        try:
            results = []
            
            if not entity_types:
                entity_types = ['invoices', 'clients', 'payments', 'expenses']
            
            # Search invoices
            if 'invoices' in entity_types:
                invoices = db.query(Invoice).join(Client).filter(
                    Invoice.is_deleted == False,
                    or_(
                        Invoice.number.ilike(f"%{query}%"),
                        Invoice.notes.ilike(f"%{query}%"),
                        Client.name.ilike(f"%{query}%")
                    )
                ).limit(limit // len(entity_types)).all()
                
                for inv in invoices:
                    results.append({
                        'id': str(inv.id),
                        'type': 'invoices',
                        'score': 1.0,
                        'data': {
                            'id': str(inv.id),
                            'number': inv.number,
                            'client_name': inv.client.name if inv.client else '',
                            'total_amount': float(inv.amount or 0),
                            'status': inv.status,
                            'created_at': inv.created_at.isoformat() if inv.created_at else None
                        },
                        'highlights': {}
                    })
            
            # Search clients
            if 'clients' in entity_types:
                clients = db.query(Client).filter(
                    or_(
                        Client.name.ilike(f"%{query}%"),
                        Client.email.ilike(f"%{query}%"),
                        Client.company.ilike(f"%{query}%")
                    )
                ).limit(limit // len(entity_types)).all()
                
                for client in clients:
                    results.append({
                        'id': str(client.id),
                        'type': 'clients',
                        'score': 1.0,
                        'data': {
                            'id': str(client.id),
                            'name': client.name,
                            'email': client.email or '',
                            'company': client.company or '',
                            'created_at': client.created_at.isoformat() if client.created_at else None
                        },
                        'highlights': {}
                    })
            
            return {
                'results': results[:limit],
                'total': len(results),
                'query': query,
                'fallback': True
            }
            
        except Exception as e:
            logger.error(f"Error in database fallback search: {e}")
            return {'results': [], 'total': 0, 'error': str(e), 'fallback': True}
    
    def delete_document(self, entity_type: str, entity_id: str):
        """Delete a document from the index"""
        if not self.enabled:
            return
            
        try:
            index_name = self._get_tenant_index(entity_type)
            self.client.delete(
                index=index_name,
                id=str(entity_id),
                ignore=[404]
            )
            logger.debug(f"Deleted {entity_type} {entity_id} from index")
        except Exception as e:
            logger.error(f"Error deleting {entity_type} {entity_id}: {e}")
    
    def reindex_all(self, db: Session):
        """Reindex all documents for the current tenant"""
        if not self.enabled:
            return
            
        try:
            # Clear existing indices
            entity_types = ['invoices', 'clients', 'payments', 'expenses', 'statements', 'attachments']
            for entity_type in entity_types:
                index_name = self._get_tenant_index(entity_type)
                try:
                    self.client.indices.delete(index=index_name, ignore=[404])
                except Exception:
                    pass
            
            # Recreate indices
            self._ensure_indices()
            
            # Reindex all data
            tenant_id = get_tenant_context()
            
            # Index invoices
            invoices = db.query(Invoice).filter(Invoice.is_deleted == False).all()
            for invoice in invoices:
                client = db.query(Client).filter(Client.id == invoice.client_id).first()
                self.index_invoice(invoice, client)
            
            # Index clients
            clients = db.query(Client).filter(Client.is_deleted == False).all()
            for client in clients:
                self.index_client(client)
            
            # Index payments
            payments = db.query(Payment).all()
            for payment in payments:
                invoice = db.query(Invoice).filter(Invoice.id == payment.invoice_id).first()
                client = db.query(Client).filter(Client.id == invoice.client_id).first() if invoice else None
                self.index_payment(payment, invoice, client)
            
            logger.info(f"Reindexed all documents for tenant {tenant_id}")
            
        except Exception as e:
            logger.error(f"Error reindexing: {e}")
            raise

# Global search service instance
search_service = SearchService()
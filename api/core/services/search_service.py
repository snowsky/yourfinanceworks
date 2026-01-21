import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from opensearchpy import OpenSearch, RequestsHttpConnection
from opensearchpy.exceptions import NotFoundError, RequestError
from sqlalchemy.orm import Session

from core.models.models_per_tenant import Invoice, Client, Payment, Expense, BankStatement, InventoryItem, Reminder
from core.models.database import get_tenant_context
from sqlalchemy.orm import Session
from sqlalchemy import or_
import re

logger = logging.getLogger(__name__)

def _looks_like_encrypted_data(value: str) -> bool:
    """
    Check if a value looks like encrypted data (base64 encoded).
    This is used to detect when decryption failed and we're showing raw encrypted data.
    """
    if not isinstance(value, str) or len(value) < 30:
        return False

    # Base64 pattern check
    base64_pattern = re.compile(r'^[A-Za-z0-9+/]*={0,2}$')

    # If it contains common plain text patterns, it's probably not encrypted
    if '@' in value and '.' in value:  # Looks like email
        return False
    if ' ' in value:  # Has spaces - likely plain text
        return False

    return base64_pattern.match(value) is not None and len(value) > 30

def _sanitize_value(value: str, fallback: str = '') -> str:
    """
    Sanitize a value for search display.
    If the value looks like encrypted data, return the fallback instead.
    """
    if value is None:
        return fallback
    if _looks_like_encrypted_data(value):
        logger.warning(f"Detected encrypted data in search results, replacing with fallback")
        return fallback
    return value

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
                logger.info(f"OpenSearch connected successfully at {self.host}:{self.port}")
            except Exception as e:
                logger.warning(f"OpenSearch connection failed: {e}. Search functionality will be disabled.")
                self.enabled = False
                self.client = None

    def _get_tenant_index(self, entity_type: str, tenant_id: int = None) -> str:
        """Get tenant-specific index name"""
        if tenant_id is None:
            tenant_id = get_tenant_context()
        if not tenant_id:
            raise ValueError("Tenant context is required for search operations")
        return f"tenant_{tenant_id}_{entity_type}"

    def _ensure_indices(self):
        """Create indices if they don't exist"""
        if not self.enabled or not self.client:
            return

        # Skip if no tenant context (during initialization)
        try:
            tenant_id = get_tenant_context()
            if tenant_id is None:
                return
        except Exception:
            return

        indices = ['invoices', 'clients', 'payments', 'expenses', 'statements', 'attachments', 'inventory', 'reminders']

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
                logger.warning(f"Error creating index {index_name}: {e}")
                # Don't disable search entirely, just log the error

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
                    'amount': {'type': 'float'},
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
            },
            'inventory': {
                'properties': {
                    **base_mapping['properties'],
                    'name': {'type': 'text'},
                    'sku': {'type': 'keyword'},
                    'description': {'type': 'text'},
                    'category': {'type': 'keyword'},
                    'quantity': {'type': 'integer'},
                    'unit_price': {'type': 'float'},
                    'currency': {'type': 'keyword'}
                }
            },
            'reminders': {
                'properties': {
                    **base_mapping['properties'],
                    'title': {'type': 'text'},
                    'description': {'type': 'text'},
                    'status': {'type': 'keyword'},
                    'priority': {'type': 'keyword'},
                    'due_date': {'type': 'date'},
                    'assigned_to_name': {'type': 'text'}
                }
            }
        }

        return entity_mappings.get(entity_type, base_mapping)

    def index_invoice(self, invoice: Invoice, client: Client = None):
        """Index an invoice document"""
        if not self.enabled:
            return

        # Skip indexing if no tenant context
        try:
            tenant_id = get_tenant_context()
            if tenant_id is None:
                logger.debug("Skipping search indexing: no tenant context")
                return
        except Exception:
            logger.debug("Skipping search indexing: failed to get tenant context")
            return

        try:
            doc = {
                'id': str(invoice.id),
                'tenant_id': get_tenant_context(),
                'number': invoice.number,
                'client_id': str(invoice.client_id),
                'client_name': _sanitize_value(client.name, 'Unknown') if client else '',
                'status': invoice.status,
                'amount': float(invoice.amount or 0),
                'currency': invoice.currency or 'USD',
                'description': invoice.notes or '',
                'attachment_filename': invoice.attachment_filename or '',
                'created_at': invoice.created_at.isoformat() if invoice.created_at else None,
                'updated_at': invoice.updated_at.isoformat() if invoice.updated_at else None,
                'searchable_text': f"{invoice.number} {_sanitize_value(client.name, 'Unknown') if client else ''} {invoice.notes or ''} {invoice.attachment_filename or ''}"
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

        # Skip indexing if no tenant context
        try:
            tenant_id = get_tenant_context()
            if tenant_id is None:
                logger.debug("Skipping search indexing: no tenant context")
                return
        except Exception:
            logger.debug("Skipping search indexing: failed to get tenant context")
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

        # Skip indexing if no tenant context
        try:
            tenant_id = get_tenant_context()
            if tenant_id is None:
                logger.debug("Skipping search indexing: no tenant context")
                return
        except Exception:
            logger.debug("Skipping search indexing: failed to get tenant context")
            return

        try:
            doc = {
                'id': str(payment.id),
                'tenant_id': get_tenant_context(),
                'invoice_id': str(payment.invoice_id),
                'invoice_number': invoice.number if invoice else '',
                'client_name': _sanitize_value(client.name, 'Unknown') if client else '',
                'amount': float(payment.amount or 0),
                'currency': payment.currency or 'USD',
                'payment_method': payment.payment_method or '',
                'notes': payment.notes or '',
                'created_at': payment.created_at.isoformat() if payment.created_at else None,
                'updated_at': payment.updated_at.isoformat() if payment.updated_at else None,
                'searchable_text': f"{invoice.number if invoice else ''} {_sanitize_value(client.name, 'Unknown') if client else ''} {payment.payment_method or ''} {payment.notes or ''}"
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

    def index_inventory_item(self, item: InventoryItem):
        """Index an inventory item document"""
        if not self.enabled:
            return

        try:
            doc = {
                'id': str(item.id),
                'tenant_id': get_tenant_context(),
                'name': item.name,
                'sku': item.sku or '',
                'description': item.description or '',
                'category': item.category or '',
                'quantity': item.quantity or 0,
                'unit_price': float(item.unit_price or 0),
                'currency': item.currency or 'USD',
                'created_at': item.created_at.isoformat() if item.created_at else None,
                'updated_at': item.updated_at.isoformat() if item.updated_at else None,
                'searchable_text': f"{item.name} {item.sku or ''} {item.description or ''} {item.category or ''}"
            }

            index_name = self._get_tenant_index('inventory')
            self.client.index(
                index=index_name,
                id=str(item.id),
                body=doc
            )
            logger.debug(f"Indexed inventory item {item.id}")
        except Exception as e:
            logger.error(f"Error indexing inventory item {item.id}: {e}")

    def index_expense(self, expense: Expense):
        """Index an expense document"""
        if not self.enabled:
            return

        # Skip indexing if no tenant context
        try:
            tenant_id = get_tenant_context()
            if tenant_id is None:
                logger.debug("Skipping search indexing: no tenant context")
                return
        except Exception:
            logger.debug("Skipping search indexing: failed to get tenant context")
            return

        try:
            doc = {
                'id': str(expense.id),
                'tenant_id': get_tenant_context(),
                'vendor': expense.vendor or '',
                'category': expense.category or '',
                'amount': float(expense.amount or 0),
                'currency': expense.currency or 'USD',
                'description': expense.notes or '',
                'receipt_filename': expense.receipt_filename or '',
                'created_at': expense.created_at.isoformat() if expense.created_at else None,
                'updated_at': expense.updated_at.isoformat() if expense.updated_at else None,
                'searchable_text': f"{expense.vendor or ''} {expense.category or ''} {expense.notes or ''} {expense.receipt_filename or ''}"
            }

            index_name = self._get_tenant_index('expenses')
            self.client.index(
                index=index_name,
                id=str(expense.id),
                body=doc
            )
            logger.debug(f"Indexed expense {expense.id}")
        except Exception as e:
            logger.error(f"Error indexing expense {expense.id}: {e}")

    def index_reminder(self, reminder: Reminder):
        """Index a reminder document"""
        if not self.enabled:
            return

        try:
            doc = {
                'id': str(reminder.id),
                'tenant_id': get_tenant_context(),
                'title': reminder.title,
                'description': reminder.description or '',
                'status': reminder.status,
                'priority': reminder.priority,
                'due_date': reminder.due_date.isoformat() if reminder.due_date else None,
                'assigned_to_name': '',  # Can be enhanced with user lookup
                'created_at': reminder.created_at.isoformat() if reminder.created_at else None,
                'updated_at': reminder.updated_at.isoformat() if reminder.updated_at else None,
                'searchable_text': f"{reminder.title} {reminder.description or ''}"
            }

            index_name = self._get_tenant_index('reminders')
            self.client.index(
                index=index_name,
                id=str(reminder.id),
                body=doc
            )
            logger.debug(f"Indexed reminder {reminder.id}")
        except Exception as e:
            logger.error(f"Error indexing reminder {reminder.id}: {e}")

    def index_bank_statement(self, statement: BankStatement):
        """Index a bank statement document"""
        if not self.enabled:
            return

        # Skip indexing if no tenant context
        try:
            tenant_id = get_tenant_context()
            if tenant_id is None:
                logger.debug("Skipping search indexing: no tenant context")
                return
        except Exception:
            logger.debug("Skipping search indexing: failed to get tenant context")
            return

        try:
            doc = {
                'id': str(statement.id),
                'tenant_id': get_tenant_context(),
                'original_filename': statement.original_filename,
                'bank_name': '',  # Can be extracted from filename or enhanced with parsing
                'account_number': '',  # Can be extracted from filename or enhanced with parsing
                'statement_content': statement.notes or '',
                'status': statement.status,
                'extracted_count': statement.extracted_count or 0,
                'created_at': statement.created_at.isoformat() if statement.created_at else None,
                'updated_at': statement.updated_at.isoformat() if statement.updated_at else None,
                'searchable_text': f"{statement.original_filename} {statement.stored_filename or ''} {statement.notes or ''}"
            }

            index_name = self._get_tenant_index('statements')
            self.client.index(
                index=index_name,
                id=str(statement.id),
                body=doc
            )
            logger.debug(f"Indexed bank statement {statement.id}")
        except Exception as e:
            logger.error(f"Error indexing bank statement {statement.id}: {e}")

    def search(self, query: str, entity_types: List[str] = None, limit: int = 50, db: Session = None) -> Dict[str, Any]:
        """Search across all indexed documents with database fallback"""
        logger.info(f"Search query: '{query}', entity_types: {entity_types}, limit: {limit}")
        logger.info(f"OpenSearch enabled: {self.enabled}, client available: {self.client is not None}")

        if self.enabled and self.client:
            logger.info("Using OpenSearch search")
            return self._opensearch_search(query, entity_types, limit)
        else:
            logger.info("Using database fallback search")
            return self._database_fallback_search(query, entity_types, limit, db)

    def _opensearch_search(self, query: str, entity_types: List[str] = None, limit: int = 50) -> Dict[str, Any]:
        """Search using OpenSearch"""
        try:
            # Ensure indices exist for current tenant
            self._ensure_indices()

            if not entity_types:
                entity_types = ['invoices', 'clients', 'payments', 'expenses', 'statements', 'attachments', 'inventory', 'reminders']

            # Get tenant context with fallback
            tenant_id = get_tenant_context()
            if not tenant_id:
                tenant_id = 1
                logger.warning(f"No tenant context available, using fallback tenant_id: {tenant_id}")

            indices = [self._get_tenant_index(et, tenant_id) for et in entity_types]
            logger.info(f"Searching indices: {indices}")

            search_body = {
                'query': {
                    'bool': {
                        'filter': [
                            {'term': {'tenant_id': tenant_id}}
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

            # Use different query strategy for short terms vs long terms
            if len(query) <= 4:
                # For short queries, use wildcard search for better partial matching
                search_body['query']['bool']['should'] = [
                    {
                        'wildcard': {
                            'original_filename': f'*{query}*'
                        }
                    },
                    {
                        'wildcard': {
                            'searchable_text': f'*{query}*'
                        }
                    }
                ]
                # Remove the empty 'must' array
                search_body['query']['bool'].pop('must', None)
            else:
                # For longer queries, use multi_match with fuzziness
                search_body['query']['bool']['must'] = [
                    {
                        'multi_match': {
                            'query': query,
                            'fields': ['searchable_text^2', 'name', 'number', 'description', 'filename', 'client_name', 'vendor', 'title', 'email', 'phone', 'company', 'sku', 'category', 'payment_method', 'invoice_number', 'original_filename'],
                            'type': 'best_fields',
                            'fuzziness': 'AUTO'
                        }
                    }
                ]

            # Add tenant filter
            search_body['query']['bool']['filter'] = [
                {'term': {'tenant_id': tenant_id}}
            ]
            logger.info(f"Added tenant filter for tenant_id: {tenant_id}")

            logger.info(f"OpenSearch query body: {search_body}")
            response = self.client.search(
                index=','.join(indices),
                body=search_body
            )

            total_hits = response['hits']['total']['value']
            logger.info(f"OpenSearch returned {total_hits} total hits")

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
                logger.debug(f"Found {result['type']} with score {result['score']}: {result['data'].get('original_filename', result['data'].get('name', 'N/A'))}")

            return {
                'results': results,
                'total': total_hits,
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
                entity_types = ['invoices', 'clients', 'payments', 'expenses', 'statements', 'attachments', 'inventory', 'reminders']

            # Calculate per-type limit with a minimum to ensure each type gets a fair chance
            per_type_limit = max(5, limit // len(entity_types))

            # Search invoices
            if 'invoices' in entity_types:
                invoices = db.query(Invoice).join(Client).filter(
                    Invoice.is_deleted == False,
                    or_(
                        Invoice.number.ilike(f"%{query}%"),
                        Invoice.notes.ilike(f"%{query}%"),
                        Client.name.ilike(f"%{query}%")
                    )
                ).limit(per_type_limit).all()

                for inv in invoices:
                    results.append({
                        'id': str(inv.id),
                        'type': 'invoices',
                        'score': 1.0,
                        'data': {
                            'id': str(inv.id),
                            'number': inv.number,
                            'client_name': _sanitize_value(inv.client.name, 'Unknown') if inv.client else '',
                            'amount': float(inv.amount or 0),
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
                ).limit(per_type_limit).all()

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

            # Search inventory
            if 'inventory' in entity_types:
                inventory_items = db.query(InventoryItem).filter(
                    or_(
                        InventoryItem.name.ilike(f"%{query}%"),
                        InventoryItem.sku.ilike(f"%{query}%"),
                        InventoryItem.description.ilike(f"%{query}%")
                    )
                ).limit(per_type_limit).all()

                for item in inventory_items:
                    results.append({
                        'id': str(item.id),
                        'type': 'inventory',
                        'score': 1.0,
                        'data': {
                            'id': str(item.id),
                            'name': item.name,
                            'sku': item.sku or '',
                            'quantity': item.quantity or 0,
                            'unit_price': float(item.unit_price or 0),
                            'created_at': item.created_at.isoformat() if item.created_at else None
                        },
                        'highlights': {}
                    })

            # Search expenses
            if 'expenses' in entity_types:
                expenses = db.query(Expense).filter(
                    or_(
                        Expense.vendor.ilike(f"%{query}%"),
                        Expense.category.ilike(f"%{query}%"),
                        Expense.notes.ilike(f"%{query}%"),
                        Expense.receipt_filename.ilike(f"%{query}%")
                    )
                ).limit(per_type_limit).all()

                for expense in expenses:
                    results.append({
                        'id': str(expense.id),
                        'type': 'expenses',
                        'score': 1.0,
                        'data': {
                            'id': str(expense.id),
                            'vendor': expense.vendor or '',
                            'category': expense.category or '',
                            'amount': float(expense.amount or 0),
                            'currency': expense.currency or 'USD',
                            'created_at': expense.created_at.isoformat() if expense.created_at else None
                        },
                        'highlights': {}
                    })

            # Search reminders
            if 'reminders' in entity_types:
                reminders = db.query(Reminder).filter(
                    or_(
                        Reminder.title.ilike(f"%{query}%"),
                        Reminder.description.ilike(f"%{query}%")
                    )
                ).limit(per_type_limit).all()

                for reminder in reminders:
                    results.append({
                        'id': str(reminder.id),
                        'type': 'reminders',
                        'score': 1.0,
                        'data': {
                            'id': str(reminder.id),
                            'title': reminder.title,
                            'description': reminder.description or '',
                            'status': reminder.status,
                            'priority': reminder.priority,
                            'due_date': reminder.due_date.isoformat() if reminder.due_date else None,
                            'created_at': reminder.created_at.isoformat() if reminder.created_at else None
                        },
                        'highlights': {}
                    })

            # Search bank statements
            if 'statements' in entity_types:
                try:
                    statements = db.query(BankStatement).filter(
                        BankStatement.is_deleted == False,
                        or_(
                            BankStatement.original_filename.ilike(f"%{query}%"),
                            BankStatement.stored_filename.ilike(f"%{query}%"),
                            BankStatement.notes.ilike(f"%{query}%")
                        )
                    ).limit(per_type_limit).all()

                    for statement in statements:
                        results.append({
                            'id': str(statement.id),
                            'type': 'statements',
                            'score': 1.0,
                            'data': {
                                'id': str(statement.id),
                                'original_filename': statement.original_filename,
                                'status': statement.status,
                                'extracted_count': statement.extracted_count or 0,
                                'created_at': statement.created_at.isoformat() if statement.created_at else None
                            },
                            'highlights': {}
                        })
                except Exception as e:
                    logger.warning(f"Error searching bank statements: {e}")
                    # Continue with other entity types if bank statements table doesn't exist
                    pass

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
            entity_types = ['invoices', 'clients', 'payments', 'expenses', 'statements', 'attachments', 'inventory', 'reminders']
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
            clients = db.query(Client).all()
            for client in clients:
                self.index_client(client)

            # Index payments
            payments = db.query(Payment).all()
            for payment in payments:
                invoice = db.query(Invoice).filter(Invoice.id == payment.invoice_id).first()
                client = db.query(Client).filter(Client.id == invoice.client_id).first() if invoice else None
                self.index_payment(payment, invoice, client)

            # Index inventory items
            inventory_items = db.query(InventoryItem).all()
            for item in inventory_items:
                self.index_inventory_item(item)

            # Index expenses
            expenses = db.query(Expense).all()
            for expense in expenses:
                self.index_expense(expense)

            # Index reminders
            reminders = db.query(Reminder).all()
            for reminder in reminders:
                self.index_reminder(reminder)

            # Index bank statements
            statements = db.query(BankStatement).filter(BankStatement.is_deleted == False).all()
            for statement in statements:
                self.index_bank_statement(statement)

            logger.info(f"Reindexed all documents for tenant {tenant_id}")

        except Exception as e:
            logger.error(f"Error reindexing: {e}")
            raise

# Global search service instance
search_service = SearchService()

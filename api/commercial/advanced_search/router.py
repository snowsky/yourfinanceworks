from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

from core.models.database import get_db
from core.models.models import MasterUser
from core.routers.auth import get_current_user
from core.services.search_service import search_service
from core.utils.feature_gate import require_feature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/search", tags=["search"])

@router.get("")
@require_feature("advanced_search")
async def global_search(
    q: str = Query(..., min_length=1, description="Search query"),
    types: Optional[str] = Query(None, description="Comma-separated entity types to search (invoices,clients,payments,expenses,statements,attachments,inventory,reminders)"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of results"),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Global search across all system entities"""
    try:
        entity_types = None
        if types:
            entity_types = [t.strip() for t in types.split(',') if t.strip()]
        
        results = search_service.search(
            query=q,
            entity_types=entity_types,
            limit=limit,
            db=db
        )
        
        # Enhance results with URLs and additional metadata
        enhanced_results = []
        for result in results['results']:
            entity_type = result['type']
            entity_id = result['data']['id']
            
            # Generate appropriate URLs and metadata based on entity type
            url = None
            title = None
            subtitle = None
            
            if entity_type == 'invoices':
                url = f"/invoices/edit/{entity_id}"
                title = f"Invoice {result['data'].get('number', entity_id)}"
                subtitle = f"Client: {result['data'].get('client_name', 'Unknown')} • ${result['data'].get('amount', 0)}"
            elif entity_type == 'clients':
                url = f"/clients/edit/{entity_id}"
                title = result['data'].get('name', f'Client {entity_id}')
                subtitle = result['data'].get('email', result['data'].get('company', ''))
            elif entity_type == 'payments':
                url = f"/payments"
                title = f"Payment for Invoice {result['data'].get('invoice_number', entity_id)}"
                subtitle = f"${result['data'].get('amount', 0)} • {result['data'].get('payment_method', 'Unknown method')}"
            elif entity_type == 'expenses':
                url = f"/expenses/edit/{entity_id}"
                title = f"Expense #{entity_id}"
                subtitle = f"{result['data'].get('vendor', 'Unknown vendor')} • ${result['data'].get('amount', 0)}"
            elif entity_type == 'statements':
                url = f"/statements"
                title = f"Bank Statement #{entity_id}"
                subtitle = result['data'].get('original_filename', 'Unknown file')
            elif entity_type == 'attachments':
                url = f"/attachments"
                title = result['data'].get('filename', f'Attachment {entity_id}')
                subtitle = f"{result['data'].get('entity_type', 'Unknown')} attachment"
            elif entity_type == 'inventory':
                url = f"/inventory"
                title = result['data'].get('name', f'Item {entity_id}')
                sku = result['data'].get('sku', '')
                qty = result['data'].get('quantity', 0)
                subtitle = f"SKU: {sku} • Qty: {qty}" if sku else f"Qty: {qty}"
            elif entity_type == 'reminders':
                url = f"/reminders"
                title = result['data'].get('title', f'Reminder {entity_id}')
                priority = result['data'].get('priority', 'medium')
                status = result['data'].get('status', 'pending')
                subtitle = f"{priority.title()} priority • {status.title()}"
            
            enhanced_result = {
                'id': entity_id,
                'type': entity_type,
                'title': title,
                'subtitle': subtitle,
                'url': url,
                'score': result['score'],
                'highlights': result.get('highlights', {}),
                'data': result['data']
            }
            enhanced_results.append(enhanced_result)
        
        return {
            'query': q,
            'results': enhanced_results,
            'total': results['total'],
            'types_searched': entity_types or ['all']
        }
        
    except Exception as e:
        logger.error(f"Error in global search: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )

@router.post("/reindex")
@require_feature("advanced_search")
async def reindex_all_data(
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Reindex all data for the current tenant (admin only)"""
    try:
        # Check if user is admin
        if current_user.role not in ['admin', 'superuser']:
            raise HTTPException(
                status_code=403,
                detail="Only admins can reindex data"
            )
        
        search_service.reindex_all(db)
        
        from core.models.database import get_tenant_context
        return {
            'message': 'Reindexing completed successfully',
            'tenant_id': get_tenant_context()
        }
        
    except Exception as e:
        logger.error(f"Error reindexing data: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Reindexing failed: {str(e)}"
        )

@router.get("/suggestions")
@require_feature("advanced_search")
async def search_suggestions(
    q: str = Query(..., min_length=1, description="Partial search query"),
    limit: int = Query(10, ge=1, le=20, description="Maximum number of suggestions"),
    db: Session = Depends(get_db),
    current_user: MasterUser = Depends(get_current_user)
):
    """Get search suggestions based on partial query"""
    try:
        # For now, return basic suggestions based on search results
        # This could be enhanced with dedicated suggestion indices
        results = search_service.search(
            query=q,
            entity_types=None,
            limit=limit,
            db=db
        )
        
        suggestions = []
        seen_titles = set()
        
        for result in results['results']:
            entity_type = result['type']
            data = result['data']
            
            if entity_type == 'invoices':
                title = f"Invoice {data.get('number', '')}"
            elif entity_type == 'clients':
                title = data.get('name', '')
            elif entity_type == 'payments':
                title = f"Payment {data.get('invoice_number', '')}"
            elif entity_type == 'expenses':
                title = f"Expense {data.get('vendor', '')}"
            else:
                title = f"{entity_type.title()} {data.get('id', '')}"
            
            if title and title not in seen_titles:
                suggestions.append({
                    'title': title,
                    'type': entity_type,
                    'id': data.get('id')
                })
                seen_titles.add(title)
        
        return {
            'query': q,
            'suggestions': suggestions[:limit]
        }
        
    except Exception as e:
        logger.error(f"Error getting search suggestions: {str(e)}")
        return {
            'query': q,
            'suggestions': []
        }

@router.get("/status")
@require_feature("advanced_search")
async def search_status(
    current_user: MasterUser = Depends(get_current_user)
):
    """Get search service status"""
    try:
        logger.info(f"Getting search status for user {current_user.id}")
        
        status = {
            'opensearch_enabled': search_service.enabled,
            'opensearch_connected': search_service.client is not None,
            'host': search_service.host,
            'port': search_service.port,
            'fallback_available': True
        }
        
        if search_service.enabled and search_service.client:
            try:
                health = search_service.client.cluster.health()
                status['opensearch_health'] = health['status']
                status['opensearch_nodes'] = health['number_of_nodes']
            except Exception as e:
                logger.warning(f"OpenSearch health check failed: {str(e)}")
                status['opensearch_error'] = str(e)
        
        logger.info(f"Search status: {status}")
        return status
        
    except Exception as e:
        logger.error(f"Error getting search status: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return {
            'opensearch_enabled': False,
            'opensearch_connected': False,
            'fallback_available': True,
            'error': str(e)
        }
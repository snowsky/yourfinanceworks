"""
Search-related tools mixin.
"""
from typing import Any, Dict, List, Optional


class SearchToolsMixin:
    # Advanced Search Tools
    async def global_search(self, query: str, entity_types: List[str] = None, limit: int = 50) -> Dict[str, Any]:
        """Perform global search across all entities"""
        if not query or len(query.strip()) < 1:
            return {"success": False, "error": "Search query cannot be empty"}

        if limit < 1 or limit > 100:
            return {"success": False, "error": "Limit must be between 1 and 100"}

        try:
            results = await self.api_client.global_search(
                query=query.strip(),
                entity_types=entity_types,
                limit=limit
            )

            return {
                "success": True,
                "data": results,
                "query": query,
                "results_count": len(results.get('results', [])),
                "total_available": results.get('total', 0),
                "types_searched": results.get('types_searched', [])
            }

        except Exception as e:
            return {"success": False, "error": f"Search failed: {e}"}

    async def search_suggestions(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Get search suggestions based on partial query"""
        if not query or len(query.strip()) < 1:
            return {"success": False, "error": "Query cannot be empty"}

        if limit < 1 or limit > 20:
            return {"success": False, "error": "Limit must be between 1 and 20"}

        try:
            suggestions = await self.api_client.search_suggestions(
                query=query.strip(),
                limit=limit
            )

            return {
                "success": True,
                "data": suggestions,
                "query": query,
                "suggestions_count": len(suggestions.get('suggestions', []))
            }

        except Exception as e:
            return {"success": False, "error": f"Failed to get suggestions: {e}"}

    async def reindex_all_data(self) -> Dict[str, Any]:
        """Reindex all data for search (admin only)"""
        try:
            result = await self.api_client.reindex_all_data()
            return {
                "success": True,
                "data": result,
                "message": "Data reindexing completed successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Reindexing failed: {e}"}

    async def get_search_status(self) -> Dict[str, Any]:
        """Get search service status"""
        try:
            status = await self.api_client.get_search_status()
            return {
                "success": True,
                "data": status,
                "message": "Search status retrieved successfully"
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to get search status: {e}"}

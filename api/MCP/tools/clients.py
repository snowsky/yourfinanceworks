"""
Client-related tools mixin.
"""
from typing import Any, Dict, List, Optional
import logging
from pydantic import BaseModel, Field
from core.schemas.client import ClientBase


class ListClientsArgs(BaseModel):
    skip: int = Field(default=0, description="Number of clients to skip for pagination")
    limit: int = Field(default=100, description="Maximum number of clients to return")


class SearchClientsArgs(BaseModel):
    query: str = Field(description="Search query to find clients by name, email, phone, or address")
    skip: int = Field(default=0, description="Number of results to skip for pagination")
    limit: int = Field(default=100, description="Maximum number of results to return")


class GetClientArgs(BaseModel):
    client_id: int = Field(description="ID of the client to retrieve")


class CreateClientArgs(ClientBase):
    pass


class CreateClientNoteArgs(BaseModel):
    client_id: int = Field(description="ID of the client to add a note to")
    title: str = Field(description="Note title")
    content: str = Field(description="Note content")
    note_type: str = Field(default="general", description="Type of note (general, follow_up, etc.)")


class ClientToolsMixin:
    async def list_clients(self, skip: int = 0, limit: int = 100) -> Dict[str, Any]:
        """List all clients"""
        try:
            response = await self.api_client.list_clients(skip=skip, limit=limit)

            # Extract items from paginated response
            clients = self._extract_items_from_response(response, ["items", "data", "clients"])

            return {
                "success": True,
                "data": clients,
                "count": len(clients),
                "pagination": {
                    "skip": skip,
                    "limit": limit
                }
            }

        except Exception as e:
            try:
                from ..auth_client import AuthenticationError
                if isinstance(e, AuthenticationError):
                    logging.getLogger(__name__).error(f"Authentication failed in list_clients: {e}")
                    return {"success": False, "error": f"Authentication failed: {e}"}
            except ImportError:
                pass
            logging.getLogger(__name__).error(f"Failed to list clients: {e}")
            return {"success": False, "error": f"Failed to list clients: {e}"}

    async def search_clients(self, query: str, skip: int = 0, limit: int = 100) -> Dict[str, Any]:
        """Search for clients"""
        try:
            response = await self.api_client.search_clients(
                query=query,
                skip=skip,
                limit=limit
            )

            # Extract items from paginated response
            clients = self._extract_items_from_response(response, ["items", "data", "clients"])

            return {
                "success": True,
                "data": clients,
                "count": len(clients),
                "search_query": query,
                "pagination": {
                    "skip": skip,
                    "limit": limit
                }
            }

        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to search clients: {e}")
            return {"success": False, "error": f"Failed to search clients: {e}"}

    async def get_client(self, client_id: int) -> Dict[str, Any]:
        """Get a specific client"""
        try:
            client = await self.api_client.get_client(client_id)

            return {
                "success": True,
                "data": client
            }

        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to get client {client_id}: {e}")
            return {"success": False, "error": f"Failed to get client: {e}"}

    async def create_client(self, name: str, email: Optional[str] = None, phone: Optional[str] = None, address: Optional[str] = None) -> Dict[str, Any]:
        """Create a new client"""
        try:
            client_data = {"name": name}
            if email:
                client_data["email"] = email
            if phone:
                client_data["phone"] = phone
            if address:
                client_data["address"] = address

            client = await self.api_client.create_client(client_data)

            return {
                "success": True,
                "data": client,
                "message": "Client created successfully"
            }

        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to create client {name}: {e}")
            return {"success": False, "error": f"Failed to create client: {e}"}

    async def create_client_note(self, client_id: int, title: str, content: str, note_type: str = "general") -> Dict[str, Any]:
        """Create a note for a client"""
        try:
            note_data = {
                "title": title,
                "content": content,
                "note_type": note_type
            }

            note = await self.api_client.create_client_note(client_id, note_data)

            return {
                "success": True,
                "data": note,
                "message": "Client note created successfully"
            }

        except Exception as e:
            return {"success": False, "error": f"Failed to create client note: {e}"}

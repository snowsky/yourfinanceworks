#!/usr/bin/env python3
"""
Simple test endpoint to verify basic functionality
"""
from fastapi import APIRouter, HTTPException

router = APIRouter(
    prefix="/test-inventory/{item_id}/attachments",
    tags=["test-inventory-attachments"]
)

@router.get("/")
@router.get("")
async def test_get_attachments(item_id: int):
    """Simple test endpoint that doesn't depend on database models"""
    return {
        "message": f"Test endpoint working for item {item_id}",
        "item_id": item_id,
        "attachments": []
    }

@router.post("/")
@router.post("")
async def test_upload_attachment(item_id: int):
    """Simple test endpoint for POST requests"""
    return {
        "message": f"Test POST endpoint working for item {item_id}",
        "item_id": item_id,
        "status": "success"
    }
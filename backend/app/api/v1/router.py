"""Collects every v1 router under one prefix."""

from fastapi import APIRouter

from app.api.v1 import (
    auth,
    dashboard,
    health,
    operations,
    partners,
    products,
    stock,
    users,
    warehouses,
    ws,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(warehouses.router)
api_router.include_router(products.router)
api_router.include_router(partners.router)
api_router.include_router(operations.router)
api_router.include_router(stock.router)
api_router.include_router(dashboard.router)
api_router.include_router(ws.router)

"""Тесты product-service. Используют PostgreSQL из docker-compose."""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app, get_db


@pytest.fixture
async def client(db_session):
    """HTTP клиент с переопределённой БД."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# --- Health ---
async def test_health(client):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "product-service"


# --- List Products ---
async def test_list_products_empty(client):
    resp = await client.get("/api/products")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_products(client):
    await client.post("/api/products", json={
        "name": "Test Product",
        "cost_price": 100.0,
        "quantity": 10,
    })
    resp = await client.get("/api/products")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Test Product"
    assert data[0]["user_price"] == 120.0  # 100 * 1.2


# --- Get Product ---
async def test_get_product(client):
    create_resp = await client.post("/api/products", json={
        "name": "Single Product",
        "cost_price": 50.0,
        "quantity": 5,
    })
    product_id = create_resp.json()["id"]

    resp = await client.get(f"/api/products/{product_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Single Product"


async def test_get_product_not_found(client):
    resp = await client.get("/api/products/9999")
    assert resp.status_code == 404


# --- Create Product ---
async def test_create_product(client):
    resp = await client.post("/api/products", json={
        "name": "New Product",
        "description": "A great product",
        "cost_price": 75.0,
        "quantity": 20,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "New Product"
    assert data["cost_price"] == 75.0
    assert data["user_price"] == 90.0  # 75 * 1.2
    assert data["quantity"] == 20


async def test_create_product_invalid_price(client):
    resp = await client.post("/api/products", json={
        "name": "Bad Product",
        "cost_price": -10.0,
        "quantity": 5,
    })
    assert resp.status_code == 422


# --- Update Product ---
async def test_update_product(client):
    create_resp = await client.post("/api/products", json={
        "name": "Old Name",
        "cost_price": 100.0,
        "quantity": 10,
    })
    product_id = create_resp.json()["id"]

    resp = await client.put(f"/api/products/{product_id}", json={"name": "New Name", "quantity": 15})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "New Name"
    assert data["quantity"] == 15
    assert data["cost_price"] == 100.0  # unchanged


# --- Delete Product ---
async def test_delete_product(client):
    create_resp = await client.post("/api/products", json={
        "name": "Delete Me",
        "cost_price": 50.0,
        "quantity": 5,
    })
    product_id = create_resp.json()["id"]

    resp = await client.delete(f"/api/products/{product_id}")
    assert resp.status_code == 204

    resp = await client.get(f"/api/products/{product_id}")
    assert resp.status_code == 404


# --- Reserve Stock ---
async def test_reserve_stock(client):
    create_resp = await client.post("/api/products", json={
        "name": "Stock Product",
        "cost_price": 100.0,
        "quantity": 10,
    })
    product_id = create_resp.json()["id"]

    resp = await client.post("/api/products/reserve-stock", json={
        "product_id": product_id,
        "quantity": 3,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["remaining_quantity"] == 7


async def test_reserve_stock_insufficient(client):
    create_resp = await client.post("/api/products", json={
        "name": "Low Stock",
        "cost_price": 100.0,
        "quantity": 2,
    })
    product_id = create_resp.json()["id"]

    resp = await client.post("/api/products/reserve-stock", json={
        "product_id": product_id,
        "quantity": 5,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert data["remaining_quantity"] == 2


# --- Unreserve Stock ---
async def test_unreserve_stock(client):
    create_resp = await client.post("/api/products", json={
        "name": "Return Product",
        "cost_price": 100.0,
        "quantity": 10,
    })
    product_id = create_resp.json()["id"]

    # Reserve first
    await client.post("/api/products/reserve-stock", json={
        "product_id": product_id,
        "quantity": 5,
    })
    # Then unreserve
    resp = await client.post("/api/products/unreserve-stock", json={
        "product_id": product_id,
        "quantity": 5,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["remaining_quantity"] == 10

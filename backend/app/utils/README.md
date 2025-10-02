# Database Utilities Documentation

A comprehensive set of database utilities for CRUD operations, query building, and transaction management.

## 📁 File Structure

```
utils/
├── __init__.py              # Export all utilities
├── db_session.py            # Database session management
├── crud_repository.py       # Generic CRUD operations
├── query_builder.py         # Dynamic query building
├── transaction_manager.py   # Transaction handling
├── examples.py              # Usage examples
└── README.md               # This file
```

## 🚀 Quick Start

### 1. Define a Model

```python
from app.utils import Base
from sqlalchemy import Column, Integer, String, Float, Boolean

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    price = Column(Float)
    stock = Column(Integer)
    is_active = Column(Boolean, default=True)
```

### 2. Use CRUD Repository

```python
from app.utils import CRUDRepository, get_db_session

product_repo = CRUDRepository(Product)

with get_db_session() as db:
    # Create
    product = product_repo.create(db, {
        "name": "Laptop",
        "price": 1299.99,
        "stock": 50
    })

    # Read
    product = product_repo.get_by_id(db, 1)
    products = product_repo.get_all(db, skip=0, limit=10)

    # Update
    updated = product_repo.update(db, 1, {"price": 1199.99})

    # Delete
    deleted = product_repo.delete(db, 1)
```

### 3. Use Query Builder

```python
from app.utils import QueryBuilder, FilterOperator, SortOrder

with get_db_session() as db:
    results = (
        QueryBuilder(Product, db)
        .filter("is_active", True)
        .filter("price", 100, FilterOperator.GREATER_THAN)
        .sort("price", SortOrder.ASC)
        .paginate(page=1, page_size=20)
        .all()
    )
```

## 📚 Core Components

### 1. Database Session Manager (`db_session.py`)

Manages database connections and session lifecycle.

#### Key Features:

- **Automatic session management** with context managers
- **Connection pooling** for better performance
- **Transaction support** with auto-commit/rollback

#### Usage:

```python
from app.utils import get_db_session, get_session_manager

# As FastAPI dependency
@app.get("/products")
def get_products(db: Session = Depends(get_db_session)):
    return db.query(Product).all()

# Manual session management
manager = get_session_manager()
with manager.session_scope() as session:
    # Your database operations
    pass
```

### 2. CRUD Repository (`crud_repository.py`)

Generic repository pattern for database operations.

#### Available Methods:

| Method                                | Description                     |
| ------------------------------------- | ------------------------------- |
| `create(db, data)`                    | Create a new record             |
| `get_by_id(db, id)`                   | Get record by primary key       |
| `get_by_field(db, field, value)`      | Get record by any field         |
| `get_all(db, skip, limit)`            | Get all records with pagination |
| `get_multi_by_filter(db, filters)`    | Get records matching filters    |
| `update(db, id, data)`                | Update record by ID             |
| `update_by_filter(db, filters, data)` | Update records matching filters |
| `delete(db, id)`                      | Delete record by ID             |
| `delete_by_filter(db, filters)`       | Delete records matching filters |
| `exists(db, id)`                      | Check if record exists          |
| `count(db, filters)`                  | Count records                   |
| `bulk_create(db, data_list)`          | Create multiple records         |

#### Examples:

```python
from app.utils import CRUDRepository

repo = CRUDRepository(Product)

# Create single record
product = repo.create(db, {"name": "Mouse", "price": 29.99})

# Bulk create
products = repo.bulk_create(db, [
    {"name": "Keyboard", "price": 79.99},
    {"name": "Monitor", "price": 299.99}
])

# Filter and get
active_products = repo.get_multi_by_filter(
    db,
    filters={"is_active": True},
    skip=0,
    limit=100
)

# Bulk update
count = repo.update_by_filter(
    db,
    filters={"stock": 0},
    update_data={"is_active": False}
)

# Count with filters
total = repo.count(db, filters={"is_active": True})
```

### 3. Query Builder (`query_builder.py`)

Fluent API for building complex database queries.

#### Supported Operators:

| Operator                | Description                      |
| ----------------------- | -------------------------------- |
| `EQUALS`                | Exact match (=)                  |
| `NOT_EQUALS`            | Not equal (!=)                   |
| `GREATER_THAN`          | Greater than (>)                 |
| `GREATER_THAN_OR_EQUAL` | Greater or equal (>=)            |
| `LESS_THAN`             | Less than (<)                    |
| `LESS_THAN_OR_EQUAL`    | Less or equal (<=)               |
| `LIKE`                  | Pattern match (case-sensitive)   |
| `ILIKE`                 | Pattern match (case-insensitive) |
| `IN`                    | In list                          |
| `NOT_IN`                | Not in list                      |
| `IS_NULL`               | Is NULL                          |
| `IS_NOT_NULL`           | Is not NULL                      |
| `BETWEEN`               | Between two values               |

#### Examples:

```python
from app.utils import QueryBuilder, FilterOperator, SortOrder

# Simple filter
products = (
    QueryBuilder(Product, db)
    .filter("price", 100, FilterOperator.GREATER_THAN)
    .all()
)

# Multiple filters
products = (
    QueryBuilder(Product, db)
    .filter("is_active", True)
    .filter("stock", 0, FilterOperator.GREATER_THAN)
    .filter("name", "%Laptop%", FilterOperator.ILIKE)
    .all()
)

# OR conditions
products = (
    QueryBuilder(Product, db)
    .filter_or([
        ("category", "Electronics", FilterOperator.EQUALS),
        ("category", "Computers", FilterOperator.EQUALS),
    ])
    .all()
)

# BETWEEN
products = (
    QueryBuilder(Product, db)
    .filter("price", (50, 200), FilterOperator.BETWEEN)
    .all()
)

# Sorting and pagination
products = (
    QueryBuilder(Product, db)
    .filter("is_active", True)
    .sort("price", SortOrder.DESC)
    .paginate(page=1, page_size=20)
    .all()
)

# Get single result
product = (
    QueryBuilder(Product, db)
    .filter("id", 1)
    .first()
)

# Count
count = (
    QueryBuilder(Product, db)
    .filter("is_active", True)
    .count()
)

# Check existence
exists = (
    QueryBuilder(Product, db)
    .filter("name", "Laptop")
    .exists()
)
```

### 4. Transaction Manager (`transaction_manager.py`)

Handles database transactions with automatic rollback on errors.

#### Features:

- **Context manager** for transaction scope
- **Decorator** for automatic transaction handling
- **Batch operations** for multiple operations in one transaction

#### Examples:

```python
from app.utils import TransactionManager, transactional, BatchOperationManager

# Using decorator
@transactional
def create_order_with_items(session, order_data):
    order_repo = CRUDRepository(Order)
    item_repo = CRUDRepository(OrderItem)

    # Create order
    order = order_repo.create(session, order_data)

    # Create items
    for item_data in order_data["items"]:
        item_repo.create(session, {
            **item_data,
            "order_id": order.id
        })

    return order
    # Auto-commits on success, rolls back on error

# Manual transaction
with get_db_session() as db:
    tx_manager = TransactionManager(db)

    with tx_manager.transaction() as session:
        # Your operations
        product_repo.create(session, {...})
        product_repo.update(session, 1, {...})
        # Commits on success, rolls back on error

# Batch operations
with get_db_session() as db:
    batch = BatchOperationManager(db)

    batch.add_operation(lambda s: product_repo.create(s, {...}))
    batch.add_operation(lambda s: product_repo.update(s, 1, {...}))
    batch.add_operation(lambda s: product_repo.delete(s, 2))

    results = batch.execute_all()  # All or nothing
```

## 🔥 Real-World Examples

### E-Commerce Product Search

```python
def search_products(search_term: str, min_price: float, max_price: float, page: int):
    with get_db_session() as db:
        results = (
            QueryBuilder(Product, db)
            .filter("name", f"%{search_term}%", FilterOperator.ILIKE)
            .filter("price", (min_price, max_price), FilterOperator.BETWEEN)
            .filter("is_active", True)
            .filter("stock", 0, FilterOperator.GREATER_THAN)
            .sort("price", SortOrder.ASC)
            .paginate(page=page, page_size=20)
            .all()
        )
        return results
```

### Inventory Management

```python
@transactional
def process_sale(session, product_id: int, quantity: int):
    product_repo = CRUDRepository(Product)

    # Get product
    product = product_repo.get_by_id(session, product_id)

    if not product or product.stock < quantity:
        raise ValueError("Insufficient stock")

    # Update stock
    product_repo.update(session, product_id, {
        "stock": product.stock - quantity
    })

    # Mark as inactive if out of stock
    if product.stock - quantity == 0:
        product_repo.update(session, product_id, {"is_active": False})

    return product
```

### Bulk Data Import

```python
def import_products(products_data: list):
    product_repo = CRUDRepository(Product)

    with get_db_session() as db:
        # Bulk create all products
        created = product_repo.bulk_create(db, products_data)
        return len(created)
```

## 🎯 Best Practices

1. **Always use context managers** for session management
2. **Use transactions** for multi-step operations
3. **Use repositories** for consistent data access patterns
4. **Use query builder** for complex, dynamic queries
5. **Keep models focused** - one table per model class
6. **Handle errors gracefully** - transactions auto-rollback on errors
7. **Use pagination** for large result sets
8. **Index frequently queried fields** for better performance

## 🔧 Integration with FastAPI

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.utils import get_db_session, CRUDRepository, QueryBuilder

router = APIRouter()
product_repo = CRUDRepository(Product)

@router.get("/products")
def list_products(
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db_session)
):
    products = product_repo.get_all(db, skip=skip, limit=limit)
    return products

@router.get("/products/search")
def search_products(
    q: str,
    db: Session = Depends(get_db_session)
):
    results = (
        QueryBuilder(Product, db)
        .filter("name", f"%{q}%", FilterOperator.ILIKE)
        .filter("is_active", True)
        .limit(20)
        .all()
    )
    return results

@router.post("/products")
def create_product(
    product_data: dict,
    db: Session = Depends(get_db_session)
):
    product = product_repo.create(db, product_data)
    return product
```

## 📝 Notes

- All utilities follow **single responsibility principle**
- Each file is **under 200 lines** for maintainability
- **Type hints** for better IDE support
- **Comprehensive error handling** with automatic rollback
- **Reusable and composable** components
- **Framework-agnostic** design (works with any SQLAlchemy setup)

## 🧪 Testing

See `examples.py` for comprehensive usage examples and test scenarios.

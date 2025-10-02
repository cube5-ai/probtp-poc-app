# Database Utils - Quick Reference

## 🚀 Quick Imports

```python
from app.utils import (
    # Models
    Base,

    # Session
    get_db_session,
    get_session_manager,

    # CRUD
    CRUDRepository,

    # Query
    QueryBuilder,
    FilterOperator,
    SortOrder,

    # Transactions
    transactional,
    TransactionManager,
    BatchOperationManager,
)
```

## 📝 Common Patterns

### 1. Basic CRUD

```python
# Setup
repo = CRUDRepository(Product)

# Create
product = repo.create(db, {"name": "Item", "price": 10})

# Read
product = repo.get_by_id(db, 1)
products = repo.get_all(db, skip=0, limit=10)

# Update
repo.update(db, 1, {"price": 15})

# Delete
repo.delete(db, 1)
```

### 2. Query Filters

```python
# Equals
.filter("is_active", True)

# Comparison
.filter("price", 100, FilterOperator.GREATER_THAN)
.filter("stock", 50, FilterOperator.LESS_THAN_OR_EQUAL)

# Text search
.filter("name", "%laptop%", FilterOperator.ILIKE)

# Range
.filter("price", (50, 200), FilterOperator.BETWEEN)

# List
.filter("id", [1, 2, 3], FilterOperator.IN)

# Null checks
.filter("deleted_at", None, FilterOperator.IS_NULL)
```

### 3. Sorting & Pagination

```python
# Sort ascending
.sort("price", SortOrder.ASC)

# Sort descending
.sort("created_at", SortOrder.DESC)

# Paginate (page 1, 20 items)
.paginate(page=1, page_size=20)

# Manual limit/offset
.limit(10).offset(20)
```

### 4. Query Results

```python
# Get all
results = query.all()

# Get first
result = query.first()

# Get one (error if not exactly 1)
result = query.one()

# Count
count = query.count()

# Check exists
exists = query.exists()
```

### 5. Transactions

```python
# Decorator
@transactional
def my_function(session):
    # operations auto-commit
    pass

# Context manager
with tx_manager.transaction() as session:
    # operations
    pass

# Batch
batch.add_operation(lambda s: repo.create(s, {...}))
batch.execute_all()
```

## 🎯 Complete Examples

### Search with Filters

```python
QueryBuilder(Product, db)
    .filter("name", f"%{search}%", FilterOperator.ILIKE)
    .filter("is_active", True)
    .filter("price", min_price, FilterOperator.GREATER_THAN_OR_EQUAL)
    .filter("price", max_price, FilterOperator.LESS_THAN_OR_EQUAL)
    .sort("price", SortOrder.ASC)
    .paginate(page=1, page_size=20)
    .all()
```

### Multi-table Operation

```python
@transactional
def create_order(session, order_data):
    order = order_repo.create(session, order_data)

    for item in order_data["items"]:
        item_repo.create(session, {
            **item,
            "order_id": order.id
        })

    return order
```

### Bulk Update/Delete

```python
# Update all matching
repo.update_by_filter(
    db,
    filters={"is_active": False},
    update_data={"archived": True}
)

# Delete all matching
repo.delete_by_filter(
    db,
    filters={"stock": 0, "is_active": False}
)
```

## 🔍 FastAPI Integration

```python
@router.get("/items")
def get_items(
    q: str = None,
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db_session)
):
    query = QueryBuilder(Item, db)

    if q:
        query.filter("name", f"%{q}%", FilterOperator.ILIKE)

    return query.offset(skip).limit(limit).all()
```

## ⚡ Performance Tips

1. **Use pagination** - Always limit results
2. **Index fields** - Index commonly filtered/sorted fields
3. **Bulk operations** - Use `bulk_create` for multiple inserts
4. **Lazy loading** - Use `.first()` instead of `.all()[0]`
5. **Count smart** - Use `.count()` instead of `len(.all())`

## 🐛 Common Mistakes

❌ **Don't:**

```python
# Don't fetch all then count
count = len(repo.get_all(db))

# Don't use multiple sessions
session1 = ...
session2 = ...
```

✅ **Do:**

```python
# Use count method
count = repo.count(db)

# Use single session
with get_db_session() as db:
    # all operations
```

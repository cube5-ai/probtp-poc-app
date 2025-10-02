"""
Usage examples for database utilities
Demonstrates how to use CRUD operations, query builder, and transaction manager
"""
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from datetime import datetime

from app.utils import (
    Base,
    CRUDRepository,
    QueryBuilder,
    FilterOperator,
    SortOrder,
    get_db_session,
    transactional,
)


# Example model
class Product(Base):
    """Example product model"""
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String)
    price = Column(Float)
    stock = Column(Integer)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ============= CRUD Repository Examples =============

def example_crud_operations():
    """Example: Using CRUDRepository for basic CRUD operations"""
    
    # Initialize repository for Product model
    product_repo = CRUDRepository(Product)
    
    # Get database session
    with get_db_session() as db:
        
        # CREATE - Add a new product
        new_product = product_repo.create(db, {
            "name": "Laptop",
            "description": "High-performance laptop",
            "price": 1299.99,
            "stock": 50,
            "is_active": True
        })
        print(f"Created product: {new_product.name}")
        
        # READ - Get product by ID
        product = product_repo.get_by_id(db, new_product.id)
        print(f"Retrieved product: {product.name}")
        
        # READ - Get product by field
        product = product_repo.get_by_field(db, "name", "Laptop")
        print(f"Found product by name: {product.name}")
        
        # READ - Get all products with pagination
        all_products = product_repo.get_all(db, skip=0, limit=10)
        print(f"Total products: {len(all_products)}")
        
        # READ - Get products by filters
        active_products = product_repo.get_multi_by_filter(
            db,
            filters={"is_active": True},
            skip=0,
            limit=100
        )
        print(f"Active products: {len(active_products)}")
        
        # UPDATE - Update product
        updated_product = product_repo.update(
            db,
            new_product.id,
            {"price": 1199.99, "stock": 45}
        )
        print(f"Updated product price: {updated_product.price}")
        
        # UPDATE - Bulk update by filter
        updated_count = product_repo.update_by_filter(
            db,
            filters={"is_active": False},
            update_data={"stock": 0}
        )
        print(f"Updated {updated_count} inactive products")
        
        # DELETE - Delete product
        deleted = product_repo.delete(db, new_product.id)
        print(f"Product deleted: {deleted}")
        
        # DELETE - Bulk delete by filter
        deleted_count = product_repo.delete_by_filter(
            db,
            filters={"stock": 0}
        )
        print(f"Deleted {deleted_count} out-of-stock products")
        
        # CHECK - Check if product exists
        exists = product_repo.exists(db, new_product.id)
        print(f"Product exists: {exists}")
        
        # COUNT - Count products
        total = product_repo.count(db)
        active_count = product_repo.count(db, filters={"is_active": True})
        print(f"Total: {total}, Active: {active_count}")
        
        # BULK CREATE - Create multiple products
        products_data = [
            {"name": "Mouse", "price": 29.99, "stock": 100},
            {"name": "Keyboard", "price": 79.99, "stock": 75},
            {"name": "Monitor", "price": 299.99, "stock": 30}
        ]
        created_products = product_repo.bulk_create(db, products_data)
        print(f"Bulk created {len(created_products)} products")


# ============= Query Builder Examples =============

def example_query_builder():
    """Example: Using QueryBuilder for complex queries"""
    
    with get_db_session() as db:
        
        # Simple filter
        products = (
            QueryBuilder(Product, db)
            .filter("is_active", True)
            .all()
        )
        print(f"Active products: {len(products)}")
        
        # Multiple filters
        products = (
            QueryBuilder(Product, db)
            .filter("price", 100, FilterOperator.GREATER_THAN)
            .filter("stock", 0, FilterOperator.GREATER_THAN)
            .all()
        )
        print(f"Products > $100 in stock: {len(products)}")
        
        # LIKE search
        products = (
            QueryBuilder(Product, db)
            .filter("name", "%Laptop%", FilterOperator.LIKE)
            .all()
        )
        print(f"Products matching 'Laptop': {len(products)}")
        
        # IN operator
        products = (
            QueryBuilder(Product, db)
            .filter("id", [1, 2, 3], FilterOperator.IN)
            .all()
        )
        print(f"Products with IDs 1, 2, 3: {len(products)}")
        
        # BETWEEN operator
        products = (
            QueryBuilder(Product, db)
            .filter("price", (50, 200), FilterOperator.BETWEEN)
            .all()
        )
        print(f"Products priced between $50-$200: {len(products)}")
        
        # OR conditions
        products = (
            QueryBuilder(Product, db)
            .filter_or([
                ("name", "%Laptop%", FilterOperator.LIKE),
                ("name", "%Desktop%", FilterOperator.LIKE),
            ])
            .all()
        )
        print(f"Laptops or Desktops: {len(products)}")
        
        # Sorting
        products = (
            QueryBuilder(Product, db)
            .filter("is_active", True)
            .sort("price", SortOrder.DESC)
            .all()
        )
        print(f"Active products sorted by price DESC: {len(products)}")
        
        # Pagination
        products = (
            QueryBuilder(Product, db)
            .filter("is_active", True)
            .sort("created_at", SortOrder.DESC)
            .paginate(page=1, page_size=10)
            .all()
        )
        print(f"Page 1 products (10 per page): {len(products)}")
        
        # Complex query with multiple operations
        products = (
            QueryBuilder(Product, db)
            .filter("is_active", True)
            .filter("price", 50, FilterOperator.GREATER_THAN_OR_EQUAL)
            .filter("stock", 10, FilterOperator.GREATER_THAN)
            .sort("price", SortOrder.ASC)
            .limit(5)
            .all()
        )
        print(f"Top 5 cheapest available products: {len(products)}")
        
        # Get single result
        product = (
            QueryBuilder(Product, db)
            .filter("name", "Laptop")
            .first()
        )
        if product:
            print(f"Found product: {product.name}")
        
        # Count
        count = (
            QueryBuilder(Product, db)
            .filter("price", 100, FilterOperator.LESS_THAN)
            .count()
        )
        print(f"Products under $100: {count}")
        
        # Check existence
        exists = (
            QueryBuilder(Product, db)
            .filter("name", "Laptop")
            .exists()
        )
        print(f"Laptop exists: {exists}")


# ============= Transaction Examples =============

@transactional
def example_transactional_decorator(session):
    """Example: Using @transactional decorator"""
    
    product_repo = CRUDRepository(Product)
    
    # Create product
    product = product_repo.create(session, {
        "name": "Transactional Product",
        "price": 99.99,
        "stock": 10
    })
    
    # Update product
    product_repo.update(session, product.id, {"stock": 5})
    
    # If any error occurs, all changes will be rolled back
    return product


def example_manual_transaction():
    """Example: Manual transaction management"""
    from app.utils import TransactionManager
    
    with get_db_session() as db:
        tx_manager = TransactionManager(db)
        
        with tx_manager.transaction() as session:
            product_repo = CRUDRepository(Product)
            
            # Create multiple products
            product_repo.create(session, {
                "name": "Product 1",
                "price": 10.00,
                "stock": 100
            })
            
            product_repo.create(session, {
                "name": "Product 2",
                "price": 20.00,
                "stock": 200
            })
            
            # All operations committed together


def example_batch_operations():
    """Example: Batch operations with transaction"""
    from app.utils import BatchOperationManager
    
    with get_db_session() as db:
        batch = BatchOperationManager(db)
        product_repo = CRUDRepository(Product)
        
        # Add operations to batch
        batch.add_operation(
            lambda s: product_repo.create(s, {"name": "Batch 1", "price": 5.00, "stock": 50})
        )
        batch.add_operation(
            lambda s: product_repo.create(s, {"name": "Batch 2", "price": 10.00, "stock": 100})
        )
        batch.add_operation(
            lambda s: product_repo.create(s, {"name": "Batch 3", "price": 15.00, "stock": 150})
        )
        
        # Execute all at once
        results = batch.execute_all()
        print(f"Batch created {len(results)} products")


# ============= Real-World Example =============

def example_real_world_scenario():
    """Example: Real-world e-commerce scenario"""
    
    product_repo = CRUDRepository(Product)
    
    with get_db_session() as db:
        
        # Search for products with filters
        search_term = "laptop"
        min_price = 500
        max_price = 2000
        
        results = (
            QueryBuilder(Product, db)
            .filter("name", f"%{search_term}%", FilterOperator.ILIKE)
            .filter("price", (min_price, max_price), FilterOperator.BETWEEN)
            .filter("is_active", True)
            .filter("stock", 0, FilterOperator.GREATER_THAN)
            .sort("price", SortOrder.ASC)
            .paginate(page=1, page_size=20)
            .all()
        )
        
        print(f"Search results: {len(results)} products")
        
        for product in results:
            print(f"- {product.name}: ${product.price} ({product.stock} in stock)")
        
        # Update stock for purchased items
        if results:
            first_product = results[0]
            updated = product_repo.update(
                db,
                first_product.id,
                {"stock": first_product.stock - 1}
            )
            print(f"Updated stock for {updated.name}: {updated.stock}")
        
        # Get low stock products
        low_stock = (
            QueryBuilder(Product, db)
            .filter("stock", 10, FilterOperator.LESS_THAN_OR_EQUAL)
            .filter("stock", 0, FilterOperator.GREATER_THAN)
            .filter("is_active", True)
            .sort("stock", SortOrder.ASC)
            .all()
        )
        
        print(f"\nLow stock alert: {len(low_stock)} products")
        for product in low_stock:
            print(f"- {product.name}: {product.stock} remaining")


if __name__ == "__main__":
    # Run examples
    print("=== CRUD Repository Examples ===")
    example_crud_operations()
    
    print("\n=== Query Builder Examples ===")
    example_query_builder()
    
    print("\n=== Real-World Example ===")
    example_real_world_scenario()

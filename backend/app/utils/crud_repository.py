"""
Generic CRUD repository for database operations
Provides reusable create, read, update, delete operations for any model
"""
from typing import TypeVar, Generic, Type, List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.utils.db_session import Base


ModelType = TypeVar("ModelType", bound=Base)


class CRUDRepository(Generic[ModelType]):
    """Generic repository for CRUD operations on database models"""
    
    def __init__(self, model: Type[ModelType]):
        """Initialize repository with a SQLAlchemy model class"""
        self.model = model
    
    def create(self, db: Session, obj_data: Dict[str, Any]) -> ModelType:
        """Create a new record in the database"""
        db_obj = self.model(**obj_data)
        db.add(db_obj)
        db.flush()
        db.refresh(db_obj)
        return db_obj
    
    def get_by_id(self, db: Session, record_id: Any) -> Optional[ModelType]:
        """Retrieve a single record by its primary key ID"""
        return db.query(self.model).filter(self.model.id == record_id).first()
    
    def get_by_field(
        self, 
        db: Session, 
        field_name: str, 
        field_value: Any
    ) -> Optional[ModelType]:
        """Retrieve a single record by any field name and value"""
        return db.query(self.model).filter(
            getattr(self.model, field_name) == field_value
        ).first()
    
    def get_all(
        self, 
        db: Session, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[ModelType]:
        """Retrieve all records with pagination"""
        return db.query(self.model).offset(skip).limit(limit).all()
    
    def get_multi_by_filter(
        self,
        db: Session,
        filters: Dict[str, Any],
        skip: int = 0,
        limit: int = 100
    ) -> List[ModelType]:
        """Retrieve multiple records matching filter criteria"""
        query = db.query(self.model)
        
        for field_name, field_value in filters.items():
            if hasattr(self.model, field_name):
                query = query.filter(getattr(self.model, field_name) == field_value)
        
        return query.offset(skip).limit(limit).all()
    
    def update(
        self, 
        db: Session, 
        record_id: Any, 
        update_data: Dict[str, Any]
    ) -> Optional[ModelType]:
        """Update an existing record by ID"""
        db_obj = self.get_by_id(db, record_id)
        
        if not db_obj:
            return None
        
        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        
        db.flush()
        db.refresh(db_obj)
        return db_obj
    
    def update_by_filter(
        self,
        db: Session,
        filters: Dict[str, Any],
        update_data: Dict[str, Any]
    ) -> int:
        """Update multiple records matching filter criteria"""
        query = db.query(self.model)
        
        for field_name, field_value in filters.items():
            if hasattr(self.model, field_name):
                query = query.filter(getattr(self.model, field_name) == field_value)
        
        count = query.update(update_data, synchronize_session=False)
        db.flush()
        return count
    
    def delete(self, db: Session, record_id: Any) -> bool:
        """Delete a record by ID"""
        db_obj = self.get_by_id(db, record_id)
        
        if not db_obj:
            return False
        
        db.delete(db_obj)
        db.flush()
        return True
    
    def delete_by_filter(
        self,
        db: Session,
        filters: Dict[str, Any]
    ) -> int:
        """Delete multiple records matching filter criteria"""
        query = db.query(self.model)
        
        for field_name, field_value in filters.items():
            if hasattr(self.model, field_name):
                query = query.filter(getattr(self.model, field_name) == field_value)
        
        count = query.delete(synchronize_session=False)
        db.flush()
        return count
    
    def exists(self, db: Session, record_id: Any) -> bool:
        """Check if a record exists by ID"""
        return db.query(self.model).filter(self.model.id == record_id).first() is not None
    
    def count(self, db: Session, filters: Dict[str, Any] = None) -> int:
        """Count records, optionally with filters"""
        query = db.query(self.model)
        
        if filters:
            for field_name, field_value in filters.items():
                if hasattr(self.model, field_name):
                    query = query.filter(getattr(self.model, field_name) == field_value)
        
        return query.count()
    
    def bulk_create(self, db: Session, objects_data: List[Dict[str, Any]]) -> List[ModelType]:
        """Create multiple records in bulk"""
        db_objects = [self.model(**obj_data) for obj_data in objects_data]
        db.add_all(db_objects)
        db.flush()
        
        for obj in db_objects:
            db.refresh(obj)
        
        return db_objects

"""
Database query builder utility
Provides dynamic query construction with filters, sorting, and pagination
"""
from typing import Any, Dict, List, Optional, Type, Tuple
from enum import Enum

from sqlalchemy import asc, desc, and_, or_, not_
from sqlalchemy.orm import Query, Session

from app.utils.db_session import Base


class FilterOperator(str, Enum):
    """Supported filter operators for query building"""
    EQUALS = "eq"
    NOT_EQUALS = "ne"
    GREATER_THAN = "gt"
    GREATER_THAN_OR_EQUAL = "gte"
    LESS_THAN = "lt"
    LESS_THAN_OR_EQUAL = "lte"
    LIKE = "like"
    ILIKE = "ilike"
    IN = "in"
    NOT_IN = "not_in"
    IS_NULL = "is_null"
    IS_NOT_NULL = "is_not_null"
    BETWEEN = "between"


class SortOrder(str, Enum):
    """Sort order options"""
    ASC = "asc"
    DESC = "desc"


class QueryBuilder:
    """Dynamic query builder for flexible database queries"""
    
    def __init__(self, model: Type[Base], session: Session):
        """Initialize query builder with model and session"""
        self.model = model
        self.session = session
        self._query = session.query(model)
    
    def filter(
        self, 
        field: str, 
        value: Any, 
        operator: FilterOperator = FilterOperator.EQUALS
    ) -> 'QueryBuilder':
        """Add a filter condition to the query"""
        if not hasattr(self.model, field):
            return self
        
        column = getattr(self.model, field)
        
        if operator == FilterOperator.EQUALS:
            self._query = self._query.filter(column == value)
        elif operator == FilterOperator.NOT_EQUALS:
            self._query = self._query.filter(column != value)
        elif operator == FilterOperator.GREATER_THAN:
            self._query = self._query.filter(column > value)
        elif operator == FilterOperator.GREATER_THAN_OR_EQUAL:
            self._query = self._query.filter(column >= value)
        elif operator == FilterOperator.LESS_THAN:
            self._query = self._query.filter(column < value)
        elif operator == FilterOperator.LESS_THAN_OR_EQUAL:
            self._query = self._query.filter(column <= value)
        elif operator == FilterOperator.LIKE:
            self._query = self._query.filter(column.like(value))
        elif operator == FilterOperator.ILIKE:
            self._query = self._query.filter(column.ilike(value))
        elif operator == FilterOperator.IN:
            self._query = self._query.filter(column.in_(value))
        elif operator == FilterOperator.NOT_IN:
            self._query = self._query.filter(~column.in_(value))
        elif operator == FilterOperator.IS_NULL:
            self._query = self._query.filter(column.is_(None))
        elif operator == FilterOperator.IS_NOT_NULL:
            self._query = self._query.filter(column.isnot(None))
        elif operator == FilterOperator.BETWEEN:
            if isinstance(value, (list, tuple)) and len(value) == 2:
                self._query = self._query.filter(column.between(value[0], value[1]))
        
        return self
    
    def filter_multi(self, filters: Dict[str, Any]) -> 'QueryBuilder':
        """Add multiple filter conditions using dictionary"""
        for field, value in filters.items():
            self.filter(field, value)
        return self
    
    def filter_or(self, conditions: List[Tuple[str, Any, FilterOperator]]) -> 'QueryBuilder':
        """Add OR filter conditions"""
        or_conditions = []
        
        for field, value, operator in conditions:
            if hasattr(self.model, field):
                column = getattr(self.model, field)
                
                if operator == FilterOperator.EQUALS:
                    or_conditions.append(column == value)
                elif operator == FilterOperator.NOT_EQUALS:
                    or_conditions.append(column != value)
                elif operator == FilterOperator.GREATER_THAN:
                    or_conditions.append(column > value)
                elif operator == FilterOperator.LIKE:
                    or_conditions.append(column.like(value))
                elif operator == FilterOperator.ILIKE:
                    or_conditions.append(column.ilike(value))
                elif operator == FilterOperator.IN:
                    or_conditions.append(column.in_(value))
        
        if or_conditions:
            self._query = self._query.filter(or_(*or_conditions))
        
        return self
    
    def sort(self, field: str, order: SortOrder = SortOrder.ASC) -> 'QueryBuilder':
        """Add sorting to the query"""
        if hasattr(self.model, field):
            column = getattr(self.model, field)
            if order == SortOrder.DESC:
                self._query = self._query.order_by(desc(column))
            else:
                self._query = self._query.order_by(asc(column))
        return self
    
    def paginate(self, page: int = 1, page_size: int = 10) -> 'QueryBuilder':
        """Add pagination to the query"""
        skip = (page - 1) * page_size
        self._query = self._query.offset(skip).limit(page_size)
        return self
    
    def limit(self, limit: int) -> 'QueryBuilder':
        """Add limit to the query"""
        self._query = self._query.limit(limit)
        return self
    
    def offset(self, offset: int) -> 'QueryBuilder':
        """Add offset to the query"""
        self._query = self._query.offset(offset)
        return self
    
    def all(self) -> List[Base]:
        """Execute query and return all results"""
        return self._query.all()
    
    def first(self) -> Optional[Base]:
        """Execute query and return first result"""
        return self._query.first()
    
    def one(self) -> Base:
        """Execute query and return exactly one result"""
        return self._query.one()
    
    def count(self) -> int:
        """Return count of matching records"""
        return self._query.count()
    
    def exists(self) -> bool:
        """Check if any records match the query"""
        return self._query.first() is not None
    
    def get_query(self) -> Query:
        """Get the underlying SQLAlchemy query object"""
        return self._query

"""
Database transaction manager
Handles complex multi-step transactions with rollback support
"""
from contextlib import contextmanager
from typing import Callable, Any, Optional, Generator
from functools import wraps

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.utils.db_session import get_session_manager


class TransactionManager:
    """Manages database transactions with automatic rollback on errors"""
    
    def __init__(self, session: Session):
        """Initialize transaction manager with database session"""
        self.session = session
    
    @contextmanager
    def transaction(self) -> Generator[Session, None, None]:
        """Context manager for handling database transactions"""
        try:
            yield self.session
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
    
    def execute_in_transaction(
        self, 
        operation: Callable[[Session], Any]
    ) -> Any:
        """Execute a database operation within a transaction"""
        try:
            result = operation(self.session)
            self.session.commit()
            return result
        except Exception:
            self.session.rollback()
            raise
    
    def execute_batch_operations(
        self,
        operations: list[Callable[[Session], Any]]
    ) -> list[Any]:
        """Execute multiple operations in a single transaction"""
        results = []
        
        try:
            for operation in operations:
                result = operation(self.session)
                results.append(result)
            
            self.session.commit()
            return results
        except Exception:
            self.session.rollback()
            raise


def transactional(func: Callable) -> Callable:
    """Decorator to wrap a function in a database transaction"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        # Try to find session in args or kwargs
        session = None
        
        # Check if first arg is a Session
        if args and isinstance(args[0], Session):
            session = args[0]
        # Check if 'db' or 'session' in kwargs
        elif 'db' in kwargs and isinstance(kwargs['db'], Session):
            session = kwargs['db']
        elif 'session' in kwargs and isinstance(kwargs['session'], Session):
            session = kwargs['session']
        
        if session:
            # Use existing session with transaction
            try:
                result = func(*args, **kwargs)
                session.commit()
                return result
            except Exception:
                session.rollback()
                raise
        else:
            # Create new session for transaction
            session_manager = get_session_manager()
            with session_manager.session_scope() as new_session:
                # Replace or add session in kwargs
                if 'db' in kwargs:
                    kwargs['db'] = new_session
                elif 'session' in kwargs:
                    kwargs['session'] = new_session
                else:
                    kwargs['session'] = new_session
                
                return func(*args, **kwargs)
    
    return wrapper


class BatchOperationManager:
    """Manages batch database operations with transaction support"""
    
    def __init__(self, session: Session):
        """Initialize batch operation manager"""
        self.session = session
        self.operations = []
    
    def add_operation(self, operation: Callable[[Session], Any]) -> 'BatchOperationManager':
        """Add an operation to the batch"""
        self.operations.append(operation)
        return self
    
    def execute_all(self) -> list[Any]:
        """Execute all batched operations in a single transaction"""
        results = []
        
        try:
            for operation in self.operations:
                result = operation(self.session)
                results.append(result)
            
            self.session.commit()
            self.operations.clear()
            return results
        except Exception:
            self.session.rollback()
            self.operations.clear()
            raise
    
    def clear(self) -> 'BatchOperationManager':
        """Clear all pending operations"""
        self.operations.clear()
        return self

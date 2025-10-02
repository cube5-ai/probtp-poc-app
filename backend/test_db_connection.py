#!/usr/bin/env python3
"""
Database connection test script for Google Cloud SQL
"""
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from app.core.config import get_settings


def test_database_connection():
    """Test the database connection using the configured DATABASE_URL"""
    try:
        # Get settings to access DATABASE_URL
        # Using localhost since Cloud SQL Proxy is running on port 5433
        database_url = "postgresql://probtp-poc_user:X0i7!W0e3/CIgg@localhost:5433/probtp-poc_prod"
        
        print(f"Testing database connection...")
        print(f"Database URL: {database_url[:50]}...")  # Show first 50 chars for security
        
        # Create database engine with connection timeout
        engine = create_engine(database_url, connect_args={"connect_timeout": 10})
        
        # Test the connection
        with engine.connect() as connection:
            # Execute a simple query to test the connection
            result = connection.execute(text("SELECT 1 as test_query"))
            test_value = result.fetchone()[0]
            
            if test_value == 1:
                print("✅ Database connection successful!")
                print(f"Test query returned: {test_value}")
                
                # Get database version info
                try:
                    version_result = connection.execute(text("SELECT version()"))
                    version = version_result.fetchone()[0]
                    print(f"Database version: {version}")
                except Exception as e:
                    print(f"Could not retrieve version info: {e}")
                
                # Get current database name
                try:
                    db_name_result = connection.execute(text("SELECT current_database()"))
                    db_name = db_name_result.fetchone()[0]
                    print(f"Connected to database: {db_name}")
                except Exception as e:
                    print(f"Could not retrieve database name: {e}")
                
                return True
            else:
                print(f"❌ Unexpected test query result: {test_value}")
                return False
                
    except SQLAlchemyError as e:
        print(f"❌ Database connection failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def main():
    """Main function to run the database connection test"""
    print("=" * 50)
    print("Google Cloud SQL Connection Test")
    print("=" * 50)
    
    # Check if DATABASE_URL is set
    # if not os.getenv("DATABASE_URL"):
    #     print("❌ DATABASE_URL environment variable is not set!")
    #     print("Please set DATABASE_URL in your .env file or environment variables.")
    #     sys.exit(1)
    
    success = test_database_connection()
    
    print("=" * 50)
    if success:
        print("🎉 Database connection test completed successfully!")
        sys.exit(0)
    else:
        print("💥 Database connection test failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()

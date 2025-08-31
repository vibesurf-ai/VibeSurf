"""
Database Initialization and Migration Scripts - Simplified

Handles database schema creation for Task, LLMProfile, and UploadedFile tables.
"""

import asyncio
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..database.models import Base

async def init_database(database_url: str = "sqlite+aiosqlite:///./vibe_surf.db") -> bool:
    """
    Initialize the database with Task, LLMProfile, and UploadedFile tables and indexes.
    
    Args:
        database_url: Database connection URL
        
    Returns:
        bool: True if initialization was successful
    """
    try:
        # Create async engine
        engine = create_async_engine(
            database_url,
            echo=False,
            future=True,
            pool_pre_ping=True
        )
        
        # Create all tables
        success = await create_tables(engine)
        
        if success:
            print("✅ Database initialized successfully")
            print(f"📍 Database URL: {database_url}")
            
            # Print table information
            await print_table_info(engine)
        else:
            print("❌ Database initialization failed")
        
        await engine.dispose()
        return success
        
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        return False

async def create_tables(engine: AsyncEngine) -> bool:
    """
    Create all tables (Task, LLMProfile, UploadedFile) and indexes.
    
    Args:
        engine: SQLAlchemy async engine
        
    Returns:
        bool: True if creation was successful
    """
    try:
        async with engine.begin() as conn:
            # Create all tables (Task, LLMProfile, UploadedFile)
            await conn.run_sync(Base.metadata.create_all)
            
            # Create additional indexes for performance
            await create_performance_indexes(conn)
            
        print("✅ Database tables created successfully")
        return True
        
    except SQLAlchemyError as e:
        print(f"❌ Error creating tables: {e}")
        return False

async def drop_tables(engine: AsyncEngine) -> bool:
    """
    Drop all database tables (use with caution).
    
    Args:
        engine: SQLAlchemy async engine
        
    Returns:
        bool: True if drop was successful
    """
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            
        print("✅ Database tables dropped successfully")
        return True
        
    except SQLAlchemyError as e:
        print(f"❌ Error dropping tables: {e}")
        return False

async def create_performance_indexes(conn):
    """
    Create additional performance indexes for all tables.
    
    Args:
        conn: Database connection
    """
    # Performance indexes for all tables
    indexes = [
        # Tasks - for session task tracking
        "CREATE INDEX IF NOT EXISTS idx_tasks_session_status ON tasks(session_id, status)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_session_created ON tasks(session_id, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_status_created ON tasks(status, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_completed ON tasks(completed_at DESC)",
        
        # LLMProfile - for profile lookups
        "CREATE INDEX IF NOT EXISTS idx_llm_profiles_name ON llm_profiles(profile_name)",
        "CREATE INDEX IF NOT EXISTS idx_llm_profiles_provider ON llm_profiles(provider)",
        "CREATE INDEX IF NOT EXISTS idx_llm_profiles_created ON llm_profiles(created_at DESC)",
        
        # UploadedFile - for file management
        "CREATE INDEX IF NOT EXISTS idx_uploaded_files_session ON uploaded_files(session_id)",
        "CREATE INDEX IF NOT EXISTS idx_uploaded_files_session_active ON uploaded_files(session_id, is_deleted)",
        "CREATE INDEX IF NOT EXISTS idx_uploaded_files_upload_time ON uploaded_files(upload_time DESC)",
        "CREATE INDEX IF NOT EXISTS idx_uploaded_files_deleted ON uploaded_files(is_deleted, deleted_at)",
        "CREATE INDEX IF NOT EXISTS idx_uploaded_files_filename ON uploaded_files(original_filename)",
    ]
    
    for index_sql in indexes:
        try:
            await conn.execute(text(index_sql))
            print(f"✅ Created index: {index_sql.split('idx_')[1].split(' ')[0]}")
        except Exception as e:
            print(f"⚠️  Index creation warning: {e}")

async def print_table_info(engine: AsyncEngine):
    """
    Print information about created tables.
    
    Args:
        engine: SQLAlchemy async engine
    """
    try:
        async with engine.connect() as conn:
            # Get table list
            if "sqlite" in str(engine.url):
                result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            else:
                result = await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))
            
            tables = [row[0] for row in result]
            
            print(f"\n📊 Created {len(tables)} tables:")
            for table in sorted(tables):
                if not table.startswith('sqlite_'):  # Skip SQLite system tables
                    print(f"   • {table}")
            
            # Get approximate row counts (for SQLite)
            if "sqlite" in str(engine.url):
                print(f"\n📈 Table sizes:")
                for table in sorted(tables):
                    if not table.startswith('sqlite_'):
                        try:
                            count_result = await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                            count = count_result.scalar()
                            print(f"   • {table}: {count} rows")
                        except Exception:
                            print(f"   • {table}: - rows")
    
    except Exception as e:
        print(f"⚠️  Could not retrieve table information: {e}")

async def verify_database_schema(database_url: str = "sqlite+aiosqlite:///./vibe_surf.db") -> bool:
    """
    Verify that the database schema is correctly set up.
    
    Args:
        database_url: Database connection URL
        
    Returns:
        bool: True if schema is valid
    """
    try:
        engine = create_async_engine(database_url, echo=False)
        
        # Expected tables (Task, LLMProfile, UploadedFile)
        expected_tables = ['tasks', 'llm_profiles', 'uploaded_files']
        
        async with engine.connect() as conn:
            # Check if all expected tables exist
            if "sqlite" in str(engine.url):
                result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            else:
                result = await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public'"))
            
            existing_tables = {row[0] for row in result}
            missing_tables = set(expected_tables) - existing_tables
            
            if missing_tables:
                print(f"❌ Missing tables: {missing_tables}")
                await engine.dispose()
                return False
            
            # Test basic operations
            await conn.execute(text("SELECT 1"))
            
        await engine.dispose()
        print("✅ Database schema verification passed")
        return True
        
    except Exception as e:
        print(f"❌ Database schema verification failed: {e}")
        return False

async def reset_database(database_url: str = "sqlite+aiosqlite:///./vibe_surf.db") -> bool:
    """
    Reset the database by dropping and recreating all tables.
    
    Args:
        database_url: Database connection URL
        
    Returns:
        bool: True if reset was successful
    """
    try:
        engine = create_async_engine(database_url, echo=False)
        
        print("🔄 Resetting database...")
        
        # Drop all tables
        if not await drop_tables(engine):
            await engine.dispose()
            return False
        
        # Recreate all tables
        if not await create_tables(engine):
            await engine.dispose()
            return False
        
        await engine.dispose()
        print("✅ Database reset completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Database reset failed: {e}")
        return False

async def migrate_database(database_url: str = "sqlite+aiosqlite:///./vibe_surf.db") -> bool:
    """
    Apply database migrations and updates.
    
    Args:
        database_url: Database connection URL
        
    Returns:
        bool: True if migration was successful
    """
    try:
        engine = create_async_engine(database_url, echo=False)
        
        print("🔄 Running database migrations...")
        
        # For now, this is equivalent to create_tables
        # In the future, this could handle schema updates
        success = await create_tables(engine)
        
        await engine.dispose()
        
        if success:
            print("✅ Database migrations completed successfully")
        else:
            print("❌ Database migrations failed")
            
        return success
        
    except Exception as e:
        print(f"❌ Database migration failed: {e}")
        return False

# CLI functions for direct usage
async def main():
    """Main function for running migrations from command line."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m backend.migrations.init_db [init|reset|verify|migrate]")
        return
    
    command = sys.argv[1]
    database_url = sys.argv[2] if len(sys.argv) > 2 else "sqlite+aiosqlite:///./vibe_surf.db"
    
    if command == "init":
        await init_database(database_url)
    elif command == "reset":
        await reset_database(database_url)
    elif command == "verify":
        await verify_database_schema(database_url)
    elif command == "migrate":
        await migrate_database(database_url)
    else:
        print(f"Unknown command: {command}")
        print("Available commands: init, reset, verify, migrate")

if __name__ == "__main__":
    asyncio.run(main())
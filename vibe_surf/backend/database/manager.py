"""
Database Manager for VibeSurf Session Management

Handles database connections, session management, and initialization
with optimized configuration for real-time operations.
"""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from .models import Base
from typing import AsyncGenerator
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Database connection and session management"""
    
    def __init__(self, database_url: str = None):
        """Initialize database manager
        
        Args:
            database_url: Database connection URL. Defaults to SQLite if not provided.
        """
        from .. import shared_state
        self.database_url = database_url or os.getenv(
            'VIBESURF_DATABASE_URL',
            f'sqlite+aiosqlite:///{os.path.join(shared_state.workspace_dir, "vibe_surf.db")}'
        )
        
        # Configure engine based on database type
        if self.database_url.startswith('sqlite'):
            # SQLite configuration for development
            self.engine = create_async_engine(
                self.database_url,
                poolclass=StaticPool,
                connect_args={
                    "check_same_thread": False,
                    "timeout": 30
                },
                echo=False  # Set to True for SQL debugging
            )
        else:
            # PostgreSQL/MySQL configuration for production
            self.engine = create_async_engine(
                self.database_url,
                pool_size=20,
                max_overflow=30,
                pool_pre_ping=True,
                pool_recycle=3600,
                echo=False
            )
        
        self.async_session_factory = sessionmaker(
            self.engine, 
            class_=AsyncSession, 
            expire_on_commit=False
        )
    
    async def create_tables(self):
        """Create all database tables"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    
    async def drop_tables(self):
        """Drop all database tables"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get async database session"""
        async with self.async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def close(self):
        """Close database connections"""
        await self.engine.dispose()

# Dependency for FastAPI
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions"""
    from .. import shared_state
    
    if not shared_state.db_manager:
        raise RuntimeError("Database manager not initialized. Call initialize_vibesurf_components() first.")
    
    async for session in shared_state.db_manager.get_session():
        yield session

# Database initialization script
async def init_database():
    """Initialize database with tables"""
    from .. import shared_state
    
    logger.info("🗄️ Initializing VibeSurf database...")
    
    try:
        if not shared_state.db_manager:
            raise RuntimeError("Database manager not initialized. Call initialize_vibesurf_components() first.")
            
        await shared_state.db_manager.create_tables()
        logger.info("✅ Database tables created successfully")
        logger.info("✅ VibeSurf database ready for single-task execution")
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise

if __name__ == "__main__":
    # For standalone execution, initialize a temporary db_manager
    import os
    from .. import shared_state
    
    workspace_dir = os.getenv("VIBESURF_WORKSPACE", os.path.join(os.path.dirname(__file__), "../vibesurf_workspace"))
    database_url = os.getenv(
        'VIBESURF_DATABASE_URL',
        f'sqlite+aiosqlite:///{os.path.join(workspace_dir, "vibe_surf.db")}'
    )
    shared_state.db_manager = DatabaseManager(database_url)
    asyncio.run(init_database())
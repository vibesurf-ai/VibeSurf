"""
Database Manager for VibeSurf Session Management

Handles database connections, session management, and initialization
with optimized configuration for real-time operations.
"""

import asyncio
import os
import glob
import pdb
import re
from pathlib import Path
from typing import AsyncGenerator, List, Tuple, Optional
import logging
import aiosqlite
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from .models import Base

from vibe_surf.logger import get_logger

logger = get_logger(__name__)


class DBMigrationManager:
    """Simplified database migration manager."""
    
    def __init__(self, db_path: str = None):
        """Initialize migration manager
        
        Args:
            db_path: Database file path. Will be extracted from database_url if not provided.
        """
        if db_path is None:
            # Extract database path from shared_state
            from .. import shared_state
            database_url = os.getenv(
                'VIBESURF_DATABASE_URL',
                f'sqlite+aiosqlite:///{os.path.join(shared_state.workspace_dir, "vibe_surf.db")}'
            )
            self.db_path = database_url
        else:
            self.db_path = db_path
            
        # Extract path from sqlite URL
        if self.db_path.startswith('sqlite+aiosqlite:///'):
            self.db_path = self.db_path[20:]  # Remove 'sqlite+aiosqlite:///' prefix
        else:
            raise ValueError(f"Migration manager only supports SQLite databases, got: {self.db_path}")
            
        self.migrations_dir = Path(__file__).parent / "migrations"
    
    async def get_db_version(self) -> int:
        """Get current database version."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("PRAGMA user_version;")
                result = await cursor.fetchone()
                return result[0] if result else 0
        except Exception:
            return 0
    
    async def set_db_version(self, version: int) -> None:
        """Set database version."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"PRAGMA user_version = {version};")
            await db.commit()
    
    def get_migration_files(self) -> List[Tuple[int, str]]:
        """Get migration files sorted by version. Returns (version, filepath) tuples."""
        migrations = []
        pattern = str(self.migrations_dir / "v*.sql")
        
        for filepath in glob.glob(pattern):
            filename = os.path.basename(filepath)
            match = re.match(r'v(\d+)_.*\.sql$', filename)
            if match:
                version = int(match.group(1))
                migrations.append((version, filepath))
            else:
                logger.warning(f"Migration file {filename} doesn't match pattern v000_description.sql")
        
        return sorted(migrations, key=lambda x: x[0])
    
    async def init_database(self) -> None:
        """Initialize database directory if needed."""
        db_dir = os.path.dirname(self.db_path)
        os.makedirs(db_dir, exist_ok=True)
        
        current_version = await self.get_db_version()
        
        if current_version == 0:
            logger.info("Database version is 0, will be initialized via migrations...")
        else:
            logger.info(f"Database already exists (version {current_version})")
    
    async def apply_migrations(self, target_version: Optional[int] = None) -> int:
        """Apply pending migrations. Returns final version."""
        await self.init_database()  # Ensure database exists
        
        current_version = await self.get_db_version()
        migrations = self.get_migration_files()
        
        if not migrations:
            logger.info("No migration files found")
            return current_version
        
        if target_version is None:
            target_version = max(m[0] for m in migrations)
        
        logger.info(f"Current version: {current_version}, Target: {target_version}")
        
        if current_version >= target_version:
            logger.info("Database is up to date")
            return current_version
        
        applied = 0
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA foreign_keys = ON;")
            
            for version, filepath in migrations:
                if version <= current_version or version > target_version:
                    continue
                
                try:
                    logger.info(f"Applying migration v{version:03d}: {os.path.basename(filepath)}")
                    
                    with open(filepath, 'r', encoding='utf-8') as f:
                        sql_content = f.read()
                    
                    await db.executescript(sql_content)
                    await self.set_db_version(version)
                    applied += 1
                    
                    logger.info(f"Successfully applied migration v{version:03d}")
                    
                except Exception as e:
                    logger.error(f"Migration v{version:03d} failed: {e}")
                    raise RuntimeError(f"Migration failed at version {version}: {e}")
        
        final_version = await self.get_db_version()
        logger.info(f"Applied {applied} migrations. Final version: {final_version}")
        return final_version


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
        
        # Initialize migration manager for SQLite databases
        if self.database_url.startswith('sqlite'):
            try:
                self.migration_manager = DBMigrationManager(db_path=self.database_url)
            except Exception as e:
                logger.warning(f"Failed to initialize migration manager: {e}")
                self.migration_manager = None
        else:
            self.migration_manager = None
            logger.info("Migration manager is only supported for SQLite databases")

    async def create_tables(self, use_migrations: bool = True):
        """Create all database tables
        
        Args:
            use_migrations: If True, use migration system. If False, use direct table creation.
        """
        if use_migrations and self.migration_manager:
            logger.info("🔄 Using migration system to initialize database...")
            try:
                await self.migration_manager.apply_migrations()
                logger.info("✅ Database initialized via migrations")
                return
            except Exception as e:
                logger.warning(f"Migration failed, falling back to direct table creation: {e}")
        
        # Fallback to direct table creation
        logger.info("🔄 Using direct table creation...")
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Database initialized via direct table creation")

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

    async def apply_migrations(self, target_version: Optional[int] = None) -> int:
        """Apply database migrations
        
        Args:
            target_version: Target migration version. If None, applies all available migrations.
            
        Returns:
            Final database version after applying migrations.
            
        Raises:
            RuntimeError: If migration manager is not available or migration fails.
        """
        if not self.migration_manager:
            raise RuntimeError("Migration manager is not available. Only SQLite databases support migrations.")
        
        return await self.migration_manager.apply_migrations(target_version)
    
    async def get_db_version(self) -> int:
        """Get current database version
        
        Returns:
            Current database version, or 0 if not available.
        """
        if not self.migration_manager:
            logger.warning("Migration manager not available, cannot get database version")
            return 0
        
        return await self.migration_manager.get_db_version()

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

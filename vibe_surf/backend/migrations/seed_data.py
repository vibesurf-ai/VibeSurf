"""
Database Seed Data Scripts - Simplified Single Task Model

Creates sample data for development and testing purposes using the simplified Task table.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List

from ..database.models import Task, TaskStatus
from .. import shared_state

async def seed_sample_tasks(database_url: str = "sqlite+aiosqlite:///./vibe_surf.db") -> bool:
    """
    Seed the database with sample tasks for development.
    
    Args:
        database_url: Database connection URL
        
    Returns:
        bool: True if seeding was successful
    """
    try:
        # Use shared_state db_manager if available, otherwise create temporary one
        if shared_state.db_manager:
            db_manager = shared_state.db_manager
        else:
            from ..database.manager import DatabaseManager
            db_manager = DatabaseManager(database_url)
        
        async for db in db_manager.get_session():
            # Check if data already exists
            result = await db.execute("SELECT COUNT(*) FROM tasks")
            count = result.scalar()
            
            if count > 0:
                print(f"⚠️  Database already contains {count} tasks. Skipping seed data.")
                return True
            
            print("🌱 Seeding sample tasks...")
            
            # Create sample tasks
            tasks = await create_sample_tasks(db)
            
            await db.commit()
            
        print("✅ Sample tasks seeded successfully")
        return True
        
    except Exception as e:
        print(f"❌ Seeding failed: {e}")
        return False

async def create_sample_tasks(db) -> List[Task]:
    """Create sample tasks for testing."""
    
    sample_tasks = [
        Task(
            session_id="session_001",
            task_description="Create a simple web scraper to extract product information from an e-commerce website",
            status=TaskStatus.COMPLETED,
            upload_files_path="./uploads/session_001/requirements.pdf",
            mcp_server_config={
                "exclude_actions": [],
                "max_actions_per_task": 100,
                "display_files_in_done_text": True
            },
            llm_config={
                "model": "gpt-4o-mini",
                "provider": "openai",
                "temperature": 0.1,
                "max_tokens": 4000
            },
            task_result="Successfully created web scraper that extracts product names, prices, and descriptions. Generated 500 product records.",
            report_path="./reports/session_001/scraper_report.html",
            started_at=datetime.now() - timedelta(hours=2),
            completed_at=datetime.now() - timedelta(hours=1),
            task_metadata={
                "execution_duration_seconds": 3600.0,
                "total_actions": 45,
                "created_via": "api"
            }
        ),
        Task(
            session_id="session_002",
            task_description="Automate login process for a social media platform and post a scheduled message",
            status=TaskStatus.RUNNING,
            upload_files_path="./uploads/session_002/login_credentials.txt",
            mcp_server_config={
                "exclude_actions": ["dangerous_action"],
                "max_actions_per_task": 50,
                "display_files_in_done_text": True
            },
            llm_config={
                "model": "gpt-4o",
                "provider": "openai",
                "temperature": 0.2,
                "max_tokens": 2000
            },
            started_at=datetime.now() - timedelta(minutes=30),
            task_metadata={
                "created_via": "api",
                "estimated_duration": 1800
            }
        ),
        Task(
            session_id="session_003",
            task_description="Research and compile information about top AI companies and their latest products",
            status=TaskStatus.PENDING,
            mcp_server_config={
                "exclude_actions": [],
                "max_actions_per_task": 200,
                "display_files_in_done_text": True
            },
            llm_config={
                "model": "claude-3-sonnet-20240229",
                "provider": "anthropic",
                "temperature": 0.3,
                "max_tokens": 8000
            },
            task_metadata={
                "created_via": "api",
                "priority": "high"
            }
        ),
        Task(
            session_id="session_004",
            task_description="Fill out and submit an online form with provided customer data",
            status=TaskStatus.FAILED,
            upload_files_path="./uploads/session_004/customer_data.csv",
            mcp_server_config={
                "exclude_actions": [],
                "max_actions_per_task": 30,
                "display_files_in_done_text": True
            },
            llm_config={
                "model": "gpt-3.5-turbo",
                "provider": "openai",
                "temperature": 0.0,
                "max_tokens": 1000
            },
            error_message="Form submission failed due to CAPTCHA protection",
            started_at=datetime.now() - timedelta(hours=6),
            completed_at=datetime.now() - timedelta(hours=5, minutes=45),
            task_metadata={
                "execution_duration_seconds": 900.0,
                "total_actions": 15,
                "created_via": "api",
                "error_recovery_attempts": 3
            }
        ),
        Task(
            session_id="session_005",
            task_description="Monitor a website for price changes and send notifications when target price is reached",
            status=TaskStatus.PAUSED,
            mcp_server_config={
                "exclude_actions": [],
                "max_actions_per_task": 1000,
                "display_files_in_done_text": False
            },
            llm_config={
                "model": "gpt-4o-mini",
                "provider": "openai",
                "temperature": 0.1,
                "max_tokens": 2000
            },
            started_at=datetime.now() - timedelta(hours=12),
            task_metadata={
                "created_via": "api",
                "monitoring_interval": 3600,
                "target_price": 299.99
            }
        )
    ]
    
    for task in sample_tasks:
        db.add(task)
    
    await db.flush()
    return sample_tasks

async def clear_sample_data(database_url: str = "sqlite+aiosqlite:///./vibe_surf.db") -> bool:
    """
    Clear all sample data from the database.
    
    Args:
        database_url: Database connection URL
        
    Returns:
        bool: True if clearing was successful
    """
    try:
        # Use shared_state db_manager if available, otherwise create temporary one
        if shared_state.db_manager:
            db_manager = shared_state.db_manager
        else:
            from ..database.manager import DatabaseManager
            db_manager = DatabaseManager(database_url)
        
        async for db in db_manager.get_session():
            print("🧹 Clearing sample tasks...")
            
            # Delete all tasks
            await db.execute("DELETE FROM tasks")
            await db.commit()
            
        print("✅ Sample data cleared successfully")
        return True
        
    except Exception as e:
        print(f"❌ Clearing sample data failed: {e}")
        return False

# CLI functions
async def main():
    """Main function for running seed operations from command line."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m backend.migrations.seed_data [seed|clear]")
        return
    
    command = sys.argv[1]
    database_url = sys.argv[2] if len(sys.argv) > 2 else "sqlite+aiosqlite:///./vibe_surf.db"
    
    if command == "seed":
        await seed_sample_tasks(database_url)
    elif command == "clear":
        await clear_sample_data(database_url)
    else:
        print(f"Unknown command: {command}")
        print("Available commands: seed, clear")

if __name__ == "__main__":
    asyncio.run(main())
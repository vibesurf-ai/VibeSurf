"""
Shared State Module

Contains global state variables shared between main.py and routers
to avoid circular import issues.
"""
import pdb
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging
import os
import json
import platform
from pathlib import Path

# VibeSurf components
from vibe_surf.agents.vibe_surf_agent import VibeSurfAgent
from vibe_surf.tools.browser_use_tools import BrowserUseTools
from vibe_surf.tools.vibesurf_tools import VibeSurfTools
from vibe_surf.browser.browser_manager import BrowserManager
from browser_use.llm.base import BaseChatModel
from browser_use.llm.openai.chat import ChatOpenAI
from browser_use.browser import BrowserProfile
from vibe_surf.llm.openai_compatible import ChatOpenAICompatible
from vibe_surf.browser.agent_browser_session import AgentBrowserSession
from vibe_surf.browser.agen_browser_profile import AgentBrowserProfile

logger = logging.getLogger(__name__)

# Global VibeSurf components
vibesurf_agent: Optional[VibeSurfAgent] = None
browser_manager: Optional[BrowserManager] = None
vibesurf_tools: Optional[VibeSurfTools] = None
llm: Optional[BaseChatModel] = None
db_manager: Optional['DatabaseManager'] = None
current_llm_profile_name: Optional[str] = None

# Environment variables
workspace_dir: str = ""
browser_execution_path: str = ""
browser_user_data: str = ""

# Global environment variables dictionary
envs: Dict[str, str] = {}

# MCP server management
active_mcp_server: Dict[str, str] = {}  # Dict[mcp_id: mcp_server_name]

# Single task execution tracking
active_task: Optional[Dict[str, Any]] = None


def get_all_components():
    """Get all components as a dictionary"""
    global vibesurf_agent, browser_manager, vibesurf_tools, llm, db_manager, current_llm_profile_name
    global workspace_dir, browser_execution_path, browser_user_data, active_mcp_server, envs

    return {
        "vibesurf_agent": vibesurf_agent,
        "browser_manager": browser_manager,
        "tools": vibesurf_tools,
        "llm": llm,
        "db_manager": db_manager,
        "workspace_dir": workspace_dir,
        "browser_execution_path": browser_execution_path,
        "browser_user_data": browser_user_data,
        "active_mcp_server": active_mcp_server,
        "active_task": active_task,
        "current_llm_profile_name": current_llm_profile_name,
        "envs": envs
    }


def set_components(**kwargs):
    """Update global components"""
    global vibesurf_agent, browser_manager, vibesurf_tools, llm, db_manager, current_llm_profile_name
    global workspace_dir, browser_execution_path, browser_user_data, active_mcp_server, envs

    if "vibesurf_agent" in kwargs:
        vibesurf_agent = kwargs["vibesurf_agent"]
    if "browser_manager" in kwargs:
        browser_manager = kwargs["browser_manager"]
    if "tools" in kwargs:
        vibesurf_tools = kwargs["tools"]
    if "llm" in kwargs:
        llm = kwargs["llm"]
    if "db_manager" in kwargs:
        db_manager = kwargs["db_manager"]
    if "workspace_dir" in kwargs:
        workspace_dir = kwargs["workspace_dir"]
    if "browser_execution_path" in kwargs:
        browser_execution_path = kwargs["browser_execution_path"]
    if "browser_user_data" in kwargs:
        browser_user_data = kwargs["browser_user_data"]
    if "active_mcp_server" in kwargs:
        active_mcp_server = kwargs["active_mcp_server"]
    if "envs" in kwargs:
        envs = kwargs["envs"]
    if "current_llm_profile_name" in kwargs:
        envs = kwargs["current_llm_profile_name"]


async def execute_task_background(
        task_id: str,
        session_id: str,
        task: str,
        llm_profile_name: str,
        upload_files: Optional[List[str]] = None,
        agent_mode: str = "thinking",
        db_session=None
):
    """Background task execution function for single task with LLM profile support"""
    global vibesurf_agent, active_task, current_llm_profile_name

    try:
        current_llm_profile_name = llm_profile_name

        # Check if MCP server configuration needs update
        await _check_and_update_mcp_servers(db_session)

        # Update active task status to running
        active_task = {
            "task_id": task_id,
            "status": "running",
            "session_id": session_id,
            "task": task,
            "llm_profile_name": llm_profile_name,
            "workspace_dir": workspace_dir,
            "upload_files": upload_files or [],
            "active_mcp_servers": list(active_mcp_server.values()),  # List of MCP server names
            "start_time": datetime.now(),
            "agent_id": task_id  # Use task_id as agent_id for tracking
        }

        logger.info(f"Task {task_id} started for session {session_id} with profile {llm_profile_name}")

        # Ensure correct workspace directory is set for this task
        if vibesurf_agent:
            vibesurf_agent.workspace_dir = workspace_dir

        # Execute the task
        result = await vibesurf_agent.run(
            task=task,
            upload_files=upload_files,
            session_id=session_id,
            agent_mode=agent_mode
        )

        # Update task status to completed
        if active_task and active_task.get("status") != "stopped":
            active_task.update({
                "status": "completed",
                "result": result,
                "end_time": datetime.now()
            })

        # Get session directory for report path
        session_dir = os.path.join(workspace_dir, session_id)
        report_path = None

        # Look for generated report
        reports_dir = os.path.join(session_dir, "reports")
        if os.path.exists(reports_dir):
            for file in os.listdir(reports_dir):
                if file.endswith('.html'):
                    report_path = os.path.join(reports_dir, file)
                    break

        # Save task to database
        if db_session:
            try:
                from .database.queries import TaskQueries
                await TaskQueries.update_task_completion(
                    db_session,
                    task_id=task_id,
                    task_result=result,
                    task_status=active_task.get("status", "completed") if active_task else "completed",
                    report_path=report_path
                )
                await db_session.commit()
            except Exception as e:
                logger.error(f"Failed to update task in database: {e}")

        logger.info(f"Task {task_id} completed for session {session_id}")

    except Exception as e:
        logger.error(f"Task execution failed: {e}")
        # Update task status to failed
        if active_task and active_task.get("task_id") == task_id:
            active_task.update({
                "status": "failed",
                "error": str(e),
                "end_time": datetime.now()
            })

        # Save failed task to database
        if db_session:
            try:
                from .database.queries import TaskQueries
                await TaskQueries.update_task_completion(
                    db_session,
                    task_id=task_id,
                    task_result=None,
                    task_status="failed",
                    error_message=str(e)
                )
                await db_session.commit()
            except Exception as e:
                logger.error(f"Failed to save failed task to database: {e}")

        logger.error(f"Task {task_id} failed for session {session_id}: {e}")
    finally:
        # Clear active task when execution is complete (success or failure)
        active_task = None


def is_task_running() -> bool:
    """Quick check if any task is currently running"""
    global active_task
    return active_task is not None and active_task.get("status") not in ["failed",
                                                                         "completed",
                                                                         "stopped"]


def get_active_task_info() -> Optional[Dict[str, Any]]:
    """Get current active task information"""
    global active_task
    return active_task.copy() if active_task else None


def clear_active_task():
    """Clear the active task (used when stopping)"""
    global active_task
    active_task = None


async def _check_and_update_mcp_servers(db_session):
    """Check if MCP server configuration has changed and update tools if needed"""
    global vibesurf_tools, active_mcp_server

    try:
        if not db_session:
            return

        from .database.queries import McpProfileQueries

        # Get current active MCP servers from database
        active_profiles = await McpProfileQueries.get_active_profiles(db_session)
        current_active_servers = {profile.mcp_id: profile.mcp_server_name for profile in active_profiles}

        # Compare with shared state
        if current_active_servers != active_mcp_server:
            logger.info(f"MCP server configuration changed. Updating tools...")
            logger.info(f"Old config: {active_mcp_server}")
            logger.info(f"New config: {current_active_servers}")

            # Update shared state
            active_mcp_server = current_active_servers.copy()

            # Create new MCP server config for tools
            mcp_server_config = await _build_mcp_server_config(active_profiles)

            # Unregister old MCP clients and register new ones
            if vibesurf_tools:
                await vibesurf_tools.unregister_mcp_clients()
                vibesurf_tools.mcp_server_config = mcp_server_config
                await vibesurf_tools.register_mcp_clients()
                logger.info("✅ Controller MCP configuration updated successfully")

    except Exception as e:
        logger.error(f"Failed to check and update MCP servers: {e}")


async def _build_mcp_server_config(active_profiles) -> Dict[str, Any]:
    """Build MCP server configuration from active profiles"""
    mcp_server_config = {
        "mcpServers": {}
    }

    for profile in active_profiles:
        mcp_server_config["mcpServers"][profile.mcp_server_name] = json.loads(profile.mcp_server_params)

    return mcp_server_config


async def _load_active_mcp_servers():
    """Load active MCP servers from database and return config"""
    global db_manager, active_mcp_server

    try:
        if not db_manager:
            logger.info("Database manager not available, returning empty MCP config")
            return {"mcpServers": {}}

        from .database.queries import McpProfileQueries

        async for db in db_manager.get_session():
            try:
                # Get all active MCP profiles
                active_profiles = await McpProfileQueries.get_active_profiles(db)

                # Update shared state
                active_mcp_server = {profile.mcp_id: profile.mcp_server_name for profile in active_profiles}

                # Build MCP server config
                mcp_server_config = await _build_mcp_server_config(active_profiles)

                logger.info(f"✅ Loaded {len(active_profiles)} active MCP servers: {list(active_mcp_server.values())}")

                return mcp_server_config

            except Exception as e:
                logger.warning(f"Failed to load MCP servers from database: {e}")
                return {"mcpServers": {}}
            finally:
                break

    except Exception as e:
        logger.warning(f"Database not available for MCP server loading: {e}")
        return {"mcpServers": {}}


async def initialize_vibesurf_components():
    """Initialize VibeSurf components from environment variables and default LLM profile"""
    global vibesurf_agent, browser_manager, vibesurf_tools, llm, db_manager, current_llm_profile_name
    global workspace_dir, browser_execution_path, browser_user_data, envs
    from vibe_surf import common

    try:
        # Load environment variables
        workspace_dir = common.get_workspace_dir()
        logger.info("WorkSpace directory: {}".format(workspace_dir))

        # Load environment configuration from envs.json
        envs_file_path = os.path.join(workspace_dir, "envs.json")
        try:
            if os.path.exists(envs_file_path):
                with open(envs_file_path, 'r', encoding='utf-8') as f:
                    envs = json.load(f)
                logger.info(f"✅ Loaded environment configuration from {envs_file_path}")
                
                # Set loaded environment variables to system environment
                for key, value in envs.items():
                    if value:  # Only set non-empty values
                        os.environ[key] = value
                        logger.info(f"🔧 Set environment variable: {key}")
            else:
                envs = {}
                logger.info("📝 No existing envs.json found, initializing empty environment configuration")
        except Exception as e:
            logger.warning(f"Failed to load envs.json: {e}, initializing empty environment configuration")
            envs = {}
        browser_execution_path = os.getenv("BROWSER_EXECUTION_PATH", "")
        assert os.path.exists(browser_execution_path), "Please set the BROWSER_EXECUTION_PATH environment variable"
        browser_user_data = os.getenv("BROWSER_USER_DATA", "")
        if not browser_user_data:
            browser_user_data = os.path.join(workspace_dir, "browser_user_data",
                                             f"{os.path.basename(browser_execution_path)}-profile")

        # Get VibeSurf extension path
        vibesurf_extension = os.getenv("VIBESURF_EXTENSION", "")
        if not vibesurf_extension.strip():
            current_file = Path(__file__)
            project_root = current_file.parent.parent.absolute()
            vibesurf_extension = str(project_root / "chrome_extension")
            assert os.path.exists(vibesurf_extension)

        # Get backend URL
        backend_port = os.getenv("VIBESURF_BACKEND_PORT", "9335")
        if not backend_port or not backend_port.strip():
            backend_port = "9335"
        backend_port = int(backend_port)

        backend_url = f'http://127.0.0.1:{backend_port}'

        # Update envs dictionary with current environment variables
        envs.update({
            "BROWSER_EXECUTION_PATH": browser_execution_path,
            "BROWSER_USER_DATA": browser_user_data,
            "VIBESURF_EXTENSION": vibesurf_extension,
            "VIBESURF_BACKEND_URL": backend_url
        })

        # Create directories if they don't exist
        os.makedirs(workspace_dir, exist_ok=True)

        # Initialize database manager after workspace_dir is set
        from .database.manager import DatabaseManager

        # Debug: Check environment variable value
        env_database_url = os.getenv('VIBESURF_DATABASE_URL')
        logger.info(f"🔍 VIBESURF_DATABASE_URL environment variable: '{env_database_url}'")
        logger.info(f"🔍 workspace_dir: '{workspace_dir}'")

        # Handle empty string environment variable properly
        if env_database_url and env_database_url.strip():
            database_url = env_database_url
        else:
            database_url = f'sqlite+aiosqlite:///{os.path.join(workspace_dir, "vibe_surf.db")}'

        logger.info(f"🔍 Final database_url: '{database_url}'")

        db_manager = DatabaseManager(database_url)

        # Initialize database tables with migration support
        await db_manager.create_tables(use_migrations=True)
        logger.info("✅ Database manager initialized successfully")

        # Initialize LLM from default profile (if available) or fallback to environment variables
        llm = await _initialize_default_llm()

        # Initialize browser manager
        if browser_manager:
            main_browser_session = browser_manager.main_browser_session
        else:
            from screeninfo import get_monitors
            primary_monitor = get_monitors()[0]
            _update_extension_backend_url(envs["VIBESURF_EXTENSION"], backend_url)
            
            browser_profile = AgentBrowserProfile(
                executable_path=browser_execution_path,
                user_data_dir=browser_user_data,
                headless=False,
                keep_alive=True,
                auto_download_pdfs=False,
                highlight_elements=True,
                custom_extensions=[envs["VIBESURF_EXTENSION"]],
                window_size={"width": primary_monitor.width, "height": primary_monitor.height}
            )

            # Initialize components
            main_browser_session = AgentBrowserSession(browser_profile=browser_profile)
            await main_browser_session.start()
        browser_manager = BrowserManager(
            main_browser_session=main_browser_session
        )

        # Load active MCP servers from database
        mcp_server_config = await _load_active_mcp_servers()

        # Initialize vibesurf tools with MCP server config
        vibesurf_tools = VibeSurfTools(mcp_server_config=mcp_server_config)

        # Register MCP clients if there are any active MCP servers
        if mcp_server_config and mcp_server_config.get("mcpServers"):
            await vibesurf_tools.register_mcp_clients()
            logger.info(f"✅ Registered {len(mcp_server_config['mcpServers'])} MCP servers")

        # Initialize VibeSurfAgent
        vibesurf_agent = VibeSurfAgent(
            llm=llm,
            browser_manager=browser_manager,
            tools=vibesurf_tools,
            workspace_dir=workspace_dir
        )

        # Save environment configuration to envs.json
        try:
            with open(envs_file_path, 'w', encoding='utf-8') as f:
                json.dump(envs, f, indent=2, ensure_ascii=False)
            logger.info(f"✅ Saved environment configuration to {envs_file_path}")
        except Exception as e:
            logger.warning(f"Failed to save envs.json: {e}")

        logger.info("✅ VibeSurf components initialized successfully")

    except Exception as e:
        logger.error(f"❌ Failed to initialize VibeSurf components: {e}")
        raise


async def _initialize_default_llm():
    """Initialize LLM from default profile or fallback to environment variables"""
    global db_manager, current_llm_profile_name

    try:
        # Try to get default LLM profile from database
        from .database.queries import LLMProfileQueries
        from .utils.llm_factory import create_llm_from_profile

        # Get database session from shared state db_manager
        if db_manager:
            async for db in db_manager.get_session():
                try:
                    default_profile = await LLMProfileQueries.get_default_profile(db)
                    if default_profile:
                        # Get profile with decrypted API key
                        profile_with_key = await LLMProfileQueries.get_profile_with_decrypted_key(
                            db, default_profile.profile_name
                        )
                        if profile_with_key:
                            llm_instance = create_llm_from_profile(profile_with_key)
                            current_llm_profile_name = default_profile.profile_name
                            logger.info(f"✅ LLM initialized from default profile: {default_profile.profile_name}")
                            return llm_instance
                    break
                except Exception as e:
                    logger.warning(f"Failed to load default LLM profile: {e}")
                    break
    except Exception as e:
        logger.warning(f"Database not available for LLM profile loading: {e}")

    # Fallback to environment variables
    logger.info("🔄 Falling back to environment variable LLM configuration")
    return ChatOpenAI(
        model=os.getenv("LLM_MODEL", "gpt-4.1-mini"),
        base_url=os.getenv("OPENAI_ENDPOINT", "https://api.openai.com/v1"),
        api_key=os.getenv("OPENAI_API_KEY", "")
    )


async def update_llm_from_profile(profile_name: str):
    """Update the global LLM instance from a specific profile"""
    global vibesurf_agent, llm, db_manager

    try:
        from .database.queries import LLMProfileQueries
        from .utils.llm_factory import create_llm_from_profile

        # Get database session from shared state db_manager
        if not db_manager:
            raise ValueError("Database manager not initialized")

        async for db in db_manager.get_session():
            try:
                # Get profile with decrypted API key
                profile_with_key = await LLMProfileQueries.get_profile_with_decrypted_key(db, profile_name)
                if not profile_with_key:
                    raise ValueError(f"LLM profile '{profile_name}' not found")

                # Create new LLM instance
                new_llm = create_llm_from_profile(profile_with_key)

                # Update global state
                llm = new_llm
                if vibesurf_agent and vibesurf_agent.token_cost_service:
                    # FIX: Register new LLM with token cost service to maintain tracking
                    vibesurf_agent.llm = vibesurf_agent.token_cost_service.register_llm(new_llm)

                logger.info(f"✅ LLM updated to profile: {profile_name}")
                return True

            except Exception as e:
                logger.error(f"Failed to update LLM from profile {profile_name}: {e}")
                raise
            finally:
                break

    except Exception as e:
        logger.error(f"Database error while updating LLM profile: {e}")
        raise


def get_envs() -> Dict[str, str]:
    """Get the current environment variables dictionary"""
    global envs
    return envs.copy()


def update_envs(updates: Dict[str, str]) -> bool:
    """Update environment variables and save to envs.json"""
    global envs, workspace_dir
    
    try:
        # Update the envs dictionary
        envs.update(updates)
        
        # Save to envs.json
        envs_file_path = os.path.join(workspace_dir, "envs.json")
        with open(envs_file_path, 'w', encoding='utf-8') as f:
            json.dump(envs, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Updated and saved environment variables to {envs_file_path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to update environment variables: {e}")
        return False


def _update_extension_backend_url(extension_path: str, backend_url: str):
    try:
        import re

        config_js_path = os.path.join(extension_path, "config.js")
        if not os.path.exists(config_js_path):
            logger.warning(f"Extension config.js not found at: {config_js_path}")
            return

        with open(config_js_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 匹配 BACKEND_URL: 'xyz' 或 BACKEND_URL: "xyz"，xyz是任意内容
        pattern = r"BACKEND_URL:\s*(['\"]).*?\1"
        replacement = f"BACKEND_URL: '{backend_url}'"

        updated_content = re.sub(pattern, replacement, content)

        with open(config_js_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)

        logger.info(f"✅ Updated extension backend URL to: {backend_url}")

    except Exception as e:
        logger.error(f"❌ Failed to update extension backend URL: {e}")


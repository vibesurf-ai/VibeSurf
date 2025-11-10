"""
Shared State Module

Contains global state variables shared between main.py and routers
to avoid circular import issues.
"""
import pdb
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import logging
import os
import json
import platform
import asyncio
from pathlib import Path
from composio import Composio
from composio_langchain import LangchainProvider
from croniter import croniter
from sqlalchemy import select, update

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
from vibe_surf.backend.utils.utils import configure_system_proxies
from vibe_surf.logger import get_logger

logger = get_logger(__name__)

# Global VibeSurf components
vibesurf_agent: Optional[VibeSurfAgent] = None
browser_manager: Optional[BrowserManager] = None
vibesurf_tools: Optional[VibeSurfTools] = None
llm: Optional[BaseChatModel] = None
db_manager: Optional['DatabaseManager'] = None
current_llm_profile_name: Optional[str] = None
composio_instance: Optional[Any] = None  # Global Composio instance
schedule_manager: Optional['ScheduleManager'] = None  # Global Schedule manager

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
    global workspace_dir, browser_execution_path, browser_user_data, active_mcp_server, envs, composio_instance, schedule_manager

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
        "composio_instance": composio_instance,
        "schedule_manager": schedule_manager,
        "envs": envs
    }


def set_components(**kwargs):
    """Update global components"""
    global vibesurf_agent, browser_manager, vibesurf_tools, llm, db_manager, current_llm_profile_name
    global workspace_dir, browser_execution_path, browser_user_data, active_mcp_server, envs, composio_instance, schedule_manager

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
        current_llm_profile_name = kwargs["current_llm_profile_name"]
    if "composio_instance" in kwargs:
        composio_instance = kwargs["composio_instance"]
    if "schedule_manager" in kwargs:
        schedule_manager = kwargs["schedule_manager"]


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
        
        # Check if Composio tools configuration needs update
        await _check_and_update_composio_tools(db_session)

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


async def _check_and_update_composio_tools(db_session):
    """Check if Composio tools configuration has changed and update tools if needed"""
    global vibesurf_tools, composio_instance

    try:
        if not db_session:
            return

        from .database.queries import ComposioToolkitQueries

        # Get current enabled Composio toolkits from database
        enabled_toolkits = await ComposioToolkitQueries.get_enabled_toolkits(db_session)
        
        # Build toolkit_tools_dict from enabled toolkits
        current_toolkit_tools = {}
        for toolkit in enabled_toolkits:
            if toolkit.tools:
                try:
                    tools_data = json.loads(toolkit.tools)
                    current_toolkit_tools[toolkit.slug] = tools_data
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning(f"Failed to parse tools for toolkit {toolkit.slug}: {e}")

        # Check if Composio tools need to be updated
        tools_changed = False
        if vibesurf_tools and vibesurf_tools.composio_client:
            # Compare current tools with registered tools
            if vibesurf_tools.composio_client._toolkit_tools != current_toolkit_tools:
                tools_changed = True
        elif current_toolkit_tools:
            # No composio client but we have enabled tools - need to register
            tools_changed = True

        if tools_changed:
            logger.info(f"Composio tools configuration changed. Updating tools...")
            logger.info(f"New toolkit tools: {list(current_toolkit_tools.keys())}")

            # Update Composio tools in vibesurf_tools
            if vibesurf_tools:
                await vibesurf_tools.update_composio_tools(
                    composio_instance=composio_instance,
                    toolkit_tools_dict=current_toolkit_tools
                )
                logger.info("✅ Composio tools configuration updated successfully")

    except Exception as e:
        logger.error(f"Failed to check and update Composio tools: {e}")


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

    except Exception as e:
        logger.warning(f"Database not available for MCP server loading: {e}")
        return {"mcpServers": {}}


async def _load_enabled_composio_toolkits():
    """Load enabled Composio toolkits from database and return toolkit_tools_dict"""
    global db_manager

    try:
        if not db_manager:
            logger.info("Database manager not available, returning empty Composio config")
            return {}

        from .database.queries import ComposioToolkitQueries

        async for db in db_manager.get_session():
            try:
                # Get all enabled Composio toolkits
                enabled_toolkits = await ComposioToolkitQueries.get_enabled_toolkits(db)
                
                # Build toolkit_tools_dict from enabled toolkits
                toolkit_tools_dict = {}
                for toolkit in enabled_toolkits:
                    if toolkit.tools:
                        try:
                            tools_data = json.loads(toolkit.tools)
                            toolkit_tools_dict[toolkit.slug] = tools_data
                        except (json.JSONDecodeError, TypeError) as e:
                            logger.warning(f"Failed to parse tools for toolkit {toolkit.slug}: {e}")

                logger.info(f"✅ Loaded {len(toolkit_tools_dict)} enabled Composio toolkits: {list(toolkit_tools_dict.keys())}")

                return toolkit_tools_dict

            except Exception as e:
                logger.warning(f"Failed to load Composio toolkits from database: {e}")
                return {}

    except Exception as e:
        logger.warning(f"Database not available for Composio toolkit loading: {e}")
        return {}


async def load_composio():
    # Load and register Composio tools from enabled toolkits
    global composio_instance
    from .api.composio import _get_composio_api_key_from_db
    api_key = await _get_composio_api_key_from_db()
    if api_key:
        try:
            # Create Composio instance
            composio_instance = Composio(
                api_key=api_key,
                provider=LangchainProvider()
            )
            logger.info("Successfully create Composio instance!")
        except Exception as e:
            logger.error(f"Failed to create Composio instance: {e}")
            composio_instance = None
    toolkit_tools_dict = await _load_enabled_composio_toolkits()
    if toolkit_tools_dict:
        await vibesurf_tools.register_composio_clients(
            composio_instance=composio_instance,
            toolkit_tools_dict=toolkit_tools_dict
        )
        logger.info(f"✅ Registered Composio tools from {len(toolkit_tools_dict)} enabled toolkits")


async def initialize_vibesurf_components():
    """Initialize VibeSurf components from environment variables and default LLM profile"""
    global vibesurf_agent, browser_manager, vibesurf_tools, llm, db_manager, current_llm_profile_name, composio_instance
    global workspace_dir, browser_execution_path, browser_user_data, envs
    from vibe_surf import common

    try:
        # Load environment variables
        workspace_dir = common.get_workspace_dir()
        logger.info("WorkSpace directory: {}".format(workspace_dir))
        configure_system_proxies()
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
        if not browser_user_data or not os.path.exists(browser_user_data):
            browser_user_data = os.path.join(workspace_dir, "browser_user_data",
                                             f"{os.path.basename(browser_execution_path)}-profile")

        # Get VibeSurf extension path
        vibesurf_extension = os.getenv("VIBESURF_EXTENSION", "")
        if not vibesurf_extension.strip() or not os.path.exists(vibesurf_extension):
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

        # Load active MCP servers from database
        mcp_server_config = await _load_active_mcp_servers()

        # Initialize vibesurf tools with MCP server config
        vibesurf_tools = VibeSurfTools(mcp_server_config=mcp_server_config)

        # Register MCP clients if there are any active MCP servers
        if mcp_server_config and mcp_server_config.get("mcpServers"):
            await vibesurf_tools.register_mcp_clients()
            logger.info(f"✅ Registered {len(mcp_server_config['mcpServers'])} MCP servers")

        load_composio_task = asyncio.create_task(load_composio())

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

        pattern = r"BACKEND_URL:\s*(['\"]).*?\1"
        replacement = f"BACKEND_URL: '{backend_url}'"

        updated_content = re.sub(pattern, replacement, content)

        with open(config_js_path, 'w', encoding='utf-8') as f:
            f.write(updated_content)

        logger.info(f"✅ Updated extension backend URL to: {backend_url}")

    except Exception as e:
        logger.error(f"❌ Failed to update extension backend URL: {e}")


class ScheduleManager:
    """Manager for handling scheduled workflow execution"""
    
    def __init__(self):
        self.schedules = {}  # Dict[flow_id, schedule_dict]
        self.running = False
        self.check_interval = 60  # Check every minute
        self._task = None
        
    async def start(self):
        """Start the schedule manager"""
        if self.running:
            return
            
        self.running = True
        await self.reload_schedules()
        self._task = asyncio.create_task(self._schedule_loop())
        logger.info("✅ Schedule manager started")
    
    async def stop(self):
        """Stop the schedule manager"""
        self.running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Schedule manager stopped")
    
    async def reload_schedules(self):
        """Reload schedules from the database"""
        try:
            global db_manager
            if not db_manager:
                logger.warning("Database manager not available for schedule reload")
                return

            logger.debug("Starting schedule reload from database...")
            async for session in db_manager.get_session():
                logger.debug("Successfully obtained database session")
                
                # Import Schedule model
                from .database.models import Schedule
                
                # Use SQLAlchemy ORM query
                result = await session.execute(
                    select(Schedule).where(
                        (Schedule.is_enabled == True) &
                        (Schedule.cron_expression.isnot(None))
                    )
                )
                schedules = result.scalars().all()
                logger.debug(f"Found {len(schedules)} enabled schedules in database")
                
                self.schedules = {}
                for schedule in schedules:
                    logger.info(f"Loading flow: {schedule.flow_id} into schedule")
                    schedule_dict = {
                        'id': schedule.id,
                        'flow_id': schedule.flow_id,
                        'cron_expression': schedule.cron_expression,
                        'is_enabled': schedule.is_enabled,
                        'description': schedule.description,
                        'last_execution_at': schedule.last_execution_at,
                        'next_execution_at': schedule.next_execution_at,
                        'execution_count': schedule.execution_count,
                        'created_at': schedule.created_at,
                        'updated_at': schedule.updated_at
                    }
                    self.schedules[schedule.flow_id] = schedule_dict
                
                logger.info(f"✅ Successfully reloaded {len(self.schedules)} active schedules")
                break  # Exit after processing to avoid multiple iterations
                
        except Exception as e:
            logger.error(f"❌ Failed to reload schedules: {e}")
            # Log the stack trace for debugging
            import traceback
            logger.error(f"Schedule reload traceback: {traceback.format_exc()}")
    
    async def _schedule_loop(self):
        """Main schedule checking loop"""
        while self.running:
            try:
                await self._check_and_execute_schedules()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in schedule loop: {e}")
                await asyncio.sleep(self.check_interval)
    
    async def _check_and_execute_schedules(self):
        """Check for schedules that need to be executed"""
        now = datetime.now(timezone.utc)
        
        for flow_id, schedule in self.schedules.items():
            try:
                # Check if it's time to execute this schedule
                if await self._should_execute_schedule(schedule, now):
                    await self._execute_scheduled_flow(flow_id, schedule)
                    
            except Exception as e:
                logger.error(f"Error checking schedule for flow {flow_id}: {e}")
    
    async def _should_execute_schedule(self, schedule: dict, now: datetime) -> bool:
        """Check if a schedule should be executed now"""
        try:
            cron_expr = schedule.get('cron_expression')
            if not cron_expr:
                return False
            
            # Check if we have a next execution time
            next_execution_str = schedule.get('next_execution_at')
            if not next_execution_str:
                # Calculate and update next execution time
                await self._update_next_execution_time(schedule['flow_id'], cron_expr)
                return False
            
            # Parse next execution time
            if isinstance(next_execution_str, str):
                next_execution = datetime.fromisoformat(next_execution_str.replace('Z', '+00:00'))
            else:
                next_execution = next_execution_str
                
            # Make sure next_execution is timezone-aware
            if next_execution.tzinfo is None:
                next_execution = next_execution.replace(tzinfo=timezone.utc)
            
            # Check for minimum execution interval (prevent rapid re-execution)
            last_execution = schedule.get('last_execution_at')
            if last_execution:
                if isinstance(last_execution, str):
                    last_execution = datetime.fromisoformat(last_execution.replace('Z', '+00:00'))
                if last_execution.tzinfo is None:
                    last_execution = last_execution.replace(tzinfo=timezone.utc)
                
                # Prevent execution if less than 30 seconds have passed
                min_interval = 30  # seconds
                if (now - last_execution).total_seconds() < min_interval:
                    return False
            
            # Check if it's time to execute (with a small buffer for timing precision)
            return now >= next_execution
            
        except Exception as e:
            logger.error(f"Error checking schedule execution time: {e}")
            return False
    
    async def _execute_scheduled_flow(self, flow_id: str, schedule: dict):
        """Execute a scheduled flow"""
        try:
            logger.info(f"Executing scheduled flow: {flow_id}")
            
            # Import here to avoid circular imports
            import httpx
            
            # Get backend URL from environment
            backend_port = os.getenv("VIBESURF_BACKEND_PORT", "9335")
            backend_url = f"http://127.0.0.1:{backend_port}"
            
            # Make API call to execute the flow
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{backend_url}/api/v1/build/{flow_id}/flow",
                    json={}  # Empty request body for now
                )
                
                if response.status_code == 200:
                    logger.info(f"Successfully triggered scheduled flow {flow_id}")
                else:
                    logger.error(f"Failed to trigger scheduled flow {flow_id}: {response.status_code} {response.text}")
            
            # Update execution tracking
            await self._update_execution_tracking(flow_id, schedule)
            
        except Exception as e:
            logger.error(f"Error executing scheduled flow {flow_id}: {e}")
    
    async def _update_execution_tracking(self, flow_id: str, schedule: dict):
        """Update execution tracking in the database"""
        try:
            global db_manager
            if not db_manager:
                return
                
            now = datetime.now(timezone.utc)
            
            # Calculate next execution time using local timezone
            cron_expr = schedule.get('cron_expression')
            next_execution = None
            if cron_expr:
                try:
                    local_now = datetime.now().astimezone()
                    cron = croniter(cron_expr, local_now)
                    local_next = cron.get_next(datetime)
                    # Make sure the result has timezone info
                    if local_next.tzinfo is None:
                        local_next = local_next.replace(tzinfo=local_now.tzinfo)
                    # Convert to UTC for storage
                    next_execution = local_next.astimezone(timezone.utc)
                    logger.info(f"Updated next execution for flow {flow_id}: {next_execution} UTC (local: {local_next})")
                except (ValueError, TypeError):
                    logger.error(f"Invalid cron expression for flow {flow_id}: {cron_expr}")
            
            async for session in db_manager.get_session():
                # Import Schedule model
                from .database.models import Schedule
                
                # Use SQLAlchemy ORM update
                await session.execute(
                    update(Schedule)
                    .where(Schedule.flow_id == flow_id)
                    .values(
                        last_execution_at=now,
                        next_execution_at=next_execution,
                        execution_count=Schedule.execution_count + 1,
                        updated_at=now
                    )
                )
                
                await session.commit()
                
                # Update local schedule cache AFTER successful database update
                if flow_id in self.schedules:
                    old_next = self.schedules[flow_id].get('next_execution_at')
                    self.schedules[flow_id].update({
                        'last_execution_at': now,
                        'next_execution_at': next_execution,
                        'execution_count': schedule.get('execution_count', 0) + 1,
                        'updated_at': now
                    })
                    logger.info(f"Local cache updated for flow {flow_id}: next_execution changed from {old_next} to {next_execution}")
                else:
                    logger.warning(f"Flow {flow_id} not found in local cache during execution tracking update")
                
                break  # Exit after processing to avoid multiple iterations
                
        except Exception as e:
            logger.error(f"Error updating execution tracking for flow {flow_id}: {e}")
    
    async def _update_next_execution_time(self, flow_id: str, cron_expr: str):
        """Update next execution time for a schedule"""
        try:
            global db_manager
            if not db_manager:
                return
                
            now = datetime.now(timezone.utc)
            
            try:
                local_now = datetime.now().astimezone()
                cron = croniter(cron_expr, local_now)
                local_next = cron.get_next(datetime)
                # Make sure the result has timezone info
                if local_next.tzinfo is None:
                    local_next = local_next.replace(tzinfo=local_now.tzinfo)
                # Convert to UTC for storage
                next_execution = local_next.astimezone(timezone.utc)
                logger.info(f"Calculated next execution for flow {flow_id}: {next_execution} UTC (local: {local_next})")
            except (ValueError, TypeError):
                logger.error(f"Invalid cron expression for flow {flow_id}: {cron_expr}")
                return
            
            async for session in db_manager.get_session():
                # Import Schedule model
                from .database.models import Schedule
                
                # Use SQLAlchemy ORM update
                await session.execute(
                    update(Schedule)
                    .where(Schedule.flow_id == flow_id)
                    .values(
                        next_execution_at=next_execution,
                        updated_at=now
                    )
                )
                
                await session.commit()
                
                # Update local schedule cache AFTER successful database update
                if flow_id in self.schedules:
                    old_next = self.schedules[flow_id].get('next_execution_at')
                    self.schedules[flow_id].update({
                        'next_execution_at': next_execution,
                        'updated_at': now
                    })
                    logger.info(f"Local cache updated for flow {flow_id}: next_execution changed from {old_next} to {next_execution}")
                else:
                    logger.warning(f"Flow {flow_id} not found in local cache during next execution time update")
                
                break  # Exit after processing to avoid multiple iterations
                
        except Exception as e:
            logger.error(f"Error updating next execution time for flow {flow_id}: {e}")


async def initialize_schedule_manager():
    """Initialize and start the schedule manager"""
    global schedule_manager
    
    try:
        if schedule_manager:
            await schedule_manager.stop()
        
        schedule_manager = ScheduleManager()
        await schedule_manager.start()
        logger.info("✅ Schedule manager initialized and started")
        
    except Exception as e:
        logger.error(f"Failed to initialize schedule manager: {e}")


async def shutdown_schedule_manager():
    """Shutdown the schedule manager"""
    global schedule_manager
    
    try:
        if schedule_manager:
            await schedule_manager.stop()
            schedule_manager = None
        logger.info("Schedule manager shutdown completed")
        
    except Exception as e:
        logger.error(f"Error shutting down schedule manager: {e}")


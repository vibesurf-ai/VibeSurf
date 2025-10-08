import asyncio
import subprocess
import signal
import os
import sys
import tempfile
import json
import time
from typing import Optional, Dict, Any, List
from pathlib import Path
from vibe_surf.logger import get_logger

from vibe_surf.notebook.config import NotebookServerConfig
from vibe_surf.notebook.utils import generate_token

logger = get_logger(__name__)


class NotebookServerLauncher:
    """
    Handles Jupyter Lab server process lifecycle.
    
    This class manages the actual subprocess execution of Jupyter Lab,
    including configuration file generation, process monitoring, and
    graceful shutdown procedures.
    """
    
    def __init__(self, config: NotebookServerConfig):
        """
        Initialize server launcher with configuration.
        
        Args:
            config: Server configuration settings
        """
        self.config = config
        self.process: Optional[subprocess.Popen] = None
        self.server_token: Optional[str] = None
        
        logger.debug(f"Initialized JupyterServerLauncher with config: {config}")
    
    async def start_server(self) -> Dict[str, Any]:
        """
        Start Jupyter Lab server process.
        
        Returns:
            Dictionary containing server information (URL, token, PID, etc.)
        
        Raises:
            ServerStartupError: If server fails to start
            ServerConfigurationError: If configuration is invalid
        """
        if self.is_running():
            logger.warning("Server is already running")
            return self._get_server_info()
        
        try:
            logger.info("Starting Jupyter Lab server...")
            
            # Step 1: Generate secure token if not provided
            if not self.config.token:
                self.server_token = generate_token()
                logger.debug("Generated secure server token")
            else:
                self.server_token = self.config.token
            
            # Step 2: Create configuration file
            await self._create_config_file()
            
            # Step 3: Build command and start process
            cmd = self._build_command()
            logger.debug(f"Starting server with command: {' '.join(cmd)}")
            
            self.process = await self._start_process(cmd)
            
            # Step 4: Wait for server to be ready
            await self._wait_for_server_ready()
            
            server_info = self._get_server_info()
            logger.info(f"Jupyter Lab server started successfully on {server_info['url']}")
            return server_info
            
        except Exception as e:
            await self._cleanup_on_failure()
            raise RuntimeError(f"Failed to start Jupyter server: {e}")
    
    async def stop_server(self, force: bool = False) -> bool:
        """
        Stop Jupyter Lab server process.
        
        Args:
            force: If True, forcefully terminate the process
        
        Returns:
            True if server was stopped successfully
        
        Raises:
            ServerShutdownError: If server fails to stop gracefully
        """
        if not self.is_running():
            logger.warning("Server is not running")
            return True
        
        try:
            logger.info("Stopping Jupyter Lab server...")
            
            if force:
                await self._force_stop_server()
            else:
                await self._graceful_stop_server()
            
            # Cleanup temporary files
            await self._cleanup_files()
            
            logger.info("Jupyter Lab server stopped successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping server: {e}")
            if not force:
                # Try force stop as fallback
                logger.warning("Attempting force stop as fallback...")
                return await self.stop_server(force=True)
            raise RuntimeError(f"Failed to stop Jupyter server: {e}")
    
    def is_running(self) -> bool:
        """
        Check if server process is running.
        
        Returns:
            True if server process is active
        """
        if self.process is None:
            return False
        
        # Check if process is still alive
        poll_result = self.process.poll()
        return poll_result is None
    
    def get_server_url(self) -> Optional[str]:
        """
        Get server URL if running.
        
        Returns:
            Server URL string or None if not running
        """
        if not self.is_running():
            return None
        
        protocol = "https" if self.config.certfile else "http"
        return f"{protocol}://{self.config.host}:{self.config.port}"
    
    def get_server_token(self) -> Optional[str]:
        """
        Get server authentication token.
        
        Returns:
            Server token string or None if not set
        """
        return self.server_token
    
    def get_process_id(self) -> Optional[int]:
        """
        Get server process ID.
        
        Returns:
            Process ID or None if not running
        """
        if self.process:
            return self.process.pid
        return None
    
    async def restart_server(self) -> Dict[str, Any]:
        """
        Restart the Jupyter Lab server.
        
        Returns:
            Dictionary containing new server information
        """
        logger.info("Restarting Jupyter Lab server...")
        await self.stop_server()
        return await self.start_server()
    
    def _get_server_info(self) -> Dict[str, Any]:
        """Get comprehensive server information."""
        return {
            "url": self.get_server_url(),
            "token": self.get_server_token(),
            "pid": self.get_process_id(),
            "host": self.config.host,
            "port": self.config.port,
            "notebook_dir": self.config.notebook_dir,
            "running": self.is_running(),
            "config_file": self.config_file,
        }
    
    def _build_command(self) -> List[str]:
        """
        Build Jupyter Lab command with all necessary arguments.
        
        Returns:
            Command list ready for subprocess execution
        """
        cmd = [
            sys.executable, "-m", "jupyter", "lab",
            f"--port={self.config.port}",
            f"--ip={self.config.host}",
            "--no-browser",
        ]
        
        # Add token authentication
        if self.server_token:
            cmd.append(f"--ServerApp.token={self.server_token}")
        
        # Add notebook directory
        if self.config.notebook_dir:
            cmd.append(f"--notebook-dir={self.config.notebook_dir}")
        
        # Add configuration file
        if self.config.config_file:
            cmd.append(f"--config={self.config.config_file}")
        
        # Security settings
        if self.config.disable_check_xsrf:
            cmd.append("--ServerApp.disable_check_xsrf=True")
        
        if self.config.allow_origin:
            cmd.append(f"--ServerApp.allow_origin={self.config.allow_origin}")
        
        # Logging settings
        cmd.extend([
            f"--log-level={self.config.log_level}",
            "--ServerApp.open_browser=False",
        ])
        
        # Allow remote access if configured (not recommended for security)
        if not self.config.allow_remote_access:
            cmd.append("--ServerApp.allow_remote_access=False")
        
        return cmd
    
    async def _create_config_file(self) -> None:
        """Create temporary Jupyter configuration file."""
        try:
            # Create temporary config file
            temp_dir = tempfile.gettempdir()
            config_fd, self.config.config_file = tempfile.mkstemp(
                prefix="jupyter_config_", 
                suffix=".py",
                dir=temp_dir
            )
            
            # Generate configuration content
            config_content = self._generate_config_content()
            
            # Write configuration to file
            with os.fdopen(config_fd, 'w') as f:
                f.write(config_content)
            
            logger.debug(f"Created configuration file: {self.config_file}")
            
        except Exception as e:
            raise RuntimeError(f"Failed to create configuration file: {e}")
    
    def _generate_config_content(self) -> str:
        """Generate Jupyter configuration file content."""
        config_lines = [
            "# VibeSUrf Jupyter Lab Configuration",
            "# Auto-generated configuration for secure local operation",
            "",
            "c = get_config()",
            "",
            "# Security settings",
            f"c.ServerApp.token = '{self.server_token}'",
            "c.ServerApp.password = ''",
            f"c.ServerApp.open_browser = {self.config.open_browser}",
            f"c.ServerApp.allow_remote_access = {self.config.allow_remote_access}",
            "",
            "# Network settings", 
            f"c.ServerApp.ip = '{self.config.host}'",
            f"c.ServerApp.port = {self.config.port}",
            "",
            "# CORS settings for local development",
            f"c.ServerApp.allow_origin = '{self.config.allow_origin}'",
            f"c.ServerApp.disable_check_xsrf = {self.config.disable_check_xsrf}",
            "",
        ]
        
        if self.config.notebook_dir:
            config_lines.append(f"c.ServerApp.notebook_dir = '{self.config.notebook_dir}'")
        
        config_lines.extend([
            "",
            "# Logging settings",
            f"c.Application.log_level = '{self.config.log_level}'",
            "",
            "# Kernel management",
            "c.MappingKernelManager.cull_idle_timeout = 3600",  # 1 hour
            "c.MappingKernelManager.cull_interval = 300",       # 5 minutes
        ])
        
        return "\n".join(config_lines)
    
    async def _start_process(self, cmd: List[str]) -> subprocess.Popen:
        """Start the Jupyter server subprocess."""
        try:
            # Prepare environment
            env = os.environ.copy()
            env['JUPYTER_RUNTIME_DIR'] = tempfile.gettempdir()
            
            # Start process with proper stdio handling
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                env=env,
                cwd=self.config.notebook_dir or os.getcwd(),
                start_new_session=True,  # Create new process group
            )
            
            logger.debug(f"Started Jupyter process with PID: {process.pid}")
            return process
            
        except FileNotFoundError:
            raise ValueError("Jupyter Lab not found. Please ensure jupyterlab is installed.")
        except Exception as e:
            raise ValueError(f"Failed to start Jupyter process: {e}")
    
    async def _wait_for_server_ready(self) -> None:
        """Wait for server to be ready to accept connections."""
        import aiohttp
        
        logger.info("Starting server readiness check...")
        
        url = self.get_server_url()
        if not url:
            raise ValueError("Server URL not available")
        
        logger.info(f"Server URL: {url}")
        
        # First, let's check if jupyter lab is actually installed
        try:
            import subprocess
            result = subprocess.run([sys.executable, "-m", "jupyter", "--version"],
                                  capture_output=True, text=True, timeout=10)
            logger.info(f"Jupyter version check: {result.stdout.strip() if result.stdout else 'No output'}")
            if result.stderr:
                logger.warning(f"Jupyter version stderr: {result.stderr.strip()}")
        except Exception as e:
            logger.error(f"Failed to check Jupyter version: {e}")
        
        # Check if process output contains any useful information
        if self.process:
            try:
                # Try to read any available output without blocking (Unix only)
                if sys.platform != "win32":
                    import fcntl
                    import os
                    
                    # Make stdout and stderr non-blocking
                    if self.process.stdout:
                        fd = self.process.stdout.fileno()
                        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
                        
                    if self.process.stderr:
                        fd = self.process.stderr.fileno()
                        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
                        
            except Exception as e:
                logger.debug(f"Could not make process streams non-blocking: {e}")
        
        # Construct health check URL
        health_url = f"{url}/api/status"
        logger.info(f"Health check URL: {health_url}")
        
        start_time = time.time()
        attempt = 0
        last_process_output_time = start_time
        
        while time.time() - start_time < self.config.shutdown_timeout:
            attempt += 1
            elapsed = time.time() - start_time
            logger.info(f"Health check attempt {attempt} at {elapsed:.1f}s")
            
            # DEBUG: Log before capture_process_output to identify blocking
            logger.debug("About to call _capture_process_output()")
            
            try:
                # Check if process is still running
                if not self.is_running():
                    logger.error("Server process terminated unexpectedly")
                    await self._capture_process_output()
                    raise ValueError("Server process terminated unexpectedly")
                
                logger.debug(f"Process is running (PID: {self.process.pid})")
                
                # Capture any new process output
                if time.time() - last_process_output_time > 5:  # Every 5 seconds
                    logger.debug("About to capture process output")
                    await self._capture_process_output()
                    logger.debug("Completed capturing process output")
                    last_process_output_time = time.time()
                
                # Try to connect to server
                logger.debug("Attempting HTTP connection...")
                async with aiohttp.ClientSession() as session:
                    headers = {}
                    if self.server_token:
                        headers['Authorization'] = f'token {self.server_token}'
                        logger.debug(f"Using token auth: {self.server_token[:10]}...")
                    
                    # Try multiple endpoints that might be available earlier
                    test_urls = [
                        health_url,  # /api/status
                        f"{url}/api",  # /api
                        f"{url}/",  # root
                        f"{url}/tree"  # notebook tree
                    ]
                    
                    for test_url in test_urls:
                        try:
                            logger.debug(f"Testing URL: {test_url}")
                            async with session.get(test_url, headers=headers, timeout=5) as response:
                                logger.info(f"URL {test_url} returned status: {response.status}")
                                if response.status in [200, 302]:  # 302 might be redirect to login
                                    logger.info(f"Server responding at {test_url} with status {response.status}")
                                    return
                                elif response.status == 403:
                                    logger.warning(f"Got 403 Forbidden - possible token issue")
                                elif response.status == 404:
                                    logger.debug(f"Got 404 - endpoint not ready yet")
                                else:
                                    logger.warning(f"Unexpected status {response.status}")
                        except Exception as url_error:
                            logger.debug(f"URL {test_url} failed: {url_error}")
                            continue
                    
                    logger.debug("None of the test URLs responded successfully")
                        
            except asyncio.TimeoutError:
                logger.debug("HTTP request timed out, server not ready yet")
            except aiohttp.ClientConnectorError as e:
                logger.debug(f"Connection failed (expected during startup): {e}")
            except Exception as e:
                logger.debug(f"Server not ready yet - {type(e).__name__}: {e}")
            
            # Wait before next check
            logger.debug(f"Waiting 2 seconds before next attempt...")
            await asyncio.sleep(2)
        
        # Timeout reached - get comprehensive diagnostic info
        logger.error(f"Server failed to start within {self.config.shutdown_timeout} seconds")
        await self._comprehensive_diagnostics()
        
        raise ValueError(
            f"Server failed to start within {self.config.shutdown_timeout} seconds"
        )
    
    async def _graceful_stop_server(self) -> None:
        """Attempt graceful server shutdown with enhanced cleanup."""
        if not self.process:
            return
        
        logger.info(f"Starting graceful shutdown of Jupyter server (PID: {self.process.pid})")
        
        try:
            # First try to shutdown Jupyter gracefully via API if possible
            await self._try_api_shutdown()
            
            # Then send OS signal for graceful shutdown
            if sys.platform != "win32":
                self.process.send_signal(signal.SIGTERM)
            else:
                self.process.terminate()
            
            # Wait for process to exit gracefully
            try:
                await asyncio.wait_for(
                    self._wait_for_process_exit(),
                    timeout=self.config.shutdown_timeout,
                )
                logger.info("Server shutdown gracefully")
                
                # Verify port is released
                await self._verify_port_released()
                
            except asyncio.TimeoutError:
                logger.warning("Graceful shutdown timed out, forcing termination")
                await self._force_stop_server()
                
        except Exception as e:
            logger.error(f"Error during graceful shutdown: {e}")
            await self._force_stop_server()
    
    async def _force_stop_server(self) -> None:
        """Force server termination with comprehensive cleanup."""
        if not self.process:
            return
        
        original_pid = self.process.pid
        logger.warning(f"Force terminating Jupyter server (PID: {original_pid})")
        
        try:
            # Force kill the process and its children
            if sys.platform != "win32":
                try:
                    # Kill entire process group
                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                    logger.debug("Killed process group")
                except (ProcessLookupError, OSError):
                    # Process group might not exist, try individual process
                    try:
                        self.process.kill()
                        logger.debug("Killed individual process")
                    except ProcessLookupError:
                        pass
            else:
                # Windows: Kill process and try to kill child processes
                try:
                    import psutil
                    parent = psutil.Process(self.process.pid)
                    children = parent.children(recursive=True)
                    
                    # Kill children first
                    for child in children:
                        try:
                            child.kill()
                            logger.debug(f"Killed child process {child.pid}")
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                    
                    # Kill parent
                    self.process.kill()
                    
                    # Wait for all to be gone
                    gone, alive = psutil.wait_procs(children + [parent], timeout=3)
                    for p in alive:
                        logger.warning(f"Process {p.pid} still alive after force kill")
                        
                except ImportError:
                    # Fallback if psutil not available
                    self.process.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    # Process already gone or access denied
                    pass
            
            # Wait for process to be fully terminated
            await self._wait_for_process_exit()
            logger.info(f"Server terminated forcefully (was PID: {original_pid})")
            
            # Additional cleanup - check if port is still occupied
            await self._cleanup_remaining_processes()
            
            # Verify port is released
            await self._verify_port_released()
            
        except ProcessLookupError:
            # Process already terminated
            logger.debug("Process already terminated")
        except Exception as e:
            logger.error(f"Error during force termination: {e}")
        finally:
            self.process = None
    
    async def _try_api_shutdown(self) -> None:
        """Try to shutdown Jupyter server via API first."""
        try:
            if not self.server_token:
                return
                
            import aiohttp
            shutdown_url = f"{self.get_server_url()}/api/shutdown"
            headers = {"Authorization": f"token {self.server_token}"}
            
            async with aiohttp.ClientSession() as session:
                async with session.post(shutdown_url, headers=headers, timeout=5) as response:
                    if response.status == 200:
                        logger.info("Jupyter server shutdown via API successful")
                    else:
                        logger.debug(f"API shutdown returned status {response.status}")
        except Exception as e:
            logger.debug(f"API shutdown failed: {e}")
    
    async def _cleanup_remaining_processes(self) -> None:
        """Clean up any remaining Jupyter processes on the same port."""
        try:
            import psutil
            port = self.config.port
            
            for conn in psutil.net_connections(kind='inet'):
                if conn.laddr and conn.laddr.port == port and conn.pid:
                    try:
                        process = psutil.Process(conn.pid)
                        cmdline = ' '.join(process.cmdline()).lower()
                        if 'jupyter' in cmdline:
                            logger.warning(f"Found remaining Jupyter process {conn.pid} on port {port}, terminating...")
                            process.kill()
                            process.wait(timeout=3)
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                        pass
        except ImportError:
            logger.debug("psutil not available for remaining process cleanup")
        except Exception as e:
            logger.debug(f"Error cleaning up remaining processes: {e}")
    
    async def _verify_port_released(self) -> None:
        """Verify that the port has been released."""
        import socket
        max_attempts = 10
        port = self.config.port
        
        for attempt in range(max_attempts):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    s.bind((self.config.host, port))
                    logger.info(f"Port {port} has been successfully released")
                    return
            except OSError:
                if attempt < max_attempts - 1:
                    logger.debug(f"Port {port} still occupied, waiting... (attempt {attempt + 1}/{max_attempts})")
                    await asyncio.sleep(1)
                else:
                    logger.warning(f"Port {port} is still occupied after {max_attempts} attempts")
    
    async def _wait_for_process_exit(self) -> None:
        """Wait for process to exit."""
        if not self.process:
            return
        
        # Poll process status in async manner
        while self.process.poll() is None:
            await asyncio.sleep(0.1)
    
    async def _cleanup_files(self) -> None:
        """Clean up temporary configuration files."""
        try:
            if self.config.config_file and os.path.exists(self.config.config_file):
                os.unlink(self.config.config_file)
                logger.debug(f"Cleaned up configuration file: {self.config.config_file}")
                self.config_file = None
        except Exception as e:
            logger.warning(f"Failed to cleanup configuration file: {e}")
    
    async def _capture_process_output(self) -> None:
        """Capture and log any available process output using Windows-compatible approach."""
        if not self.process:
            return
        
        logger.debug("_capture_process_output: Starting")
        
        try:
            # WINDOWS-COMPATIBLE FIX: Use threading and queues for non-blocking reads
            import threading
            import queue
            import time
            
            def read_stream(stream, q, stream_name):
                """Thread function to read from stream without blocking main thread."""
                try:
                    while True:
                        line = stream.readline()
                        if not line:
                            break
                        q.put((stream_name, line))
                except Exception as e:
                    logger.debug(f"Error in {stream_name} reader thread: {e}")
            
            # Create queues for stdout and stderr
            output_queue = queue.Queue()
            
            # Start reader threads for available streams
            threads = []
            if self.process.stdout:
                stdout_thread = threading.Thread(
                    target=read_stream,
                    args=(self.process.stdout, output_queue, "stdout"),
                    daemon=True
                )
                stdout_thread.start()
                threads.append(stdout_thread)
            
            if self.process.stderr:
                stderr_thread = threading.Thread(
                    target=read_stream,
                    args=(self.process.stderr, output_queue, "stderr"),
                    daemon=True
                )
                stderr_thread.start()
                threads.append(stderr_thread)
            
            # Read available output with timeout
            timeout_time = time.time() + 1  # 1 second timeout
            output_captured = False
            
            while time.time() < timeout_time:
                try:
                    stream_name, line = output_queue.get_nowait()
                    if line:
                        text = line.decode('utf-8', errors='ignore').strip()
                        if text:
                            if stream_name == "stdout":
                                logger.info(f"Jupyter stdout: {text}")
                            else:
                                logger.warning(f"Jupyter stderr: {text}")
                            output_captured = True
                except queue.Empty:
                    # No output available, wait a bit
                    await asyncio.sleep(0.1)
                    continue
            
            if not output_captured:
                logger.debug("No process output captured")
                
        except Exception as e:
            logger.debug(f"Error capturing process output: {e}")
        
        logger.debug("_capture_process_output: Completed")
    
    async def _comprehensive_diagnostics(self) -> None:
        """Run comprehensive diagnostics when startup fails."""
        logger.error("=== JUPYTER SERVER STARTUP DIAGNOSTICS ===")
        
        # Process information
        if self.process:
            logger.error(f"Process still running: {self.is_running()}")
            logger.error(f"Process PID: {self.process.pid}")
            logger.error(f"Process return code: {self.process.returncode}")
            
            # Final attempt to capture output
            await self._capture_process_output()
            
        # System information
        try:
            import psutil
            logger.error(f"System memory: {psutil.virtual_memory()}")
            logger.error(f"System CPU: {psutil.cpu_percent()}")
        except ImportError:
            logger.debug("psutil not available for system diagnostics")
        except Exception as e:
            logger.debug(f"Error getting system info: {e}")
        
        # Network information
        try:
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                result = s.connect_ex((self.config.host, self.config.port))
                if result == 0:
                    logger.error(f"Port {self.config.port} is responding to connections")
                else:
                    logger.error(f"Port {self.config.port} is not accepting connections (error: {result})")
        except Exception as e:
            logger.error(f"Error checking port: {e}")
        
        # Configuration information
        logger.error(f"Server config - Host: {self.config.host}, Port: {self.config.port}")
        logger.error(f"Notebook dir: {self.config.notebook_dir}")
        logger.error(f"Config file: {self.config_file}")
        
        # Environment information
        logger.error(f"Python executable: {sys.executable}")
        logger.error(f"Working directory: {os.getcwd()}")
        
        # Check if jupyter lab is accessible
        try:
            result = subprocess.run([sys.executable, "-m", "jupyter", "lab", "--help"],
                                  capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                logger.error("Jupyter Lab command is accessible")
            else:
                logger.error(f"Jupyter Lab command failed: {result.stderr}")
        except Exception as e:
            logger.error(f"Cannot run jupyter lab command: {e}")
        
        logger.error("=== END DIAGNOSTICS ===")

    async def _cleanup_on_failure(self) -> None:
        """Clean up resources when startup fails."""
        try:
            if self.process:
                await self._force_stop_server()
            await self._cleanup_files()
        except Exception as e:
            logger.error(f"Error during failure cleanup: {e}")
        finally:
            self.process = None
            self.server_token = None
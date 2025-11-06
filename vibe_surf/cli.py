#!/usr/bin/env python3
"""
VibeSurf CLI
A command-line interface for VibeSurf browser automation tool.
"""

import os
import pdb
import sys
import glob
import json
import socket
import platform
import time
import importlib.util
import argparse
from pathlib import Path
from typing import Optional
import os

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt, Confirm
    from rich.text import Text
    from rich import print as rprint
except ImportError:
    print("Error: rich library is required. Install with: pip install rich")
    sys.exit(1)

# Logo components with styling for rich panels
VIBESURF_LOGO = """
[white]██╗   ██╗██╗██████╗ ███████╗[/]    [darkorange]███████╗██╗   ██╗██████╗ ███████╗[/]
[white]██║   ██║██║██╔══██╗██╔════╝[/]    [darkorange]██╔════╝██║   ██║██╔══██╗██╔════╝[/]
[white]██║   ██║██║██████╔╝█████╗  [/]    [darkorange]███████╗██║   ██║██████╔╝█████╗  [/]
[white]╚██╗ ██╔╝██║██╔══██╗██╔══╝  [/]    [darkorange]╚════██║██║   ██║██╔══██╗██╔══╝  [/]
[white] ╚████╔╝ ██║██████╔╝███████╗[/]    [darkorange]███████║╚██████╔╝██║  ██║██║     [/]
[white]  ╚═══╝  ╚═╝╚═════╝ ╚══════╝[/]    [darkorange]╚══════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝     [/]
"""

console = Console()

# Add logger import for the workspace directory logging
from vibe_surf.logger import get_logger
from vibe_surf.telemetry.service import ProductTelemetry
from vibe_surf.telemetry.views import CLITelemetryEvent

logger = get_logger(__name__)


def find_chrome_browser() -> Optional[str]:
    """Find Chrome browser executable."""
    system = platform.system()
    patterns = []

    # Get playwright browsers path from environment variable if set
    playwright_path = os.environ.get('PLAYWRIGHT_BROWSERS_PATH')

    if system == 'Darwin':  # macOS
        if not playwright_path:
            playwright_path = '~/Library/Caches/ms-playwright'
        patterns = [
            '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            f'{playwright_path}/chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium',
            '/Applications/Chromium.app/Contents/MacOS/Chromium',
            '/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary',
        ]
    elif system == 'Linux':
        if not playwright_path:
            playwright_path = '~/.cache/ms-playwright'
        patterns = [
            '/usr/bin/google-chrome-stable',
            '/usr/bin/google-chrome',
            '/usr/local/bin/google-chrome',
            f'{playwright_path}/chromium-*/chrome-linux/chrome',
            '/usr/bin/chromium',
            '/usr/bin/chromium-browser',
            '/usr/local/bin/chromium',
            '/snap/bin/chromium',
            '/usr/bin/google-chrome-beta',
            '/usr/bin/google-chrome-dev',
        ]
    elif system == 'Windows':
        if not playwright_path:
            playwright_path = r'%LOCALAPPDATA%\ms-playwright'
        patterns = [
            r'C:\Program Files\Google\Chrome\Application\chrome.exe',
            r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
            r'%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe',
            r'%PROGRAMFILES%\Google\Chrome\Application\chrome.exe',
            r'%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe',
            f'{playwright_path}\\chromium-*\\chrome-win\\chrome.exe',
            r'C:\Program Files\Chromium\Application\chrome.exe',
            r'C:\Program Files (x86)\Chromium\Application\chrome.exe',
            r'%LOCALAPPDATA%\Chromium\Application\chrome.exe',
        ]

    return _find_browser_from_patterns(patterns)


def find_edge_browser() -> Optional[str]:
    """Find Microsoft Edge browser executable."""
    system = platform.system()
    patterns = []

    if system == 'Darwin':  # macOS
        patterns = [
            '/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge',
        ]
    elif system == 'Linux':
        patterns = [
            '/usr/bin/microsoft-edge-stable',
            '/usr/bin/microsoft-edge',
            '/usr/bin/microsoft-edge-beta',
            '/usr/bin/microsoft-edge-dev',
        ]
    elif system == 'Windows':
        patterns = [
            r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
            r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
            r'%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe',
        ]

    return _find_browser_from_patterns(patterns)


def find_brave_browser() -> Optional[str]:
    """Find Brave browser executable."""
    system = platform.system()
    patterns = []

    if system == 'Darwin':  # macOS
        patterns = [
            '/Applications/Brave Browser.app/Contents/MacOS/Brave Browser',
        ]
    elif system == 'Linux':
        patterns = [
            '/usr/bin/brave-browser',
            '/usr/bin/brave',
            '/usr/local/bin/brave',
            '/snap/bin/brave',
            '/usr/bin/brave-browser-stable',
            '/usr/bin/brave-browser-beta',
            '/usr/bin/brave-browser-dev',
        ]
    elif system == 'Windows':
        patterns = [
            r'C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe',
            r'C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe',
            r'%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe',
        ]

    return _find_browser_from_patterns(patterns)


def _find_browser_from_patterns(patterns: list[str]) -> Optional[str]:
    """Helper function to find browser from patterns."""
    system = platform.system()
    
    for pattern in patterns:
        # Expand user home directory
        expanded_pattern = Path(pattern).expanduser()

        # Handle Windows environment variables
        if system == 'Windows':
            pattern_str = str(expanded_pattern)
            for env_var in ['%LOCALAPPDATA%', '%PROGRAMFILES%', '%PROGRAMFILES(X86)%']:
                if env_var in pattern_str:
                    env_key = env_var.strip('%').replace('(X86)', ' (x86)')
                    env_value = os.environ.get(env_key, '')
                    if env_value:
                        pattern_str = pattern_str.replace(env_var, env_value)
            expanded_pattern = Path(pattern_str)

        # Convert to string for glob
        pattern_str = str(expanded_pattern)

        # Check if pattern contains wildcards
        if '*' in pattern_str:
            # Use glob to expand the pattern
            matches = glob.glob(pattern_str)
            if matches:
                # Sort matches and take the last one (alphanumerically highest version)
                matches.sort()
                browser_path = matches[-1]
                if Path(browser_path).exists() and Path(browser_path).is_file():
                    return browser_path
        else:
            # Direct path check
            if expanded_pattern.exists() and expanded_pattern.is_file():
                return str(expanded_pattern)

    return None


def is_port_available(port: int) -> bool:
    """Check if a port is available."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', port))
            return result != 0
    except Exception:
        return False


def find_available_port(start_port: int) -> int:
    """Find the next available port starting from start_port."""
    port = start_port
    while port <= 65535:
        if is_port_available(port):
            return port
        port += 1
    raise RuntimeError("No available ports found")


def select_browser() -> Optional[str]:
    """Interactive browser selection."""
    console.print("\n[bold cyan]🌐 Browser Selection[/bold cyan]")
    console.print("VibeSurf supports Chrome, Edge, and Brave browsers.\n")
    
    options = []
    browsers = {}
    
    # Check for Chrome
    chrome_path = find_chrome_browser()
    if chrome_path:
        options.append("1")
        browsers["1"] = ("Chrome", chrome_path)
        console.print(f"[green]1.[/green] Chrome ([dim]{chrome_path}[/dim])")
    
    # Check for Edge
    edge_path = find_edge_browser()
    if edge_path:
        option_num = str(len(options) + 1)
        options.append(option_num)
        browsers[option_num] = ("Edge", edge_path)
        console.print(f"[green]{option_num}.[/green] Microsoft Edge ([dim]{edge_path}[/dim])")
    
    # Check for Brave
    brave_path = find_brave_browser()
    if brave_path:
        option_num = str(len(options) + 1)
        options.append(option_num)
        browsers[option_num] = ("Brave", brave_path)
        console.print(f"[green]{option_num}.[/green] Brave Browser ([dim]{brave_path}[/dim])")
    
    # Custom browser option
    custom_option = str(len(options) + 1)
    options.append(custom_option)
    console.print(f"[yellow]{custom_option}.[/yellow] Custom browser path")
    
    # Quit option
    quit_option = str(len(options) + 1)
    options.append(quit_option)
    console.print(f"[red]{quit_option}.[/red] Quit")
    
    if not chrome_path and not edge_path and not brave_path:
        console.print("\n[yellow]⚠️  No supported browsers found automatically.[/yellow]")
    
    while True:
        choice = Prompt.ask(
            "\n[bold]Select a browser",
            choices=options,
            default="1" if options else None
        )
        
        if choice == quit_option:
            console.print("[yellow]👋 Goodbye![/yellow]")
            return None
        elif choice == custom_option:
            while True:
                custom_path = Prompt.ask("[bold]Enter browser executable path")
                if custom_path.strip():
                    custom_path = custom_path.strip().strip('"\'')
                    if Path(custom_path).exists() and Path(custom_path).is_file():
                        console.print(f"[green]✅ Browser found: {custom_path}[/green]")
                        return custom_path
                    else:
                        console.print(f"[red]❌ Browser not found: {custom_path}[/red]")
                        if not Confirm.ask("[yellow]Try again?[/yellow]", default=True):
                            break
                else:
                    console.print("[red]❌ Path cannot be empty[/red]")
        else:
            if choice in browsers:
                browser_name, browser_path = browsers[choice]
                console.print(f"[green]✅ Selected {browser_name}: {browser_path}[/green]")
                return browser_path
    
    return None


def find_first_available_browser() -> Optional[str]:
    """Find the first available browser in order: Chrome, Edge, Brave."""
    # Try Chrome first
    chrome_path = find_chrome_browser()
    if chrome_path:
        return chrome_path
    
    # Try Edge second
    edge_path = find_edge_browser()
    if edge_path:
        return edge_path
    
    # Try Brave third
    brave_path = find_brave_browser()
    if brave_path:
        return brave_path
    
    return None


def configure_port() -> int:
    """Configure backend port."""
    console.print("\n[bold cyan]🔌 Port Configuration[/bold cyan]")
    
    # Get port from environment variable
    env_port = os.environ.get('VIBESURF_BACKEND_PORT', '').strip()
    default_port = 9335
    
    if env_port:
        try:
            default_port = int(env_port)
        except ValueError:
            console.print(f"[yellow]⚠️  Invalid VIBESURF_BACKEND_PORT: {env_port}. Using default: {default_port}[/yellow]")
    
    # Check if default port is available
    if is_port_available(default_port):
        console.print(f"[green]✅ Port {default_port} is available[/green]")
        selected_port = default_port
    else:
        console.print(f"[yellow]⚠️  Port {default_port} is occupied, finding next available port...[/yellow]")
        selected_port = find_available_port(default_port + 1)
        console.print(f"[green]✅ Using port {selected_port}[/green]")
    
    # Set environment variable
    os.environ['VIBESURF_BACKEND_PORT'] = str(selected_port)
    return selected_port


def configure_extension_path() -> str:
    """Configure extension path."""
    console.print("\n[bold cyan]🧩 Extension Configuration[/bold cyan]")
    
    # Get extension path from environment variable
    env_extension = os.environ.get('VIBESURF_EXTENSION', '').strip()
    
    if env_extension and Path(env_extension).exists():
        console.print(f"[green]✅ Using extension from environment: {env_extension}[/green]")
        return env_extension
    
    # Check if running in PyInstaller frozen environment
    if getattr(sys, 'frozen', False):
        # PyInstaller frozen environment
        bundle_dir = Path(sys._MEIPASS)
        default_extension = bundle_dir / "vibe_surf" / "chrome_extension"
        console.print(f"[cyan]📦 Detected packaged environment, using bundled extension[/cyan]")
    else:
        # Development environment
        default_extension = Path(__file__).parent / "chrome_extension"
    
    if default_extension.exists():
        extension_path = str(default_extension.resolve())
        console.print(f"[green]✅ Using default extension: {extension_path}[/green]")
        os.environ['VIBESURF_EXTENSION'] = extension_path
        return extension_path
    else:
        console.print(f"[red]❌ Extension not found at: {default_extension}[/red]")
        console.print("[yellow]⚠️  VibeSurf may not function properly without the extension[/yellow]")
        return str(default_extension)


def start_backend(port: int) -> None:
    """Start the VibeSurf backend."""
    console.print(f"\n[bold cyan]🚀 Starting VibeSurf Backend on port {port}[/bold cyan]")
    
    try:
        import uvicorn

        from vibe_surf.backend.main import app
        
        console.print("[green]✅ Backend modules loaded successfully[/green]")
        console.print(f"[cyan]🌍 Access VibeSurf at: http://127.0.0.1:{port}[/cyan]")
        console.print("[yellow]📝 Press Ctrl+C to stop the server[/yellow]\n")
        
        # Run the server
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="error")
        
    except KeyboardInterrupt:
        console.print("\n[yellow]🛑 Server stopped by user[/yellow]")
    except ImportError as e:
        console.print(f"[red]❌ Failed to import backend modules: {e}[/red]")
        console.print("[yellow]💡 Make sure you're running from the VibeSurf project directory[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]❌ Failed to start backend: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def get_browser_execution_path() -> Optional[str]:
    """Get browser execution path from envs.json or environment variables."""
    # 1. Load environment variables
    from vibe_surf.common import get_workspace_dir

    workspace_dir = get_workspace_dir()
    os.makedirs(workspace_dir, exist_ok=True)
    logger.info("WorkSpace directory: {}".format(workspace_dir))

    # Load environment configuration from envs.json
    envs_file_path = os.path.join(workspace_dir, "envs.json")
    browser_path_from_envs = None
    try:
        if os.path.exists(envs_file_path):
            with open(envs_file_path, 'r', encoding='utf-8') as f:
                envs = json.load(f)
                browser_path_from_envs = envs.get("BROWSER_EXECUTION_PATH", "")
                if browser_path_from_envs:
                    browser_path_from_envs = browser_path_from_envs.strip()
    except (json.JSONDecodeError, IOError) as e:
        logger.info(f"Failed to load envs.json: {e}")
        browser_path_from_envs = None

    # 2. Get BROWSER_EXECUTION_PATH from environment variables
    browser_path_from_env = os.getenv("BROWSER_EXECUTION_PATH", "")
    if browser_path_from_env:
        browser_path_from_env = browser_path_from_env.strip()

    # Check paths in priority order: 1. envs.json -> 2. environment variables
    for source, path in [("envs.json", browser_path_from_envs), ("environment variable", browser_path_from_env)]:
        if path and os.path.exists(path) and os.path.isfile(path):
            console.print(f"[green]✅ Using browser path from {source}: {path}[/green]")
            return path
        elif path:
            console.print(f"[yellow]⚠️  Browser path from {source} exists but file not found: {path}[/yellow]")

    return None


def main():
    """Main CLI entry point."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="VibeSurf CLI - Browser automation tool")
    parser.add_argument('--no_select_browser', action='store_true',
                       help='Skip browser selection and use first available browser (Chrome -> Edge -> Brave)')
    args = parser.parse_args()
    
    try:
        # Initialize telemetry
        telemetry = ProductTelemetry()
        start_time = time.time()
        
        # Display logo
        console.print(Panel(VIBESURF_LOGO, title="[bold cyan]VibeSurf CLI[/bold cyan]", border_style="cyan"))
        console.print("[dim]A powerful browser automation tool for vibe surfing 🏄‍♂️[/dim]")
        import vibe_surf
        console.print(f"[dim]Version: {vibe_surf.__version__}[/dim]\n")
        console.print(f"[dim]Author: WarmShao and Community Contributors [/dim]\n")
        console.print("[dim]VibeSurf collects anonymous usage data by default to improve user experience.[/dim]")
        console.print("[dim]To opt out, set environment variable: VIBESURF_ANONYMIZED_TELEMETRY=false[/dim]\n")
        
        # Capture telemetry start event
        start_event = CLITelemetryEvent(
            version=vibe_surf.__version__,
            action='start',
            mode='interactive'
        )
        telemetry.capture(start_event)
        
        # Check for existing browser path from configuration
        browser_path = get_browser_execution_path()
        
        # If no valid browser path found, handle based on --no_select_browser flag
        if not browser_path:
            if args.no_select_browser:
                # Find first available browser without user interaction
                browser_path = find_first_available_browser()
                if not browser_path:
                    console.print("[red]❌ No supported browsers found![/red]")
                    console.print("[yellow]Please download and install Chrome, Edge, or Brave browser.[/yellow]")
                    return
                else:
                    # Determine which browser was found
                    browser_name = "Unknown"
                    if find_chrome_browser() == browser_path:
                        browser_name = "Chrome"
                    elif find_edge_browser() == browser_path:
                        browser_name = "Edge"
                    elif find_brave_browser() == browser_path:
                        browser_name = "Brave"
                    console.print(f"[green]✅ Auto-selected {browser_name}: {browser_path}[/green]")
            else:
                # Interactive browser selection (original behavior)
                browser_path = select_browser()
                if not browser_path:
                    return
        
        # Port configuration
        port = configure_port()
        
        # Extension configuration
        extension_path = configure_extension_path()
        
        # Set browser path in environment
        os.environ['BROWSER_EXECUTION_PATH'] = browser_path
        
        # Start backend
        start_backend(port)
        
        # Capture telemetry completion event
        end_time = time.time()
        duration = end_time - start_time
        completion_event = CLITelemetryEvent(
            version=vibe_surf.__version__,
            action='startup_completed',
            mode='interactive',
            duration_seconds=duration,
            browser_path=browser_path
        )
        telemetry.capture(completion_event)
        telemetry.flush()
        
    except KeyboardInterrupt:
        console.print("\n[yellow]👋 Goodbye![/yellow]")
        # Capture telemetry interruption event
        try:
            end_time = time.time()
            duration = end_time - start_time
            interrupt_event = CLITelemetryEvent(
                version=vibe_surf.__version__,
                action='interrupted',
                mode='interactive',
                duration_seconds=duration
            )
            telemetry.capture(interrupt_event)
            telemetry.flush()
        except:
            pass
    except Exception as e:
        console.print(f"\n[red]❌ Unexpected error: {e}[/red]")
        # Capture telemetry error event
        try:
            end_time = time.time()
            duration = end_time - start_time
            error_event = CLITelemetryEvent(
                version=vibe_surf.__version__,
                action='error',
                mode='interactive',
                duration_seconds=duration,
                error_message=str(e)[:200]
            )
            telemetry.capture(error_event)
            telemetry.flush()
        except:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
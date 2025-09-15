import asyncio
import pdb

import aiohttp
import json
import time
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional

from dotenv import load_dotenv
import sys
import pdb

sys.path.append(".")
load_dotenv()

# Base URL for the backend API
BASE_URL = "http://127.0.0.1:9335"
API_BASE = f"{BASE_URL}/api"


class BackendAPITester:
    """Real API test client for VibeSurf Backend"""

    def __init__(self):
        self.session = None
        self.test_session_id_1 = "068ac695-6ea2-795c-8000-ad03fc9c2b6c"
        self.test_session_id_2 = "068ac696-00e4-77c1-8000-a134f2f75d0b"
        self.created_profiles = []  # Track created profiles for cleanup

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def wait_for_backend(self, max_retries=30):
        """Wait for backend to be ready"""
        for i in range(max_retries):
            try:
                async with self.session.get(f"{BASE_URL}/health") as resp:
                    if resp.status == 200:
                        print("✅ Backend is ready")
                        return True
            except:
                pass
            await asyncio.sleep(1)
        return False

    # Helper methods for API calls
    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make GET request with optional query parameters"""
        url = f"{API_BASE}{endpoint}"
        if params:
            async with self.session.get(url, params=params) as resp:
                result = await resp.json()
                # params_str = f"?{params}" if params else ""
                return {"status": resp.status, "data": result}
        else:
            async with self.session.get(url) as resp:
                result = await resp.json()
                return {"status": resp.status, "data": result}

    async def post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make POST request"""
        async with self.session.post(
                f"{API_BASE}{endpoint}",
                json=data,
                headers={"Content-Type": "application/json"}
        ) as resp:
            result = await resp.json()
            print(f"POST {endpoint}: {resp.status} - {result}")
            return {"status": resp.status, "data": result}

    async def put(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make PUT request"""
        async with self.session.put(
                f"{API_BASE}{endpoint}",
                json=data,
                headers={"Content-Type": "application/json"}
        ) as resp:
            result = await resp.json()
            print(f"PUT {endpoint}: {resp.status} - {result}")
            return {"status": resp.status, "data": result}

    async def delete(self, endpoint: str) -> Dict[str, Any]:
        """Make DELETE request"""
        async with self.session.delete(f"{API_BASE}{endpoint}") as resp:
            result = await resp.json()
            print(f"DELETE {endpoint}: {resp.status} - {result}")
            return {"status": resp.status, "data": result}


async def test_health_check():
    """Test basic health check"""
    print("🧪 Testing health check...")
    async with BackendAPITester() as tester:
        if not await tester.wait_for_backend():
            print("❌ Backend not ready")
            return False

        async with tester.session.get(f"{BASE_URL}/health") as resp:
            result = await resp.json()
            print(f"Health check: {resp.status} - {result}")
            assert resp.status == 200
            assert result["status"] == "healthy"
            print("✅ Health check passed")
            return True


async def test_llm_profile_management():
    """Test LLM profile CRUD operations"""
    print("\n🧪 Testing LLM Profile Management...")
    async with BackendAPITester() as tester:
        await tester.wait_for_backend()

        # 1. List available providers
        print("\n📋 Testing get available providers...")
        providers_resp = await tester.get("/config/llm/providers")
        assert providers_resp["status"] == 200
        providers = providers_resp["data"]["providers"]
        print(f"Found {len(providers)} providers")

        # 2. Create a test LLM profile
        print("\n➕ Testing create LLM profile...")
        test_profile = {
            "profile_name": f"test-profile-{int(time.time())}",
            "provider": "openai",
            "model": "gpt-4o-mini",
            "api_key": "test-api-key-123",
            "base_url": "https://api.openai.com/v1",
            "temperature": 0.7,
            "max_tokens": 2000,
            "description": "Test profile for API testing",
            "is_default": False
        }

        create_resp = await tester.post("/config/llm-profiles", test_profile)
        if create_resp["status"] == 200:
            print("✅ LLM profile created successfully")
            tester.created_profiles.append(test_profile["profile_name"])
        else:
            print(f"❌ Failed to create LLM profile: {create_resp}")

        # 3. List LLM profiles
        print("\n📋 Testing list LLM profiles...")
        list_resp = await tester.get("/config/llm-profiles")
        assert list_resp["status"] == 200
        profiles = list_resp["data"]
        print(f"Found {len(profiles)} profiles")

        # 4. Get specific profile
        print("\n🔍 Testing get specific profile...")
        profile_resp = await tester.get(f"/config/llm-profiles/{test_profile['profile_name']}")
        if profile_resp["status"] == 200:
            print("✅ Retrieved profile successfully")
            profile_data = profile_resp["data"]
            assert profile_data["profile_name"] == test_profile["profile_name"]
            assert profile_data["provider"] == test_profile["provider"]

        # 5. Update profile
        print("\n✏️ Testing update profile...")
        update_data = {
            "temperature": 0.5,
            "description": "Updated test profile"
        }
        update_resp = await tester.put(f"/config/llm-profiles/{test_profile['profile_name']}", update_data)
        if update_resp["status"] == 200:
            print("✅ Profile updated successfully")

        # 6. Create a second profile and set as default
        print("\n➕ Testing create second profile as default...")
        default_profile = {
            "profile_name": f"default-profile-{int(time.time())}",
            "provider": "openai",
            "model": "gpt-4o",
            "api_key": "default-api-key-123",
            "temperature": 0.3,
            "description": "Default test profile",
            "is_default": True
        }

        default_resp = await tester.post("/config/llm-profiles", default_profile)
        if default_resp["status"] == 200:
            print("✅ Default profile created successfully")
            tester.created_profiles.append(default_profile["profile_name"])

        # 7. Get default profile
        print("\n🏆 Testing get default profile...")
        default_get_resp = await tester.get("/config/llm-profiles/default/current")
        if default_get_resp["status"] == 200:
            print("✅ Retrieved default profile successfully")

        # 8. Delete non-default profile (cleanup)
        print("\n🗑️ Testing delete profile...")
        delete_resp = await tester.delete(f"/config/llm-profiles/{test_profile['profile_name']}")
        if delete_resp["status"] == 200:
            print("✅ Profile deleted successfully")
            tester.created_profiles.remove(test_profile["profile_name"])

        print("✅ LLM Profile Management tests completed")


async def test_controller_configuration():
    """Test tools/MCP server configuration"""
    print("\n🧪 Testing Controller Configuration...")
    async with BackendAPITester() as tester:
        await tester.wait_for_backend()

        # 1. Get current tools config
        print("\n📋 Testing get tools config...")
        config_resp = await tester.get("/config/tools")
        print(f"Controller config response: {config_resp}")

        # 2. Update tools config (using new Pydantic model)
        print("\n✏️ Testing update tools config...")
        controller_config = {
            "exclude_actions": ["scroll_up", "scroll_down"],
            "max_actions_per_task": 150,
            "display_files_in_done_text": False
        }

        update_resp = await tester.post("/config/tools", controller_config)
        if update_resp["status"] == 200:
            print("✅ Controller configuration updated successfully")
        else:
            print(f"❌ Controller config update failed: {update_resp}")

        # 3. Verify the update
        print("\n🔍 Testing verify tools config update...")
        verify_resp = await tester.get("/config/tools")
        if verify_resp["status"] == 200:
            print("✅ Controller configuration verified")

        print("✅ Controller Configuration tests completed")


async def test_task_lifecycle_same_session():
    """Test task submission, control operations (pause/resume/stop) with same session"""
    print("\n🧪 Testing Task Lifecycle - Same Session...")
    async with BackendAPITester() as tester:
        await tester.wait_for_backend()

        # Ensure we have a default LLM profile
        default_profile_name = "vibesurf_openai"
        default_resp = await tester.get(f"/config/llm-profiles/{default_profile_name}")
        if default_resp["status"] != 200:
            print("⚠️ No default LLM profile found, creating one...")
            test_profile = {
                "profile_name": f"{default_profile_name}",
                "provider": "openai_compatible",
                "model": "gemini-2.5-flash",
                "api_key": os.getenv("OPENAI_API_KEY"),
                "base_url": os.getenv("OPENAI_ENDPOINT"),
                "temperature": 0.7,
                "is_default": True
            }
            create_resp = await tester.post("/config/llm-profiles", test_profile)
            if create_resp["status"] == 200:
                tester.created_profiles.append(test_profile["profile_name"])
                default_profile_name = test_profile["profile_name"]
            else:
                print("❌ Failed to create default profile for testing")
                return

        # 1. Check initial status
        print("\n📊 Testing initial task status...")
        status_resp = await tester.get("/tasks/status")
        print(f"Initial status: {status_resp}")

        # 2. Submit first task
        print("\n🚀 Testing submit first task...")
        task_1 = {
            "session_id": tester.test_session_id_1,
            "task_description": "search for the founders of browser-use.",
            "llm_profile_name": default_profile_name
        }

        submit_resp = await tester.post("/tasks/submit", task_1)
        if submit_resp["status"] == 200:
            print("✅ Task 1 submitted successfully")
            task_1_id = submit_resp["data"]["task_id"]
            while True:
                status_resp = await tester.get("/tasks/status")
                print("Check agent is available")
                print(status_resp)
                if status_resp.get("data", {}).get("has_active_task", False):
                    break
                await asyncio.sleep(1)

            # 4. Test pause (using new JSON body format)
            print("\n⏸️ Testing pause task...")
            pause_data = {"reason": "Testing pause functionality"}
            pause_resp = await tester.post("/tasks/pause", pause_data)
            if pause_resp["status"] == 200:
                print("✅ Task paused successfully")

                # Check status after pause
                await asyncio.sleep(1)
                status_resp = await tester.get("/tasks/status")
                print(f"Status after pause: {status_resp}")

                # 5. Test resume (using new JSON body format)
                print("\n▶️ Testing resume task...")
                resume_data = {"reason": "Testing resume functionality"}
                resume_resp = await tester.post("/tasks/resume", resume_data)
                if resume_resp["status"] == 200:
                    print("✅ Task resumed successfully")

                    # 6. Test stop (using new JSON body format)
                    print("\n🛑 Testing stop task...")
                    stop_data = {"reason": "Testing stop functionality"}
                    stop_resp = await tester.post("/tasks/stop", stop_data)
                    if stop_resp["status"] == 200:
                        print("✅ Task stopped successfully")
                    else:
                        print(f"⚠️ Stop failed: {stop_resp}")
                else:
                    print(f"❌ Resume failed: {resume_resp}")
            else:
                print(f"❌ Pause failed: {pause_resp}")

        # 7. Wait for task to complete and try another task in same session
        while True:
            status_resp = await tester.get("/tasks/status")
            if not status_resp.get("data", {}).get("has_active_task", False):
                break
            await asyncio.sleep(1)

        print("\n🔄 Testing second task in same session...")

        task_2 = {
            "session_id": tester.test_session_id_1,  # Same session
            "task_description": "Please say 'Task 2 in same session executed successfully'.",
            "llm_profile_name": default_profile_name
        }

        submit_resp_2 = await tester.post("/tasks/submit", task_2)
        if submit_resp_2["status"] == 200:
            print("✅ Task 2 (same session) submitted successfully")
            # Let it run to completion
            await asyncio.sleep(10)
        else:
            print(f"❌ Task 2 submission failed: {submit_resp_2}")

        print("✅ Task Lifecycle - Same Session tests completed")


async def test_activity_and_history():
    """Test activity logs and task history retrieval"""
    print("\n🧪 Testing Activity Logs and History...")
    async with BackendAPITester() as tester:
        await tester.wait_for_backend()

        # 1. Get recent tasks
        default_profile_name = "vibesurf_openai"
        default_resp = await tester.get(f"/config/llm-profiles/{default_profile_name}")
        if default_resp["status"] != 200:
            print("⚠️ No default LLM profile found, creating one...")
            test_profile = {
                "profile_name": f"{default_profile_name}",
                "provider": "openai_compatible",
                "model": "gemini-2.5-flash",
                "api_key": os.getenv("OPENAI_API_KEY"),
                "base_url": os.getenv("OPENAI_ENDPOINT"),
                "temperature": 0.7,
                "is_default": True
            }
            create_resp = await tester.post("/config/llm-profiles", test_profile)
            if create_resp["status"] == 200:
                tester.created_profiles.append(test_profile["profile_name"])
                default_profile_name = test_profile["profile_name"]
            else:
                print("❌ Failed to create default profile for testing")
                return

        # 1. Check initial status
        print("\n📊 Testing initial task status...")
        status_resp = await tester.get("/tasks/status")
        print(f"Initial status: {status_resp}")

        # 2. Submit first task
        print("\n🚀 Testing submit first task...")
        task_1 = {
            "session_id": tester.test_session_id_1,
            "task_description": "search for the founders of langflow.",
            "llm_profile_name": default_profile_name
        }

        # get current activity logs before submit
        activity_resp = await tester.get(f"/activity/sessions/{tester.test_session_id_1}/activity")
        activity_logs = activity_resp.get("data", {}).get("activity_logs", [])
        print(f"Current has {len(activity_logs)} activity logs")
        prev_activity_log = activity_logs[-1] if activity_logs else None

        submit_resp = await tester.post("/tasks/submit", task_1)

        # 3. Get session tasks
        print(f"\n📋 Testing get session tasks for {tester.test_session_id_1}...")

        while True:
            # Use query parameters for activity endpoint
            activity_resp = await tester.get(f"/activity/sessions/{tester.test_session_id_1}/activity",
                                             params={"message_index": len(activity_logs)})
            cur_activity_log = activity_resp.get("data", {}).get("activity_log", None)
            if activity_resp["status"] == 200 and cur_activity_log and (prev_activity_log is None or
                    prev_activity_log and prev_activity_log != cur_activity_log):
                print(cur_activity_log)
                activity_logs.append(cur_activity_log)
                prev_activity_log = cur_activity_log
                if cur_activity_log["agent_status"] == "done":
                    break
            else:
                await asyncio.sleep(1)

        # 5. Get latest activity
        print(f"\n📋 Testing get latest activity...")
        latest_resp = await tester.get(f"/activity/sessions/{tester.test_session_id_1}/latest_activity")
        if latest_resp["status"] == 200:
            print("✅ Latest activity retrieved successfully")
        print(latest_resp)
        print("✅ Activity and History tests completed")


async def test_configuration_status():
    """Test configuration status endpoints"""
    print("\n🧪 Testing Configuration Status...")
    async with BackendAPITester() as tester:
        await tester.wait_for_backend()

        # 1. Get overall configuration status
        print("\n📊 Testing get configuration status...")
        status_resp = await tester.get("/config/status")
        if status_resp["status"] == 200:
            print("✅ Configuration status retrieved successfully")
            status_data = status_resp["data"]
            print(f"Overall status: {status_data.get('overall_status')}")
            print(f"LLM profiles: {status_data.get('llm_profiles')}")
            print(f"Controller initialized: {status_data.get('tools', {}).get('initialized')}")
            print(f"Browser manager initialized: {status_data.get('browser_manager', {}).get('initialized')}")
            print(f"Swarm agent initialized: {status_data.get('swarm_agent', {}).get('initialized')}")

        # 2. Get system status
        print("\n📊 Testing get system status...")
        async with tester.session.get(f"{API_BASE}/status") as resp:
            if resp.status == 200:
                result = await resp.json()
                print(f"System status: {result}")
                print("✅ System status retrieved successfully")

        print("✅ Configuration Status tests completed")


async def test_file_upload():
    """Test file upload functionality"""
    print("\n🧪 Testing File Upload...")
    async with BackendAPITester() as tester:
        await tester.wait_for_backend()

        # 1. Test file upload with session_id
        print("\n📁 Testing file upload with session ID...")
        test_file_path = "tmp/swarm_surf_workspace/activity_logs.pkl"
        
        # Check if test file exists
        if not os.path.exists(test_file_path):
            print(f"⚠️ Test file not found: {test_file_path}")
            return
        
        # Prepare multipart form data
        with open(test_file_path, 'rb') as f:
            file_content = f.read()
        
        # Create form data for upload
        data = aiohttp.FormData()
        data.add_field('files', file_content, filename='activity_logs.pkl', content_type='application/octet-stream')
        data.add_field('session_id', tester.test_session_id_1)
        
        # Upload file
        async with tester.session.post(f"{API_BASE}/files/upload", data=data) as resp:
            if resp.status == 200:
                result = await resp.json()
                print(f"✅ File uploaded successfully: {result}")
                
                # Verify response structure
                assert "message" in result
                assert "files" in result
                assert len(result["files"]) == 1
                
                uploaded_file = result["files"][0]
                assert uploaded_file["original_filename"] == "activity_logs.pkl"
                assert uploaded_file["session_id"] == tester.test_session_id_1
                assert "file_id" in uploaded_file
                
                file_id = uploaded_file["file_id"]
                print(f"📄 File ID: {file_id}")
                
                # 2. Test file listing
                print("\n📋 Testing file listing...")
                list_resp = await tester.get(f"/files?session_id={tester.test_session_id_1}")
                if list_resp["status"] == 200:
                    files_data = list_resp["data"]
                    assert "files" in files_data
                    assert files_data["total_count"] >= 1
                    print(f"✅ Found {files_data['total_count']} files in session")

                # 3. Test file download
                print("\n📥 Testing file download...")
                async with tester.session.get(f"{API_BASE}/files/{file_id}") as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        print(f"✅ File download successful, size: {len(content)} bytes")
                    else:
                        print(f"⚠️ File download failed: {resp.status}")
                
                # 4. Test file deletion (cleanup)
                print("\n🗑️ Testing file deletion...")
                delete_resp = await tester.delete(f"/files/{file_id}")
                if delete_resp["status"] == 200:
                    print("✅ File deleted successfully")
                else:
                    print(f"⚠️ File deletion failed: {delete_resp}")
                    
            else:
                result = await resp.json()
                print(f"❌ File upload failed: {resp.status} - {result}")

        # 5. Test file upload without session_id
        print("\n📁 Testing file upload without session ID...")
        data_no_session = aiohttp.FormData()
        data_no_session.add_field('files', file_content, filename='activity_logs_global.pkl', content_type='application/octet-stream')
        
        async with tester.session.post(f"{API_BASE}/files/upload", data=data_no_session) as resp:
            if resp.status == 200:
                result = await resp.json()
                print(f"✅ Global file uploaded successfully")
                
                # Clean up global file
                if result["files"]:
                    global_file_id = result["files"][0]["file_id"]
                    await tester.delete(f"/files/{global_file_id}")
                    print("✅ Global file cleaned up")
            else:
                result = await resp.json()
                print(f"⚠️ Global file upload failed: {resp.status} - {result}")

        print("✅ File Upload tests completed")


async def cleanup_test_profiles():
    """Clean up test profiles created during testing"""
    print("\n🧹 Cleaning up test profiles...")
    async with BackendAPITester() as tester:
        await tester.wait_for_backend()

        # Get all profiles
        list_resp = await tester.get("/config/llm-profiles", params={"active_only": "false"})
        if list_resp["status"] == 200:
            profiles = list_resp["data"]

            # Delete test profiles (ones containing 'test' or 'auto-default')
            for profile in profiles:
                profile_name = profile["profile_name"]
                if ("test" in profile_name.lower() or
                        "auto-default" in profile_name.lower() or
                        "default-profile" in profile_name.lower()):

                    if not profile["is_default"]:  # Can't delete default profile
                        print(f"🗑️ Deleting test profile: {profile_name}")
                        delete_resp = await tester.delete(f"/config/llm-profiles/{profile_name}")
                        if delete_resp["status"] == 200:
                            print(f"✅ Deleted {profile_name}")
                        else:
                            print(f"⚠️ Failed to delete {profile_name}: {delete_resp}")
                    else:
                        print(f"⚠️ Skipping default profile: {profile_name}")


async def test_mcp_profile_management():
    """Test MCP profile CRUD operations"""
    print("\n🧪 Testing MCP Profile Management...")
    async with BackendAPITester() as tester:
        await tester.wait_for_backend()
        created_mcp_profiles = []  # Track for cleanup

        try:
            # 1. Create a test MCP profile
            print("\n➕ Testing create MCP profile...")
            test_mcp_profile = {
                "display_name": f"test-mcp-filesystem-{int(time.time())}",
                "mcp_server_name": f"filesystem-test-{int(time.time())}",
                "mcp_server_params": {
                    "command": "npx",
                    "args": [
                        "-y",
                        "@modelcontextprotocol/server-filesystem",
                        "/tmp/test"
                    ]
                },
                "description": "Test filesystem MCP server"
            }

            create_resp = await tester.post("/config/mcp-profiles", test_mcp_profile)
            if create_resp["status"] == 200:
                print("✅ MCP profile created successfully")
                created_profile = create_resp["data"]
                created_mcp_profiles.append(created_profile["mcp_id"])
                
                # Verify created profile structure
                assert created_profile["display_name"] == test_mcp_profile["display_name"]
                assert created_profile["mcp_server_name"] == test_mcp_profile["mcp_server_name"]
                assert created_profile["mcp_server_params"] == test_mcp_profile["mcp_server_params"]
                assert created_profile["is_active"] == True  # Default value
            else:
                print(f"❌ Failed to create MCP profile: {create_resp}")
                return

            # 2. Test uniqueness constraint on mcp_server_name
            print("\n🔒 Testing mcp_server_name uniqueness constraint...")
            duplicate_profile = {
                "display_name": f"duplicate-test-{int(time.time())}",
                "mcp_server_name": test_mcp_profile["mcp_server_name"],  # Same server name
                "mcp_server_params": {
                    "command": "docker",
                    "args": ["run", "test"]
                }
            }
            
            duplicate_resp = await tester.post("/config/mcp-profiles", duplicate_profile)
            if duplicate_resp["status"] == 400:
                print("✅ Uniqueness constraint working correctly")
            else:
                print(f"⚠️ Uniqueness constraint test unexpected result: {duplicate_resp}")

            # 3. List MCP profiles
            print("\n📋 Testing list MCP profiles...")
            list_resp = await tester.get("/config/mcp-profiles")
            if list_resp["status"] == 200:
                profiles = list_resp["data"]
                print(f"Found {len(profiles)} MCP profiles")
                
                # Verify our profile is in the list
                profile_found = any(p["mcp_id"] == created_profile["mcp_id"] for p in profiles)
                assert profile_found, "Created profile not found in list"
                print("✅ Created profile found in list")

            # 4. Get specific MCP profile
            print("\n🔍 Testing get specific MCP profile...")
            profile_resp = await tester.get(f"/config/mcp-profiles/{created_profile['mcp_id']}")
            if profile_resp["status"] == 200:
                profile_data = profile_resp["data"]
                assert profile_data["mcp_id"] == created_profile["mcp_id"]
                assert profile_data["display_name"] == test_mcp_profile["display_name"]
                print("✅ Retrieved MCP profile successfully")

            # 5. Update MCP profile
            print("\n✏️ Testing update MCP profile...")
            update_data = {
                "description": "Updated test filesystem MCP server",
                "is_active": False,
                "mcp_server_params": {
                    "command": "npx",
                    "args": [
                        "-y",
                        "@modelcontextprotocol/server-filesystem",
                        "/tmp/updated"
                    ]
                }
            }
            
            update_resp = await tester.put(f"/config/mcp-profiles/{created_profile['mcp_id']}", update_data)
            if update_resp["status"] == 200:
                updated_profile = update_resp["data"]
                assert updated_profile["description"] == update_data["description"]
                assert updated_profile["is_active"] == False
                assert updated_profile["mcp_server_params"]["args"][-1] == "/tmp/updated"
                print("✅ MCP profile updated successfully")

            # 6. Create another profile for different server
            print("\n➕ Testing create second MCP profile...")
            second_profile = {
                "display_name": f"test-mcp-markitdown-{int(time.time())}",
                "mcp_server_name": f"markitdown-test-{int(time.time())}",
                "mcp_server_params": {
                    "command": "docker",
                    "args": [
                        "run",
                        "--rm",
                        "-i",
                        "markitdown-mcp:latest"
                    ]
                },
                "description": "Test markitdown MCP server"
            }
            
            second_resp = await tester.post("/config/mcp-profiles", second_profile)
            if second_resp["status"] == 200:
                second_created = second_resp["data"]
                created_mcp_profiles.append(second_created["mcp_id"])
                print("✅ Second MCP profile created successfully")

            # 7. List only active profiles
            print("\n📋 Testing list active MCP profiles...")
            active_resp = await tester.get("/config/mcp-profiles", params={"active_only": "true"})
            if active_resp["status"] == 200:
                active_profiles = active_resp["data"]
                # First profile should be inactive, second should be active
                active_ids = [p["mcp_id"] for p in active_profiles]
                assert created_profile["mcp_id"] not in active_ids, "Inactive profile found in active list"
                assert second_created["mcp_id"] in active_ids, "Active profile not found in active list"
                print("✅ Active profile filtering working correctly")

            # 8. Test 404 for non-existent profile
            print("\n🔍 Testing get non-existent MCP profile...")
            notfound_resp = await tester.get("/config/mcp-profiles/non-existent-id")
            if notfound_resp["status"] == 404:
                print("✅ 404 returned for non-existent profile")

        finally:
            # Cleanup: Delete created profiles
            print("\n🗑️ Cleaning up MCP profiles...")
            for mcp_id in created_mcp_profiles:
                delete_resp = await tester.delete(f"/config/mcp-profiles/{mcp_id}")
                if delete_resp["status"] == 200:
                    print(f"✅ Deleted MCP profile {mcp_id}")
                else:
                    print(f"⚠️ Failed to delete MCP profile {mcp_id}: {delete_resp}")

        print("✅ MCP Profile Management tests completed")


async def run_all_tests():
    """Run all API tests in sequence"""
    print("🚀 Starting VibeSurf Backend API Tests")
    print("=" * 60)

    try:
        # Basic connectivity
        # await test_health_check()

        # Configuration tests
        # await test_llm_profile_management()
        # await test_mcp_profile_management()
        # await test_controller_configuration()
        # await test_configuration_status()
        #
        # # Task execution tests
        # await test_task_lifecycle_same_session()
        #
        # # Activity and history tests
        await test_activity_and_history()
        
        # File upload tests
        # await test_file_upload()

        print("\n🎉 All API tests completed successfully!")

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

    print("=" * 60)
    print("✅ VibeSurf Backend API Testing Complete")


if __name__ == "__main__":
    print("VibeSurf Backend API Tester")
    print("Make sure your backend is running on http://127.0.0.1:9335")
    print("Command: uvicorn vibe_surf.backend.main:app --host 127.0.0.1 --port 9335")
    print()

    asyncio.run(run_all_tests())

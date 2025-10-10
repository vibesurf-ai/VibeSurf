import asyncio
import pdb
import sys
import time
import os
from typing import Dict

sys.path.append(".")

from dotenv import load_dotenv

load_dotenv()


async def test_tools_with_mcp():
    import os
    from vibe_surf.tools.vibesurf_tools import VibeSurfTools

    mcp_server_config = {
        "mcpServers": {
            # "markitdown": {
            #     "command": "docker",
            #     "args": [
            #         "run",
            #         "--rm",
            #         "-i",
            #         "markitdown-mcp:latest"
            #     ]
            # },
            # "desktop-commander": {
            #     "command": "npx",
            #     "args": [
            #         "-y",
            #         "@wonderwhy-er/desktop-commander"
            #     ],
            # },
            "filesystem": {
                "command": "npx",
                "args": [
                    "-y",
                    "@modelcontextprotocol/server-filesystem",
                    "E:\\AIBrowser\\VibeSurf\\tmp\\code",
                ]
            },
        }
    }

    controller = VibeSurfTools(mcp_server_config=mcp_server_config)
    await controller.register_mcp_clients()
    pdb.set_trace()
    # action_name = "mcp.desktop-commander.start_process"
    action_name = "mcp.filesystem.list_directory"
    action_info = controller.registry.registry.actions[action_name]
    param_model = action_info.param_model
    print(param_model.model_json_schema())
    # params = {
    #     "command": f"python ./tmp/code/test.py",
    #     "timeout_ms": 30000
    # }
    params = {
        "path": r"E:\AIBrowser\VibeSurf\tmp\code",
    }
    validated_params = param_model(**params)
    ActionModel_ = controller.registry.create_action_model()
    # Create ActionModel instance with the validated parameters
    action_model = ActionModel_(**{action_name: validated_params})
    result = await controller.act(action_model)
    result = result.extracted_content

    # print(result)
    # if result and "Command is still running. Use read_output to get more output." in result and "PID" in \
    #         result.split("\n")[0]:
    #     pid = int(result.split("\n")[0].split("PID")[-1].strip())
    #     pdb.set_trace()
    #     action_name = "mcp.desktop-commander.read_process_output"
    #     action_info = tools.registry.registry.actions[action_name]
    #     param_model = action_info.param_model
    #     print(param_model.model_json_schema())
    #     params = {"pid": pid}
    #     validated_params = param_model(**params)
    #     action_model = ActionModel_(**{action_name: validated_params})
    #     output_result = ""
    #     while True:
    #         time.sleep(1)
    #         result = await tools.act(action_model)
    #         result = result.extracted_content
    #         if result:
    #             output_result = result
    #             break
    #     print(output_result)
    await controller.unregister_mcp_clients()


async def test_filesystem():
    from vibe_surf.tools.file_system import CustomFileSystem

    file_system_path = r"E:\AIBrowser\VibeSurf\tmp\vibesurf_workspace"
    filesystem = CustomFileSystem(file_system_path)
    result = await filesystem.create_file("reports/final_report.html")
    print(result)
    result = filesystem.get_absolute_path("reports/final_report.html")
    print(result)


async def test_bu_tools():
    import os
    from vibe_surf.tools.browser_use_tools import BrowserUseTools

    tools = BrowserUseTools()
    print(tools.registry.registry.actions.keys())


async def test_vibesurf_tools():
    import os
    from vibe_surf.tools.vibesurf_tools import VibeSurfTools

    tools = VibeSurfTools()
    print(tools.registry.registry.actions.keys())


async def test_finance_tools():
    from vibe_surf.tools.finance_tools import FinanceDataRetriever

    retriever = FinanceDataRetriever('TSLA')

    result = retriever.get_finance_data(["get_news"])

    pdb.set_trace()


async def test_composio_integrations():
    from composio import Composio
    from langchain_core.tools import Tool
    from composio_langchain import LangchainProvider

    composio = Composio(
        api_key=os.getenv("COMPOSIO_API_KEY"),
        provider=LangchainProvider()
    )

    schema = composio.toolkits.get()
    composio_toolkits = []
    for schema_ in schema:
        if 'OAUTH2' in schema_.auth_schemes:
            composio_toolkits.append({
                'name': schema_.name,
                'slug': schema_.slug,
                'description': schema_.meta.description,
                'logo': schema_.meta.logo,
                'app_url': schema_.meta.app_url,
            })

    def configure_tools(entity_id: str, app_name: str, limit: int | None = None) -> Dict:
        if limit is None:
            limit = 999

        tools = composio.tools.get(user_id=entity_id, toolkits=[app_name.lower()], limit=limit)
        configured_tools = []
        tools_map = {}
        for tool in tools:
            # Set the tags
            tools_map[tool.name] = {
                'description': tool.description,
                'args_schema': tool.args_schema.model_json_schema(),
                'func': tool.func,
            }
        return tools_map

    def _find_active_connection_for_app(entity_id: str, app_name: str) -> tuple[str, str] | None:
        """Find any ACTIVE connection for this app/user. Returns (connection_id, status) or None."""
        try:
            connection_list = composio.connected_accounts.list(
                user_ids=[entity_id], toolkit_slugs=[app_name.lower()]
            )

            if connection_list and hasattr(connection_list, "items") and connection_list.items:
                for connection in connection_list.items:
                    connection_id = getattr(connection, "id", None)
                    connection_status = getattr(connection, "status", None)
                    if connection_status == "ACTIVE" and connection_id:
                        return connection_id, connection_status

        except (ValueError, ConnectionError) as e:
            return None
        else:
            return None

    app_name = "gmail"
    entity_id = "default"
    connected_ret = _find_active_connection_for_app(entity_id=entity_id, app_name=app_name)
    if connected_ret and connected_ret[1] == "ACTIVE":
        gmail_tools_map = configure_tools(entity_id=entity_id, app_name=app_name)
        pdb.set_trace()
        result = gmail_tools_map['GMAIL_FETCH_EMAILS']['func']()
        pdb.set_trace()
        # result = composio.tools.execute(
        #     slug="GMAIL_FETCH_EMAILS",
        #     arguments={},
        #     user_id=entity_id,
        # )
    else:
        auth_configs = composio.auth_configs.list(toolkit_slug=app_name)

        if len(auth_configs.items) == 0:
            auth_config_id = composio.auth_configs.create(toolkit=app_name,
                                                          options={"type": "use_composio_managed_auth"})
            auth_config_id = auth_config_id
        else:
            auth_config_id = None
            for auth_config in auth_configs.items:
                if auth_config.auth_scheme == "OAUTH2":
                    auth_config_id = auth_config.id
                    break
        connection_request = composio.connected_accounts.initiate(
            user_id=entity_id, auth_config_id=auth_config_id, allow_multiple=True
        )
        connected_account = connection_request.wait_for_connection()
        print(connection_request.redirect_url)
        connected_ret = _find_active_connection_for_app(entity_id=entity_id, app_name=app_name)

if __name__ == '__main__':
    # asyncio.run(test_tools_with_mcp())
    # asyncio.run(test_filesystem())
    # asyncio.run(test_bu_tools())
    # asyncio.run(test_vibesurf_tools())
    # asyncio.run(test_finance_tools())
    asyncio.run(test_composio_integrations())

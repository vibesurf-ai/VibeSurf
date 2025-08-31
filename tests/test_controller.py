import asyncio
import pdb
import sys
import time

sys.path.append(".")

from dotenv import load_dotenv

load_dotenv()


async def test_controller_with_mcp():
    import os
    from vibe_surf.controller.vibesurf_controller import VibeSurfController
    from browser_use.controller.registry.views import ActionModel

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

    controller = VibeSurfController(mcp_server_config=mcp_server_config)
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
    #     action_info = controller.registry.registry.actions[action_name]
    #     param_model = action_info.param_model
    #     print(param_model.model_json_schema())
    #     params = {"pid": pid}
    #     validated_params = param_model(**params)
    #     action_model = ActionModel_(**{action_name: validated_params})
    #     output_result = ""
    #     while True:
    #         time.sleep(1)
    #         result = await controller.act(action_model)
    #         result = result.extracted_content
    #         if result:
    #             output_result = result
    #             break
    #     print(output_result)
    await controller.unregister_mcp_clients()


async def test_filesystem():
    from browser_use.filesystem.file_system import FileSystem

    file_system_path = r"E:\AIBrowser\VibeSurf\tmp\vibesurf_workspace"
    filesystem = FileSystem(file_system_path)
    result = await filesystem.read_file(
        "E:/AIBrowser/VibeSurf/tmp/vibesurf_workspace/068b3165-ddb7-7a49-8000-d4df8a16ae2d/upload_files/Ayers Application Form.md")
    print(result)


if __name__ == '__main__':
    # asyncio.run(test_controller_with_mcp())
    asyncio.run(test_filesystem())

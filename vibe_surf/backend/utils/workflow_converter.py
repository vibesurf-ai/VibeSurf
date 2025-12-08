"""
Workflow Converter - Convert recorded workflows to Langflow format

This module provides utilities to convert VibeSurf workflow recordings
into Langflow-compatible workflow JSON files and save them to the database.
"""

import json
import os
import sys
import traceback
from pathlib import Path
from typing import Dict, List, Any, Optional
from uuid import uuid4
import networkx as nx

from vibe_surf.logger import get_logger
from vibe_surf.langflow.graph import Graph

# Import browser components
from vibe_surf.workflows.Browser.browser_session import BrowserSessionComponent
from vibe_surf.workflows.Browser.browser_navigate import BrowserNavigateComponent
from vibe_surf.workflows.Browser.browser_click_element import BrowserClickElementComponent
from vibe_surf.workflows.Browser.browser_input_text import BrowserInputTextComponent
from vibe_surf.workflows.Browser.browser_scroll import BrowserScrollComponent
from vibe_surf.workflows.Browser.browser_press_key import BrowserPressKeyComponent

logger = get_logger(__name__)


def build_workflow_graph(raw_workflow_data: Dict[str, Any]) -> Graph:
    """
    Build a Langflow Graph from raw workflow recording data
    
    Args:
        raw_workflow_data: Raw workflow data containing actions
        
    Returns:
        Graph object ready to be dumped to JSON
    """
    graph = Graph()
    
    workflows = raw_workflow_data.get("workflows", [])
    
    # Initialize Browser Session (root component)
    browser_session = BrowserSessionComponent()
    browser_session.display_name = "Browser Session"
    browser_session.description = "Create browser sessions using the browser manager"
    session_id = graph.add_component(browser_session)
    
    # Track previous component for chaining
    previous_id = session_id
    previous_output = "browser_session"
    
    # Process each workflow action
    for idx, action in enumerate(workflows):
        action_type = action.get("action", "").lower()
        
        component = None
        component_id = None
        output_name = "output_browser_session"
        
        if action_type == "navigate":
            # Create Navigation component
            url = action.get("url", "")
            component = BrowserNavigateComponent(url=url)
            component.display_name = "Navigation"
            component.description = "Navigates to a specific url"
            component_id = graph.add_component(component)
            
        elif action_type == "click":
            # Create Click Element component
            target_text = action.get("target_text", "")
            target_selector = action.get("target_selector", "") or action.get("cssSelector", "")
            
            # If target_text is "Unknown Element", set it to empty
            if target_text == "Unknown Element":
                target_text = ""
            
            component = BrowserClickElementComponent(
                # element_text=target_text,  # Always pass string, even if empty
                css_selector=target_selector  # Always pass string, even if empty
            )
            
            # Set display name - for click, include target_text if available
            display_name = f"Click {target_text}" if target_text else "Click element"
            component.display_name = display_name
            component_id = graph.add_component(component)
            
        elif action_type == "type" or action_type == "input":
            # Create Input Text component
            input_text = action.get("value", "")
            target_selector = action.get("target_selector", "") or action.get("cssSelector", "")
            
            component = BrowserInputTextComponent(
                input_text=input_text,
                css_selector=target_selector  # Always pass string, even if empty
            )
            component_id = graph.add_component(component)
            
        elif action_type == "scroll":
            # Create Scroll component
            scroll_delta_x = action.get("scrollX", 0)
            scroll_delta_y = action.get("scrollY", 500)
            component = BrowserScrollComponent(
                scroll_delta_x=scroll_delta_x,
                scroll_delta_y=scroll_delta_y
            )
            component_id = graph.add_component(component)

        elif action_type == "press" or action_type == "keypress":
            # Create Press Key component
            key = action.get("key", "")
            modifiers = action.get("modifiers", [])
            
            keys_to_press = key
            if modifiers and isinstance(modifiers, list):
                # Filter out empty modifiers and join
                valid_modifiers = [m for m in modifiers if m]
                if valid_modifiers:
                    keys_to_press = "+".join(valid_modifiers + [key])
            
            component = BrowserPressKeyComponent(
                keys=keys_to_press
            )
            component.display_name = f"Press {keys_to_press}"
            component_id = graph.add_component(component)
            
        else:
            logger.warning(f"Unknown action type: {action_type}, skipping")
            continue
        
        # Connect previous component to current component
        if component_id:
            graph.add_component_edge(
                previous_id,
                (previous_output, "browser_session"),
                component_id
            )
            
            # Update previous references
            previous_id = component_id
            previous_output = output_name
    
    return graph


def convert_raw_workflow_to_langflow(raw_json_path: str) -> Dict[str, Any]:
    """
    Convert raw workflow recording to Langflow format
    
    Args:
        raw_json_path: Path to the raw workflow JSON file
        
    Returns:
        Dict containing Langflow-compatible workflow data
    """
    # Load raw workflow data
    with open(raw_json_path, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
    
    workflow_name = raw_data.get("name", "Recorded Workflow")
    workflow_description = raw_data.get("description", "")
    
    # Build the graph
    graph = build_workflow_graph(raw_data)
    
    # Prepare and dump the graph
    graph.prepare()
    graph_data = graph.dump()["data"]

    for node_data in graph_data["nodes"]:
        node_data.update({
            "type": "genericNode",
        })

    flow_json_string = json.dumps(graph_data, ensure_ascii=False)
    flow_json_string = flow_json_string.replace('"type": "FieldTypes.TEXT"', '"type": "str"')
    flow_json_string = flow_json_string.replace('"type": "FieldTypes.OTHER"', '"type": "other"')
    graph_data = json.loads(flow_json_string)

    # Return full workflow structure
    workflow_data = {
        "name": workflow_name,
        "description": workflow_description,
        "data": graph_data
    }
    
    return workflow_data


def generate_langflow_edges(graph_data: dict) -> dict:
    """Generate Langflow-compatible edge format"""
    edges = graph_data.get('edges', [])
    fixed_edges = []

    for edge in edges:
        if 'data' in edge and 'sourceHandle' in edge['data'] and 'targetHandle' in edge['data']:
            # Get handle information
            source_handle_obj = edge['data']['sourceHandle']
            target_handle_obj = edge['data']['targetHandle']

            # Generate stringified handles (using special character œ instead of quotes)
            source_handle_str = stringify_handle(source_handle_obj)
            target_handle_str = stringify_handle(target_handle_obj)

            # Generate complex edge ID
            edge_id = generate_edge_id(
                edge['source'],
                source_handle_str,
                edge['target'],
                target_handle_str
            )

            # Build complete edge object
            langflow_edge = {
                "animated": edge.get("animated", False),
                "className": edge.get("className", ""),
                "data": {
                    "sourceHandle": source_handle_obj,  # Keep object format
                    "targetHandle": target_handle_obj  # Keep object format
                },
                "id": edge_id,
                "selected": edge.get("selected", False),
                "source": edge['source'],
                "sourceHandle": source_handle_str,  # String format
                "target": edge['target'],
                "targetHandle": target_handle_str  # String format
            }

            fixed_edges.append(langflow_edge)
            logger.debug(f"✅ Generated edge: {edge['source']} -> {edge['target']}")
            logger.debug(f"   ID: {edge_id}")
        else:
            logger.warning(f"❌ Skipping edge: missing necessary handle information")

    # Update graph data
    graph_data['edges'] = fixed_edges
    return graph_data


def stringify_handle(handle_obj: dict) -> str:
    """Convert handle object to Langflow special format string"""
    # Convert object to JSON string, then replace quotes with œ
    json_str = json.dumps(handle_obj, separators=(',', ':'), ensure_ascii=False)
    # Replace quotes with œ (special character used by Langflow)
    langflow_str = json_str.replace('"', 'œ')
    return langflow_str


def generate_edge_id(source: str, source_handle: str, target: str, target_handle: str) -> str:
    """Generate Langflow format edge ID"""
    edge_id = f"xy-edge__{source}{source_handle}-{target}{target_handle}"
    return edge_id


def calculate_langflow_style_layout(graph_data: dict,
                                    node_width: int = 320,
                                    node_height: int = 258,
                                    horizontal_spacing: int = 200,
                                    vertical_spacing: int = 200,
                                    layer_spacing: int = 200) -> dict:
    """Langflow-style layout algorithm"""
    nodes = graph_data.get('nodes', [])
    edges = graph_data.get('edges', [])

    if not nodes:
        return graph_data

    # Create NetworkX graph
    G = nx.DiGraph()

    # Add nodes
    for node in nodes:
        G.add_node(node['id'], **node)

    # Add edges
    for edge in edges:
        if edge.get('source') and edge.get('target'):
            G.add_edge(edge['source'], edge['target'])

    # Calculate layout
    positions = _langflow_hierarchical_layout(
        G,
        node_width=node_width,
        node_height=node_height,
        horizontal_spacing=horizontal_spacing,
        vertical_spacing=vertical_spacing,
        layer_spacing=layer_spacing
    )

    # Apply to nodes
    for node in nodes:
        if node['id'] in positions:
            x, y = positions[node['id']]
            node['position'] = {'x': x, 'y': y}

        node['measured'] = {
            'width': node_width,
            'height': node_height
        }

    return graph_data


def _langflow_hierarchical_layout(G: nx.DiGraph,
                                  node_width: int = 320,
                                  node_height: int = 258,
                                  horizontal_spacing: int = 150,
                                  vertical_spacing: int = 160,
                                  layer_spacing: int = 160) -> Dict:
    """
    Implement Langflow-style hierarchical layout
    Features: left-to-right, elegant spacing, considering component dimensions
    """
    # 1. Topological sorting layers (left to right)
    layers = _topological_layering(G)

    # 2. Reduce crossing edges (beautify connections)
    layers = _reduce_crossings(G, layers)

    # 3. Calculate vertical positions for each layer (center alignment)
    layer_positions = _calculate_layer_positions(layers, node_height, vertical_spacing)

    # 4. Calculate final coordinates
    pos = {}

    for layer_idx, layer in enumerate(layers):
        # X coordinate: left to right
        x = layer_idx * (node_width + layer_spacing)

        # Y coordinate: vertically distributed within this layer
        layer_y_positions = layer_positions[layer_idx]

        for node_idx, node in enumerate(layer):
            y = layer_y_positions[node_idx]
            pos[node] = (x, y)

    return pos


def _topological_layering(G: nx.DiGraph) -> List[List[str]]:
    """Topological sorting layers, handling cycles"""
    layers = []
    remaining_nodes = set(G.nodes())
    in_degree = dict(G.in_degree())

    while remaining_nodes:
        # Find nodes with in-degree 0
        current_layer = [node for node in remaining_nodes if in_degree[node] == 0]

        # Handle cycles
        if not current_layer:
            # Select the node with the most connections from remaining nodes
            node_connections = {node: len(list(G.neighbors(node))) + len(list(G.predecessors(node)))
                                for node in remaining_nodes}
            current_layer = [max(node_connections.keys(), key=node_connections.get)]

        layers.append(current_layer)

        # Update state
        for node in current_layer:
            remaining_nodes.discard(node)
            for successor in G.successors(node):
                if successor in remaining_nodes:
                    in_degree[successor] -= 1

    return layers


def _reduce_crossings(G: nx.DiGraph, layers: List[List[str]]) -> List[List[str]]:
    """Reduce crossing edges using barycenter sorting"""
    if len(layers) <= 1:
        return layers

    # Multiple optimization rounds
    for _ in range(3):  # Iterate 3 times
        # Optimize left to right
        for i in range(1, len(layers)):
            layers[i] = _sort_layer_by_barycenter(G, layers[i - 1], layers[i], direction='down')

        # Optimize right to left
        for i in range(len(layers) - 2, -1, -1):
            layers[i] = _sort_layer_by_barycenter(G, layers[i + 1], layers[i], direction='up')

    return layers


def _sort_layer_by_barycenter(G: nx.DiGraph,
                              reference_layer: List[str],
                              target_layer: List[str],
                              direction: str) -> List[str]:
    """Sort by barycenter position"""
    def get_barycenter(node: str) -> float:
        if direction == 'down':
            # Look at connections from previous layer
            predecessors = [pred for pred in G.predecessors(node) if pred in reference_layer]
            if predecessors:
                positions = [reference_layer.index(pred) for pred in predecessors]
                return sum(positions) / len(positions)
        else:
            # Look at connections from next layer
            successors = [succ for succ in G.successors(node) if succ in reference_layer]
            if successors:
                positions = [reference_layer.index(succ) for succ in successors]
                return sum(positions) / len(positions)

        return float('inf')  # Nodes without connections go last

    # Sort by barycenter position
    return sorted(target_layer, key=get_barycenter)


def _calculate_layer_positions(layers: List[List[str]],
                               node_height: int,
                               vertical_spacing: int) -> Dict[int, List[float]]:
    """Calculate vertical positions of nodes within each layer"""
    layer_positions = {}

    for layer_idx, layer in enumerate(layers):
        if len(layer) == 1:
            # Single node, center it
            layer_positions[layer_idx] = [0]
        else:
            # Multiple nodes, evenly distribute
            total_height = len(layer) * node_height + (len(layer) - 1) * vertical_spacing
            start_y = -total_height / 2

            positions = []
            for i in range(len(layer)):
                y = start_y + i * (node_height + vertical_spacing) + node_height / 2
                positions.append(y)

            layer_positions[layer_idx] = positions

    return layer_positions


async def save_workflow_to_db(workflow_json_path: str,
                              workflow_name: Optional[str] = "",
                              workflow_description: Optional[str] = ""):
    """
    Save workflow to database with proper layout and edge formatting
    
    Args:
        workflow_json_path: Path to the workflow JSON file
        workflow_name: Name of the workflow
        workflow_description: Description of the workflow
        
    Returns:
        Database flow object if successful, None otherwise
    """
    from vibe_surf.langflow.services.deps import get_variable_service, session_scope, get_settings_service
    from vibe_surf.langflow.services.auth.utils import create_super_user
    from vibe_surf.langflow.services.database.models.flow import FlowCreate
    from vibe_surf.langflow.api.v1.flows import _new_flow, _save_flow_to_fs

    with open(workflow_json_path, "r", encoding="utf-8") as f:
        workflow_data = json.load(f)
    
    # Get graph data
    graph_data = workflow_data.get("data", {})
    
    # Ensure viewport is set
    graph_data["viewport"] = {
        "x": 0,
        "y": 0,
        "zoom": 1
    }
    
    # Apply layout algorithm
    graph_data = calculate_langflow_style_layout(graph_data)
    
    # Generate proper Langflow edges
    graph_data = generate_langflow_edges(graph_data)
    
    new_workflow_json_path = os.path.splitext(workflow_json_path)[0] + "-db.json"
    settings_service = get_settings_service()
    username = settings_service.auth_settings.SUPERUSER
    password = settings_service.auth_settings.SUPERUSER_PASSWORD

    async with session_scope() as async_session:
        current_user = await create_super_user(db=async_session, username=username, password=password)
        try:
            flow = FlowCreate(
                name=workflow_name,
                description=workflow_description,
                data=graph_data,
                fs_path=new_workflow_json_path,
            )
            db_flow = await _new_flow(session=async_session, flow=flow, user_id=current_user.id)
            await async_session.commit()
            await async_session.refresh(db_flow)
            await _save_flow_to_fs(db_flow)
            logger.info(f"Add workflow to db successfully! {new_workflow_json_path}")
            return db_flow

        except Exception as e:
            traceback.print_exc()
            return None


async def convert_and_save_workflow(raw_json_path: str,
                                    output_json_path: Optional[str] = None,
                                    save_to_db: bool = True) -> Dict[str, Any]:
    """
    Convert raw workflow recording to Langflow format and optionally save to database
    
    Args:
        raw_json_path: Path to the raw workflow JSON file
        output_json_path: Optional path to save the converted JSON
        save_to_db: Whether to save the workflow to database
        
    Returns:
        Dict containing conversion result and metadata
    """
    try:
        # Convert workflow
        logger.info(f"Converting workflow from {raw_json_path}")
        workflow_data = convert_raw_workflow_to_langflow(raw_json_path)
        
        # Determine output path
        if output_json_path is None:
            base_name = os.path.splitext(raw_json_path)[0]
            output_json_path = f"{base_name}-langflow.json"
        
        # Save to JSON file
        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(workflow_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Converted workflow saved to {output_json_path}")
        
        result = {
            "success": True,
            "message": "Workflow converted successfully",
            "output_path": output_json_path,
            "workflow_name": workflow_data.get("name"),
            "db_flow": None
        }
        
        # Optionally save to database
        if save_to_db:
            db_flow = await save_workflow_to_db(
                output_json_path,
                workflow_data.get("name"),
                workflow_data.get("description")
            )
            result["db_flow"] = db_flow
            if db_flow:
                logger.info(f"Workflow saved to database with ID: {db_flow.id}")
            else:
                logger.warning("Failed to save workflow to database")
        
        return result
        
    except Exception as e:
        logger.error(f"Error converting workflow: {e}")
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Failed to convert workflow: {str(e)}",
            "output_path": None,
            "workflow_name": None,
            "db_flow": None
        }


if __name__ == "__main__":
    """
    Example usage:
    python -m vibe_surf.backend.utils.workflow_converter path/to/raw.json
    """
    import asyncio
    
    if len(sys.argv) < 2:
        print("Usage: python -m vibe_surf.backend.utils.workflow_converter <raw_json_path> [output_json_path]")
        sys.exit(1)
    
    raw_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    result = asyncio.run(convert_and_save_workflow(raw_path, output_path, save_to_db=False))
    
    if result["success"]:
        print(f"✅ Success: {result['message']}")
        print(f"   Output: {result['output_path']}")
    else:
        print(f"❌ Error: {result['message']}")
        sys.exit(1)
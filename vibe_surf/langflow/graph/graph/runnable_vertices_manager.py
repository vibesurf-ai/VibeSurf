import pdb
from collections import defaultdict


class RunnableVerticesManager:
    def __init__(self) -> None:
        self.run_map: dict[str, list[str]] = defaultdict(list)  # Tracks successors of each vertex
        self.run_predecessors: dict[str, list[str]] = defaultdict(list)  # Tracks predecessors for each vertex
        self.vertices_to_run: set[str] = set()  # Set of vertices that are ready to run
        self.vertices_being_run: set[str] = set()  # Set of vertices that are currently running
        self.cycle_vertices: set[str] = set()  # Set of vertices that are in a cycle
        self.ran_at_least_once: set[str] = set()  # Set of vertices that have been run at least once
        self._graph_ref = None  # Reference to the graph for accessing vertex information

    def to_dict(self) -> dict:
        return {
            "run_map": self.run_map,
            "run_predecessors": self.run_predecessors,
            "vertices_to_run": self.vertices_to_run,
            "vertices_being_run": self.vertices_being_run,
            "ran_at_least_once": self.ran_at_least_once,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RunnableVerticesManager":
        instance = cls()
        instance.run_map = data["run_map"]
        instance.run_predecessors = data["run_predecessors"]
        instance.vertices_to_run = data["vertices_to_run"]
        instance.vertices_being_run = data["vertices_being_run"]
        instance.ran_at_least_once = data.get("ran_at_least_once", set())
        return instance

    def __getstate__(self) -> object:
        return {
            "run_map": self.run_map,
            "run_predecessors": self.run_predecessors,
            "vertices_to_run": self.vertices_to_run,
            "vertices_being_run": self.vertices_being_run,
            "ran_at_least_once": self.ran_at_least_once,
        }

    def __setstate__(self, state: dict) -> None:
        self.run_map = state["run_map"]
        self.run_predecessors = state["run_predecessors"]
        self.vertices_to_run = state["vertices_to_run"]
        self.vertices_being_run = state["vertices_being_run"]
        self.ran_at_least_once = state["ran_at_least_once"]

    def all_predecessors_are_fulfilled(self) -> bool:
        return all(not value for value in self.run_predecessors.values())

    def update_run_state(self, run_predecessors: dict, vertices_to_run: set) -> None:
        self.run_predecessors.update(run_predecessors)
        self.vertices_to_run.update(vertices_to_run)
        self.build_run_map(self.run_predecessors, self.vertices_to_run)

    def is_vertex_runnable(self, vertex_id: str, *, is_active: bool, is_loop: bool = False) -> bool:
        """Determines if a vertex is runnable based on its active state and predecessor fulfillment."""
        if not is_active:
            return False
        if vertex_id in self.vertices_being_run:
            return False
        if vertex_id not in self.vertices_to_run:
            return False

        return self.are_all_predecessors_fulfilled(vertex_id, is_loop=is_loop)

    def are_all_predecessors_fulfilled(self, vertex_id: str, *, is_loop: bool) -> bool:
        """Determines if all predecessors for a vertex have been fulfilled.

        This method checks if a vertex is ready to run by verifying that either:
        1. It has no pending predecessors that need to complete first
        2. For vertices in cycles, none of its pending predecessors are also cycle vertices
           (which would create a circular dependency)
        3. For non-cycle vertices, all predecessors must be truly complete (including loop done outputs)

        Args:
            vertex_id (str): The ID of the vertex to check
            is_loop (bool): Whether the vertex is a loop
        Returns:
            bool: True if all predecessor conditions are met, False otherwise
        """
        # Get pending predecessors, return True if none exist
        graph = self._graph_ref
        pending = self.run_predecessors.get(vertex_id, [])
        if not pending:
            all_predecessors = self._get_all_edge_predecessors(graph.get_vertex(vertex_id), graph)
            if is_loop:
                all_ready = all([pred_vertex.built for pred_vertex in all_predecessors if
                                 pred_vertex.id not in self.cycle_vertices or "Loop" in pred_vertex.id])
            else:
                all_ready = all([pred_vertex.built for pred_vertex in all_predecessors])
            return all_ready

        # For cycle vertices, we need special handling but also want to use the new edge-based checking
        if vertex_id in self.cycle_vertices:
            if "Loop" in vertex_id:
                target_vertex = graph.get_vertex(vertex_id)
                all_predecessors = self._get_all_edge_predecessors(target_vertex, graph)
                # Only check non-cycle predecessors to avoid circular dependencies
                non_cycle_predecessors = [pred for pred in all_predecessors if
                                          pred.id not in self.cycle_vertices or "Loop" in pred.id]

                # Add detailed status for each predecessor
                for pred_vertex in non_cycle_predecessors:
                    if not pred_vertex.built:
                        return False

                    if "Loop" in pred_vertex.id:
                        loop_done = self._check_loop_done_completion(pred_vertex)
                        if not loop_done:
                            return False
                return True

            pending_set = set(pending)
            running_predecessors = pending_set & self.vertices_being_run

            # If this vertex has already run at least once, be strict: wait until NOTHING is pending or running
            if vertex_id in self.ran_at_least_once:
                # Wait if there are still pending or running predecessors; otherwise allow.
                return not (pending_set or running_predecessors)

            # FIRST execution of a cycle vertex
            # Allow running **only** if it's a loop AND *all* pending predecessors are cycle vertices
            return is_loop and pending_set <= self.cycle_vertices

        # For non-cycle vertices, check if all predecessors are actually ready
        # This fixes the issue where vertices dependent on loop outputs run too early
        return self._check_predecessors_actually_complete(vertex_id)

    def _check_predecessors_actually_complete(self, vertex_id: str) -> bool:
        """Check if ALL predecessor vertices are actually complete for the requesting vertex.

        This method implements edge-based predecessor checking: find all predecessor vertices
        through incoming edges, not just the current pending_predecessors list.

        Args:
            vertex_id: The vertex requesting to run
            pending_predecessors: List of predecessor vertex IDs that are still pending (for debugging)

        Returns:
            bool: True if ALL predecessors are actually complete for this vertex's needs
        """
        # If we don't have a graph reference, fall back to old behavior
        if not self._graph_ref:
            return False

        graph = self._graph_ref

        try:
            target_vertex = graph.get_vertex(vertex_id)
            # Get ALL predecessor vertices through incoming edges - this is the key fix!
            all_predecessors = self._get_all_edge_predecessors(target_vertex, graph)

            # Check each predecessor
            for pred_vertex in all_predecessors:
                if not self._is_predecessor_truly_complete(pred_vertex, target_vertex, graph):
                    return False

            return True

        except (ValueError, AttributeError) as e:
            return False

    def _get_all_edge_predecessors(self, target_vertex, graph):
        """Get all predecessor vertices through incoming edges."""
        predecessors = []

        # Get all incoming edges to this vertex
        if hasattr(target_vertex, 'incoming_edges'):
            incoming_edges = target_vertex.incoming_edges

            for edge in incoming_edges:
                try:
                    pred_vertex = graph.get_vertex(edge.source_id)
                    predecessors.append(pred_vertex)
                except ValueError:
                    continue

        return predecessors

    def _is_predecessor_truly_complete(self, pred_vertex, target_vertex, graph) -> bool:
        """Check if a single predecessor is truly complete for the target vertex."""
        # Basic check: predecessor must be built
        if not pred_vertex.built:
            return False

        # Special handling for loop vertices
        if pred_vertex.is_loop:
            # For loop vertices, we need to check if the specific output this edge connects to is ready
            is_done = self._is_loop_output_ready_for_target(pred_vertex, target_vertex, graph)
            return is_done

        return True

    def _is_loop_output_ready_for_target(self, loop_vertex, target_vertex, graph) -> bool:
        """Check if the loop's output that the target depends on is ready."""
        # Find the edge connecting loop to target
        connecting_edges = [
            edge for edge in loop_vertex.outgoing_edges
            if edge.target_id == target_vertex.id
        ]

        for edge in connecting_edges:
            source_handle = edge.source_handle
            if hasattr(source_handle, 'name'):
                if 'done' in source_handle.name.lower():  # Check for 'done' in handle name
                    return self._check_loop_done_completion(loop_vertex)
                elif 'item' in source_handle.name.lower():
                    return self._check_loop_has_data(loop_vertex)
                else:
                    return loop_vertex.built

        return self._check_loop_done_completion(loop_vertex)

    def _check_loop_has_data(self, loop_vertex) -> bool:
        """Check if a loop component has data available for item output.

        For components depending on 'item' output, they must wait until the loop
        component has data loaded in its context.
        """
        # Basic check: loop must be built first
        if not loop_vertex.built:
            return False

        # Check if the loop component has data loaded
        if hasattr(loop_vertex, 'custom_component') and loop_vertex.custom_component:
            component = loop_vertex.custom_component
            if hasattr(component, 'ctx') and component.ctx:
                loop_id = component._id
                data_length = len(component.ctx.get(f"{loop_id}_data", []))
                has_data = data_length > 0
                return has_data

        return False

    def _check_loop_done_completion(self, loop_vertex) -> bool:
        """Check multiple indicators to determine if a loop has completed its 'done' output."""
        # print("_check_loop_done_completion")
        # Method 2: Check if the loop component has a context indicating completion
        if hasattr(loop_vertex, 'custom_component') and loop_vertex.custom_component:
            component = loop_vertex.custom_component
            # For Loop components, check if the loop index exceeds data length
            if hasattr(component, 'ctx') and component.ctx:
                loop_id = component._id
                current_index = component.ctx.get(f"{loop_id}_index", 0)
                data_length = len(component.ctx.get(f"{loop_id}_data", []))
                return data_length > 0 and current_index >= data_length

        return False

    def _has_new_loop_data_available(self, vertex_id: str) -> bool:
        """Check if there's new loop data available for cycle vertices to process.

        This method determines if cycle vertices should re-execute by checking:
        1. If any loop vertex in the cycle has progressed its iteration
        2. If there's new data that cycle vertices haven't processed yet

        Args:
            vertex_id: The cycle vertex to check

        Returns:
            bool: True if new loop data is available for processing
        """
        if not self._graph_ref:
            return False

        graph = self._graph_ref

        try:
            # Find loop vertices that this vertex depends on (directly or indirectly)
            target_vertex = graph.get_vertex(vertex_id)
            loop_predecessors = []

            # Check all predecessors to find loop components
            all_predecessors = self._get_all_edge_predecessors(target_vertex, graph)
            for pred in all_predecessors:
                if pred.is_loop and pred.id in self.cycle_vertices:
                    loop_predecessors.append(pred)

            # For each loop predecessor, check if it has new data
            for loop_vertex in loop_predecessors:
                if hasattr(loop_vertex, 'custom_component') and loop_vertex.custom_component:
                    component = loop_vertex.custom_component
                    if hasattr(component, 'ctx') and component.ctx:
                        loop_id = component._id
                        current_index = component.ctx.get(f"{loop_id}_current_index", 0)
                        data_length = len(component.ctx.get(f"{loop_id}_data", []))

                        # There's new data if the loop has progressed but hasn't finished
                        # and the current iteration should trigger downstream processing
                        if data_length > 0 and current_index < data_length:
                            return True

            return False

        except (ValueError, AttributeError):
            return False

    def set_graph_reference(self, graph):
        """Set a reference to the graph for predecessor checking."""
        self._graph_ref = graph

    def remove_from_predecessors(self, vertex_id: str) -> None:
        """Removes a vertex from the predecessor list of its successors."""
        predecessors = self.run_map.get(vertex_id, [])
        for predecessor in predecessors:
            if vertex_id in self.run_predecessors[predecessor]:
                self.run_predecessors[predecessor].remove(vertex_id)

    def build_run_map(self, predecessor_map, vertices_to_run) -> None:
        """Builds a map of vertices and their runnable successors."""
        self.run_map = defaultdict(list)
        for vertex_id, predecessors in predecessor_map.items():
            for predecessor in predecessors:
                self.run_map[predecessor].append(vertex_id)
        self.run_predecessors = predecessor_map.copy()
        self.vertices_to_run = vertices_to_run

    def update_vertex_run_state(self, vertex_id: str, *, is_runnable: bool) -> None:
        """Updates the runnable state of a vertex."""
        if is_runnable:
            self.vertices_to_run.add(vertex_id)
        else:
            self.vertices_being_run.discard(vertex_id)

    def remove_vertex_from_runnables(self, v_id) -> None:
        self.update_vertex_run_state(v_id, is_runnable=False)
        self.remove_from_predecessors(v_id)

    def add_to_vertices_being_run(self, v_id) -> None:
        self.vertices_being_run.add(v_id)

    def add_to_cycle_vertices(self, v_id):
        self.cycle_vertices.add(v_id)

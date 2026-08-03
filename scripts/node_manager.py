import csv
import os
import re

try:
    from nicegui import ui
except ImportError:
    pass

class NodeManager:
    def __init__(self):
        self.nodes = []
        self.paths = []
        self.nodes_file = ""
        self.paths_file = ""
        self.hidden_paths = set()
        self.hidden_nodes = set()
        self.selected_path_id = None
        self.selected_node_id = None
        self.node_ui_rows = {}
        self.path_ui_rows = {}

    @staticmethod
    def get_node_type(node_id="", name="", node_type=""):
        """
        Classifies node as 'via' or 'inspection'.
        If 'via' is present anywhere in node_id, name, or node_type, returns 'via'.
        Otherwise, returns 'inspection'.
        """
        full_text = f"{node_id} {name} {node_type}".lower()
        if 'via' in full_text:
            return 'via'
        return 'inspection'

    def load_nodes(self, csv_path):
        """Loads nodes.csv where each row is kept exactly as read."""
        if not os.path.exists(csv_path):
            return False
        self.nodes = []
        self.nodes_file = csv_path
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if row:
                    while len(row) < 8:
                        row.append("1")
                    if str(row[7]).strip() == "":
                        row[7] = "1"
                    self.nodes.append(row)
        return True

    def save_nodes(self, csv_path=None):
        """Saves back nodes.csv with minimal quoting to match original style."""
        path = csv_path or self.nodes_file
        if not path:
            return False
        with open(path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            for row in self.nodes:
                writer.writerow(row)
        self.nodes_file = path
        return True

    def load_paths(self, csv_path):
        """Loads paths.csv where each row is kept exactly as read."""
        if not os.path.exists(csv_path):
            return False
        self.paths = []
        self.paths_file = csv_path
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if row:
                    self.paths.append(row)
        return True

    def save_paths(self, csv_path=None):
        """Saves back paths.csv with minimal quoting to match original style."""
        path = csv_path or self.paths_file
        if not path:
            return False
        with open(path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            for row in self.paths:
                writer.writerow(row)
        self.paths_file = path
        return True

    def get_node_by_id(self, node_id):
        for row in self.nodes:
            if len(row) > 0 and row[0] == node_id:
                return row
        return None

    def get_paths_from_node(self, node_id):
        paths = []
        for row in self.paths:
            if len(row) > 1 and row[1] == node_id:
                paths.append(row)
        return paths

    def _handle_node_click(self, e, nid, on_update_callback):
        old_id = getattr(self, 'selected_node_id', None)
        self.selected_node_id = nid
        try:
            if old_id in self.node_ui_rows and not getattr(self.node_ui_rows[old_id], 'is_deleted', False):
                old_hidden = old_id in self.hidden_nodes
                self.node_ui_rows[old_id].style(f'background-color: {"#002a55" if old_hidden else "#004080"}')
        except Exception:
            pass

        try:
            if nid in self.node_ui_rows and not getattr(self.node_ui_rows[nid], 'is_deleted', False):
                self.node_ui_rows[nid].style('background-color: #0ea5e9')
                try:
                    ui.run_javascript(f'setTimeout(() => {{ document.getElementById("c{self.node_ui_rows[nid].id}").scrollIntoView({{behavior: "smooth", block: "start"}}); }}, 50);')
                except Exception:
                    pass
        except Exception:
            pass

        on_update_callback(update_sidebar=False)

    def _handle_node_eye(self, e, nid, on_update_callback):
        if nid in self.hidden_nodes:
            self.hidden_nodes.remove(nid)
        else:
            self.hidden_nodes.add(nid)
        on_update_callback(update_sidebar=True)
        
    def _handle_node_delete(self, e, nid, on_update_callback):
        on_update_callback(update_sidebar=False, push_undo=True)
        self.nodes = [n for n in self.nodes if len(n) > 0 and n[0] != nid]
        if getattr(self, 'selected_node_id', None) == nid:
            self.selected_node_id = None
        on_update_callback(update_sidebar=True)

    def _handle_path_click(self, e, pid, on_update_callback):
        old_id = getattr(self, 'selected_path_id', None)
        self.selected_path_id = pid
        try:
            if old_id in self.path_ui_rows and not getattr(self.path_ui_rows[old_id], 'is_deleted', False):
                old_hidden = old_id in self.hidden_paths
                self.path_ui_rows[old_id].style(f'background-color: {"#002a55" if old_hidden else "#004080"}')
        except Exception:
            pass

        try:
            if pid in self.path_ui_rows and not getattr(self.path_ui_rows[pid], 'is_deleted', False):
                self.path_ui_rows[pid].style('background-color: #0ea5e9')
                try:
                    ui.run_javascript(f'setTimeout(() => {{ document.getElementById("c{self.path_ui_rows[pid].id}").scrollIntoView({{behavior: "smooth", block: "start"}}); }}, 50);')
                except Exception:
                    pass
        except Exception:
            pass

        on_update_callback(update_sidebar=False)

    def _handle_path_eye(self, e, pid, on_update_callback):
        if pid in self.hidden_paths:
            self.hidden_paths.remove(pid)
        else:
            self.hidden_paths.add(pid)
        on_update_callback(update_sidebar=True)
        
    def _handle_path_delete(self, e, pid, on_update_callback):
        on_update_callback(update_sidebar=False, push_undo=True)
        self.paths = [p for p in self.paths if p[0] != pid]
        if getattr(self, 'selected_path_id', None) == pid:
            self.selected_path_id = None
        on_update_callback(update_sidebar=True)

    def render_left_sidebar_nodes(self, on_update_callback, search_query=""):
        """Renders the node list UI components using NiceGUI."""
        self.node_ui_rows.clear()
        def sort_key(row):
            return [int(t) if t.isdigit() else t.lower() for t in re.split('([0-9]+)', str(row[0]) if len(row) > 0 else "")]
            
        for row in sorted(self.nodes, key=sort_key):
            if len(row) < 1: continue
            n_id = row[0]
            name = row[1] if len(row) > 1 else ""
            display_name = f"[{n_id}] {name}".strip()
            
            if search_query and search_query not in display_name.lower():
                continue
                
            is_hidden = n_id in self.hidden_nodes
            is_selected = (n_id == getattr(self, 'selected_node_id', None))
            bg_color = '#0ea5e9' if is_selected else ('#002a55' if is_hidden else '#004080')
            text_color = 'white'
            
            with ui.row().classes('items-center no-wrap w-full').style(f'background-color: {bg_color}; padding: 8px; border-radius: 6px; cursor: pointer;') as row_ui:
                self.node_ui_rows[n_id] = row_ui
                with ui.element('div').classes('flex-1 flex items-center').on('click', lambda e, nid=n_id: self._handle_node_click(e, nid, on_update_callback)):
                    ui.label(f'[{n_id}]').classes('font-bold mr-2 text-yellow-300')
                    ui.label(name).classes(f'overflow-hidden text-ellipsis whitespace-nowrap text-{text_color}')
                
                icon_name = 'visibility_off' if is_hidden else 'visibility'
                ui.button(icon=icon_name, on_click=lambda e, nid=n_id: self._handle_node_eye(e, nid, on_update_callback)).props('flat dense').style('color: white; padding: 0; margin-right: 8px;')
                ui.button(icon='delete', on_click=lambda e, nid=n_id: self._handle_node_delete(e, nid, on_update_callback)).props('flat dense color=red-9').style('padding: 0;')

    def render_left_sidebar_paths(self, on_update_callback, search_query=""):
        """Renders the path list UI components using NiceGUI."""
        self.path_ui_rows.clear()
        def sort_key(row):
            return [int(t) if t.isdigit() else t.lower() for t in re.split('([0-9]+)', str(row[0]) if len(row) > 0 else "")]
            
        for row in sorted(self.paths, key=sort_key):
            if len(row) < 3: continue
            p_id, n1, n2 = row[0], row[1], row[2]
            name = f"{n1} ➡ {n2}"
            
            if search_query and search_query not in name.lower() and search_query not in str(p_id):
                continue
                
            is_hidden = p_id in self.hidden_paths
            is_selected = (p_id == self.selected_path_id)
            
            bg_color = '#0ea5e9' if is_selected else ('#002a55' if is_hidden else '#004080')
            text_color = 'white'
            
            with ui.row().classes('items-center no-wrap w-full').style(f'background-color: {bg_color}; padding: 8px; border-radius: 6px; cursor: pointer;') as row_ui:
                self.path_ui_rows[p_id] = row_ui
                with ui.element('div').classes('flex-1 flex items-center').on('click', lambda e, pid=p_id: self._handle_path_click(e, pid, on_update_callback)):
                    ui.label(f'[{p_id}]').classes('font-bold mr-2 text-cyan-300')
                    ui.label(name).classes(f'overflow-hidden text-ellipsis whitespace-nowrap text-{text_color}')
                
                icon_name = 'visibility_off' if is_hidden else 'visibility'
                ui.button(icon=icon_name, on_click=lambda e, pid=p_id: self._handle_path_eye(e, pid, on_update_callback)).props('flat dense').style('color: white; padding: 0; margin-right: 8px;')
                ui.button(icon='delete', on_click=lambda e, pid=p_id: self._handle_path_delete(e, pid, on_update_callback)).props('flat dense color=red-9').style('padding: 0;')

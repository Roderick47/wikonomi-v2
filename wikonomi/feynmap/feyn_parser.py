import ast
import os
import re
from pathlib import Path

class FeynExtractor:
    def __init__(self, project_path):
        self.project_path = Path(project_path)
        self.graph = {"nodes": [], "edges": []}

    def scan(self):
        for root, _, files in os.walk(self.project_path):
            for file in files:
                file_path = Path(root) / file
                if file.endswith(".py"):
                    self._parse_python(file_path)
                elif file.endswith(".html"):
                    self._parse_template(file_path)
        return self.graph

    def _parse_python(self, path):
        with open(path, "r", encoding="utf-8") as f:
            try:
                tree = ast.parse(f.read())
                for node in ast.walk(tree):
                    # Particle Identification (Django Models)
                    if isinstance(node, ast.ClassDef):
                        if any(base.attr == 'Model' for base in node.bases if hasattr(base, 'attr')):
                            self.graph["nodes"].append({"id": node.name, "type": "PARTICLE", "file": path.name})
                    
                    # Vertex Identification (Django Views)
                    if isinstance(node, ast.ClassDef) and ("View" in node.name or "APIView" in node.name):
                         self.graph["nodes"].append({"id": node.name, "type": "VERTEX", "file": path.name})
                         
                    # Transition Identification (Serializers)
                    if isinstance(node, ast.ClassDef) and "Serializer" in node.name:
                         self.graph["nodes"].append({"id": node.name, "type": "TRANSFORM", "file": path.name})
            except Exception:
                pass

    def _parse_template(self, path):
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            # Observation Points (Variables in Templates)
            vars = re.findall(r'{{\s*([\w\.]+)\s*}}', content)
            for v in vars:
                self.graph["edges"].append({
                    "source": path.name, 
                    "target": v.split('.')[0], 
                    "type": "OBSERVATION"
                })
import os
import ast
import re

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(ROOT_DIR, "app")
TEMPLATES_DIR = os.path.join(ROOT_DIR, "templates")

def get_python_files(dir_path):
    py_files = []
    for root, dirs, files in os.walk(dir_path):
        if any(d in root.split(os.sep) for d in ['__pycache__', '.git', '.pytest_cache', 'build', 'dist', 'installer']):
            continue
        for f in files:
            if f.endswith('.py'):
                py_files.append(os.path.join(root, f))
    return py_files

def get_all_files(dir_path):
    all_files = []
    for root, dirs, files in os.walk(dir_path):
        if any(d in root.split(os.sep) for d in ['__pycache__', '.git', '.pytest_cache', 'build', 'dist', 'installer']):
            continue
        for f in files:
            all_files.append(os.path.join(root, f))
    return all_files

class ImportVisitor(ast.NodeVisitor):
    def __init__(self):
        self.imports = [] # list of dicts: {name, line, is_alias, node}
        self.used_names = set()

    def visit_Import(self, node):
        for name in node.names:
            alias = name.asname or name.name.split('.')[0]
            self.imports.append({
                'name': alias,
                'full_name': name.name,
                'line': node.lineno,
                'type': 'import'
            })
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        for name in node.names:
            if name.name == '*':
                # If it's a wildcard import, we won't easily know without executing, but we can note it
                continue
            alias = name.asname or name.name
            self.imports.append({
                'name': alias,
                'full_name': f"{node.module or ''}.{name.name}",
                'line': node.lineno,
                'type': 'import_from'
            })
        self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.used_names.add(node.id)
        self.generic_visit(node)

def audit_unused_imports():
    py_files = get_python_files(APP_DIR)
    unused_by_file = {}
    for filepath in py_files:
        rel_path = os.path.relpath(filepath, ROOT_DIR)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            tree = ast.parse(content, filepath)
            visitor = ImportVisitor()
            visitor.visit(tree)
            
            # Filter imports whose alias/name is NOT in used_names
            # Note: We need to be careful with __init__.py files where imports might be exposing API
            is_init = filepath.endswith('__init__.py')
            
            unused = []
            for imp in visitor.imports:
                name = imp['name']
                # If name is not used in the file, and it's not exposing APIs in __init__.py
                if name not in visitor.used_names:
                    if is_init:
                        # In __init__.py, imported names might be meant for re-export.
                        # Let's check if they are in __all__ if defined, or just skip __init__.py for unused imports audit unless we are sure.
                        continue
                    # Ignore common standard imports that might be placeholders, but let's list them
                    if name in ['annotations']:
                        continue
                    unused.append(imp)
            if unused:
                unused_by_file[rel_path] = unused
        except Exception as e:
            print(f"Error parsing {rel_path}: {e}")
    return unused_by_file

def audit_file_dependencies():
    # Find all python files, convert to module paths, check if they are imported anywhere
    py_files = get_python_files(APP_DIR)
    module_paths = []
    file_to_module = {}
    for fp in py_files:
        rel_path = os.path.relpath(fp, ROOT_DIR)
        # Convert path to module format, e.g., app.core.config
        parts = rel_path[:-3].split(os.sep)
        mod_name = ".".join(parts)
        module_paths.append(mod_name)
        file_to_module[fp] = mod_name

    # Read all files to search for references to these modules
    imports_count = {mod: 0 for mod in module_paths}
    # Also keep track of relative imports or parts of imports
    for fp in py_files:
        with open(fp, 'r', encoding='utf-8') as f:
            content = f.read()
        for mod in module_paths:
            # Check if module name is referenced in content
            # e.g., "import app.core.config" or "from app.core import config" or "from app.core.config import ..."
            # We look for module name as a whole word
            pattern = r'\b' + re.escape(mod) + r'\b'
            # Also check if it's imported relatively, but absolute import check is safer
            # Let's see if this file itself is the module (don't count self-import unless it really imports itself)
            if file_to_module[fp] == mod:
                continue
            if re.search(pattern, content):
                imports_count[mod] += 1
                
            # If the module is app.web.router, check if it's imported as router in app/web/ or main.py
            # Let's also do a fallback check for the module's basename if it's imported relatively.
            # e.g. for app/web/router.py imported from app/web/deps.py as "from . import router" or "from .router import ..."
            mod_parts = mod.split('.')
            if len(mod_parts) > 1:
                sub_mod_pattern = r'from\s+\.+\s+import\s+.*\b' + re.escape(mod_parts[-1]) + r'\b'
                sub_mod_pattern_2 = r'from\s+\.+' + re.escape(mod_parts[-1]) + r'\b'
                # Check if importing from parent/sibling
                if (re.search(sub_mod_pattern, content) or re.search(sub_mod_pattern_2, content)) and os.path.dirname(fp) == os.path.dirname(os.path.join(ROOT_DIR, *mod_parts)):
                    imports_count[mod] += 1

    return imports_count

class DefinitionVisitor(ast.NodeVisitor):
    def __init__(self):
        self.definitions = [] # list of (name, type, lineno)

    def visit_FunctionDef(self, node):
        # Ignore private helper methods / functions starting with _
        if not node.name.startswith('_'):
            self.definitions.append((node.name, 'function', node.lineno))
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        if not node.name.startswith('_'):
            self.definitions.append((node.name, 'class', node.lineno))
        self.generic_visit(node)

def audit_unused_definitions():
    # Scan services and utils directories for functions/classes, and see if they are referenced anywhere else
    py_files = get_python_files(APP_DIR)
    
    # We want to identify unused functions and classes in app/services/ and app/utils/
    target_dirs = ['services', 'utils', 'repositories']
    
    definitions_by_file = {}
    all_defined_names = {} # name -> (filepath, type, line)
    
    for fp in py_files:
        rel_path = os.path.relpath(fp, ROOT_DIR)
        parts = rel_path.split(os.sep)
        # Check if the file is in app/services/ app/utils/ app/repositories/ etc.
        if len(parts) >= 3 and parts[0] == 'app' and parts[1] in target_dirs:
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    content = f.read()
                tree = ast.parse(content, fp)
                visitor = DefinitionVisitor()
                visitor.visit(tree)
                if visitor.definitions:
                    definitions_by_file[rel_path] = visitor.definitions
                    for name, dtype, line in visitor.definitions:
                        if name not in all_defined_names:
                            all_defined_names[name] = []
                        all_defined_names[name].append((rel_path, dtype, line))
            except Exception as e:
                print(f"Error parsing {rel_path} for definitions: {e}")

    # Now check usage of these defined names across all python files and templates
    # We count references. If a defined name is referenced in ANY file other than its defining file, it's used.
    usage_counts = {name: 0 for name in all_defined_names}
    
    # Check in Python files
    for fp in py_files:
        rel_path = os.path.relpath(fp, ROOT_DIR)
        with open(fp, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # To avoid false negatives, we also search for token matches as whole words
        # (Using simple regex search or ast.Name checks. Regex search is more conservative/safer
        # as it will find references even in dynamic usage, routes, templates, etc.)
        for name in all_defined_names:
            # Skip if this is the defining file (we only care if it's imported/used elsewhere)
            defining_files = [x[0] for x in all_defined_names[name]]
            if rel_path in defining_files:
                # Still check if it is used multiple times in the defining file if we want,
                # but typically we only care if it's used *externally*.
                # Wait, if a service function is only defined in its file and never used anywhere at all (not even locally), it is unused.
                # Let's count references in other files.
                pass
            
            # Count occurrences as whole word
            pattern = r'\b' + re.escape(name) + r'\b'
            matches = len(re.findall(pattern, content))
            if rel_path in defining_files:
                # If it's the defining file, subtract 1 for the definition itself (e.g. "def name" or "class name")
                # Wait, to be precise, let's just count uses in OTHER files.
                # If there are any matches in OTHER files, then usage_counts[name] += matches.
                pass
            else:
                usage_counts[name] += matches

    # Check in html files (templates)
    html_files = []
    for root, dirs, files in os.walk(TEMPLATES_DIR):
        for f in files:
            if f.endswith('.html'):
                html_files.append(os.path.join(root, f))
                
    for fp in html_files:
        try:
            with open(fp, 'r', encoding='utf-8') as f:
                content = f.read()
            for name in all_defined_names:
                pattern = r'\b' + re.escape(name) + r'\b'
                usage_counts[name] += len(re.findall(pattern, content))
        except Exception as e:
            pass

    return all_defined_names, usage_counts

if __name__ == "__main__":
    print("=== AUDITING UNUSED IMPORTS ===")
    unused_imp = audit_unused_imports()
    for f, imps in sorted(unused_imp.items()):
        print(f"\n{f}:")
        for imp in imps:
            print(f"  Line {imp['line']}: unused import '{imp['name']}' (full: {imp['full_name']})")
            
    print("\n=== AUDITING MODULE INTER-DEPENDENCIES ===")
    module_imports = audit_file_dependencies()
    unused_modules = []
    for mod, count in sorted(module_imports.items()):
        # Let's filter modules that are entry points, like main, launcher, router, or alembic/app init
        is_entry = any(x in mod for x in ['app.main', 'app.web.router', 'app.__init__'])
        if count == 0 and not is_entry:
            unused_modules.append(mod)
            print(f"Module '{mod}' is imported/referenced 0 times in the rest of the application.")

    print("\n=== AUDITING UNUSED FUNCTIONS & CLASSES IN SERVICES/UTILS/REPOSITORIES ===")
    all_defs, usage = audit_unused_definitions()
    unused_defs = []
    for name, defs in sorted(all_defs.items()):
        if usage[name] == 0:
            for filepath, dtype, line in defs:
                # Double check: if it's a pytest file or something, ignore, but we only scanned target_dirs
                # Some names might be common web-framework names or hooks, we can review them
                unused_defs.append((name, filepath, dtype, line))
                print(f"Unused {dtype} '{name}' in {filepath}:{line}")

import os
import re

def update_file(path):
    with open(path, 'r') as f:
        content = f.read()

    # Replace 'import apply_agent' with 'from src import legacy_apply_agent as apply_agent'
    content = re.sub(r'^import apply_agent$', 'from src import legacy_apply_agent as apply_agent', content, flags=re.MULTILINE)
    
    # Replace 'from apply_agent import' with 'from src.legacy_apply_agent import'
    content = content.replace('from apply_agent import', 'from src.legacy_apply_agent import')
    
    # Replace 'apply_agent.' with 'apply_agent.' (no change needed if imported as apply_agent)
    
    # Also in tests/search/test_search_pagination.py: monkeypatch.setattr(apply_agent.time ... )
    
    with open(path, 'w') as f:
        f.write(content)

for root, _, files in os.walk('.'):
    if 'venv' in root or '.git' in root or 'node_modules' in root or '__pycache__' in root:
        continue
    for file in files:
        if file.endswith('.py') and file != 'refactor_apply_agent.py':
            update_file(os.path.join(root, file))

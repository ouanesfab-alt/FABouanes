import sys
from pathlib import Path
import re

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    log_path = Path(r"C:\Users\massi\.gemini\antigravity\brain\8126c5c0-5efd-4ce3-8b0e-9ea070941618\.system_generated\tasks\task-7625.log")
    if not log_path.exists():
        print(f"Log path does not exist: {log_path}")
        return
        
    content = log_path.read_text("utf-8")
    
    failures = re.findall(r"(?:_[^\n]*\n(?:[^\n]*\n){0,40}?E\s+[^\n]*)", content)
    print(f"Found {len(failures)} failures snippets:")
    for i, fail in enumerate(failures[:10]):
        print(f"\n--- Failure {i+1} ---")
        print(fail)

if __name__ == "__main__":
    main()

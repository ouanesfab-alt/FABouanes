import re
from pathlib import Path

def main():
    log_path = Path(r"C:\Users\massi\.gemini\antigravity\brain\8126c5c0-5efd-4ce3-8b0e-9ea070941618\.system_generated\tasks\task-7683.log")
    if not log_path.exists():
        print(f"Log path does not exist: {log_path}")
        return
        
    content = log_path.read_text("utf-8")
    
    # Let's find all lines starting with "FAIL" or "ERROR" in the summary
    # and print lines of failures.
    # Pytest failure sections start with something like "____ test_name ____"
    # and end with another test or "=== short test summary info ==="
    
    sections = re.split(r"(^_{10,}.*_{10,}\n)", content, flags=re.MULTILINE)
    print(f"Total sections: {len(sections)}")
    
    failures = []
    for i in range(1, len(sections), 2):
        header = sections[i]
        body = sections[i+1] if i+1 < len(sections) else ""
        # Find the exception line, usually starts with "E   "
        exc_lines = [line for line in body.split('\n') if line.startswith('E   ')]
        failures.append((header.strip(), exc_lines))
        
    print(f"Found {len(failures)} test failures/errors:")
    for idx, (head, excs) in enumerate(failures):
        # Clean header for encoding
        safe_head = head.encode('ascii', errors='replace').decode('ascii')
        print(f"\n--- {idx+1}. {safe_head} ---")
        for exc in excs[-3:]:  # Print the last 3 E lines which show the final error
            safe_exc = exc.encode('ascii', errors='replace').decode('ascii')
            print(safe_exc)

if __name__ == "__main__":
    main()

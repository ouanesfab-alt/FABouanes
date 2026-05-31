import os
import json
from pathlib import Path

def main():
    brain_root = Path(r"C:\Users\massi\.gemini\antigravity\brain")
    if not brain_root.exists():
        print(f"Brain root does not exist: {brain_root}")
        return
        
    for log_file in brain_root.glob("**/transcript.jsonl"):
        print(f"\nScanning: {log_file}")
        with open(log_file, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f):
                try:
                    data = json.loads(line)
                    # Check messages
                    content = data.get("content", "")
                    if content and ("### " in content or "⚠️" in content or "✅" in content or "FAILED" in content):
                        print(f"  Line {idx} content contains interesting headings (len={len(content)}):")
                        # print first 200 chars
                        print(f"    {content[:200].strip()}...")
                    # Check tool calls
                    if "tool_calls" in data:
                        for tc in data["tool_calls"]:
                            if tc.get("name") in ("send_message", "write_to_file", "replace_file_content"):
                                args = tc.get("args", {})
                                text = ""
                                if "Message" in args:
                                    text = args["Message"]
                                elif "CodeContent" in args:
                                    text = args["CodeContent"]
                                if text and ("Audit" in text or "Improvement" in text or "Suggestions" in text or "dette technique" in text.lower()):
                                    print(f"  Line {idx} tool {tc['name']} contains text (len={len(text)}):")
                                    print(f"    {text[:300].strip()}...")
                except Exception as e:
                    pass

if __name__ == "__main__":
    main()

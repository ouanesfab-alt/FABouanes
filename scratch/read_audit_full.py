import json
from pathlib import Path

def main():
    log_path = Path(r"C:\Users\massi\.gemini\antigravity\brain\d1ddafc1-c047-444c-8dbd-7765fb0a4e56\.system_generated\logs\transcript.jsonl")
    if not log_path.exists():
        print(f"Log path does not exist: {log_path}")
        return
        
    with open(log_path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            try:
                data = json.loads(line)
                if "tool_calls" in data:
                    for tc in data["tool_calls"]:
                        if tc.get("name") == "send_message":
                            msg = tc.get("args", {}).get("Message", "")
                            if msg and "Audit" in msg:
                                out_path = Path("scratch/audit_report_complete.txt")
                                out_path.write_text(msg, encoding="utf-8")
                                print(f"Wrote audit report to {out_path} ({len(msg)} characters)")
            except Exception as e:
                pass

if __name__ == "__main__":
    main()

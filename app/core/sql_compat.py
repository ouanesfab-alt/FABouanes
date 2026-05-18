from __future__ import annotations

def split_sql_script(script: str) -> list[str]:
    statements = []
    current = []
    in_dollar = False
    in_single_quote = False
    in_double_quote = False
    
    i = 0
    n = len(script)
    while i < n:
        char = script[i]
        
        if char == '$' and i + 1 < n and script[i+1] == '$':
            in_dollar = not in_dollar
            current.append('$$')
            i += 2
            continue
            
        if not in_dollar:
            if char == "'" and (i == 0 or script[i-1] != '\\'):
                in_single_quote = not in_single_quote
            elif char == '"' and (i == 0 or script[i-1] != '\\'):
                in_double_quote = not in_double_quote
                
        if char == ';' and not in_dollar and not in_single_quote and not in_double_quote:
            stmt = "".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
        else:
            current.append(char)
        i += 1
        
    stmt = "".join(current).strip()
    if stmt:
        statements.append(stmt)
    return statements

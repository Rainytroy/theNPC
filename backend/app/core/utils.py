import json
import re
from typing import Dict, Any, Optional

def extract_json_with_stack(text: str, start_char: str = '{') -> Optional[str]:
    """
    使用栈匹配完整的JSON对象或数组
    
    Args:
        text: 要搜索的文本
        start_char: 起始字符 ('{' 或 '[')
    
    Returns:
        完整的JSON字符串，如果未找到则返回None
    """
    start = text.find(start_char)
    if start == -1:
        return None
    
    # 确定配对的结束字符
    end_char = '}' if start_char == '{' else ']'
    
    stack = []
    in_string = False
    escape_next = False
    
    for i in range(start, len(text)):
        char = text[i]
        
        # 处理转义字符
        if char == '\\' and not escape_next:
            escape_next = True
            continue
        
        # 处理字符串边界
        if char == '"' and not escape_next:
            in_string = not in_string
        
        escape_next = False
        
        # 只在字符串外处理括号
        if not in_string:
            if char in ('{', '['):
                stack.append(char)
            elif char in ('}', ']'):
                if stack:
                    stack.pop()
                    # 栈空了，说明找到完整的JSON
                    if not stack:
                        return text[start:i+1]
    
    return None

def repair_truncated_json(json_str: str) -> str:
    """尝试修复截断的JSON字符串（补全缺失的括号和引号）"""
    if not json_str:
        return json_str
        
    stack = []
    in_string = False
    escape = False
    
    for char in json_str:
        if char == '"' and not escape:
            in_string = not in_string
        
        if char == '\\' and not escape:
            escape = True
            continue
        escape = False
        
        if not in_string:
            if char == '{':
                stack.append('}')
            elif char == '[':
                stack.append(']')
            elif char == '}' or char == ']':
                if stack:
                    # 简单的栈匹配，不强制检查类型匹配，假设结构大致正确
                    if stack[-1] == char:
                        stack.pop()
    
    # 如果字符串未闭合，补全引号
    if in_string:
        json_str += '"'
    
    # 补全缺失的闭合括号
    while stack:
        json_str += stack.pop()
        
    return json_str

def repair_unescaped_quotes(json_str: str) -> str:
    """
    智能修复JSON字符串值中未转义的双引号
    例如: "desc": "He said "Hello"" -> "desc": "He said \"Hello\""
    """
    if not json_str:
        return json_str
        
    result = []
    in_string = False
    escape = False
    length = len(json_str)
    
    i = 0
    while i < length:
        char = json_str[i]
        
        if char == '\\':
            # 保留转义符
            result.append(char)
            # 添加下一个字符（无论是什么）
            if i + 1 < length:
                result.append(json_str[i+1])
                i += 2
                continue
            else:
                i += 1
                continue
                
        if char == '"':
            if not in_string:
                # 进入字符串
                in_string = True
                result.append(char)
            else:
                # 在字符串内遇到引号，检查是否是结束引号
                # 结束引号后面通常跟着：空白 + (逗号 或 结束大括号 或 结束中括号 或 冒号)
                # 注意：冒号是 key 的结束引号后
                
                is_closing = False
                # 向前看
                j = i + 1
                while j < length and json_str[j].isspace():
                    j += 1
                
                if j < length and json_str[j] in ',}]:':
                    is_closing = True
                
                if is_closing:
                    in_string = False
                    result.append(char)
                else:
                    # 不是结束引号，说明是内容中的引号，需要转义
                    result.append('\\"')
        else:
            result.append(char)
            
        i += 1
        
    return "".join(result)

def parse_json_from_llm(text: str) -> Dict[str, Any]:
    """
    多重策略解析LLM输出的JSON
    
    策略优先级：
    1. Markdown json代码块（```json ... ```）
    2. 普通代码块（``` ... ```）
    3. 栈匹配纯JSON对象
    4. 栈匹配纯JSON数组
    5. 尝试修复截断的JSON
    
    Args:
        text: LLM的响应文本
    
    Returns:
        解析后的字典，如果解析失败则返回空字典
    """
    if not text:
        print("DEBUG: Empty input text")
        return {}
    
    json_str = None
    method = "unknown"
    
    try:
        # ===== 策略1: Markdown json 代码块 =====
        match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
        if match:
            code_block = match.group(1).strip()
            # 检测代码块内第一个字符是 [ 还是 {，优先匹配对应类型
            first_bracket = code_block.find('[')
            first_brace = code_block.find('{')
            
            # 优先匹配先出现的类型
            if first_bracket != -1 and (first_brace == -1 or first_bracket < first_brace):
                json_str = extract_json_with_stack(code_block, '[')
            elif first_brace != -1:
                json_str = extract_json_with_stack(code_block, '{')
            
            if json_str:
                method = "markdown_json_block"
        
        # ===== 策略2: 普通代码块 =====
        if not json_str:
            match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
            if match:
                code_block = match.group(1).strip()
                first_bracket = code_block.find('[')
                first_brace = code_block.find('{')
                
                if first_bracket != -1 and (first_brace == -1 or first_bracket < first_brace):
                    json_str = extract_json_with_stack(code_block, '[')
                elif first_brace != -1:
                    json_str = extract_json_with_stack(code_block, '{')
                    
                if json_str:
                    method = "generic_code_block"
        
        # ===== 策略3: 直接栈匹配（检测先出现的类型） =====
        if not json_str:
            first_bracket = text.find('[')
            first_brace = text.find('{')
            
            if first_bracket != -1 and (first_brace == -1 or first_bracket < first_brace):
                json_str = extract_json_with_stack(text, '[')
                if json_str:
                    method = "direct_array_match"
            elif first_brace != -1:
                json_str = extract_json_with_stack(text, '{')
                if json_str:
                    method = "direct_object_match"
        
        # ===== 策略5: 尝试修复截断的JSON =====
        if not json_str:
             # 尝试找到第一个 { 或 [
            start_idx_obj = text.find('{')
            start_idx_arr = text.find('[')
            
            start_idx = -1
            if start_idx_obj != -1 and start_idx_arr != -1:
                start_idx = min(start_idx_obj, start_idx_arr)
            elif start_idx_obj != -1:
                start_idx = start_idx_obj
            elif start_idx_arr != -1:
                start_idx = start_idx_arr
                
            if start_idx != -1:
                candidate = text[start_idx:]
                # 移除可能的 markdown 结尾
                if "```" in candidate:
                    parts = candidate.split("```")
                    if len(parts) > 1 and len(parts[-1].strip()) == 0:
                         # ``` 在最后，说明是闭合的，但前面的策略没抓到？
                         # 可能是 extract_json_with_stack 失败了
                         candidate = parts[0]
                
                repaired = repair_truncated_json(candidate)
                try:
                    result = json.loads(repaired)
                    print(f"DEBUG: Successfully parsed JSON after repairing truncation")
                    return result
                except json.JSONDecodeError:
                    pass

        # ===== 解析JSON =====
        if not json_str:
            print("DEBUG: No JSON structure found in text")
            print(f"DEBUG: Text preview: {text[:2000]}...")
            return {}
        
        print(f"DEBUG: JSON extracted using method: {method}")
        print(f"DEBUG: JSON string length: {len(json_str)}")
        print(f"DEBUG: JSON preview: {json_str[:200]}...")
        
        # 尝试解析
        try:
            result = json.loads(json_str)
            print(f"DEBUG: Successfully parsed JSON with {len(result)} top-level keys")
            return result
        except json.JSONDecodeError as e:
            print(f"DEBUG: JSON parse failed at position {e.pos}: {e.msg}")
            
            # ===== 修复策略 =====
            repaired_str = json_str
            
            # 修复1: 移除尾随逗号
            repaired_str = re.sub(r',\s*([}\]])', r'\1', repaired_str)
            
            try:
                result = json.loads(repaired_str)
                print("DEBUG: Successfully parsed after removing trailing commas")
                return result
            except json.JSONDecodeError:
                # 修复2: 补全未加引号的属性名
                repaired_str = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', repaired_str)
                
                try:
                    result = json.loads(repaired_str)
                    print("DEBUG: Successfully parsed after quoting property names")
                    return result
                except json.JSONDecodeError:
                    # 修复3 (新): 修复未转义的引号
                    try:
                        print("DEBUG: Attempting to repair unescaped quotes...")
                        repaired_str = repair_unescaped_quotes(json_str)
                        result = json.loads(repaired_str)
                        print("DEBUG: Successfully parsed after escaping internal quotes")
                        return result
                    except json.JSONDecodeError as e2:
                        print(f"DEBUG: All repair attempts failed: {e2.msg}")
                        print(f"DEBUG: Failed JSON: {repaired_str[:500]}...")
                        return {}
                
    except Exception as e:
        print(f"DEBUG: Unexpected error in parse_json_from_llm: {type(e).__name__}: {e}")
        return {}

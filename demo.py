from playwright_llm_agent import PlaywrightLLMAgent
from typing import Dict, Any, Optional
import json

# Use PlaywrightLLMAgent directly instead of maintaining separate code
class ManualPlaywrightDemo(PlaywrightLLMAgent):
    def __init__(self):
        super().__init__(
            user_data_dir=r"D:\User Data"
        )
    def navigate(self, url: str) -> str:
        """Navigate to a URL and capture snapshot"""
        print(f"正在导航到: {url}")
        return super().navigate(url)
    
    def execute_manual_action(self, action: Dict[str, Any]) -> str:
        """Execute manually input action - delegates to parent class"""
        print(f"执行操作: {action}")
        return super().execute_manual_action(action)

    def get_current_snapshot(self, *, method: str = "auto",
                             include_all: bool = False) -> str:
        return super().get_current_snapshot(method=method,
                                            include_all=include_all)

def parse_command(command_str: str) -> Optional[Dict[str, Any]]:
    """Parse space-separated command string into action dictionary"""
    parts = command_str.strip().split()
    if not parts:
        return None
    
    action_type = parts[0].lower()
    
    if action_type == 'click':
        if len(parts) < 3:
            print("错误: click命令需要至少2个参数: click <方式> <值>")
            return None
        
        method = parts[1].lower()
        value = ' '.join(parts[2:])  # Join remaining parts for text that may contain spaces
        
        if method == 'selector':
            return {'type': 'click', 'selector': value}
        elif method == 'text':
            return {'type': 'click', 'text': value}
        elif method == 'ref':
            return {'type': 'click', 'ref': value}
        else:
            print(f"错误: 未知的点击方式 '{method}'. 支持: selector, text, ref")
            return None
    
    elif action_type == 'type':
        if len(parts) < 4:
            print("错误: type命令需要至少3个参数: type <方式> <选择器> <文本>")
            return None
        
        method = parts[1].lower()
        target = parts[2]
        text = ' '.join(parts[3:])  # Join remaining parts for text
        
        if method == 'selector':
            return {'type': 'type', 'selector': target, 'text': text}
        elif method == 'ref':
            return {'type': 'type', 'ref': target, 'text': text}
        else:
            print(f"错误: 未知的输入方式 '{method}'. 支持: selector, ref")
            return None
    
    elif action_type == 'select':
        if len(parts) < 4:
            print("错误: select命令需要至少3个参数: select <方式> <选择器> <值>")
            return None
        
        method = parts[1].lower()
        target = parts[2]
        value = ' '.join(parts[3:])  # Join remaining parts for value
        
        if method == 'selector':
            return {'type': 'select', 'selector': target, 'value': value}
        elif method == 'ref':
            return {'type': 'select', 'ref': target, 'value': value}
        else:
            print(f"错误: 未知的选择方式 '{method}'. 支持: selector, ref")
            return None
    
    elif action_type == 'wait':
        if len(parts) < 3:
            print("错误: wait命令需要至少2个参数: wait <类型> <值>")
            return None
        
        wait_type = parts[1].lower()
        value = parts[2]
        
        if wait_type == 'timeout':
            try:
                timeout_ms = int(value)
                return {'type': 'wait', 'timeout': timeout_ms}
            except ValueError:
                print(f"错误: timeout值必须是数字: {value}")
                return None
        elif wait_type == 'selector':
            return {'type': 'wait', 'selector': value}
        else:
            print(f"错误: 未知的等待类型 '{wait_type}'. 支持: timeout, selector")
            return None
    
    elif action_type == 'scroll':
        if len(parts) < 3:
            print("错误: scroll命令需要至少2个参数: scroll <方向> <距离>")
            return None
        
        direction = parts[1].lower()
        try:
            amount = int(parts[2])
        except ValueError:
            print(f"错误: 滚动距离必须是数字: {parts[2]}")
            return None
        
        if direction in ['down', 'up']:
            return {'type': 'scroll', 'direction': direction, 'amount': amount}
        else:
            print(f"错误: 未知的滚动方向 '{direction}'. 支持: down, up")
            return None
    
    else:
        print(f"错误: 未知的操作类型 '{action_type}'")
        return None

def print_help():
    """Print available commands"""
    print("\n=== 可用操作 ===")
    print("1. navigate <url> - 导航到URL")
    print("   例如: navigate https://www.google.com")
    print("2. click - 点击元素")
    print("   格式: click <方式> <值>")
    print("   例如: click selector button")
    print("   例如: click text Search")
    print("   例如: click ref e123")
    print("3. type - 在输入框中输入文字")
    print("   格式: type <方式> <选择器> <文本>")
    print("   例如: type selector input hello world")
    print("   例如: type ref e64 Python programming")
    print("4. select - 在下拉框中选择选项")
    print("   格式: select <方式> <选择器> <值>")
    print("   例如: select selector select option1")
    print("   例如: select ref e68 English")
    print("5. wait - 等待")
    print("   格式: wait <类型> <值>")
    print("   例如: wait timeout 2000")
    print("   例如: wait selector button")
    print("6. scroll - 滚动页面")
    print("   格式: scroll <方向> <距离>")
    print("   例如: scroll down 300")
    print("   例如: scroll up 200")
    print("7. snapshot - 获取当前页面snapshot")
    print("8. help - 显示帮助")
    print("9. quit - 退出程序")
    print("================\n")

def main():
    print("=== 手动Playwright操作Demo ===")
    print("这个demo允许你用简单的空格分割命令来控制浏览器并获取snapshot")
    print("不需要复杂的JSON格式，只需输入简单的命令即可")
    print("现在使用playwright_llm_agent的统一逻辑，所有点击都是强制的！")
    
    demo = ManualPlaywrightDemo()
    
    try:
        print_help()
        
        while True:
            user_input = input("\n请输入命令 (help获取帮助): ").strip()
            
            if not user_input:
                continue
                
            if user_input.lower() == 'quit':
                print("退出程序...")
                break
            elif user_input.lower() == 'help':
                print_help()
                continue
            elif user_input.lower().startswith('snapshot'):
                # 格式: snapshot [method] [all]
                parts = user_input.split()
                method = 'auto'
                include_all = False

                for p in parts[1:]:
                    p_lower = p.lower()
                    if p_lower in ('auto', 'direct', 'node'):
                        method = p_lower
                    elif p_lower in ('all', 'full', 'include_all', 'complete'):
                        include_all = True
                    else:
                        print(f"警告: 未知snapshot参数 '{p}', 将被忽略")

                print(
                    f"正在获取当前页面snapshot… (method={method}, include_all={include_all})")
                snapshot = demo.get_current_snapshot(method=method,
                                                     include_all=include_all)
                print("当前Snapshot:")
                print(snapshot)
                continue
            elif user_input.startswith('navigate '):
                url = user_input[9:].strip()
                if url:
                    snapshot = demo.navigate(url)
                    print("导航完成，页面Snapshot:")
                    print(snapshot)
                else:
                    print("错误: 请提供URL")
                continue
            
            # Try to parse as space-separated command
            action = parse_command(user_input)
            if action:
                try:
                    result = demo.execute_manual_action(action)
                    print(f"操作结果: {result}")
                    
                    # Show updated snapshot
                    print("\n更新后的Snapshot:")
                    snapshot = demo.get_current_snapshot()
                    print(snapshot)
                    
                except Exception as e:
                    print(f"执行操作时出错: {e}")
            else:
                print("命令解析失败，请检查格式或输入help查看帮助")
                
    except KeyboardInterrupt:
        print("\n程序被中断")
    finally:
        demo.close()
        print("浏览器已关闭")

if __name__ == "__main__":
    main() 
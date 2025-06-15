from playwright.sync_api import sync_playwright
import json
from typing import Dict, List, Optional, Any, Tuple, Union
import yaml
from chat_py import chat_single, message_template
import time

class PageSnapshot:
    def __init__(self, page):
        self.page = page
        self.snapshot_data = None
        self.element_map = {}  # Store mapping from ref to actual elements
        
    def capture(self) -> str:
        """Capture accessibility snapshot of the current page using Playwright's built-in method"""
        try:
            # Wait for page to be stable
            self.page.wait_for_load_state('domcontentloaded', timeout=10000)
            time.sleep(1)  # Additional wait to ensure page stability
            
            try:
                # Try to use Playwright's built-in method
                snapshot_text = self.page.evaluate("() => window.playwright?._snapshotForAI?.()")
                if snapshot_text:
                    # Add ref attributes to elements for positioning
                    self._add_ref_attributes()
                    return f"- Page Snapshot\n```yaml\n{snapshot_text}\n```"
            except:
                pass  # If built-in method is not available, fallback to custom method
            
            # Fallback to optimized custom method
            snapshot = self.page.evaluate("""() => {
                function getOptimizedAccessibilityTree() {
                    const elements = [];
                    let refIndex = 0;
                    
                    // Priority interactive element selectors
                    const interactiveSelectors = [
                        'input', 'button', 'a', 'select', 'textarea', 
                        '[role="button"]', '[role="link"]', '[role="textbox"]',
                        '[role="searchbox"]', '[role="combobox"]', '[role="tab"]',
                        'h1', 'h2', 'h3', 'h4', 'h5', 'h6'
                    ];
                    
                    // Collect all interactive elements
                    interactiveSelectors.forEach(selector => {
                        const els = document.querySelectorAll(selector);
                        els.forEach(element => {
                            if (elements.some(e => e.element === element)) return; // Avoid duplicates
                            
                            const rect = element.getBoundingClientRect();
                            const isVisible = rect.width > 0 && rect.height > 0 && 
                                            window.getComputedStyle(element).display !== 'none' &&
                                            window.getComputedStyle(element).visibility !== 'hidden' &&
                                            rect.top < window.innerHeight && rect.bottom > 0;
                            
                            if (!isVisible) return;
                            
                            const role = element.getAttribute('role') || element.tagName.toLowerCase();
                            const text = element.textContent?.trim() || '';
                            const ref = `e${refIndex++}`;
                            
                            // Add ref attribute to element
                            element.setAttribute('data-ref', ref);
                            
                            // Filter out overly long text and meaningless elements
                            const filteredText = text.length > 150 ? text.substring(0, 150) + '...' : text;
                            
                            // Only include useful elements
                            if (filteredText.length > 0 || 
                                ['input', 'button', 'select', 'textarea', 'a'].includes(element.tagName.toLowerCase()) ||
                                element.hasAttribute('onclick') ||
                                element.hasAttribute('href')) {
                                
                                elements.push({
                                    element: element,
                                    role: role,
                                    name: filteredText,
                                    ref: ref,
                                    tag: element.tagName.toLowerCase(),
                                    attributes: {
                                        'aria-label': element.getAttribute('aria-label'),
                                        'placeholder': element.getAttribute('placeholder'),
                                        'type': element.getAttribute('type'),
                                        'value': element.value || element.getAttribute('value'),
                                        'href': element.getAttribute('href'),
                                        'id': element.getAttribute('id'),
                                        'class': element.getAttribute('class')?.split(' ').slice(0, 3).join(' '), // Limit class length
                                        'name': element.getAttribute('name')
                                    },
                                    position: {
                                        x: Math.round(rect.x),
                                        y: Math.round(rect.y),
                                        width: Math.round(rect.width),
                                        height: Math.round(rect.height),
                                        inViewport: rect.top >= 0 && rect.bottom <= window.innerHeight
                                    }
                                });
                            }
                        });
                    });
                    
                    // Sort by importance and position
                    elements.sort((a, b) => {
                        // Prioritize elements in viewport
                        if (a.position.inViewport !== b.position.inViewport) {
                            return b.position.inViewport ? 1 : -1;
                        }
                        // Sort by Y coordinate
                        return a.position.y - b.position.y;
                    });
                    
                    // Limit element count to reduce token usage
                    const maxElements = 50;
                    const limitedElements = elements.slice(0, maxElements);
                    
                    return limitedElements.map(item => ({
                        role: item.role,
                        name: item.name,
                        ref: item.ref,
                        tag: item.tag,
                        attributes: Object.fromEntries(
                            Object.entries(item.attributes).filter(([k, v]) => v !== null && v !== '')
                        ),
                        position: item.position
                    }));
                }
                
                return getOptimizedAccessibilityTree();
            }""")
            
            # Filter and optimize snapshot data
            filtered_snapshot = self._filter_snapshot(snapshot)
            
            # Convert to simplified YAML format
            yaml_output = self._format_as_compact_yaml(filtered_snapshot)
            self.snapshot_data = yaml_output
            return yaml_output
            
        except Exception as e:
            print(f"Error capturing snapshot: {e}")
            return "Error: Could not capture page snapshot"
    
    def _add_ref_attributes(self):
        """Add ref attributes to existing elements"""
        self.page.evaluate("""() => {
            const elements = document.querySelectorAll('input, button, a, select, textarea, h1, h2, h3, h4, h5, h6');
            elements.forEach((el, index) => {
                if (!el.hasAttribute('data-ref')) {
                    el.setAttribute('data-ref', `e${index}`);
                }
            });
        }""")
    
    def _filter_snapshot(self, snapshot):
        """Filter snapshot data, remove unimportant information"""
        filtered = []
        for item in snapshot:
            # Skip items without text content and not interactive elements
            if not item['name'] and item['tag'] not in ['input', 'button', 'select', 'textarea', 'a']:
                continue
            
            # Clean attributes, keep only important ones
            important_attrs = {}
            for key, value in item['attributes'].items():
                if key in ['aria-label', 'placeholder', 'type', 'href', 'id', 'name'] and value:
                    important_attrs[key] = value
            
            filtered.append({
                'role': item['role'],
                'name': item['name'],
                'ref': item['ref'],
                'tag': item['tag'],
                'attributes': important_attrs,
                'inViewport': item['position']['inViewport']
            })
        
        return filtered
    
    def _format_as_compact_yaml(self, snapshot_data):
        """Format snapshot data as compact YAML format"""
        lines = ["- Page Snapshot (Optimized for LLM)"]
        
        viewport_elements = [item for item in snapshot_data if item['inViewport']]
        other_elements = [item for item in snapshot_data if not item['inViewport']]
        
        if viewport_elements:
            lines.append("  Current Viewport Elements:")
            for item in viewport_elements[:20]:  # Limit viewport element count
                lines.append(self._format_element_line(item))
        
        if other_elements and len(viewport_elements) < 20:
            lines.append("  Other Interactive Elements:")
            remaining_slots = 30 - len(viewport_elements)
            for item in other_elements[:remaining_slots]:
                lines.append(self._format_element_line(item))
        
        return '\n'.join(lines)
    
    def _format_element_line(self, item):
        """Format single element as concise one line"""
        parts = [f"    - {item['role']}"]
        
        if item['name']:
            parts.append(f'"{item["name"]}"')
        
        # Add important attributes
        attrs = []
        for key, value in item['attributes'].items():
            if key == 'type' and value:
                attrs.append(f"type={value}")
            elif key == 'placeholder' and value:
                attrs.append(f"placeholder={value}")
            elif key == 'aria-label' and value:
                attrs.append(f"label={value}")
        
        if attrs:
            parts.append(f"[{', '.join(attrs)}]")
        
        parts.append(f"(ref={item['ref']})")
        
        return ' '.join(parts)

class PlaywrightLLMAgent:
    def __init__(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=False)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.snapshot = PageSnapshot(self.page)
        self.plan = None
        self.current_action_index = 0
        
    def navigate(self, url: str) -> str:
        """Navigate to a URL and capture snapshot"""
        try:
            print(f"Navigating to: {url}")
            self.page.goto(url, wait_until='domcontentloaded', timeout=30000)
            
            # Wait for page to fully load
            self.page.wait_for_load_state('networkidle', timeout=15000)
            time.sleep(2)  # Additional wait to ensure page stability
            
            print("Page loaded, capturing optimized snapshot...")
            return self.snapshot.capture()
            
        except Exception as e:
            print(f"Error navigating to {url}: {e}")
            return "Error: Could not navigate to page"
    
    def get_initial_plan(self, prompt: str, snapshot: str) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Get initial plan and first action from LLM"""
        messages = [
            message_template('system', """You are a web automation assistant. Analyze the optimized page snapshot and create a plan to accomplish the user's request.

The snapshot shows the most important interactive elements on the page. Each element has:
- role: The element type (button, input, link, etc.)
- name: The visible text or label
- attributes: Important properties like type, placeholder, etc.
- ref: Unique reference for interaction (use this exact value)

Your response should be a JSON object with two fields:
1. 'plan': An array of high-level steps to accomplish the task
2. 'action': The first action to take, or null if task is complete

Action format example:
{
  "plan": ["Step 1", "Step 2"],
  "action": {
    "type": "click",
    "ref": "e23"
  }
}

Available action types:
- 'click': {"type": "click", "ref": "e1"}
- 'type': {"type": "type", "ref": "e1", "text": "search text"}
- 'select': {"type": "select", "ref": "e1", "value": "option"}
- 'wait': {"type": "wait", "timeout": 2000} or {"type": "wait", "selector": "#element"}
- 'extract': {"type": "extract", "ref": "e1", "variable": "result"}
- 'scroll': {"type": "scroll", "direction": "down", "amount": 300}

IMPORTANT: Only use 'ref' values that exist in the snapshot (e.g., ref=e1, ref=e2, etc.)"""),
            message_template('user', f"Page Snapshot:\n{snapshot}\n\nUser Request: {prompt}")
        ]
        print("snapshot:",snapshot)
        response = chat_single(messages, mode="json", verbose=True)
        
        if response and isinstance(response, dict):
            plan = response.get('plan', [])
            action = response.get('action', None)
            
            # Fix action format issues
            if action and isinstance(action, dict):
                # Check if it's old format {"click": {"ref": "e23"}}
                if 'type' not in action:
                    # Try to detect action type
                    if 'click' in action:
                        click_value = action['click']
                        if isinstance(click_value, str):
                            # Handle {"click": "e23"} format
                            action = {"type": "click", "ref": click_value}
                        elif isinstance(click_value, dict):
                            # Handle {"click": {"ref": "e23"}} format
                            action = {"type": "click", "ref": click_value.get('ref')}
                    elif 'type' in action:
                        type_value = action['type']
                        if isinstance(type_value, dict):
                            action = {"type": "type", "ref": type_value.get('ref'), "text": type_value.get('text', '')}
                    elif 'select' in action:
                        select_value = action['select']
                        if isinstance(select_value, dict):
                            action = {"type": "select", "ref": select_value.get('ref'), "value": select_value.get('value', '')}
                    elif 'extract' in action:
                        extract_value = action['extract']
                        if isinstance(extract_value, dict):
                            action = {"type": "extract", "ref": extract_value.get('ref'), "variable": extract_value.get('variable', 'result')}
                    elif 'scroll' in action:
                        scroll_value = action['scroll']
                        if isinstance(scroll_value, dict):
                            action = {"type": "scroll", "direction": scroll_value.get('direction', 'down'), "amount": scroll_value.get('amount', 300)}
                    elif 'wait' in action:
                        wait_value = action['wait']
                        if isinstance(wait_value, dict):
                            if 'timeout' in wait_value:
                                action = {"type": "wait", "timeout": wait_value['timeout']}
                            elif 'selector' in wait_value:
                                action = {"type": "wait", "selector": wait_value['selector']}
                            else:
                                action = {"type": "wait", "timeout": 2000}
            
            return plan, action
        else:
            return [], None
    
    def get_next_action(self, prompt: str, snapshot: str, last_action_result: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get next action from LLM based on current state"""
        messages = [
            message_template('system', """You are a web automation assistant. Based on the current optimized page state and the last action's result, suggest the next action.

Your response should be a JSON object with a single 'action' field containing the next action to take, or null if the task is complete.

Action format example:
{
  "action": {
    "type": "click",
    "ref": "e23"
  }
}

Available action types:
- 'click': {"type": "click", "ref": "e1"}
- 'type': {"type": "type", "ref": "e1", "text": "search text"}
- 'select': {"type": "select", "ref": "e1", "value": "option"}
- 'wait': {"type": "wait", "timeout": 2000} or {"type": "wait", "selector": "#element"}
- 'extract': {"type": "extract", "ref": "e1", "variable": "result"}
- 'scroll': {"type": "scroll", "direction": "down", "amount": 300}

IMPORTANT: Only use 'ref' values that exist in the current snapshot."""),
            message_template('user', f"""Current Page Snapshot:\n{snapshot}

Last Action: {last_action_result if last_action_result else 'None'}

User Request: {prompt}

Determine the next action to take or return null if the task is complete.""")
        ]
        print("Current snapshot:",snapshot)

        response = chat_single(messages, mode="json", verbose=True)
        
        if response and isinstance(response, dict):
            action = response.get('action', None)
            
            # Fix action format issues
            if action and isinstance(action, dict):
                # Check if it's old format {"click": {"ref": "e23"}}
                if 'type' not in action:
                    # Try to detect action type
                    if 'click' in action:
                        click_value = action['click']
                        if isinstance(click_value, str):
                            # Handle {"click": "e23"} format
                            action = {"type": "click", "ref": click_value}
                        elif isinstance(click_value, dict):
                            # Handle {"click": {"ref": "e23"}} format
                            action = {"type": "click", "ref": click_value.get('ref')}
                    elif 'type' in action:
                        type_value = action['type']
                        if isinstance(type_value, dict):
                            action = {"type": "type", "ref": type_value.get('ref'), "text": type_value.get('text', '')}
                    elif 'select' in action:
                        select_value = action['select']
                        if isinstance(select_value, dict):
                            action = {"type": "select", "ref": select_value.get('ref'), "value": select_value.get('value', '')}
                    elif 'extract' in action:
                        extract_value = action['extract']
                        if isinstance(extract_value, dict):
                            action = {"type": "extract", "ref": extract_value.get('ref'), "variable": extract_value.get('variable', 'result')}
                    elif 'scroll' in action:
                        scroll_value = action['scroll']
                        if isinstance(scroll_value, dict):
                            action = {"type": "scroll", "direction": scroll_value.get('direction', 'down'), "amount": scroll_value.get('amount', 300)}
                    elif 'wait' in action:
                        wait_value = action['wait']
                        if isinstance(wait_value, dict):
                            if 'timeout' in wait_value:
                                action = {"type": "wait", "timeout": wait_value['timeout']}
                            elif 'selector' in wait_value:
                                action = {"type": "wait", "selector": wait_value['selector']}
                            else:
                                action = {"type": "wait", "timeout": 2000}
            
            return action
        else:
            return None
    
    def wait_for_page_stable(self):
        """Wait for page to be stable before executing actions"""
        try:
            self.page.wait_for_load_state('domcontentloaded', timeout=10000)
            time.sleep(0.5)  # Brief wait to ensure page stability
        except Exception as e:
            print(f"Warning: Page stability check failed: {e}")
    
    def execute_action(self, action: Dict[str, Any]) -> str:
        """Execute the action suggested by LLM"""
        if not action:
            return "No action to execute"
            
        action_type = action.get('type')
        print(f"Executing action: {action}")
        
        if not action_type:
            return f"Error: No action type specified in {action}"
        
        result = "Unknown action result"
        
        try:
            # Ensure page is stable
            self.wait_for_page_stable()
            
            if action_type == 'click':
                ref = action.get('ref')
                if not ref:
                    return "Error: No ref specified for click action"
                
                selector = f"[data-ref='{ref}']"
                print(f"Clicking element with selector: {selector}")
                
                # Check if element exists - fix JavaScript syntax error
                try:
                    element_count = self.page.evaluate(f"""
                        () => document.querySelectorAll("{selector}").length
                    """)
                    print(f"Found {element_count} elements with selector {selector}")
                except Exception as eval_error:
                    print(f"Error checking element existence: {eval_error}")
                    # Try simple selector check
                    try:
                        element_count = self.page.locator(selector).count()
                        print(f"Using locator count, found {element_count} elements")
                    except:
                        element_count = 0
                
                if element_count == 0:
                    # Try to re-add ref attributes
                    print("Element not found, re-adding ref attributes...")
                    self.snapshot._add_ref_attributes()
                    try:
                        element_count = self.page.locator(selector).count()
                        print(f"After re-adding refs, found {element_count} elements")
                    except:
                        element_count = 0
                
                if element_count == 0:
                    return f"Error: Element with ref '{ref}' not found"
                
                # Wait for element to be visible and click
                self.page.wait_for_selector(selector, timeout=10000)
                self.page.click(selector, timeout=10000)
                result = f"Successfully clicked element {ref}"
                
                # Wait for page to stabilize after click
                time.sleep(2)
                
            elif action_type == 'type':
                ref = action.get('ref')
                text = action.get('text', '')
                
                if not ref:
                    return "Error: No ref specified for type action"
                
                selector = f"[data-ref='{ref}']"
                print(f"Typing '{text}' into element with selector: {selector}")
                
                # Check if element exists
                element_count = self.page.locator(selector).count()
                if element_count == 0:
                    return f"Error: Element with ref '{ref}' not found"
                
                # Wait for element to be visible
                self.page.wait_for_selector(selector, timeout=10000)
                self.page.fill(selector, text, timeout=10000)
                result = f"Successfully typed '{text}' into element {ref}"
                
            elif action_type == 'select':
                ref = action.get('ref')
                value = action.get('value', '')
                
                if not ref:
                    return "Error: No ref specified for select action"
                
                selector = f"[data-ref='{ref}']"
                
                self.page.wait_for_selector(selector, timeout=10000)
                self.page.select_option(selector, value, timeout=10000)
                result = f"Successfully selected '{value}' in element {ref}"
                
            elif action_type == 'wait':
                if 'timeout' in action:
                    timeout = action['timeout']
                    time.sleep(timeout / 1000)  # Convert to seconds
                    result = f"Waited for {timeout}ms"
                elif 'selector' in action:
                    selector = action['selector']
                    self.page.wait_for_selector(selector, timeout=10000)
                    result = f"Waited for selector {selector}"
                else:
                    result = "Error: Wait action requires timeout or selector"
                    
            elif action_type == 'extract':
                ref = action.get('ref')
                
                if not ref:
                    return "Error: No ref specified for extract action"
                
                selector = f"[data-ref='{ref}']"
                
                self.page.wait_for_selector(selector, timeout=10000)
                text = self.page.text_content(selector, timeout=10000)
                if 'variable' in action:
                    setattr(self, action['variable'], text)
                result = f"Extracted text: {text[:100] if text else 'None'}..."
                
            elif action_type == 'scroll':
                direction = action.get('direction', 'down')
                amount = action.get('amount', 300)
                if direction == 'down':
                    self.page.evaluate(f"window.scrollBy(0, {amount})")
                else:
                    self.page.evaluate(f"window.scrollBy(0, -{amount})")
                result = f"Scrolled {direction} by {amount}px"
                time.sleep(1)  # Wait after scrolling
                
            else:
                result = f"Error: Unknown action type '{action_type}'"
                
        except Exception as e:
            result = f"Error executing {action_type}: {str(e)}"
            print(f"Action execution error: {e}")
            print(f"Full error details:", e)
            
        # Wait for page to stabilize after action, then update snapshot
        try:
            self.wait_for_page_stable()
            self.snapshot.capture()
        except Exception as e:
            print(f"Error updating snapshot after action: {e}")
            
        return result
    
    def process_command(self, prompt: str) -> None:
        """Process a user command through LLM and execute actions"""
        try:
            # 1. Get initial plan
            snapshot = self.snapshot.capture()
            if "Error:" in snapshot:
                print("Could not capture initial snapshot")
                return
                
            self.plan, action = self.get_initial_plan(prompt, snapshot)
            print("\nPlan:", json.dumps(self.plan, indent=2, ensure_ascii=False))
            
            # 2. Execute action sequence
            max_actions = 15  # Increase maximum action count
            action_count = 0
            
            while action and action_count < max_actions:
                # Execute current action
                result = self.execute_action(action)
                print(f"\nExecuted action: {json.dumps(action, indent=2, ensure_ascii=False)}")
                print(f"Result: {result}")
                
                # If action failed, try to get new snapshot
                if "Error" in result:
                    print("Action failed, trying to continue...")
                    time.sleep(2)
                
                # Get new page state
                snapshot = self.snapshot.capture()
                if "Error:" in snapshot:
                    print("Could not capture snapshot, stopping...")
                    break
                
                # Get next action
                action = self.get_next_action(prompt, snapshot, result)
                action_count += 1
                
            if action_count >= max_actions:
                print("Reached maximum action limit")
            else:
                print("Task completed")
                
        except Exception as e:
            print(f"Error in process_command: {e}")
            
    def close(self) -> None:
        """Clean up resources"""
        self.context.close()
        self.browser.close()
        self.playwright.stop()

# Usage example
if __name__ == "__main__":
    agent = PlaywrightLLMAgent()
    
    try:
        # Navigate to target page
        agent.navigate("https://google.com")
        
        # Process user command
        agent.process_command("search interesting topic in Munich and weather")
        
    finally:
        agent.close() 
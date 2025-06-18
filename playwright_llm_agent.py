from playwright.sync_api import sync_playwright
import json
from typing import Dict, List, Optional, Any, Tuple, Union
import yaml
from chat_py import chat_single, message_template, print_color
import time
import subprocess
import os


class PageSnapshot:
    def __init__(self, page):
        self.page = page
        self.snapshot_data = None
        self.element_map = {}  # Store mapping from ref to actual elements
        self._last_url = None  # Cache for URL-based optimization
        self._last_snapshot_hash = None  # Cache for content-based optimization

    def capture(self, force_refresh=False) -> str:
        """Capture accessibility snapshot of the current page using optimized method"""
        try:
            current_url = self.page.url

            # Quick optimization: if URL hasn't changed and we have cached data, return it
            if not force_refresh and current_url == self._last_url and self.snapshot_data:
                print("Using cached snapshot (same URL)")
                return self.snapshot_data

            # Fast page stability check (reduced waiting)
            start_time = time.time()
            self.page.wait_for_load_state('domcontentloaded', timeout=5000)
            print(f"Page load check: {time.time() - start_time:.2f}s")

            # Try direct evaluation first (fastest method)
            start_time = time.time()
            snapshot_text = self._get_snapshot_direct()
            if snapshot_text:
                print(
                    f"✅ Direct Python _snapshotForAI: {time.time() - start_time:.2f}s")
                formatted_snapshot = self._format_snapshot(snapshot_text)
                self._update_cache(current_url, formatted_snapshot)
                return formatted_snapshot

            # Fallback to Node.js version (slower but more reliable)
            start_time = time.time()
            snapshot_text = self._get_snapshot_via_nodejs()
            if snapshot_text:
                print(
                    f"✅ Node.js _snapshotForAI (official): {time.time() - start_time:.2f}s")
                print(snapshot_text)
                formatted_snapshot = self._format_snapshot(snapshot_text)
                self._update_cache(current_url, formatted_snapshot)
                return formatted_snapshot

            # Final fallback
            print("Warning: All snapshot methods failed, using basic fallback")
            return self._fallback_snapshot()

        except Exception as e:
            print(f"Error capturing snapshot: {e}")
            return "Error: Could not capture page snapshot"

    def _get_snapshot_direct(self) -> Optional[str]:
        """Try to get snapshot directly using page.evaluate (fastest method)"""

        return self.page.evaluate("""() => {
            function getVisibleElements() {
                const elements = [];

                function isVisible(node) {
                    const rect = node.getBoundingClientRect();
                    if (rect.width === 0 || rect.height === 0) return false;

                    const style = window.getComputedStyle(node);
                    if (style.display === 'none' || style.visibility === 'hidden') return false;

                    return true;
                }

                function getRole(node) {
                    const tag = node.tagName.toLowerCase();
                    const type = node.getAttribute('type');

                    if (node.getAttribute('role')) return node.getAttribute('role');

                    if (tag === 'input') {
                        if (type === 'checkbox') return 'checkbox';
                        if (type === 'radio') return 'radio';
                        return 'input';
                    }

                    if (tag === 'button') return 'button';
                    if (tag === 'a') return 'link';
                    if (tag === 'select') return 'select';
                    if (tag === 'textarea') return 'textarea';
                    if (tag === 'p') return 'paragraph';
                    if (tag === 'span') return 'text';

                    return 'generic';
                }

                let refCounter = 1;

                function traverse(node, depth) {
                    if (node.nodeType !== Node.ELEMENT_NODE) return;

                    if (!isVisible(node)) return;

                    const tagName = node.tagName.toLowerCase();
                    const text = node.textContent?.trim().slice(0, 50) || '';

                    const hasRoleOrText = ['button', 'a', 'input', 'select', 'textarea', 'p', 'span'].includes(tagName) || 
                                          node.getAttribute('role') || text;

                    if (hasRoleOrText) {
                        const role = getRole(node);
                        const ref = `e${refCounter++}`;
                        const label = text ? `"${text}"` : '';
                        const indent = '\\t'.repeat(depth);

                        elements.push(`${indent}- ${role} ${label} [ref=${ref}]`);
                        node.setAttribute('aria-ref', ref);
                    }

                    for (let child of node.children) {
                        traverse(child, depth + 1);
                    }
                }

                traverse(document.body, 0);
                return elements.join('\\n');
            }

            return getVisibleElements();
        }""")

    def _format_snapshot(self, snapshot_text: str) -> str:
        """Format snapshot text consistently"""
        formatted_snapshot = [
            "- Page Snapshot",
            "```yaml",
            snapshot_text,
            "```"
        ]
        return '\n'.join(formatted_snapshot)

    def _update_cache(self, url: str, snapshot: str):
        """Update cache with new snapshot data"""
        self._last_url = url
        self.snapshot_data = snapshot
        # Create simple hash for content comparison
        self._last_snapshot_hash = hash(snapshot)

    def _get_snapshot_via_nodejs(self) -> Optional[str]:
        """Try to get snapshot using Node.js version of Playwright"""
        try:
            # Get current page URL
            current_url = self.page.url

            # Check if snapshot_helper.js exists
            script_path = os.path.join(os.getcwd(), 'snapshot_helper.js')
            if not os.path.exists(script_path):
                print("snapshot_helper.js not found, skipping Node.js method")
                return None

            # Set environment to ensure UTF-8 encoding
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            if os.name == 'nt':  # Windows
                env['CHCP'] = '65001'  # Set code page to UTF-8

            # Call Node.js script with reduced timeout
            cmd = ['node', 'snapshot_helper.js', 'snapshot', current_url]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,  # Reduced from 30s to 10s
                encoding='utf-8',
                errors='replace',
                env=env
            )

            if result.returncode == 0:
                # Parse JSON response
                response_data = json.loads(result.stdout.strip())
                if response_data.get('success'):
                    print(
                        "🚀 Using Node.js page._snapshotForAI() (official method)")
                    return response_data.get('snapshot')
                else:
                    print(
                        f"Node.js snapshot failed: {response_data.get('error')}")
                    return None
            else:
                print(
                    f"Node.js script failed with return code {result.returncode}")
                if result.stderr:
                    print(f"Error output: {result.stderr}")
                return None

        except subprocess.TimeoutExpired:
            print("Node.js snapshot timeout")
            return None
        except FileNotFoundError:
            print("Node.js not found in PATH")
            return None
        except json.JSONDecodeError:
            print("Failed to parse Node.js response")
            return None
        except Exception as e:
            print(f"Error calling Node.js snapshot: {e}")
            return None

    def _fallback_snapshot(self) -> str:
        """Fallback method when _snapshotForAI is not available"""
        try:
            # Simple fallback that captures basic page info
            title = self.page.title()
            url = self.page.url

            # Get basic text content from body
            body_text = self.page.evaluate("""() => {
                const body = document.body;
                if (!body) return '';

                // Get visible text content, but limit length
                const text = body.textContent || '';
                return text.trim().slice(0, 500);
            }""")

            fallback_snapshot = [
                "- Page Snapshot",
                "```yaml",
                f"- generic [ref=e1]: {body_text}" if body_text else "- generic [ref=e1]: (no content)",
                "```"
            ]

            return '\n'.join(fallback_snapshot)

        except Exception as e:
            print(f"Error in fallback snapshot: {e}")
            return "Error: Could not capture page snapshot"


class PlaywrightLLMAgent:
    def __init__(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=False)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.snapshot = PageSnapshot(self.page)
        self.plan = None
        self.current_action_index = 0
        self._cdp_endpoint = None
        self.action_history = []  # Store history of actions and their results

    def navigate(self, url: str) -> str:
        """Navigate to a URL and capture snapshot"""
        try:
            print(f"Navigating to: {url}")
            start_time = time.time()

            self.page.goto(url, wait_until='domcontentloaded', timeout=20000)

            # Optimized loading wait - try networkidle but don't block too long
            try:
                self.page.wait_for_load_state('networkidle', timeout=5000)
            except:
                print("Networkidle timeout, proceeding anyway...")

            print(
                f"Page loaded in {time.time() - start_time:.2f}s, capturing snapshot...")
            return self.snapshot.capture(
                force_refresh=True)  # Force refresh on navigation

        except Exception as e:
            print(f"Error navigating to {url}: {e}")
            return "Error: Could not navigate to page"

    def _get_llm_response(self, prompt: str, snapshot: str,
                          action_history: Optional[List[Dict[str, Any]]] = None,
                          is_initial: bool = True) -> Optional[Dict[str, Any]]:
        """Get response from LLM - unified method for prompts"""

        # Common action types description
        action_types = """
Available action types:
- 'click': {"type": "click", "ref": "e1"} or {"type": "click", "text": "Button Text"} or {"type": "click", "selector": "button"}
- 'type': {"type": "type", "ref": "e1", "text": "search text"} or {"type": "type", "selector": "input", "text": "search text"}
- 'select': {"type": "select", "ref": "e1", "value": "option"} or {"type": "select", "selector": "select", "value": "option"}
- 'wait': {"type": "wait", "timeout": 2000} or {"type": "wait", "selector": "#element"}
- 'scroll': {"type": "scroll", "direction": "down", "amount": 300}
- 'finish': {"type": "finish", "ref": null, "summary": "task completion summary"}

IMPORTANT: 
- For 'click': Use 'ref' from snapshot, or 'text' for visible text, or 'selector' for CSS selectors
- For 'type'/'select': Use 'ref' from snapshot or 'selector' for CSS selectors
- Only use 'ref' values that exist in the snapshot (e.g., ref=e1, ref=e2, etc.)
- Use 'finish' when the task is completed successfully with a summary of what was accomplished
- click can choose radio, checkbox...
"""

        if is_initial:
            system_prompt = """You are a web automation assistant. Analyze the page snapshot and create a plan to accomplish the user's request.

The snapshot shows the page elements in YAML format. Each element has:
- role: The element type (button, input, link, etc.)
- name/text: The visible text or label
- attributes: Important properties like type, placeholder, etc.
- [ref=eX]: Unique reference for interaction (use this exact value)

Your response should be a JSON object with two fields:
1. 'plan': An array of high-level steps to accomplish the task
2. 'action': The first action to take, or use 'finish' action if task is already complete

Action format examples:
{
  "plan": ["Step 1", "Step 2"],
  "action": {
    "type": "click",
    "ref": "e1"
  }
}

If task is already complete:
{
  "plan": [],
  "action": {
    "type": "finish",
    "ref": null,
    "summary": "Task was already completed. Summary of what was found..."
  }
}""" + action_types
            user_prompt = f"Page Snapshot:\n{snapshot}\n\nUser Request: {prompt}"
        else:
            system_prompt = """You are a web automation assistant. Based on the current page state and the history of actions taken, suggest the next action.

Your response should be a JSON object with a single 'action' field containing the next action to take. If the task is complete, use the 'finish' action type with a summary.

Action format examples:
{
  "action": {
    "type": "click",
    "ref": "e1",
    "reason": ""
  }
}

When task is complete:
{
  "action": {
    "type": "finish",
    "ref": null,
    "summary": "Successfully completed the task. Summary of what was accomplished..."
  }
}""" + action_types
            
            # Format action history
            history_text = "None"
            if action_history:
                history_lines = []
                for i, entry in enumerate(action_history, 1):
                    action = entry.get('action', {})
                    result = entry.get('result', '')
                    success = entry.get('success', False)
                    status = "✅ SUCCESS" if success else "❌ FAILED"
                    history_lines.append(f"{i}. {status} - Action: {json.dumps(action, ensure_ascii=False)} | Result: {result}")
                history_text = "\n".join(history_lines)
            
            user_prompt = f"""Current Page Snapshot:\n{snapshot}

Action History:
{history_text}

User Request: {prompt}

Determine the next action to take. If the task is complete, use 'finish' action with a summary of what was accomplished.
"""
        print_color(user_prompt,"purple")
        messages = [
            message_template('system', system_prompt),
            message_template('user', user_prompt)
        ]

        print(
            f"Sending {'initial plan' if is_initial else 'next action'} request to LLM")
        response = chat_single(messages, mode="json", verbose=True)

        # Ensure we return a dict or None
        if isinstance(response, dict):
            return response
        else:
            return None

    def _fix_action_format(self, action: Optional[Dict[str, Any]]) -> Optional[
        Dict[str, Any]]:
        """Fix action format issues from LLM response"""
        if not action or not isinstance(action, dict):
            return action

        # Check if it's old format {"click": {"ref": "e23"}}
        if 'type' not in action:
            # Try to detect action type
            if 'click' in action:
                click_value = action['click']
                if isinstance(click_value, str):
                    action = {"type": "click", "ref": click_value}
                elif isinstance(click_value, dict):
                    action = {"type": "click", "ref": click_value.get('ref')}
            elif 'type' in action:
                type_value = action['type']
                if isinstance(type_value, dict):
                    action = {"type": "type", "ref": type_value.get('ref'),
                              "text": type_value.get('text', '')}
            elif 'select' in action:
                select_value = action['select']
                if isinstance(select_value, dict):
                    action = {"type": "select", "ref": select_value.get('ref'),
                              "value": select_value.get('value', '')}
            elif 'extract' in action:
                extract_value = action['extract']
                if isinstance(extract_value, dict):
                    action = {"type": "extract",
                              "ref": extract_value.get('ref'),
                              "variable": extract_value.get('variable',
                                                            'result')}
            elif 'scroll' in action:
                scroll_value = action['scroll']
                if isinstance(scroll_value, dict):
                    action = {"type": "scroll",
                              "direction": scroll_value.get('direction',
                                                            'down'),
                              "amount": scroll_value.get('amount', 300)}
            elif 'wait' in action:
                wait_value = action['wait']
                if isinstance(wait_value, dict):
                    if 'timeout' in wait_value:
                        action = {"type": "wait",
                                  "timeout": wait_value['timeout']}
                    elif 'selector' in wait_value:
                        action = {"type": "wait",
                                  "selector": wait_value['selector']}
                    else:
                        action = {"type": "wait", "timeout": 2000}
            elif 'finish' in action:
                finish_value = action['finish']
                if isinstance(finish_value, dict):
                    action = {"type": "finish", "ref": None,
                              "summary": finish_value.get('summary',
                                                          'Task completed')}
                else:
                    action = {"type": "finish", "ref": None, "summary": str(
                        finish_value) if finish_value else 'Task completed'}

        return action

    def get_initial_plan(self, prompt: str, snapshot: str) -> Tuple[
        List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Get initial plan and first action from LLM"""
        response = self._get_llm_response(prompt, snapshot, action_history=None, is_initial=True)

        if response and isinstance(response, dict):
            plan = response.get('plan', [])
            action = response.get('action', None)
            action = self._fix_action_format(action)
            return plan, action
        else:
            return [], None

    def get_next_action(self, prompt: str, snapshot: str) -> Optional[
        Dict[str, Any]]:
        """Get next action from LLM based on current state"""
        response = self._get_llm_response(prompt, snapshot, action_history=self.action_history,
                                          is_initial=False)

        if response and isinstance(response, dict):
            action = response.get('action', None)
            action = self._fix_action_format(action)
            return action
        else:
            return None

    def wait_for_page_stable(self):
        """Wait for page to be stable before executing actions - optimized"""
        try:
            self.page.wait_for_load_state('domcontentloaded', timeout=3000)
            # Removed sleep for faster execution
        except Exception as e:
            print(f"Warning: Page stability check failed: {e}")

    def execute_manual_action(self, action: Dict[str, Any]) -> str:
        """Execute manually input action (for demo usage)"""
        return self.execute_action(action)

    def get_current_snapshot(self) -> str:
        """Get current page snapshot - optimized for speed"""
        try:
            start_time = time.time()
            # Quick stability check - reduced timeout
            try:
                self.page.wait_for_load_state('domcontentloaded', timeout=3000)
            except:
                print("Quick stability check timeout, proceeding anyway...")

            print("获取当前页面snapshot...")
            result = self.snapshot.capture()
            print(f"Snapshot获取完成，耗时: {time.time() - start_time:.2f}s")
            return result
        except Exception as e:
            print(f"获取snapshot时出错: {e}")
            return "Error: Could not capture snapshot"

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
                text = action.get('text')
                selector = action.get('selector')

                # Need at least one way to find the element
                if not ref and not text and not selector:
                    return "Error: No ref, text, or selector specified for click action"

                # Try to find element using multiple strategies
                success = False

                # Strategy 1: Use provided selector
                if selector and not success:
                    try:
                        print(f"Trying to click with selector: {selector}")
                        element_count = self.page.locator(selector).count()
                        print(f"Found {element_count} elements with selector")

                        if element_count > 0:
                            self.page.click(selector, timeout=5000,
                                            force=True)  # 强制点击
                            success = True
                            result = f"Successfully clicked element using selector {selector} (force)"
                    except Exception as e:
                        print(f"Selector strategy failed: {e}")

                # Strategy 2: Use text content
                if text and not success:
                    try:
                        text_selector = f'text="{text}"'
                        print(f"Trying to click by text: {text_selector}")
                        element_count = self.page.locator(
                            text_selector).count()
                        print(
                            f"Found {element_count} elements with text selector")

                        if element_count > 0:
                            self.page.click(text_selector, timeout=5000,
                                            force=True)  # 强制点击
                            success = True
                            result = f"Successfully clicked element using text '{text}' (force)"
                    except Exception as e:
                        print(f"Text strategy failed: {e}")

                # Strategy 3: Try aria-ref attribute
                if ref and not success:
                    try:
                        aria_selector = f"[aria-ref='{ref}']"
                        print(
                            f"Trying to click element with aria-ref: {aria_selector}")
                        element_count = self.page.locator(
                            aria_selector).count()
                        print(
                            f"Found {element_count} elements with aria-ref selector")

                        if element_count > 0:
                            self.page.click(aria_selector, timeout=5000,
                                            force=True)  # 强制点击
                            success = True
                            result = f"Successfully clicked element {ref} using aria-ref (force)"
                    except Exception as e:
                        print(f"aria-ref strategy failed: {e}")

                # Strategy 4: Try to find by extracting text from ref and using text selector
                if ref and not success:
                    try:
                        # Look for text pattern in the most recent snapshot
                        snapshot_text = self.snapshot.snapshot_data or ""
                        lines = snapshot_text.split('\n')
                        target_text = None

                        for line in lines:
                            if f"[ref={ref}]" in line:
                                # Extract text from line like: - button "Search" [ref=e123]
                                import re
                                match = re.search(r'"([^"]+)"', line)
                                if match:
                                    target_text = match.group(1)
                                    break

                        if target_text:
                            print(
                                f"Extracted text from snapshot, trying to click: '{target_text}'")
                            text_selector = f'text="{target_text}"'
                            element_count = self.page.locator(
                                text_selector).count()
                            print(
                                f"Found {element_count} elements with extracted text selector")

                            if element_count > 0:
                                self.page.click(text_selector, timeout=5000,
                                                force=True)  # 强制点击
                                success = True
                                result = f"Successfully clicked element {ref} using extracted text (force)"
                    except Exception as e:
                        print(f"Text extraction strategy failed: {e}")

                # Strategy 5: Try common button/link patterns as fallback
                if not success:
                    try:
                        common_selectors = [
                            'button', 'a', 'input[type="submit"]',
                            'input[type="button"]', '[role="button"]'
                        ]

                        for sel in common_selectors:
                            elements = self.page.locator(sel)
                            count = elements.count()
                            if count > 0:
                                print(
                                    f"Found {count} {sel} elements, trying the first one")
                                elements.first.click(timeout=3000,
                                                     force=True)  # 强制点击
                                success = True
                                result = f"Successfully clicked first {sel} element as fallback (force)"
                                break

                    except Exception as e:
                        print(f"Fallback strategy failed: {e}")

                if not success:
                    return f"Error: Could not find and click element"

                # Reduced wait time after click
                time.sleep(0.5)

            elif action_type == 'type':
                ref = action.get('ref')
                text = action.get('text', '')
                selector = action.get('selector')

                if not ref and not selector:
                    return "Error: No ref or selector specified for type action"

                # Try multiple strategies to find input element
                success = False

                # Strategy 1: Use provided selector
                if selector and not success:
                    try:
                        print(f"Trying to type in selector: {selector}")
                        element_count = self.page.locator(selector).count()
                        if element_count > 0:
                            self.page.fill(selector, text, timeout=5000)
                            success = True
                            result = f"Successfully typed '{text}' into selector {selector}"
                    except Exception as e:
                        print(f"Selector typing failed: {e}")

                # Strategy 2: Try aria-ref attribute
                if ref and not success:
                    try:
                        aria_selector = f"[aria-ref='{ref}']"
                        print(f"Trying to type in aria-ref: {aria_selector}")
                        element_count = self.page.locator(
                            aria_selector).count()
                        if element_count > 0:
                            self.page.fill(aria_selector, text, timeout=5000)
                            success = True
                            result = f"Successfully typed '{text}' into element {ref} using aria-ref"
                    except Exception as e:
                        print(f"aria-ref typing failed: {e}")

                # Strategy 3: Try common input selectors as fallback
                if not success:
                    try:
                        input_selectors = [
                            'input[type="text"]', 'input[type="search"]',
                            'input:not([type])', 'textarea',
                            '[contenteditable]'
                        ]

                        for sel in input_selectors:
                            elements = self.page.locator(sel)
                            count = elements.count()
                            if count > 0:
                                print(
                                    f"Found {count} {sel} elements, typing into the first one")
                                elements.first.fill(text, timeout=3000)
                                success = True
                                result = f"Successfully typed '{text}' into {sel} element"
                                break

                    except Exception as e:
                        print(f"Input fallback strategy failed: {e}")

                if not success:
                    return f"Error: Could not find input element"

            elif action_type == 'select':
                ref = action.get('ref')
                value = action.get('value', '')
                selector = action.get('selector')

                if not ref and not selector:
                    return "Error: No ref or selector specified for select action"

                target_selector = selector or f"[aria-ref='{ref}']"

                try:
                    self.page.wait_for_selector(target_selector, timeout=10000)
                    self.page.select_option(target_selector, value,
                                            timeout=10000)
                    result = f"Successfully selected '{value}' in element"
                except Exception as e:
                    return f"Select operation failed: {e}"

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

                selector = f"[aria-ref='{ref}']"

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

            elif action_type == 'finish':
                summary = action.get('summary', 'Task completed')
                result = f"Task finished: {summary}"

            else:
                result = f"Error: Unknown action type '{action_type}'"

        except Exception as e:
            result = f"Error executing {action_type}: {str(e)}"
            print(f"Action execution error: {e}")
            print(f"Full error details:", e)

        # Optimized snapshot update after action
        try:
            old_snapshot = self.snapshot.snapshot_data
            # Use cache if possible, otherwise force refresh
            updated_snapshot = self.snapshot.capture()

            # Only update if snapshot actually changed
            if old_snapshot != updated_snapshot:
                print(
                    f"Snapshot updated after action. New size: {len(updated_snapshot)} characters")
            else:
                print("Snapshot unchanged after action")
        except Exception as e:
            print(f"Error updating snapshot after action: {e}")

        return result

    def _should_update_snapshot(self, action: Dict[str, Any]) -> bool:
        """Determine if snapshot should be updated after this action"""
        if not action:
            return False

        action_type = action.get('type', '')

        # Actions that don't change page content
        non_changing_actions = ['extract', 'wait', 'finish']

        # Actions that might change page content
        changing_actions = ['click', 'type', 'select', 'scroll']

        return action_type in changing_actions

    def process_command(self, prompt: str) -> None:
        """Process a user command through LLM and execute actions"""
        try:
            # Clear action history for new command
            self.action_history = []
            
            # 1. Get initial plan
            current_snapshot = self.snapshot.capture()
            if "Error:" in current_snapshot:
                print("Could not capture initial snapshot")
                return
            print_color(current_snapshot,'green')
            self.plan, action = self.get_initial_plan(prompt, current_snapshot)
            print("\nPlan:",
                  json.dumps(self.plan, indent=2, ensure_ascii=False))

            # 2. Execute action sequence
            max_actions = 15  # Increase maximum action count
            action_count = 0

            while action and action_count < max_actions:
                # Check if this is a finish action
                if action.get('type') == 'finish':
                    print(f"\n🎉 Task completed!")
                    print(
                        f"Summary: {action.get('summary', 'No summary provided')}")
                    return

                # Execute current action
                result = self.execute_action(action)
                print(
                    f"\nExecuted action: {json.dumps(action, indent=2, ensure_ascii=False)}")
                print(f"Result: {result}")

                # Record action in history
                success = "Error" not in result
                self.action_history.append({
                    'action': action,
                    'result': result,
                    'success': success
                })

                # If action failed, try to get new snapshot
                if "Error" in result:
                    print("Action failed, trying to continue...")
                    time.sleep(2)
                    # Force refresh on error
                    current_snapshot = self.snapshot.capture(
                        force_refresh=True)
                else:
                    # Smart snapshot update - only if action might have changed the page
                    if self._should_update_snapshot(action):
                        print(
                            "Action might have changed page, capturing fresh snapshot...")
                        old_snapshot = current_snapshot
                        current_snapshot = self.snapshot.capture(
                            force_refresh=True)

                        # Check if snapshot actually changed
                        if old_snapshot == current_snapshot:
                            print("Page content unchanged after action")
                        else:
                            print(
                                f"Page updated after action. New size: {len(current_snapshot)} characters")
                    else:
                        print(
                            f"Action '{action.get('type')}' doesn't change page content, reusing snapshot")

                if "Error:" in current_snapshot:
                    print("Could not capture snapshot, stopping...")
                    break

                # Get next action
                action = self.get_next_action(prompt, current_snapshot)
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
        agent.navigate("https://httpbin.org/forms/post")
        question = """
    "fill out the form with test data: "
    "- Customer name: 'John Doe' "
    "- Telephone: '+1-555-0123' "
    "- Email: 'john.doe@example.com' "
    "- Small pizza size "
    "- Add Choose Onion and mushroom toppings "
    "Then submit the form and report the response."

        """
        # Process user command
        agent.process_command(question)

    finally:
        agent.close() 
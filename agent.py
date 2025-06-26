from typing import Dict, Any, List, Optional
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

from snapshot import PageSnapshot
from actions import ActionExecutor
from chat_py import chat_single, message_template, print_color


class PlaywrightLLMAgent:
    """High-level orchestration: snapshot ↔ LLM ↔ action executor."""

    def __init__(self, *, user_data_dir: Optional[str] = None, headless: bool = False):
        self.playwright = sync_playwright().start()

        # --------------------------------------------------
        # Browser / context
        # --------------------------------------------------
        if user_data_dir:
            Path(user_data_dir).mkdir(parents=True, exist_ok=True)
            self.context = self.playwright.chromium.launch_persistent_context(user_data_dir=user_data_dir, headless=headless)
            self.browser = self.context.browser
        else:
            self.browser = self.playwright.chromium.launch(headless=headless)
            self.context = self.browser.new_context()

        self.page = self.context.new_page()

        # helpers
        self.snapshot = PageSnapshot(self.page)
        self.executor = ActionExecutor(self.page)
        self.action_history: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Navigation & snapshot helpers
    # ------------------------------------------------------------------
    def navigate(self, url: str) -> str:
        try:
            self.page.goto(url, wait_until="domcontentloaded", timeout=20000)
            try:
                self.page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            return self.snapshot.capture(force_refresh=True)
        except Exception as exc:
            return f"Error: could not navigate – {exc}"

    # ------------------------------------------------------------------
    # LLM interface
    # ------------------------------------------------------------------
    _ACTION_TYPES_DOC = """
Available action types:
- 'click': {"type": "click", "ref": "e1"} or {"type": "click", "text": "Button Text"} or {"type": "click", "selector": "button"}
- 'type': {"type": "type", "ref": "e1", "text": "search text"} or {"type": "type", "selector": "input", "text": "search text"}
- 'select': {"type": "select", "ref": "e1", "value": "option"} or {"type": "select", "selector": "select", "value": "option"}
- 'wait': {"type": "wait", "timeout": 2000} or {"type": "wait", "selector": "#element"}
- 'scroll': {"type": "scroll", "direction": "down", "amount": 300}
- 'enter': {"type": "enter", "ref": "e1"} or {"type": "enter", "selector": "input[name=q]"} or {"type": "enter"}
- 'navigate': {"type": "navigate", "url": "https://example.com"}
- 'finish': {"type": "finish", "ref": null, "summary": "task completion summary"}

IMPORTANT: 
- For 'click': Use 'ref' from snapshot, or 'text' for visible text, or 'selector' for CSS selectors
- For 'type'/'select': Use 'ref' from snapshot or 'selector' for CSS selectors
- Only use 'ref' values that exist in the snapshot (e.g., ref=e1, ref=e2, etc.)
- Use 'finish' when the task is completed successfully with a summary of what was accomplished
- Use 'enter' to press the Enter key (optionally focus an element first)
- Use 'navigate' to open a new URL before interacting further
- click can choose radio, checkbox...
"""

    def _llm_call(self, prompt: str, snapshot: str, is_initial: bool, history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        system_base = "You are a web automation assistant."


        system_detail = """
                " Analyse the page snapshot and create a short high-level plan, "
                "then output the FIRST action to start with.\n\n"
                "Return a JSON object in *exactly* this shape:\n"
Action format json_object examples:
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


"""

        system = system_base + system_detail + "\n" + self._ACTION_TYPES_DOC
        if is_initial:
            user = f"Snapshot:\n{snapshot}\n\nTask: {prompt}"
        else:
            hist_lines = [
                f"{i+1}. {'✅' if h['success'] else '❌'} {h['action']['type']} -> {h['result']}"
                for i, h in enumerate(history or [])
            ]
            user = f"Snapshot:\n{snapshot}\n\nHistory:\n" + "\n".join(hist_lines) + f"\n\nTask: {prompt}"
        messages = [message_template("system", system), message_template("user", user)]
        resp = chat_single(messages, mode="json", verbose=False)
        print_color(resp,'blue')
        return resp if isinstance(resp, dict) else {}

    # ------------------------------------------------------------------
    # Top-level command loop
    # ------------------------------------------------------------------
    def process_command(self, prompt: str, max_steps: int = 15):
        # Initial full snapshot (cache logic removed in PageSnapshot)
        full_snapshot = self.snapshot.capture()
        print("[Snapshot FULL]")
        print_color(full_snapshot, "green")

        plan_resp = self._llm_call(prompt, full_snapshot or "", is_initial=True)
        plan = plan_resp.get("plan", [])
        action = plan_resp.get("action")

        print("Plan:", json.dumps(plan, indent=2, ensure_ascii=False))

        steps = 0
        while action and steps < max_steps:
            if action.get("type") == "finish":
                print("🎉", action.get("summary", "Done"))
                break

            result = self._run_action(action)
            print(f"\n➡ Executed: {action}\n   Result: {result}")

            self.action_history.append({"action": action, "result": result, "success": "Error" not in result})

            diff_snapshot = self.snapshot.capture(
                force_refresh=ActionExecutor.should_update_snapshot(action),
                diff_only=True)

            # Determine if actual diff content exists
            is_diff = diff_snapshot.startswith("- Page Snapshot (diff)")
            print(f"[Snapshot {'DIFF' if is_diff else 'NO-CHANGE'}]")
            print_color(diff_snapshot, "green")

            # Update stored full snapshot when there are structural changes
            if is_diff:
                full_snapshot = self.snapshot.snapshot_data

            action = self._llm_call(prompt, full_snapshot or "", is_initial=False, history=self.action_history).get("action")
            steps += 1

    # ------------------------------------------------------------------
    def _run_action(self, action: Dict[str, Any]) -> str:
        if action.get("type") == "navigate":
            return self.navigate(action.get("url", ""))
        return self.executor.execute(action)

    # ------------------------------------------------------------------
    def close(self):
        try:
            self.context.close()
        except Exception:
            pass
        try:
            browser = getattr(self, "browser", None)
            if browser and getattr(browser, "is_connected", lambda: False)():
                browser.close()
        except Exception:
            pass
        self.playwright.stop()


# ----------------------------------------------------------------------
# Example usage
# ----------------------------------------------------------------------
if __name__ == "__main__":
    agent = PlaywrightLLMAgent(headless=False,user_data_dir="D:/User_Data")
    try:
        agent.process_command("""
        https://www.nytimes.com/games/wordle/index.html
玩一下这个游戏，你需要输入有意义的5个字母的单词，第一次输入apple
输入的时候add e 按钮就是输入e字母，add a 就是输入a
img "1st letter, E" 代表你输入的第一个字母是e 
要观察之前点击了哪些字母，然后凑出有意义的5字母单词
必须要有意义，不是随便输入5个字母
总共尝试输入5次
        
        """)
    finally:
        agent.close()
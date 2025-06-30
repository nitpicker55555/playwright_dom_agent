#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ========= Copyright 2023-2024 @ CAMEL-AI.org. All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ========= Copyright 2023-2024 @ CAMEL-AI.org. All Rights Reserved. =========

"""
Debug Demo for BrowserNonVisualToolkit

Interactive command-line tool for testing and debugging browser automation features.
Supports both visual (SoM screenshots) and non-visual (text snapshots) operations.

Usage:
    python camel_browser_debug_demo.py

Available commands:
    navigate <url>              - Navigate to a URL
    click <ref>                 - Click an element by reference (e.g., e1, e2)
    type <ref> <text>           - Type text into an element
    select <ref> <value>        - Select an option from dropdown
    snapshot                    - Get text snapshot of page
    screenshot                  - Get SoM screenshot with visual marks
    links <ref1> <ref2> ...     - Get specific links by references
    wait                        - Wait for user input (manual intervention)
    help                        - Show available commands
    exit                        - Exit the program
"""

import asyncio
import os
import shlex
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Add the parent directories to Python path for proper imports
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)
grandparent_dir = os.path.dirname(parent_dir)
root_dir = os.path.dirname(grandparent_dir)

if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# Now import from the camel package
from camel.toolkits.hybrid_browser_toolkit import HybridBrowserToolkit


class BrowserDebugDemo:
    """Interactive debug demo for BrowserNonVisualToolkit."""

    def __init__(self, headless: bool = False,
                 cache_dir: str = "debug_output"):
        """Initialize the debug demo.

        Args:
            headless (bool): Whether to run browser in headless mode
            cache_dir (str): Directory to save screenshots and outputs
        """
        self.toolkit: Optional[HybridBrowserToolkit] = None
        self.headless = headless
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.command_count = 0

        # Create session directory
        self.session_dir = self.cache_dir / f"session_{self.session_id}"
        self.session_dir.mkdir(exist_ok=True)

        print(f"Debug session started: {self.session_id}")
        print(f"Output directory: {self.session_dir}")

    async def start(self):
        """Start the debug session."""
        print("\nStarting BrowserNonVisualToolkit Debug Demo")
        print("Browser will automatically open https://google.com on startup.")
        print("Type 'help' for available commands or 'exit' to quit.\n")

        try:
            # Initialize toolkit
            self.toolkit = HybridBrowserToolkit(
                headless=self.headless,
                cache_dir=str(self.session_dir)
            )
            
            # Auto-navigate to Google on startup
            print("Auto-navigating to https://google.com...")
            result = await self.toolkit.open_browser("https://google.com")
            print(f"Navigation result: {result}")

            # Auto-execute click e117 for testing
            print("\nAuto-executing 'click e117' for testing...")
            try:
                click_result = await self._cmd_click(['e117'])
                print(f"Auto-click result: {click_result}")
            except Exception as e:
                print(f"Auto-click failed: {e}")
                import traceback
                traceback.print_exc()

            # Start interactive loop
            await self._interactive_loop()

        except KeyboardInterrupt:
            print("\nDemo interrupted by user")
        except Exception as e:
            print(f"Demo failed: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await self._cleanup()

    async def _interactive_loop(self):
        """Main interactive command loop."""
        while True:
            try:
                # Get user input
                command = input(
                    f"[{self.command_count}] browser_debug> ").strip()

                if not command:
                    continue

                self.command_count += 1

                # Parse and execute command
                result = await self._parse_and_execute(command)

                # Handle result
                await self._handle_result(command, result)

                if command.lower() in ['exit', 'quit']:
                    break

            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except UnicodeDecodeError as e:
                print(f"Unicode encoding error: {e}")
                print("This might be caused by non-UTF-8 content on the page.")
                print("Try navigating to a different page or check the browser console.")
            except Exception as e:
                print(f"Error executing command: {e}")
                import traceback
                print("Full traceback:")
                traceback.print_exc()

    async def _parse_and_execute(self, command: str) -> Any:
        """Parse user command and execute corresponding action.

        Args:
            command (str): User input command

        Returns:
            Any: Result from the executed action
        """
        # Parse command using shlex for proper quote handling
        try:
            parts = shlex.split(command.lower())
        except ValueError as e:
            return f"Command parsing error: {e}"

        if not parts:
            return "Empty command"

        cmd = parts[0]
        args = parts[1:]

        # Route to appropriate handler
        if cmd == 'help':
            return self._show_help()
        elif cmd == 'exit' or cmd == 'quit':
            return "Goodbye!"
        elif cmd == 'navigate':
            return await self._cmd_navigate(args)
        elif cmd == 'click':
            return await self._cmd_click(args)
        elif cmd == 'type':
            return await self._cmd_type(args)
        elif cmd == 'select':
            return await self._cmd_select(args)
        elif cmd == 'snapshot':
            return await self._cmd_snapshot(args)
        elif cmd == 'screenshot':
            return await self._cmd_screenshot(args)
        elif cmd == 'links':
            return await self._cmd_links(args)
        elif cmd == 'wait':
            return await self._cmd_wait(args)
        elif cmd == 'debug_elements':
            return await self._cmd_debug_elements(args)
        elif cmd == 'snapshot_mode':
            return await self._cmd_snapshot_mode(args)
        else:
            return f"Unknown command: {cmd}. Type 'help' for available commands."

    def _show_help(self) -> str:
        """Show available commands."""
        help_text = """
Available Commands:

NOTE: Browser automatically opens https://google.com on startup.

Navigation:
  navigate <url>              - Navigate to a URL
                               Example: navigate https://example.com

Interaction:
  click <ref>                 - Click an element by reference
                               Example: click e5
  type <ref> <text>           - Type text into an element  
                               Example: type e3 "hello world"
  select <ref> <value>        - Select option from dropdown
                               Example: select e7 option1

Information:
  snapshot                    - Get text snapshot of current page
  screenshot                  - Get SoM screenshot with visual marks
  links <ref1> <ref2> ...     - Get specific links by references
                               Example: links e1 e3 e5

Utilities:
  wait                        - Wait for manual user intervention
  debug_elements              - Show all available element references
  snapshot_mode               - Show current snapshot mode
  help                        - Show this help message
  exit                        - Exit the program

Tips:
- Use quotes for text with spaces: type e3 "hello world"
- References are like e1, e2, e3 (from snapshots)
- Screenshots are saved automatically to the session directory
"""
        return help_text

    async def _cmd_navigate(self, args: List[str]) -> Any:
        """Handle navigate command."""
        if not args:
            return "Usage: navigate <url>"

        url = args[0]
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        try:
            if self.toolkit is None:
                return "Toolkit not initialized"
            result = await self.toolkit.visit_page(url)
            return f"Navigated to: {url}\nFull result: {result}"
        except Exception as e:
            return f"Navigation failed: {e}"

    async def _cmd_click(self, args: List[str]) -> Any:
        """Handle click command."""
        if not args:
            return "Usage: click <ref> (e.g., click e5)"

        ref = args[0]
        try:
            if self.toolkit is None:
                return "Toolkit not initialized"
            
            # Debug: Check if element exists before clicking
            await self._debug_element_info(ref)
            
            result = await self.toolkit.click(ref=ref)
            return f"Clicked element {ref}\nFull result: {result}"
        except Exception as e:
            return f"Click failed: {e}"

    async def _debug_element_info(self, ref: str) -> str:
        """Debug helper to check element information before click."""
        if self.toolkit is None:
            return "Toolkit not initialized"
            
        try:
            # Get page handle
            page = await self.toolkit._require_page()
            
            # First, run unified analysis to ensure aria-ref attributes are set
            analysis = await self.toolkit._get_unified_analysis()
            
            # Check if element exists in analysis
            elements = analysis.get("elements", {})
            if ref not in elements:
                print(f"DEBUG: Element {ref} not found in analysis. Available refs: {list(elements.keys())[:10]}...")
                return f"Element {ref} not found in analysis"
            
            element_info = elements[ref]
            print(f"DEBUG: Element {ref} info: {element_info}")
            
            # Check if element exists in DOM with aria-ref
            selector = f'[aria-ref="{ref}"]'
            element_count = await page.locator(selector).count()
            print(f"DEBUG: Found {element_count} elements with selector {selector}")
            
            if element_count > 0:
                # Get element details
                element = page.locator(selector).first
                is_visible = await element.is_visible()
                is_enabled = await element.is_enabled()
                tag_name = await element.evaluate("el => el.tagName")
                
                print(f"DEBUG: Element details - Visible: {is_visible}, Enabled: {is_enabled}, Tag: {tag_name}")
                
                # Try to get bounding box
                try:
                    bbox = await element.bounding_box()
                    print(f"DEBUG: Bounding box: {bbox}")
                except Exception as e:
                    print(f"DEBUG: Could not get bounding box: {e}")
            
            return f"Debug info printed for {ref}"
            
        except Exception as e:
            print(f"DEBUG: Error getting element info: {e}")
            return f"Debug error: {e}"

    async def _cmd_debug_elements(self, args: List[str]) -> Any:
        """Handle debug_elements command - show all available elements."""
        try:
            if self.toolkit is None:
                return "Toolkit not initialized"
            
            # Get analysis data
            analysis = await self.toolkit._get_unified_analysis()
            elements = analysis.get("elements", {})
            
            if not elements:
                return "No elements found in current page"
            
            output = f"Found {len(elements)} elements:\n"
            for ref, info in list(elements.items())[:20]:  # Limit to first 20
                role = info.get("role", "unknown")
                name = info.get("name", "")
                output += f"  {ref}: {role}"
                if name:
                    output += f' "{name[:30]}"'
                output += "\n"
            
            if len(elements) > 20:
                output += f"... and {len(elements) - 20} more elements. Use 'snapshot' to see all."
            
            return output
            
        except Exception as e:
            return f"Debug elements failed: {e}"

    async def _cmd_snapshot_mode(self, args: List[str]) -> Any:
        """Handle snapshot_mode command - show current snapshot mode."""
        if not args:
            return ("Current snapshot mode: FULL (actions return complete snapshots)\n"
                   "Note: The toolkit has been modified to always return full snapshots after actions.")
        
        return "Snapshot mode command - currently only supports viewing mode"

    async def _cmd_type(self, args: List[str]) -> Any:
        """Handle type command."""
        if len(args) < 2:
            return "Usage: type <ref> <text> (e.g., type e3 'hello world')"

        ref = args[0]
        text = ' '.join(args[1:])

        try:
            if self.toolkit is None:
                return "Toolkit not initialized"
            result = await self.toolkit.type(ref=ref, text=text)
            return f"Typed '{text}' into element {ref}\nFull result: {result}"
        except Exception as e:
            return f"Type failed: {e}"

    async def _cmd_select(self, args: List[str]) -> Any:
        """Handle select command."""
        if len(args) < 2:
            return "Usage: select <ref> <value> (e.g., select e7 option1)"

        ref = args[0]
        value = args[1]

        try:
            if self.toolkit is None:
                return "Toolkit not initialized"
            result = await self.toolkit.select(ref=ref, value=value)
            return f"Selected '{value}' in element {ref}\nFull result: {result}"
        except Exception as e:
            return f"Select failed: {e}"

    async def _cmd_snapshot(self, args: List[str]) -> Any:
        """Handle snapshot command."""
        try:
            if self.toolkit is None:
                return "Toolkit not initialized"
            result = await self.toolkit.get_page_snapshot()
            return f"Page Snapshot:\n{result}"
        except Exception as e:
            return f"Snapshot failed: {e}"

    async def _cmd_screenshot(self, args: List[str]) -> Any:
        """Handle screenshot command."""
        try:
            if self.toolkit is None:
                return "Toolkit not initialized"
            result = await self.toolkit.get_som_screenshot()

            if "PIL not available" in result.text:
                return "Screenshot failed: PIL (Pillow) not available. Install with: pip install Pillow"

            return f"SoM Screenshot captured: {result.text}"
        except Exception as e:
            return f"Screenshot failed: {e}"

    async def _cmd_links(self, args: List[str]) -> Any:
        """Handle links command."""
        if not args:
            return "Usage: links <ref1> <ref2> ... (e.g., links e1 e3 e5)"

        try:
            if self.toolkit is None:
                return "Toolkit not initialized"
            result = await self.toolkit.get_page_links(ref=args)


            return str(result).rstrip()
        except Exception as e:
            return f"Links failed: {e}"

    async def _cmd_wait(self, args: List[str]) -> Any:
        """Handle wait command."""
        try:
            if self.toolkit is None:
                return "Toolkit not initialized"

            timeout = None
            if args and args[0].isdigit():
                timeout = float(args[0])

            result = await self.toolkit.wait_user(timeout_sec=timeout)
            return f"Wait completed\nFull result: {result}"
        except Exception as e:
            return f"Wait failed: {e}"

    async def _handle_result(self, command: str, result: Any):
        """Handle and display command result.

        Args:
            command (str): Original command
            result (Any): Result from command execution
        """
        # Save command and result to log file
        log_file = self.session_dir / "command_log.txt"
        timestamp = datetime.now().strftime("%H:%M:%S")

        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] Command: {command}\n")
            f.write(f"[{timestamp}] Result: {str(result)[:500]}...\n" if len(
                str(result)) > 500 else f"[{timestamp}] Result: {result}\n")
            f.write("-" * 50 + "\n")

        # Display result
        if isinstance(result, str):
            print(result)
        else:
            print(f"Result: {result}")

    async def _cleanup(self):
        """Cleanup resources."""
        if self.toolkit:
            try:
                await self.toolkit.close_browser()
                print("Browser closed")
            except Exception as e:
                print(f"Cleanup warning: {e}")

        print(f"Session files saved to: {self.session_dir}")


async def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(
        description="BrowserNonVisualToolkit Debug Demo")
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode"
    )
    parser.add_argument(
        "--cache-dir",
        default="debug_output",
        help="Directory to save screenshots and outputs (default: debug_output)"
    )

    args = parser.parse_args()

    demo = BrowserDebugDemo(
        headless=args.headless,
        cache_dir=args.cache_dir
    )

    await demo.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram interrupted")
    except Exception as e:
        print(f"Program failed: {e}")
        sys.exit(1)
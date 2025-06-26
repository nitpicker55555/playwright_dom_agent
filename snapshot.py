from pathlib import Path
import time
import os
import subprocess
import json
from typing import Optional, Dict, List

class PageSnapshot:
    def __init__(self, page):
        self.page = page
        self.snapshot_data = None  # Last full snapshot (formatted string)
        self.element_map = {}  # Store mapping from ref to actual elements
        # Note: Cache fields for URL/content-based optimisations were removed to
        # ensure we always take a fresh snapshot. We keep only `snapshot_data`
        # so that diff generation can compare against the previous full
        # snapshot captured during the same session.
        self._last_direct_error: Optional[str] = None  # Store last error from direct snapshot

    def _compute_diff(self, old: str, new: str) -> str:
        """Return unified diff between two snapshot strings."""
        import difflib

        old_lines = old.splitlines(keepends=False)
        new_lines = new.splitlines(keepends=False)

        diff_lines = list(
            difflib.unified_diff(
                old_lines,
                new_lines,
                lineterm="",
                fromfile="prev",
                tofile="curr",
            )
        )

        if not diff_lines:
            return "- Page Snapshot (no structural changes)"

        diff_block = ["- Page Snapshot (diff)", "```diff"] + diff_lines + ["```"]
        return "\n".join(diff_block)

    def capture(self, force_refresh: bool = False, diff_only: bool = False,
                include_all: bool = False) -> str:
        """Return the current snapshot.


     Parameters
     ----------
     force_refresh : bool, default False
         Ignore URL/hash cache and rebuild snapshot.
     diff_only : bool, default False
         If True *and* a previous snapshot exists, return a unified-diff of
         changes instead of the full YAML. Always returns full snapshot on
         first call or when cache is invalid.
     """
        try:
            # Always capture a fresh snapshot – caching logic was removed.
            current_url = self.page.url  # still used for logging/debug only

            # Short-circuit: unchanged page & caller **not** forcing diff
            # if not force_refresh and current_url == self._last_url and self.snapshot_data and not diff_only:
            #     print("Using cached snapshot (same URL)")
            #     return self.snapshot_data

            # Fast page stability check (reduced waiting)
            start_time = time.time()
            self.page.wait_for_load_state('domcontentloaded', timeout=5000)
            print(f"Page load check: {time.time() - start_time:.2f}s")

            # Try direct evaluation first (fastest method)
            start_time = time.time()
            snapshot_text = self._get_snapshot_direct(all_elements=include_all)

            if snapshot_text:
                print(
                    f"✅ Direct Python _snapshotForAI: {time.time() - start_time:.2f}s")
                formatted_snapshot = self._format_snapshot(snapshot_text)
                # Compute diff if requested
                output_snapshot = formatted_snapshot
                if diff_only and self.snapshot_data:
                    output_snapshot = self._compute_diff(self.snapshot_data, formatted_snapshot)  # type: ignore[attr-defined]

                # Persist the latest *full* snapshot only for diff generation
                # (no URL/content hash caching is kept).
                self._update_cache(current_url, formatted_snapshot)
                return output_snapshot

            # Fallback to Node.js version (slower but more reliable)
            # start_time = time.time()
            # snapshot_text = self._get_snapshot_via_nodejs()
            # if snapshot_text:
            #     print(
            #         f"✅ Node.js _snapshotForAI (official): {time.time() - start_time:.2f}s")
            #     print(snapshot_text)
            #     formatted_snapshot = self._format_snapshot(snapshot_text)
            #     # Compute diff if requested
            #     output_snapshot = formatted_snapshot
            #     if diff_only and self.snapshot_data:
            #         output_snapshot = self._compute_diff(self.snapshot_data, formatted_snapshot)  # type: ignore[attr-defined]
            #
            #     self._update_cache(current_url, formatted_snapshot)
            #     return output_snapshot

            # Final fallback
            print("Warning: All snapshot methods failed, using basic fallback")
            fallback = self._fallback_snapshot()
            if diff_only and self.snapshot_data:
                fallback = self._compute_diff(self.snapshot_data, fallback)  # type: ignore[attr-defined]
            return fallback

        except Exception as e:
            print(f"Error capturing snapshot: {e}")
            return "Error: Could not capture page snapshot"

    def _get_snapshot_direct(self, all_elements: bool = False) -> Optional[str]:
        """Try to get snapshot directly using page.evaluate (fastest method)"""
        # Choose appropriate JS snapshot implementation
        js_filename = "snapshot_complete.js" if all_elements else "snapshot.js"
        js_path = Path(__file__).parent / js_filename

        try:
            js_code = js_path.read_text(encoding="utf-8")

            result = self.page.evaluate(js_code)

            return result
        except Exception as e:
            err_msg = str(e)
            self._last_direct_error = err_msg
            print(f"Error evaluating {js_filename}: {err_msg}")
            return None

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
        # Update stored snapshot so that future `diff_only=True` calls can
        # compute differences. All other cache mechanisms were removed.
        self.snapshot_data = snapshot

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
"""Parse Slack export JSON files into searchable text.

Slack exports contain JSON arrays of messages. This parser groups messages
by thread and formats each thread as a single chunk-friendly block.
"""

import json
from datetime import datetime


class SlackParser:
    @staticmethod
    def parse(file_path: str) -> str:
        with open(file_path) as f:
            data = json.load(f)

        if isinstance(data, dict):
            # Handle single-channel export with metadata wrapper
            messages = data.get("messages", data.get("data", []))
        elif isinstance(data, list):
            messages = data
        else:
            return ""

        # Group messages by thread
        threads: dict[str, list[dict]] = {}
        standalone: list[dict] = []

        for msg in messages:
            if not isinstance(msg, dict):
                continue
            text = msg.get("text", "").strip()
            if not text:
                continue

            thread_ts = msg.get("thread_ts")
            ts = msg.get("ts", "")

            if thread_ts and thread_ts != ts:
                threads.setdefault(thread_ts, []).append(msg)
            elif thread_ts:
                threads.setdefault(thread_ts, []).insert(0, msg)
            else:
                standalone.append(msg)

        # Move standalone messages that are thread parents into their threads
        remaining_standalone = []
        for msg in standalone:
            ts = msg.get("ts", "")
            if ts in threads:
                threads[ts].insert(0, msg)
            else:
                remaining_standalone.append(msg)
        standalone = remaining_standalone

        parts = []

        # Format threaded conversations
        for thread_ts in sorted(threads.keys()):
            thread_msgs = sorted(threads[thread_ts], key=lambda m: m.get("ts", ""))
            thread_lines = []
            for msg in thread_msgs:
                user = msg.get("user", msg.get("username", "unknown"))
                text = msg.get("text", "")
                ts = msg.get("ts", "")
                date_str = _format_ts(ts)
                thread_lines.append(f"[{user}] ({date_str}): {text}")
            parts.append("\n".join(thread_lines))

        # Format standalone messages
        for msg in sorted(standalone, key=lambda m: m.get("ts", "")):
            user = msg.get("user", msg.get("username", "unknown"))
            text = msg.get("text", "")
            ts = msg.get("ts", "")
            date_str = _format_ts(ts)
            parts.append(f"[{user}] ({date_str}): {text}")

        return "\n\n---\n\n".join(parts)


def _format_ts(ts: str) -> str:
    try:
        dt = datetime.fromtimestamp(float(ts))
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError, OSError):
        return "unknown"

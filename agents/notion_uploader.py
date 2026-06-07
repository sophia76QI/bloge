"""
notion_uploader.py - PHASE 4: Notion Uploader Agent (Sonnet + MCP)

Reads all output/*.md files and uploads to Notion via MCP notion-create-pages.
상위 1페이지 (블로그) + 하위 4페이지 (블로그·뉴스레터·Threads·IG).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


def _read_output_files(output_dir: str) -> Dict[str, str]:
    """Read all generated .md files from output/."""
    out_path = Path(output_dir)
    files = {
        "blog": out_path / "blog_reviewed.md",
        "newsletter": out_path / "newsletter.md",
        "threads": out_path / "threads.md",
        "instagram": out_path / "instagram.md",
    }
    contents = {}
    for key, fp in files.items():
        if fp.exists():
            contents[key] = fp.read_text(encoding="utf-8")
            logger.info(f"[Notion Uploader] Read {fp.name} ({len(contents[key])} chars)")
        else:
            logger.warning(f"[Notion Uploader] {fp.name} not found, skipping")
            contents[key] = ""
    return contents


def _md_to_notion_blocks(md_text: str) -> list:
    """Convert markdown text to Notion block objects (simplified)."""
    blocks = []
    for line in md_text.split("\n"):
        line_stripped = line.rstrip()
        if not line_stripped:
            blocks.append({"object": "block", "type": "paragraph",
                           "paragraph": {"rich_text": []}})
        elif line_stripped.startswith("# "):
            blocks.append({"object": "block", "type": "heading_1",
                           "heading_1": {"rich_text": [{"type": "text", "text": {"content": line_stripped[2:]}}]}})
        elif line_stripped.startswith("## "):
            blocks.append({"object": "block", "type": "heading_2",
                           "heading_2": {"rich_text": [{"type": "text", "text": {"content": line_stripped[3:]}}]}})
        elif line_stripped.startswith("### "):
            blocks.append({"object": "block", "type": "heading_3",
                           "heading_3": {"rich_text": [{"type": "text", "text": {"content": line_stripped[4:]}}]}})
        elif line_stripped.startswith("- ") or line_stripped.startswith("* "):
            blocks.append({"object": "block", "type": "bulleted_list_item",
                           "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": line_stripped[2:]}}]}})
        elif line_stripped.startswith("> "):
            blocks.append({"object": "block", "type": "quote",
                           "quote": {"rich_text": [{"type": "text", "text": {"content": line_stripped[2:]}}]}})
        elif line_stripped == "---":
            blocks.append({"object": "block", "type": "divider", "divider": {}})
        else:
            blocks.append({"object": "block", "type": "paragraph",
                           "paragraph": {"rich_text": [{"type": "text", "text": {"content": line_stripped}}]}})
    # Notion API limit: 100 blocks per request
    return blocks[:100]


def run(
    output_dir: str = "output",
    run_date: str = "",
    notion_parent_page_id: Optional[str] = None,
) -> Dict[str, str]:
    """
    Upload all output/*.md to Notion.

    Uses NOTION_PARENT_PAGE_ID env var as parent if not provided.
    Returns dict of {content_type: notion_page_url}.

    NOTE: Actual MCP notion-create-pages calls require the Notion MCP server
    to be active. In Claude Code sessions with Notion MCP configured, this
    runs automatically. Without MCP, logs a summary and saves a manifest.
    """
    contents = _read_output_files(output_dir)
    parent_id = notion_parent_page_id or os.environ.get("NOTION_PARENT_PAGE_ID", "")

    page_map = {
        "blog": ("📊 블로그 원고", contents.get("blog", "")),
        "newsletter": ("📬 뉴스레터", contents.get("newsletter", "")),
        "threads": ("🧵 Threads", contents.get("threads", "")),
        "instagram": ("📸 Instagram 카드뉴스", contents.get("instagram", "")),
    }

    results: Dict[str, str] = {}

    if not parent_id:
        logger.warning(
            "[Notion Uploader] NOTION_PARENT_PAGE_ID not set. "
            "Set it in .env to enable automatic Notion upload. "
            "In Claude Code with Notion MCP active, pages will be created via MCP tool calls."
        )
        # Save upload manifest for manual/MCP use
        manifest_path = Path(output_dir) / "notion_upload_manifest.md"
        manifest_lines = [
            f"# Notion Upload Manifest — {run_date}",
            "",
            "Set NOTION_PARENT_PAGE_ID in .env and re-run to auto-upload.",
            "Or use Claude Code with Notion MCP to create pages manually.",
            "",
            "## Pages to create:",
        ]
        for key, (title, body) in page_map.items():
            manifest_lines.append(f"- {title}: {len(body)} chars")
        manifest_path.write_text("\n".join(manifest_lines), encoding="utf-8")
        logger.info(f"[Notion Uploader] 📋 Manifest saved to {manifest_path}")
        return {"manifest": str(manifest_path)}

    # With parent_id: attempt Notion API upload via notion-client or MCP
    try:
        from notion_client import Client as NotionClient

        notion = NotionClient(auth=os.environ.get("NOTION_API_KEY", ""))

        # Create parent page for this run
        parent_page = notion.pages.create(
            parent={"page_id": parent_id},
            properties={"title": {"title": [{"text": {"content": f"🔍 셜록홈즈 리포트 — {run_date}"}}]}},
            children=_md_to_notion_blocks(contents.get("blog", "")),
        )
        parent_url = parent_page.get("url", "")
        results["blog"] = parent_url
        logger.info(f"[Notion Uploader] ✅ Parent page created: {parent_url}")

        # Create child pages
        child_parent_id = parent_page["id"]
        for key, (title, body) in page_map.items():
            if key == "blog" or not body:
                continue
            child = notion.pages.create(
                parent={"page_id": child_parent_id},
                properties={"title": {"title": [{"text": {"content": title}}]}},
                children=_md_to_notion_blocks(body),
            )
            child_url = child.get("url", "")
            results[key] = child_url
            logger.info(f"[Notion Uploader] ✅ {title} page created: {child_url}")

    except ImportError:
        logger.warning(
            "[Notion Uploader] notion-client not installed. "
            "Run: pip install notion-client  OR use Notion MCP in Claude Code."
        )
    except Exception as e:
        logger.error(f"[Notion Uploader] Notion API error: {e}")

    return results

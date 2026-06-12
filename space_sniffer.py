#!/usr/bin/env python3
"""
SpaceSniffer Clone — Futuristic Disk Space Visualizer
=====================================================
A lightweight disk space analyzer with squarified treemap visualization.
Pure Python 3 + tkinter — no third-party dependencies required.

Features:
  - Squarified treemap layout for optimal rectangle proportions
  - Multi-threaded disk scanning with real-time progress
  - Dark cyberpunk / futuristic neon theme
  - Interactive zoom: click folders to drill down, breadcrumb navigation
  - Color coding by file type (documents, images, video, audio, code, etc.)
  - Hover tooltips with file/folder name and size
  - Keyboard shortcuts: Backspace=back, Esc=home, F5=rescan
  - Right-click to open in Explorer

Author: Claude Code
"""

from __future__ import annotations

import ctypes
import os
import sys
import math
import queue
import string
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from collections import defaultdict
from typing import Optional, Callable

# ═══════════════════════════════════════════════════════════════════════════════
# Constants & Configuration
# ═══════════════════════════════════════════════════════════════════════════════

APP_NAME = "SpaceSniffer"
APP_VERSION = "1.0.0"

# ── Futuristic Dark Theme Colors ────────────────────────────────────────────
C_BG         = "#08080f"   # deepest background
C_PANEL      = "#0f0f18"   # panel / sidebar
C_SURFACE    = "#14141f"   # elevated surface
C_BORDER     = "#1e1e30"   # subtle border
C_BORDER_GLOW = "#2a2a45"  # highlighted border

C_CYAN       = "#00e5ff"   # primary accent
C_MAGENTA    = "#e040fb"   # secondary accent
C_GREEN      = "#00e676"   # success / free space
C_GOLD       = "#ffd740"   # warning / archives
C_RED        = "#ff5252"   # errors / system files

C_TEXT       = "#d0d0e0"   # primary text
C_TEXT_DIM   = "#707088"   # secondary / dim text
C_TEXT_BRIGHT = "#f0f0ff"  # highlighted text

# ── Treemap Colors (by file category) ───────────────────────────────────────
# Each category maps to (base_color, glow_color) for gradient effect
CATEGORY_COLORS: dict[str, tuple[str, str]] = {
    "system":    ("#e53935", "#ff5252"),   # red — Windows / System
    "documents": ("#1e88e5", "#42a5f5"),   # blue — docs, pdf, office
    "images":    ("#d81b60", "#f06292"),   # pink — images
    "videos":    ("#ef6c00", "#ff9800"),   # orange — video
    "audio":     ("#8e24aa", "#ab47bc"),   # purple — audio
    "archives":  ("#f9a825", "#fdd835"),   # gold — archives
    "code":      ("#00c853", "#69f0ae"),   # green — source code
    "folders":   ("#1565c0", "#1e88e5"),   # dark blue — directories
    "other":     ("#546e7a", "#78909c"),   # grey — misc
}

# Category detection by extension
EXT_CATEGORY: dict[str, str] = {
    # System
    ".sys": "system", ".dll": "system", ".exe": "system", ".msi": "system",
    ".ini": "system", ".cfg": "system", ".reg": "system", ".drv": "system",
    ".bat": "system", ".cmd": "system", ".ps1": "system", ".com": "system",
    # Documents
    ".doc": "documents", ".docx": "documents", ".xls": "documents",
    ".xlsx": "documents", ".ppt": "documents", ".pptx": "documents",
    ".pdf": "documents", ".txt": "documents", ".md": "documents",
    ".rtf": "documents", ".csv": "documents", ".log": "documents",
    ".odt": "documents", ".ods": "documents", ".odp": "documents",
    # Images
    ".jpg": "images", ".jpeg": "images", ".png": "images", ".gif": "images",
    ".bmp": "images", ".svg": "images", ".ico": "images", ".webp": "images",
    ".tiff": "images", ".tif": "images", ".psd": "images", ".raw": "images",
    ".heic": "images",
    # Videos
    ".mp4": "videos", ".avi": "videos", ".mkv": "videos", ".mov": "videos",
    ".wmv": "videos", ".flv": "videos", ".webm": "videos", ".m4v": "videos",
    ".mpg": "videos", ".mpeg": "videos", ".3gp": "videos",
    # Audio
    ".mp3": "audio", ".wav": "audio", ".flac": "audio", ".aac": "audio",
    ".ogg": "audio", ".wma": "audio", ".m4a": "audio", ".opus": "audio",
    ".mid": "audio", ".midi": "audio",
    # Archives
    ".zip": "archives", ".rar": "archives", ".7z": "archives", ".tar": "archives",
    ".gz": "archives", ".bz2": "archives", ".xz": "archives", ".iso": "archives",
    ".cab": "archives", ".arj": "archives", ".lzh": "archives",
    # Code
    ".py": "code", ".js": "code", ".ts": "code", ".jsx": "code", ".tsx": "code",
    ".html": "code", ".css": "code", ".scss": "code", ".less": "code",
    ".java": "code", ".c": "code", ".cpp": "code", ".h": "code", ".hpp": "code",
    ".cs": "code", ".go": "code", ".rs": "code", ".rb": "code", ".php": "code",
    ".swift": "code", ".kt": "code", ".kts": "code", ".sh": "code",
    ".json": "code", ".xml": "code", ".yaml": "code", ".yml": "code",
    ".toml": "code", ".sql": "code", ".r": "code", ".lua": "code",
    ".ipynb": "code", ".vue": "code", ".svelte": "code",
}

# Minimum rectangle size to render (pixels)
MIN_RECT_W = 3
MIN_RECT_H = 3
MIN_TEXT_W = 40
MIN_TEXT_H = 18

# ── File size formatting ────────────────────────────────────────────────────
def fmt_size(size: int) -> str:
    """Format byte size into human-readable string."""
    if size < 1024:
        return f"{size} B"
    for unit in ("KB", "MB", "GB", "TB", "PB"):
        size /= 1024.0
        if size < 1024.0:
            return f"{size:.1f} {unit}"
    return f"{size:.1f} PB"


def fmt_size_detailed(size: int) -> str:
    """Format size with exact byte count for small sizes."""
    if size < 1024:
        return f"{size:,} B"
    return f"{fmt_size(size)} ({size:,} bytes)"


# ═══════════════════════════════════════════════════════════════════════════════
# Data Model
# ═══════════════════════════════════════════════════════════════════════════════

class FileNode:
    """Tree node representing a file or directory."""

    __slots__ = (
        "name", "path", "is_dir", "size", "children",
        "category", "extension", "scanned", "error",
    )

    def __init__(self, name: str, path: str, is_dir: bool) -> None:
        self.name = name
        self.path = path
        self.is_dir = is_dir
        self.size: int = 0
        self.children: list[FileNode] = []
        self.category = "other"
        self.extension = ""
        self.scanned = False
        self.error: Optional[str] = None

        if not is_dir:
            _, ext = os.path.splitext(name)
            self.extension = ext.lower()
            self.category = EXT_CATEGORY.get(self.extension, "other")

    def __repr__(self) -> str:
        return f"FileNode({self.name!r}, size={self.size}, dir={self.is_dir})"


# ═══════════════════════════════════════════════════════════════════════════════
# Disk Scanner (threaded)
# ═══════════════════════════════════════════════════════════════════════════════

class DiskScanner:
    """Scans a directory tree and builds FileNode hierarchy in a background thread."""

    def __init__(self):
        self._cancel_flag = threading.Event()
        self._queue: queue.Queue = queue.Queue()
        self._thread: Optional[threading.Thread] = None

    def scan(self, root_path: str) -> tuple[queue.Queue, threading.Thread]:
        """Start scanning. Returns (progress_queue, thread)."""
        self._cancel_flag.clear()
        self._queue = queue.Queue()
        self._thread = threading.Thread(
            target=self._scan_worker,
            args=(root_path,),
            daemon=True,
        )
        self._thread.start()
        return self._queue, self._thread

    def cancel(self) -> None:
        """Request scan cancellation."""
        self._cancel_flag.set()

    def _scan_worker(self, root_path: str) -> None:
        """Background worker: recursively walk the directory tree."""
        try:
            root = FileNode(
                os.path.basename(root_path) or root_path,
                root_path,
                True,
            )
            self._queue.put(("start", root_path, None))

            # First pass: collect all immediate children with sizes
            self._scan_directory(root)

            if not self._cancel_flag.is_set():
                self._queue.put(("done", root, None))
        except Exception as exc:
            self._queue.put(("error", str(exc), None))

    def _scan_directory(self, node: FileNode) -> None:
        """Scan a directory node, populating its children and sizes."""
        if self._cancel_flag.is_set():
            return

        node.scanned = True
        total_size = 0
        children: list[FileNode] = []
        dirs_to_scan: list[FileNode] = []

        try:
            with os.scandir(node.path) as entries:
                for entry in entries:
                    if self._cancel_flag.is_set():
                        return

                    try:
                        is_dir = entry.is_dir(follow_symlinks=False)
                    except OSError:
                        continue

                    child = FileNode(entry.name, entry.path, is_dir)

                    if is_dir:
                        children.append(child)
                        dirs_to_scan.append(child)
                    else:
                        try:
                            child.size = entry.stat(follow_symlinks=False).st_size
                        except OSError:
                            child.size = 0
                            child.error = "Access denied"
                        children.append(child)
                        total_size += child.size

        except PermissionError:
            node.error = "Access denied"
            node.children = children
            node.size = total_size
            self._queue.put(("progress", node.path, total_size))
            return
        except OSError as exc:
            node.error = str(exc)
            node.children = children
            node.size = total_size
            self._queue.put(("progress", node.path, total_size))
            return

        # Sort: folders first, then by size descending
        dirs = [c for c in children if c.is_dir]
        files = [c for c in children if not c.is_dir]
        dirs.sort(key=lambda c: c.name.lower())
        files.sort(key=lambda c: c.size, reverse=True)

        node.children = dirs + files
        node.size = total_size

        self._queue.put(("progress", node.path, total_size))

        # Recurse into subdirectories
        for child_dir in dirs_to_scan:
            if self._cancel_flag.is_set():
                return
            self._scan_directory(child_dir)
            if not self._cancel_flag.is_set():
                node.size += child_dir.size


# ═══════════════════════════════════════════════════════════════════════════════
# Squarified Treemap Algorithm
# ═══════════════════════════════════════════════════════════════════════════════

class TreemapRect:
    """A single rectangle in the treemap layout."""
    __slots__ = ("x", "y", "w", "h", "node")

    def __init__(self, x: float, y: float, w: float, h: float,
                 node: FileNode) -> None:
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.node = node

    def __repr__(self) -> str:
        return (f"TreemapRect(x={self.x:.1f}, y={self.y:.1f}, "
                f"w={self.w:.1f}, h={self.h:.1f}, node={self.node.name!r})")


class _NormItem:
    """Wrapper holding a FileNode with its normalized (pixel-area) size."""
    __slots__ = ("node", "norm_size")

    def __init__(self, node: FileNode, norm_size: float) -> None:
        self.node = node
        self.norm_size = norm_size


def squarify(
    items: list[FileNode],
    bounds: tuple[float, float, float, float],
) -> list[TreemapRect]:
    """
    Compute squarified treemap layout using Bruls et al.'s algorithm.

    All size calculations are done with normalized sizes (pixel area units),
    ensuring consistent aspect-ratio comparisons and pixel-perfect layout.
    """
    if not items:
        return []

    total_size = sum(it.size for it in items)
    if total_size <= 0:
        return _layout_equal(items, bounds)

    area = bounds[2] * bounds[3]
    scale = area / total_size

    # Build normalized items and sort by size descending
    norm_items = [_NormItem(it, it.size * scale) for it in items]
    norm_items.sort(key=lambda ni: ni.norm_size, reverse=True)

    result: list[TreemapRect] = []
    _squarify_recursive(norm_items, bounds, result)
    return result


def _squarify_recursive(
    items: list[_NormItem],
    bounds: tuple[float, float, float, float],
    result: list[TreemapRect],
) -> None:
    """Recursive squarified layout on normalized items."""
    if not items:
        return

    x, y, w, h = bounds

    if w <= 0 or h <= 0:
        return

    if len(items) == 1:
        result.append(TreemapRect(x, y, w, h, items[0].node))
        return

    # Orientation: lay out along the shorter side
    horizontal = w >= h

    # Greedily build a row while aspect ratio improves
    row: list[_NormItem] = [items[0]]
    row_area = items[0].norm_size

    for ni in items[1:]:
        new_area = row_area + ni.norm_size
        cur_worst = _row_worst_aspect(row, row_area, w, h, horizontal)
        new_worst = _row_worst_aspect(row + [ni], new_area, w, h, horizontal)

        if new_worst <= cur_worst:
            row.append(ni)
            row_area = new_area
        else:
            break

    # Layout the finalized row
    _layout_row(row, row_area, x, y, w, h, horizontal, result)

    # Recurse on the remaining space
    if horizontal:
        row_h = row_area / w
        remaining_bounds = (x, y + row_h, w, h - row_h)
    else:
        row_w = row_area / h
        remaining_bounds = (x + row_w, y, w - row_w, h)

    _squarify_recursive(items[len(row):], remaining_bounds, result)


def _row_worst_aspect(
    row: list[_NormItem],
    row_area: float,
    w: float,
    h: float,
    horizontal: bool,
) -> float:
    """
    Return the worst (max) aspect ratio for items in *row* laid out inside
    a rectangle of size (w × h).  All sizes are normalized pixel areas.
    Lower is better (1.0 = perfectly square).
    """
    if row_area <= 0 or w <= 0 or h <= 0 or not row:
        return float("inf")

    worst = 1.0

    if horizontal:
        # Row fills width w; height = row_area / w.
        # Each item i: width_i = (norm_i / row_area) * w, height_i = row_area / w.
        # aspect_i = max(width_i/height_i, height_i/width_i)
        #          = max(norm_i * w² / row_area²,  row_area² / (norm_i * w²))
        w2 = w * w
        ra2 = row_area * row_area
        for ni in row:
            if ni.norm_size <= 0:
                continue
            r1 = ni.norm_size * w2 / ra2
            r2 = ra2 / (ni.norm_size * w2)
            asp = r1 if r1 > r2 else r2
            if asp > worst:
                worst = asp
    else:
        # Column fills height h; width = row_area / h.
        h2 = h * h
        ra2 = row_area * row_area
        for ni in row:
            if ni.norm_size <= 0:
                continue
            r1 = ni.norm_size * h2 / ra2
            r2 = ra2 / (ni.norm_size * h2)
            asp = r1 if r1 > r2 else r2
            if asp > worst:
                worst = asp

    return worst


def _layout_row(
    row: list[_NormItem],
    row_area: float,
    x: float,
    y: float,
    w: float,
    h: float,
    horizontal: bool,
    result: list[TreemapRect],
) -> None:
    """Place the finalized row of items into the treemap."""
    if not row or row_area <= 0:
        return

    if horizontal:
        row_h = row_area / w
        cur_x = x
        for ni in row:
            item_w = (ni.norm_size / row_area) * w
            result.append(TreemapRect(cur_x, y, item_w, row_h, ni.node))
            cur_x += item_w
    else:
        row_w = row_area / h
        cur_y = y
        for ni in row:
            item_h = (ni.norm_size / row_area) * h
            result.append(TreemapRect(x, cur_y, row_w, item_h, ni.node))
            cur_y += item_h


def _layout_equal(
    items: list[FileNode],
    bounds: tuple[float, float, float, float],
) -> list[TreemapRect]:
    """Layout items equally when all sizes are zero (fallback)."""
    x, y, w, h = bounds
    n = len(items)
    if n == 0:
        return []

    cols = max(1, math.ceil(math.sqrt(n * w / h)) if h > 0 else n)
    rows = math.ceil(n / cols)
    cell_w = w / cols
    cell_h = h / rows

    result: list[TreemapRect] = []
    for i, item in enumerate(items):
        col = i % cols
        row_idx = i // cols
        rx = x + col * cell_w
        ry = y + row_idx * cell_h
        rw = cell_w if col < cols - 1 else (x + w - rx)
        rh = cell_h if row_idx < rows - 1 else (y + h - ry)
        result.append(TreemapRect(rx, ry, rw, rh, item))
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Treemap Canvas Widget
# ═══════════════════════════════════════════════════════════════════════════════

class TreemapCanvas(tk.Canvas):
    """Custom canvas that renders the treemap with futuristic styling."""

    def __init__(self, parent, **kwargs):
        bg = kwargs.pop("bg", C_BG)
        highlightthickness = kwargs.pop("highlightthickness", 0)
        super().__init__(
            parent,
            bg=bg,
            highlightthickness=highlightthickness,
            **kwargs,
        )
        self._rects: list[TreemapRect] = []
        self._canvas_rects: dict[int, tuple[TreemapRect, int]] = {}  # rect_id -> (treemap_rect, text_id)
        self._hovered_rect: Optional[TreemapRect] = None
        self._hover_rect_id: Optional[int] = None
        self._tooltip_window: Optional[tk.Toplevel] = None
        self._tooltip_label: Optional[tk.Label] = None
        self._on_click_cb: Optional[Callable[[FileNode], None]] = None
        self._on_right_click_cb: Optional[Callable[[FileNode], None]] = None

        # Bind events
        self.bind("<Motion>", self._on_mouse_move)
        self.bind("<Leave>", self._on_mouse_leave)
        self.bind("<Button-1>", self._on_left_click)
        self.bind("<Button-3>", self._on_right_click)

    def set_click_callback(self, cb: Callable[[FileNode], None]) -> None:
        self._on_click_cb = cb

    def set_right_click_callback(self, cb: Callable[[FileNode], None]) -> None:
        self._on_right_click_cb = cb

    def render(self, rects: list[TreemapRect]) -> None:
        """Render the treemap rectangles on the canvas."""
        self.delete("all")
        self._canvas_rects.clear()
        self._rects = rects

        canvas_w = self.winfo_width() or 800
        canvas_h = self.winfo_height() or 600

        for trect in rects:
            if trect.w < MIN_RECT_W or trect.h < MIN_RECT_H:
                continue

            rx, ry = trect.x, trect.y
            rw, rh = trect.w, trect.h
            node = trect.node

            # ── Determine colors ──────────────────────────────────────────
            if node.is_dir:
                cat = "folders"
            else:
                cat = node.category

            base_color, glow_color = CATEGORY_COLORS.get(
                cat, CATEGORY_COLORS["other"]
            )

            # Darken the base for a more subtle fill
            fill_color = _darken(base_color, 0.35)
            border_color = glow_color

            # ── Draw rectangle ────────────────────────────────────────────
            rect_id = self.create_rectangle(
                rx + 1, ry + 1, rx + rw - 1, ry + rh - 1,
                fill=fill_color,
                outline=border_color,
                width=1,
                tags=("trect",),
            )

            # ── Draw label if large enough ────────────────────────────────
            text_id = None
            if rw > MIN_TEXT_W and rh > MIN_TEXT_H:
                label = node.name
                size_str = fmt_size(node.size)

                # Truncate label if too long
                max_chars = max(3, int(rw / 7))
                if len(label) > max_chars:
                    label = label[:max_chars - 2] + "…"

                full_text = f"{label}\n{size_str}" if rh > 40 else label

                font_size = max(7, min(11, int(rh / 5)))
                text_id = self.create_text(
                    rx + rw / 2,
                    ry + rh / 2,
                    text=full_text,
                    fill=C_TEXT_BRIGHT,
                    font=("Segoe UI", font_size),
                    justify="center",
                    width=rw - 8,
                    tags=("tlabel",),
                )

            self._canvas_rects[rect_id] = (trect, text_id or 0)

    def _find_rect_at(self, cx: int, cy: int) -> Optional[TreemapRect]:
        """Find the treemap rectangle at canvas coordinates (cx, cy)."""
        # Search from top (last drawn = on top) for best match
        for rect_id, (trect, _) in reversed(list(self._canvas_rects.items())):
            if (trect.x <= cx <= trect.x + trect.w and
                    trect.y <= cy <= trect.y + trect.h):
                return trect
        return None

    def _on_mouse_move(self, event: tk.Event) -> None:
        """Handle mouse movement for hover effects and tooltips."""
        trect = self._find_rect_at(event.x, event.y)

        # Clear previous hover
        if self._hover_rect_id is not None:
            self.delete(self._hover_rect_id)
            self._hover_rect_id = None

        # Hide tooltip if no rect
        if trect is None:
            self._hide_tooltip()
            self._hovered_rect = None
            return

        # Draw hover highlight
        if trect.w > 5 and trect.h > 5:
            self._hover_rect_id = self.create_rectangle(
                trect.x + 1, trect.y + 1,
                trect.x + trect.w - 1, trect.y + trect.h - 1,
                outline=C_CYAN,
                width=2,
                tags=("hover",),
            )

        # Update tooltip
        if trect != self._hovered_rect:
            self._hovered_rect = trect
            self._show_tooltip(event.x_root, event.y_root, trect.node)

    def _on_mouse_leave(self, _event: tk.Event) -> None:
        """Hide tooltip and hover when mouse leaves canvas."""
        if self._hover_rect_id is not None:
            self.delete(self._hover_rect_id)
            self._hover_rect_id = None
        self._hide_tooltip()
        self._hovered_rect = None

    def _on_left_click(self, event: tk.Event) -> None:
        """Handle left click — zoom into directory."""
        trect = self._find_rect_at(event.x, event.y)
        if trect and trect.node.is_dir and self._on_click_cb:
            self._on_click_cb(trect.node)

    def _on_right_click(self, event: tk.Event) -> None:
        """Handle right click — context menu."""
        trect = self._find_rect_at(event.x, event.y)
        if trect and self._on_right_click_cb:
            self._on_right_click_cb(trect.node)

    def _show_tooltip(self, root_x: int, root_y: int, node: FileNode) -> None:
        """Show a floating tooltip with file/folder info."""
        if self._tooltip_window is not None:
            self._tooltip_window.destroy()

        tw = tk.Toplevel(self, bg=C_BORDER)
        tw.overrideredirect(True)
        tw.attributes("-topmost", True)
        tw.wm_attributes("-transparentcolor", C_BORDER)

        # Content frame
        frame = tk.Frame(tw, bg=C_SURFACE, padx=10, pady=8,
                         highlightbackground=C_CYAN,
                         highlightthickness=1)
        frame.pack()

        name_label = tk.Label(
            frame, text=node.name, fg=C_CYAN, bg=C_SURFACE,
            font=("Segoe UI", 10, "bold"), anchor="w",
        )
        name_label.pack(fill="x")

        type_str = "📁 Folder" if node.is_dir else f"📄 {node.extension or 'File'}"
        type_label = tk.Label(
            frame, text=f"{type_str}  —  {fmt_size_detailed(node.size)}",
            fg=C_TEXT, bg=C_SURFACE,
            font=("Consolas", 9), anchor="w",
        )
        type_label.pack(fill="x")

        if node.error:
            err_label = tk.Label(
                frame, text=f"⚠ {node.error}", fg=C_RED, bg=C_SURFACE,
                font=("Segoe UI", 9), anchor="w",
            )
            err_label.pack(fill="x")

        # Position tooltip near cursor
        tw.update_idletasks()
        x = root_x + 16
        y = root_y + 16
        # Keep on screen
        sw = tw.winfo_screenwidth()
        sh = tw.winfo_screenheight()
        tw_w = tw.winfo_width()
        tw_h = tw.winfo_height()
        if x + tw_w > sw:
            x = root_x - tw_w - 8
        if y + tw_h > sh:
            y = root_y - tw_h - 8
        tw.geometry(f"+{x}+{y}")

        self._tooltip_window = tw
        self._tooltip_label = name_label  # keep ref

    def _hide_tooltip(self) -> None:
        """Hide the floating tooltip."""
        if self._tooltip_window is not None:
            self._tooltip_window.destroy()
            self._tooltip_window = None
            self._tooltip_label = None


# ═══════════════════════════════════════════════════════════════════════════════
# Utility Functions
# ═══════════════════════════════════════════════════════════════════════════════

def _darken(hex_color: str, factor: float) -> str:
    """Darken a hex color by multiplying RGB by factor (0-1)."""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    r = int(r * factor)
    g = int(g * factor)
    b = int(b * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


def _lighten(hex_color: str, factor: float) -> str:
    """Lighten a hex color by interpolating toward white."""
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    r = int(r + (255 - r) * factor)
    g = int(g + (255 - g) * factor)
    b = int(b + (255 - b) * factor)
    return f"#{r:02x}{g:02x}{b:02x}"


def get_drives() -> list[str]:
    """Get available drive letters on Windows, or root on other platforms."""
    if sys.platform == "win32":
        drives = []
        for letter in string.ascii_uppercase:
            path = f"{letter}:\\"
            if os.path.exists(path):
                drives.append(path)
        return drives
    else:
        return ["/"]


def open_in_explorer(path: str) -> None:
    """Open a file or folder in the system file manager."""
    if sys.platform == "win32":
        os.startfile(os.path.normpath(path))
    elif sys.platform == "darwin":
        os.system(f'open "{path}"')
    else:
        os.system(f'xdg-open "{path}" &')


# ═══════════════════════════════════════════════════════════════════════════════
# Main Application Window
# ═══════════════════════════════════════════════════════════════════════════════

class SpaceSnifferApp:
    """Main application window."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("1200x800")
        self.root.minsize(800, 600)
        self.root.configure(bg=C_BG)

        # State
        self._scan_root: Optional[FileNode] = None
        self._current_node: Optional[FileNode] = None
        self._navigation_stack: list[FileNode] = []
        self._scanner = DiskScanner()
        self._scan_thread: Optional[threading.Thread] = None
        self._scan_queue: Optional[queue.Queue] = None
        self._scanning = False
        self._total_scanned_size = 0
        self._scan_start_time = 0.0

        # Build UI
        self._build_ui()

        # Keyboard shortcuts
        self.root.bind("<BackSpace>", lambda e: self._go_back())
        self.root.bind("<Escape>", lambda e: self._go_home())
        self.root.bind("<F5>", lambda e: self._rescan())
        self.root.bind("<Control-o>", lambda e: self._open_current())
        self.root.bind("<Configure>", self._on_resize)

        # Auto-start: scan the first available drive
        self.root.after(200, self._auto_start)

    # ── UI Construction ───────────────────────────────────────────────────

    def _build_ui(self) -> None:
        """Build the complete UI layout."""
        # ── Title bar (custom) ────────────────────────────────────────────
        self._build_title_bar()

        # ── Main content area ─────────────────────────────────────────────
        main_frame = tk.Frame(self.root, bg=C_BG)
        main_frame.pack(fill="both", expand=True, padx=2, pady=(0, 2))

        # Treemap canvas (center)
        self.canvas = TreemapCanvas(main_frame, bg=C_BG)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.set_click_callback(self._on_treemap_click)
        self.canvas.set_right_click_callback(self._on_treemap_right_click)

        # Right panel
        self._build_right_panel(main_frame)

        # ── Status bar ────────────────────────────────────────────────────
        self._build_status_bar()

    def _build_title_bar(self) -> None:
        """Build the top navigation bar."""
        title_frame = tk.Frame(self.root, bg=C_PANEL, height=44)
        title_frame.pack(fill="x", side="top")
        title_frame.pack_propagate(False)

        # App icon / title
        title_lbl = tk.Label(
            title_frame, text="◈ SPACESNIFFER",
            fg=C_CYAN, bg=C_PANEL,
            font=("Segoe UI", 13, "bold"),
        )
        title_lbl.pack(side="left", padx=(12, 20))

        # Separator
        sep = tk.Frame(title_frame, bg=C_BORDER_GLOW, width=1)
        sep.pack(side="left", fill="y", padx=2)

        # Navigation buttons
        nav_btn_style = {
            "bg": C_SURFACE, "fg": C_CYAN, "font": ("Segoe UI", 10),
            "relief": "flat", "cursor": "hand2",
            "activebackground": C_BORDER_GLOW, "activeforeground": C_CYAN,
            "bd": 0, "padx": 10, "pady": 4,
        }

        self.btn_back = tk.Button(
            title_frame, text="◀  Back", command=self._go_back,
            **nav_btn_style,
        )
        self.btn_back.pack(side="left", padx=3)

        self.btn_home = tk.Button(
            title_frame, text="⌂  Home", command=self._go_home,
            **nav_btn_style,
        )
        self.btn_home.pack(side="left", padx=3)

        self.btn_up = tk.Button(
            title_frame, text="↑  Up", command=self._go_up,
            **nav_btn_style,
        )
        self.btn_up.pack(side="left", padx=3)

        # Separator
        sep2 = tk.Frame(title_frame, bg=C_BORDER_GLOW, width=1)
        sep2.pack(side="left", fill="y", padx=6)

        # Breadcrumb / current path
        self.breadcrumb_var = tk.StringVar(value="Select a drive to begin...")
        breadcrumb_lbl = tk.Label(
            title_frame, textvariable=self.breadcrumb_var,
            fg=C_TEXT, bg=C_PANEL,
            font=("Consolas", 10), anchor="w",
        )
        breadcrumb_lbl.pack(side="left", fill="x", expand=True, padx=10)

        # Rescan button
        self.btn_rescan = tk.Button(
            title_frame, text="↻  Rescan", command=self._rescan,
            **nav_btn_style,
        )
        self.btn_rescan.pack(side="right", padx=3)

        # Open folder button
        self.btn_open = tk.Button(
            title_frame, text="📂  Open", command=self._open_current,
            **nav_btn_style,
        )
        self.btn_open.pack(side="right", padx=3)

        # Separator
        sep3 = tk.Frame(title_frame, bg=C_BORDER_GLOW, width=1)
        sep3.pack(side="right", fill="y", padx=3)

    def _build_right_panel(self, parent: tk.Frame) -> None:
        """Build the right-side info panel."""
        panel = tk.Frame(parent, bg=C_PANEL, width=240)
        panel.pack(side="right", fill="y")
        panel.pack_propagate(False)

        # ── Drive selector ────────────────────────────────────────────────
        drive_section = tk.Frame(panel, bg=C_PANEL)
        drive_section.pack(fill="x", padx=10, pady=(12, 8))

        tk.Label(
            drive_section, text="▸ SELECT DRIVE",
            fg=C_TEXT_DIM, bg=C_PANEL,
            font=("Segoe UI", 8, "bold"),
        ).pack(anchor="w")

        drives = get_drives()
        self.drive_var = tk.StringVar(value=drives[0] if drives else "C:\\")
        drive_combo = ttk.Combobox(
            drive_section, textvariable=self.drive_var,
            values=drives, state="readonly",
            font=("Consolas", 10),
        )
        drive_combo.pack(fill="x", pady=(4, 0))

        scan_btn = tk.Button(
            drive_section, text="◆  SCAN DRIVE",
            command=self._scan_drive,
            bg=C_CYAN, fg="#000000",
            font=("Segoe UI", 10, "bold"),
            relief="flat", cursor="hand2",
            activebackground=_lighten(C_CYAN, 0.3),
            activeforeground="#000000",
            bd=0, padx=12, pady=6,
        )
        scan_btn.pack(fill="x", pady=(8, 0))

        # Or browse folder
        browse_btn = tk.Button(
            drive_section, text="📁  Browse Folder...",
            command=self._browse_folder,
            bg=C_SURFACE, fg=C_TEXT,
            font=("Segoe UI", 9),
            relief="flat", cursor="hand2",
            activebackground=C_BORDER_GLOW,
            activeforeground=C_CYAN,
            bd=0, padx=8, pady=4,
        )
        browse_btn.pack(fill="x", pady=(4, 0))

        # ── Separator ─────────────────────────────────────────────────────
        tk.Frame(panel, bg=C_BORDER, height=1).pack(fill="x", padx=10, pady=10)

        # ── Current info ──────────────────────────────────────────────────
        info_section = tk.Frame(panel, bg=C_PANEL)
        info_section.pack(fill="x", padx=10, pady=(0, 8))

        tk.Label(
            info_section, text="▸ CURRENT VIEW",
            fg=C_TEXT_DIM, bg=C_PANEL,
            font=("Segoe UI", 8, "bold"),
        ).pack(anchor="w")

        self.info_name_var = tk.StringVar(value="—")
        self.info_size_var = tk.StringVar(value="—")
        self.info_items_var = tk.StringVar(value="—")

        for label_text, var in [
            ("Path:", self.info_name_var),
            ("Size:", self.info_size_var),
            ("Items:", self.info_items_var),
        ]:
            row = tk.Frame(info_section, bg=C_PANEL)
            row.pack(fill="x", pady=1)
            tk.Label(
                row, text=label_text, fg=C_TEXT_DIM, bg=C_PANEL,
                font=("Consolas", 9), width=6, anchor="w",
            ).pack(side="left")
            tk.Label(
                row, textvariable=var, fg=C_TEXT_BRIGHT, bg=C_PANEL,
                font=("Consolas", 9), anchor="w", wraplength=150,
            ).pack(side="left", fill="x", expand=True)

        # ── Separator ─────────────────────────────────────────────────────
        tk.Frame(panel, bg=C_BORDER, height=1).pack(fill="x", padx=10, pady=10)

        # ── Legend ────────────────────────────────────────────────────────
        legend_section = tk.Frame(panel, bg=C_PANEL)
        legend_section.pack(fill="x", padx=10, pady=(0, 8))

        tk.Label(
            legend_section, text="▸ FILE TYPES",
            fg=C_TEXT_DIM, bg=C_PANEL,
            font=("Segoe UI", 8, "bold"),
        ).pack(anchor="w", pady=(0, 4))

        legend_items = [
            ("📁 Folders",    CATEGORY_COLORS["folders"][1]),
            ("🖹 Documents",  CATEGORY_COLORS["documents"][1]),
            ("🖼 Images",     CATEGORY_COLORS["images"][1]),
            ("🎬 Videos",     CATEGORY_COLORS["videos"][1]),
            ("🎵 Audio",      CATEGORY_COLORS["audio"][1]),
            ("📦 Archives",   CATEGORY_COLORS["archives"][1]),
            ("⌨ Code",        CATEGORY_COLORS["code"][1]),
            ("⚙ System",     CATEGORY_COLORS["system"][1]),
            ("··· Other",     CATEGORY_COLORS["other"][1]),
        ]

        for name, color in legend_items:
            item_row = tk.Frame(legend_section, bg=C_PANEL)
            item_row.pack(fill="x", pady=1)
            swatch = tk.Frame(item_row, bg=color, width=12, height=12)
            swatch.pack(side="left", padx=(0, 6))
            swatch.pack_propagate(False)
            tk.Label(
                item_row, text=name, fg=C_TEXT, bg=C_PANEL,
                font=("Segoe UI", 9), anchor="w",
            ).pack(side="left")

    def _build_status_bar(self) -> None:
        """Build the bottom status bar."""
        status_frame = tk.Frame(self.root, bg=C_PANEL, height=28)
        status_frame.pack(fill="x", side="bottom")
        status_frame.pack_propagate(False)

        self.status_var = tk.StringVar(value="Ready. Select a drive and click SCAN.")
        status_lbl = tk.Label(
            status_frame, textvariable=self.status_var,
            fg=C_TEXT_DIM, bg=C_PANEL,
            font=("Segoe UI", 9), anchor="w",
        )
        status_lbl.pack(side="left", fill="x", expand=True, padx=12)

        # Progress bar (hidden by default)
        self.progress = ttk.Progressbar(
            status_frame, mode="indeterminate", length=160,
        )

        self.scan_time_var = tk.StringVar(value="")
        tk.Label(
            status_frame, textvariable=self.scan_time_var,
            fg=C_TEXT_DIM, bg=C_PANEL,
            font=("Consolas", 9),
        ).pack(side="right", padx=12)

    # ── Scanning ──────────────────────────────────────────────────────────

    def _auto_start(self) -> None:
        """Auto-scan the first available drive on startup."""
        drives = get_drives()
        if drives:
            self.drive_var.set(drives[0])
            self._scan_path(drives[0])

    def _scan_drive(self) -> None:
        """Start scanning the selected drive."""
        drive = self.drive_var.get()
        if drive:
            self._scan_path(drive)

    def _browse_folder(self) -> None:
        """Open folder browser dialog and scan selected folder."""
        path = filedialog.askdirectory(title="Select Folder to Scan")
        if path:
            self.drive_var.set(path)
            self._scan_path(path)

    def _scan_path(self, path: str) -> None:
        """Initiate scan of the given path."""
        if self._scanning:
            self._scanner.cancel()
            self._wait_for_scan_stop()

        self._scanning = True
        self._total_scanned_size = 0
        self._scan_start_time = time.time()

        self.status_var.set(f"Scanning: {path}")
        self.breadcrumb_var.set(f"🔍 Scanning {path} ...")
        self.progress.pack(side="right", padx=8)
        self.progress.start(10)

        self._scan_root = None
        self._current_node = None
        self._navigation_stack.clear()

        self._scan_queue, self._scan_thread = self._scanner.scan(path)
        self.root.after(80, self._poll_scan)

    def _poll_scan(self) -> None:
        """Poll scan progress from the background thread."""
        if self._scan_queue is None:
            return

        try:
            while True:
                msg_type, data, extra = self._scan_queue.get_nowait()

                if msg_type == "start":
                    pass

                elif msg_type == "progress":
                    self._total_scanned_size += extra if extra else 0
                    elapsed = time.time() - self._scan_start_time
                    self.scan_time_var.set(
                        f"Scanned: {fmt_size(self._total_scanned_size)}  |  "
                        f"{elapsed:.1f}s"
                    )

                elif msg_type == "done":
                    self._scan_root = data
                    self._current_node = data
                    self._scanning = False
                    self.progress.stop()
                    self.progress.pack_forget()
                    self._on_scan_complete(data)

                elif msg_type == "error":
                    self._scanning = False
                    self.progress.stop()
                    self.progress.pack_forget()
                    messagebox.showerror("Scan Error", f"Failed to scan:\n{data}")
                    self.status_var.set("Scan failed.")
                    self.scan_time_var.set("")

        except queue.Empty:
            pass

        if self._scanning:
            self.root.after(80, self._poll_scan)

    def _wait_for_scan_stop(self) -> None:
        """Wait for the scan thread to finish."""
        if self._scan_thread and self._scan_thread.is_alive():
            self._scan_thread.join(timeout=2.0)
        self._scanning = False

    def _on_scan_complete(self, root: FileNode) -> None:
        """Called when scanning is complete."""
        elapsed = time.time() - self._scan_start_time
        total_items = self._count_items(root)
        self.status_var.set(
            f"Scan complete: {fmt_size(root.size)} in {total_items:,} items "
            f"({elapsed:.1f}s)"
        )
        self.scan_time_var.set(
            f"Total: {fmt_size(root.size)}  |  {total_items:,} items  |  {elapsed:.1f}s"
        )
        self.breadcrumb_var.set(root.path)
        self._update_info_panel(root)
        self._render_treemap(root)

    def _count_items(self, node: FileNode) -> int:
        """Recursively count all items in the tree."""
        count = len(node.children)
        for child in node.children:
            if child.is_dir:
                count += self._count_items(child)
        return count

    # ── Treemap Rendering ─────────────────────────────────────────────────

    # Maximum number of individual items to show before grouping the smallest
    MAX_VISIBLE_ITEMS = 400

    def _render_treemap(self, node: FileNode) -> None:
        """Render the treemap for a given node's children."""
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()

        if canvas_w < 50:
            canvas_w = 800
        if canvas_h < 50:
            canvas_h = 600

        if not node.children:
            self.canvas.delete("all")
            self.canvas._canvas_rects.clear()
            # Show empty state
            self.canvas.create_text(
                canvas_w / 2, canvas_h / 2,
                text="📂  Empty Directory",
                fill=C_TEXT_DIM,
                font=("Segoe UI", 16),
                justify="center",
            )
            if node.error:
                self.canvas.create_text(
                    canvas_w / 2, canvas_h / 2 + 30,
                    text=f"⚠ {node.error}",
                    fill=C_RED,
                    font=("Segoe UI", 11),
                    justify="center",
                )
            return

        # Filter out zero-size items for the treemap
        items = [c for c in node.children if c.size > 0]
        zero_items = [c for c in node.children if c.size == 0]

        if not items and not zero_items:
            return

        # ── Performance: group smallest items if too many ─────────────────
        if len(items) > self.MAX_VISIBLE_ITEMS:
            # Sort by size descending (already sorted, but ensure)
            items.sort(key=lambda c: c.size, reverse=True)
            visible = items[:self.MAX_VISIBLE_ITEMS]
            rest = items[self.MAX_VISIBLE_ITEMS:]

            # Create a synthetic "… others" node for the grouped small files
            rest_size = sum(c.size for c in rest)
            rest_dirs = sum(1 for c in rest if c.is_dir)
            rest_files = sum(1 for c in rest if not c.is_dir)

            others_node = FileNode(
                f"… {len(rest)} more items ({rest_dirs} dirs, {rest_files} files)",
                "",
                False,
            )
            others_node.size = rest_size
            others_node.category = "other"
            visible.append(others_node)
            items = visible

        margin = 4
        bounds = (margin, margin, canvas_w - 2 * margin, canvas_h - 2 * margin)

        rects = squarify(items, bounds)

        # Handle zero-size items by placing them at the bottom as tiny rects
        if zero_items and rects:
            # Cap zero-size items to avoid clutter
            show_zeros = zero_items[:50]
            if len(zero_items) > 50:
                z_others = FileNode(
                    f"… {len(zero_items) - 50} more empty items", "", False,
                )
                z_others.size = 0
                z_others.category = "other"
                show_zeros.append(z_others)

            # Find the bottom of the last treemap rect
            max_y = max(r.y + r.h for r in rects)
            remaining_h = bounds[1] + bounds[3] - max_y
            if remaining_h > 20:
                cols = max(1, int(bounds[2] / 30))
                for i, zitem in enumerate(show_zeros):
                    col = i % cols
                    row_idx = i // cols
                    rx = bounds[0] + col * (bounds[2] / cols)
                    ry = max_y + row_idx * 16 + 2
                    rects.append(TreemapRect(
                        rx, ry,
                        bounds[2] / cols - 2, 14,
                        zitem,
                    ))

        self.canvas.render(rects)

    # ── Navigation ────────────────────────────────────────────────────────

    def _on_treemap_click(self, node: FileNode) -> None:
        """Handle clicking on a directory in the treemap."""
        if node.is_dir and node.scanned:
            self._navigation_stack.append(node)
            self._current_node = node
            self.breadcrumb_var.set(node.path)
            self._update_info_panel(node)
            self._render_treemap(node)
            self.status_var.set(
                f"Viewing: {node.name}  —  {fmt_size(node.size)}  |  "
                f"{len(node.children)} items"
            )

    def _on_treemap_right_click(self, node: FileNode) -> None:
        """Handle right-click — open in Explorer."""
        open_in_explorer(node.path)

    def _go_back(self) -> None:
        """Navigate back in history."""
        if self._navigation_stack:
            prev = self._navigation_stack.pop()
            if self._navigation_stack:
                self._current_node = self._navigation_stack[-1]
            else:
                self._current_node = self._scan_root
            if self._current_node:
                self.breadcrumb_var.set(self._current_node.path)
                self._update_info_panel(self._current_node)
                self._render_treemap(self._current_node)

    def _go_home(self) -> None:
        """Navigate to the scan root."""
        if self._scan_root:
            self._navigation_stack.clear()
            self._current_node = self._scan_root
            self.breadcrumb_var.set(self._scan_root.path)
            self._update_info_panel(self._scan_root)
            self._render_treemap(self._scan_root)
            self.status_var.set("Returned to root.")

    def _go_up(self) -> None:
        """Navigate to parent directory (by re-scanning parent)."""
        if self._current_node:
            parent_path = os.path.dirname(self._current_node.path)
            if parent_path and parent_path != self._current_node.path:
                self._scan_path(parent_path)

    def _rescan(self) -> None:
        """Rescan the current scan root."""
        if self._scan_root:
            self._scan_path(self._scan_root.path)
        elif self.drive_var.get():
            self._scan_path(self.drive_var.get())

    def _open_current(self) -> None:
        """Open the current directory in Explorer."""
        if self._current_node:
            open_in_explorer(self._current_node.path)

    # ── Info Panel Updates ────────────────────────────────────────────────

    def _update_info_panel(self, node: FileNode) -> None:
        """Update the right panel info for the given node."""
        self.info_name_var.set(node.path)
        self.info_size_var.set(fmt_size_detailed(node.size))

        if node.scanned and node.children:
            dirs = sum(1 for c in node.children if c.is_dir)
            files = sum(1 for c in node.children if not c.is_dir)
            self.info_items_var.set(f"{dirs} dirs, {files} files")
        else:
            self.info_items_var.set("—")

    # ── Resize Handling ───────────────────────────────────────────────────

    def _on_resize(self, event: tk.Event) -> None:
        """Re-render treemap on window resize (debounced)."""
        if not self._scanning and self._current_node:
            # Debounce: only re-render if resize has settled
            if hasattr(self, "_resize_after_id"):
                self.root.after_cancel(self._resize_after_id)
            self._resize_after_id = self.root.after(
                150, lambda: self._render_treemap(self._current_node) if self._current_node else None
            )

    # ── Run ───────────────────────────────────────────────────────────────

    def run(self) -> None:
        """Start the application main loop."""
        # Set dark title bar on Windows 10+
        if sys.platform == "win32":
            try:
                self.root.update()
                # Use DWM dark mode (Windows 10 20H1+)
                DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    DWMWA_USE_IMMERSIVE_DARK_MODE,
                    ctypes.byref(ctypes.c_int(1)),
                    ctypes.sizeof(ctypes.c_int),
                )
            except Exception:
                pass  # Dark title bar not supported on this Windows version

        self.root.mainloop()


# ═══════════════════════════════════════════════════════════════════════════════
# Entry Point
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    """Application entry point."""
    # Handle high-DPI displays on Windows
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # Per-monitor DPI
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

    app = SpaceSnifferApp()
    app.run()


if __name__ == "__main__":
    main()

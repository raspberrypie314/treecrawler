#!/usr/bin/env python3
"""
Crawl URL dengan wget --spider, lalu tampilkan struktur tree yang rapi.
Tidak mengunduh file apa pun.

Usage:
    python3 tree_crawler.py https://siskerma.unibi.ac.id/
    python3 tree_crawler.py https://siskerma.unibi.ac.id/ -L 3
    python3 tree_crawler.py https://siskerma.unibi.ac.id/ -L 3 -o hasil
"""

import argparse
import os
import re
import subprocess
import sys
from collections import defaultdict
from urllib.parse import urlparse

# ---------- Warna ANSI ----------
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    WHITE   = "\033[37m"
    GRAY    = "\033[90m"

    @staticmethod
    def enabled() -> bool:
        return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None

def colorize(text: str, color: str) -> str:
    if not C.enabled():
        return text
    return f"{color}{text}{C.RESET}"


# ---------- Path Cache & Result ----------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR  = os.path.join(SCRIPT_DIR, "Cache")
RESULT_DIR = os.path.join(SCRIPT_DIR, "Result")

def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


# ---------- Crawl ----------
def run_wget_spider(url: str, max_level: int | None = None) -> str:
    cache_dir = ensure_dir(CACHE_DIR)
    cmd = [
        "wget", "--spider", "-r",
        "-np", "-nH", "--cut-dirs=3",
        "-R", "index.html*",
        "--no-check-certificate",
        "--timeout=10", "--tries=1",
        "--no-hsts",
        "--no-cookies",
        "-e", "robots=off",
        "--directory-prefix", cache_dir,
    ]
    if max_level is not None:
        cmd += ["-l", str(max_level)]
    cmd.append(url)

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=300,
            cwd=cache_dir,
        )
        return proc.stdout
    except subprocess.TimeoutExpired:
        print(colorize("[!] wget timeout setelah 300 detik.", C.RED), file=sys.stderr)
        return ""
    except FileNotFoundError:
        print(colorize("[!] wget tidak ditemukan. Install dulu: sudo apt install wget", C.RED), file=sys.stderr)
        sys.exit(1)


def extract_paths(log: str, base_netloc: str) -> list[str]:
    pattern = re.compile(r'https?://([^\s/]+)(/[^\s]*)')
    paths = set()
    for m in pattern.finditer(log):
        netloc, path = m.group(1), m.group(2)
        if netloc != base_netloc:
            continue
        path = path.split("?")[0]
        if path == "":
            path = "/"
        paths.add(path)
    return sorted(paths)


# ---------- Tree builder ----------
def build_tree(paths: list[str]) -> dict:
    tree = defaultdict(dict)
    for p in paths:
        parts = [x for x in p.split("/") if x]
        node = tree
        for part in parts:
            node = node.setdefault(part, {})
    return tree


def render_tree(tree: dict, prefix: str = "", level: int = 1,
                max_level: int | None = None) -> list[str]:
    lines = []
    items = sorted(tree.items(), key=lambda kv: (not kv[1], kv[0]))
    for i, (name, child) in enumerate(items):
        is_last = (i == len(items) - 1)
        connector = "└── " if is_last else "├── "

        if child:
            label = colorize(name + "/", C.BLUE + C.BOLD)
        else:
            ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
            if ext in ("css",):
                label = colorize(name, C.MAGENTA)
            elif ext in ("js",):
                label = colorize(name, C.YELLOW)
            elif ext in ("png", "jpg", "jpeg", "gif", "svg", "webp", "ico"):
                label = colorize(name, C.CYAN)
            elif ext in ("txt", "md", "log"):
                label = colorize(name, C.WHITE + C.DIM)
            else:
                label = colorize(name, C.WHITE)

        line = colorize(prefix + connector, C.GRAY) + label
        lines.append(line)

        if child and (max_level is None or level < max_level):
            extension = "    " if is_last else "│   "
            lines.extend(render_tree(child, prefix + extension,
                                     level + 1, max_level))
        elif child:
            extension = "    " if is_last else "│   "
            lines.append(
                colorize(prefix + extension + "└── ", C.GRAY)
                + colorize("... (dipotong, level > %d)" % max_level, C.GRAY + C.DIM)
            )
    return lines


# ---------- Main ----------
def ask_save() -> tuple[bool, str]:
    """Tanya user apakah ingin menyimpan ke txt, dan minta nama file."""
    if not sys.stdin.isatty():
        return False, ""
    try:
        ans = input(colorize("Simpan hasil ke file .txt? [y/N]: ", C.GREEN)).strip().lower()
    except EOFError:
        return False, ""
    if ans not in ("y", "ya", "yes"):
        return False, ""
    name = input(colorize("Nama file (tanpa .txt): ", C.GREEN)).strip()
    if not name:
        name = "tree"
    if not name.endswith(".txt"):
        name += ".txt"
    return True, name


def main():
    parser = argparse.ArgumentParser(
        description="Crawl URL dan tampilkan tree tanpa mengunduh file.")
    parser.add_argument("url", help="URL target, contoh: https://siskerma.unibi.ac.id/")
    parser.add_argument("-L", "--level", type=int, default=None,
                        help="Batas kedalaman tree (mirip 'tree -L N')")
    parser.add_argument("-o", "--output", default=None,
                        help="Simpan hasil ke file .txt (opsional)")
    args = parser.parse_args()

    if args.level is not None and args.level < 1:
        print(colorize("[!] -L harus >= 1", C.RED), file=sys.stderr)
        sys.exit(1)

    parsed = urlparse(args.url)
    base_netloc = parsed.netloc

    print(colorize(f"[*] Crawling (spider mode): {args.url}", C.CYAN), file=sys.stderr)
    if args.level:
        print(colorize(f"[*] Batas level: {args.level}", C.CYAN), file=sys.stderr)

    log = run_wget_spider(args.url, args.level)
    if not log:
        print(colorize("[!] Log wget kosong. Cek koneksi atau URL.", C.RED), file=sys.stderr)
        sys.exit(1)

    paths = extract_paths(log, base_netloc)
    if not paths:
        print(colorize("[!] Tidak ada path ditemukan. Mungkin halaman login / butuh auth.", C.RED),
              file=sys.stderr)
        sys.exit(1)

    tree = build_tree(paths)

    root_name = parsed.path.strip("/") or base_netloc
    header = colorize(root_name + "/", C.YELLOW + C.BOLD)

    def render_plain(tree, prefix="", level=1):
        out = []
        items = sorted(tree.items(), key=lambda kv: (not kv[1], kv[0]))
        for i, (name, child) in enumerate(items):
            is_last = (i == len(items) - 1)
            connector = "└── " if is_last else "├── "
            suffix = "/" if child else ""
            out.append(f"{prefix}{connector}{name}{suffix}")
            if child and (args.level is None or level < args.level):
                extension = "    " if is_last else "│   "
                out.extend(render_plain(child, prefix + extension, level + 1))
            elif child:
                extension = "    " if is_last else "│   "
                out.append(f"{prefix}{extension}└── ... (dipotong, level > {args.level})")
        return out

    display_lines = [header] + render_tree(tree, level=1, max_level=args.level)
    plain_lines   = [root_name + "/"] + render_plain(tree, level=1)

    print("\n".join(display_lines))

    n_dirs = sum(1 for p in paths if not re.search(r'\.[a-zA-Z0-9]+$', p))
    n_files = len(paths) - n_dirs
    print()
    print(colorize(f"[*] {len(paths)} path", C.GREEN)
          + colorize(f" ({n_dirs} direktori, {n_files} file)", C.GRAY))

    save = False
    outfile = ""
    if args.output:
        save = True
        outfile = args.output
    else:
        save, outfile = ask_save()

    if save:
        if not outfile.lower().endswith(".txt"):
            outfile += ".txt"
        if not os.path.isabs(outfile) and os.path.dirname(outfile) == "":
            outfile = os.path.join(ensure_dir(RESULT_DIR), outfile)

        os.makedirs(os.path.dirname(os.path.abspath(outfile)), exist_ok=True)
        with open(outfile, "w", encoding="utf-8") as f:
            f.write("\n".join(plain_lines) + "\n")
        print(colorize(f"[*] Disimpan ke: {outfile}", C.GREEN))
    else:
        print(colorize("[*] Tidak disimpan (hanya ditampilkan).", C.GRAY))


if __name__ == "__main__":
    main()

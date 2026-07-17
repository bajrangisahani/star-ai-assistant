import csv
import json
import os
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_ROOTS = [
    Path.home() / "Desktop",
    Path.home() / "Downloads",
    Path.home() / "Documents",
    BASE_DIR,
]
EXCLUDED_DIRS = {".git", ".agents", "__pycache__", "venv", ".venv", "node_modules"}
TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".html",
    ".css",
    ".json",
    ".csv",
    ".log",
    ".env",
    ".yaml",
    ".yml",
}


def resolve_path(path_text=None):
    if not path_text:
        return BASE_DIR

    cleaned = str(path_text).strip().strip('"').strip("'")
    aliases = {
        "desktop": Path.home() / "Desktop",
        "downloads": Path.home() / "Downloads",
        "documents": Path.home() / "Documents",
        "workspace": BASE_DIR,
        "project": BASE_DIR,
    }

    lowered = cleaned.lower()
    if lowered in aliases:
        return aliases[lowered]

    path = Path(cleaned).expanduser()
    if not path.is_absolute():
        path = BASE_DIR / path
    return path.resolve()


def safe_walk(root):
    for current, dirs, files in os.walk(root):
        dirs[:] = [item for item in dirs if item not in EXCLUDED_DIRS]
        yield Path(current), dirs, files


def search_files(query, folder=None, limit=20):
    needle = query.lower().strip()
    if not needle:
        return []

    roots = [resolve_path(folder)] if folder else [root for root in DEFAULT_ROOTS if root.exists()]
    matches = []

    for root in roots:
        if not root.exists():
            continue

        if root.is_file():
            candidates = [(root.parent, [], [root.name])]
        else:
            candidates = safe_walk(root)

        for current, _dirs, files in candidates:
            for file_name in files:
                path = current / file_name
                if needle in file_name.lower():
                    matches.append(file_info(path))
                    if len(matches) >= int(limit):
                        return matches

    return matches


def file_info(path):
    path = Path(path)
    try:
        stat = path.stat()
        size = stat.st_size
        modified = stat.st_mtime
    except OSError:
        size = None
        modified = None

    return {
        "name": path.name,
        "path": str(path),
        "extension": path.suffix.lower(),
        "size_bytes": size,
        "modified": modified,
        "is_dir": path.is_dir(),
    }


def analyze_folder(path_text=None, limit=12):
    root = resolve_path(path_text)
    if not root.exists():
        return {"error": f"{root} does not exist."}

    if root.is_file():
        return {"file": file_info(root)}

    total_files = 0
    total_dirs = 0
    total_size = 0
    extensions = Counter()
    largest = []

    for current, dirs, files in safe_walk(root):
        total_dirs += len(dirs)
        for file_name in files:
            path = current / file_name
            try:
                size = path.stat().st_size
            except OSError:
                continue

            total_files += 1
            total_size += size
            extensions[path.suffix.lower() or "[no extension]"] += 1
            largest.append((size, path))

    largest.sort(reverse=True, key=lambda item: item[0])

    return {
        "path": str(root),
        "total_files": total_files,
        "total_dirs": total_dirs,
        "total_size_mb": round(total_size / (1024 ** 2), 2),
        "top_extensions": dict(extensions.most_common(int(limit))),
        "largest_files": [file_info(path) for _, path in largest[: int(limit)]],
    }


def read_file(path_text, max_chars=12000):
    path = resolve_path(path_text)
    if not path.exists():
        return {"error": f"{path} does not exist."}

    if path.is_dir():
        return {"error": f"{path} is a folder. Use folder analysis instead."}

    suffix = path.suffix.lower()
    try:
        if suffix == ".csv":
            text = read_csv_preview(path)
        elif suffix == ".json":
            text = read_json_preview(path)
        elif suffix in TEXT_EXTENSIONS:
            text = read_text_file(path)
        elif suffix == ".docx":
            text = read_docx(path)
        elif suffix == ".pdf":
            text = read_pdf(path)
        else:
            return {"error": f"{suffix or 'This file type'} is not supported for reading yet."}
    except Exception as exc:
        return {"error": f"Could not read file: {exc}"}

    return {
        "path": str(path),
        "text": text[: int(max_chars)],
        "truncated": len(text) > int(max_chars),
        "chars": len(text),
    }


def read_text_file(path):
    for encoding in ("utf-8", "utf-8-sig", "cp1252"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(errors="replace")


def read_csv_preview(path, rows=20):
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.reader(file)
        preview = []
        for index, row in enumerate(reader):
            if index >= rows:
                break
            preview.append(", ".join(row))
    return "\n".join(preview)


def read_json_preview(path):
    data = json.loads(read_text_file(path))
    return json.dumps(data, indent=2, ensure_ascii=False)


def read_docx(path):
    with zipfile.ZipFile(path) as docx:
        xml = docx.read("word/document.xml")

    root = ElementTree.fromstring(xml)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []

    for paragraph in root.findall(".//w:p", ns):
        pieces = [node.text for node in paragraph.findall(".//w:t", ns) if node.text]
        if pieces:
            paragraphs.append("".join(pieces))

    return "\n".join(paragraphs)


def read_pdf(path):
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            from PyPDF2 import PdfReader
        except ImportError as exc:
            raise RuntimeError("PDF reading needs pypdf or PyPDF2 installed.") from exc

    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages[:20]:
        pages.append(page.extract_text() or "")
    return "\n".join(pages)


def summarize_text(text, max_sentences=5):
    clean = " ".join(str(text).split())
    if len(clean) <= 700:
        return clean

    sentences = split_sentences(clean)
    if not sentences:
        return clean[:700]

    words = [clean_word(word) for word in clean.split()]
    stop_words = {
        "the", "is", "are", "a", "an", "and", "or", "to", "of", "in", "for", "on",
        "with", "this", "that", "it", "as", "by", "from", "be", "was", "were",
    }
    scores = Counter(word for word in words if len(word) > 3 and word not in stop_words)
    ranked = []

    for index, sentence in enumerate(sentences):
        score = sum(scores[clean_word(word)] for word in sentence.split())
        ranked.append((score, index, sentence))

    picked = sorted(ranked, reverse=True)[: int(max_sentences)]
    picked.sort(key=lambda item: item[1])
    return " ".join(item[2] for item in picked)


def split_sentences(text):
    normalized = text.replace("?", ".").replace("!", ".")
    return [sentence.strip() + "." for sentence in normalized.split(".") if sentence.strip()]


def clean_word(word):
    return word.strip(".,!?;:()[]{}\"'").lower()

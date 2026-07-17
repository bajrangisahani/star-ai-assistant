import ast
import subprocess
import sys
from collections import Counter
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
EXCLUDED_DIRS = {".git", ".agents", "__pycache__", "venv", ".venv", "node_modules"}
CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".html",
    ".css",
    ".json",
    ".md",
    ".yml",
    ".yaml",
    ".toml",
}


def resolve_path(path_text=None):
    if not path_text:
        return BASE_DIR

    path = Path(str(path_text).strip().strip('"').strip("'")).expanduser()
    if not path.is_absolute():
        path = BASE_DIR / path
    return path.resolve()


def iter_project_files(root=None):
    root_path = resolve_path(root)
    if root_path.is_file():
        yield root_path
        return

    for path in root_path.rglob("*"):
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in CODE_EXTENSIONS:
            yield path


def analyze_project(root=None, limit=15):
    root_path = resolve_path(root)
    files = list(iter_project_files(root_path))
    extensions = Counter(path.suffix.lower() or "[no extension]" for path in files)
    largest = sorted(files, key=lambda item: item.stat().st_size if item.exists() else 0, reverse=True)[: int(limit)]

    return {
        "root": str(root_path),
        "file_count": len(files),
        "extensions": dict(extensions.most_common()),
        "largest_files": [
            {
                "path": str(path),
                "size_bytes": path.stat().st_size,
            }
            for path in largest
        ],
    }


def search_code(query, root=None, limit=20):
    needle = str(query).lower().strip()
    if not needle:
        return []

    matches = []
    for path in iter_project_files(root):
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue

        for number, line in enumerate(lines, start=1):
            if needle in line.lower():
                matches.append({"path": str(path), "line": number, "text": line.strip()[:240]})
                if len(matches) >= int(limit):
                    return matches

    return matches


def explain_file(path_text, max_chars=4000):
    path = resolve_path(path_text)
    if not path.exists():
        return {"error": f"{path} does not exist."}
    if path.is_dir():
        return {"error": f"{path} is a folder."}

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {"error": str(exc)}

    if path.suffix.lower() == ".py":
        py_summary = summarize_python(text)
    else:
        py_summary = None

    return {
        "path": str(path),
        "language": path.suffix.lower().lstrip(".") or "text",
        "chars": len(text),
        "preview": text[: int(max_chars)],
        "python_summary": py_summary,
    }


def summarize_python(text):
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return {"syntax_error": f"line {exc.lineno}: {exc.msg}"}

    imports = []
    classes = []
    functions = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node.name)

    return {
        "imports": sorted(set(item for item in imports if item))[:25],
        "classes": classes[:25],
        "functions": functions[:40],
    }


def review_python_file(path_text):
    path = resolve_path(path_text)
    if not path.exists():
        return {"error": f"{path} does not exist."}

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(text)
    except SyntaxError as exc:
        return {
            "path": str(path),
            "findings": [
                {
                    "severity": "error",
                    "line": exc.lineno,
                    "message": f"Syntax error: {exc.msg}",
                }
            ],
        }
    except OSError as exc:
        return {"error": str(exc)}

    findings = []
    lines = text.splitlines()
    for index, line in enumerate(lines, start=1):
        if len(line) > 120:
            findings.append({"severity": "info", "line": index, "message": "Line is longer than 120 characters."})
        if "except:" in line:
            findings.append({"severity": "warning", "line": index, "message": "Bare except can hide real errors."})
        if "shell=True" in line:
            findings.append({"severity": "warning", "line": index, "message": "shell=True should be handled carefully."})

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and len(node.body) > 60:
            findings.append(
                {
                    "severity": "info",
                    "line": node.lineno,
                    "message": f"Function {node.name} is long; consider splitting later.",
                }
            )

    return {"path": str(path), "findings": findings[:50]}


def compile_python(files=None):
    targets = [resolve_path(item) for item in files] if files else [path for path in BASE_DIR.glob("*.py")]
    command = [sys.executable, "-m", "py_compile", *[str(path) for path in targets]]
    result = subprocess.run(command, capture_output=True, text=True, cwd=str(BASE_DIR))
    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "files": [str(path) for path in targets],
    }


def format_project_summary(summary):
    extensions = ", ".join(f"{key}: {value}" for key, value in summary["extensions"].items())
    return f"Project has {summary['file_count']} code/doc files. Extensions: {extensions}."


def format_findings(review):
    if review.get("error"):
        return review["error"]

    findings = review.get("findings", [])
    if not findings:
        return "No obvious issues found."

    parts = [f"{item['severity']} line {item['line']}: {item['message']}" for item in findings[:6]]
    return "Findings: " + " ".join(parts)

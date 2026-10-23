"""Conservative, read-only M0 diagnostics for user-supplied exam media."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import zipfile
from pathlib import Path
from xml.etree import ElementTree

FORMATS = {".pdf": "pdf", ".docx": "docx", ".png": "image", ".jpg": "image", ".jpeg": "image", ".mp3": "audio"}


def sniff(path: Path) -> str | None:
    with path.open("rb") as stream:
        head = stream.read(16)
    if head.startswith(b"%PDF-"):
        return "pdf"
    if head.startswith(b"\x89PNG\r\n\x1a\n") or head.startswith(b"\xff\xd8\xff"):
        return "image"
    if head.startswith(b"ID3") or (len(head) > 1 and head[0] == 255 and head[1] & 0xE0 == 0xE0):
        return "audio"
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            if "word/document.xml" in archive.namelist():
                return "docx"
    return None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_file(path: Path) -> dict:
    path = path.resolve()
    result = {"path": str(path), "size": path.stat().st_size, "sha256": sha256(path), "format": None,
              "status": "needs_review", "details": []}
    expected = FORMATS.get(path.suffix.lower())
    actual = sniff(path)
    result["format"] = actual
    if not expected or actual != expected:
        result["status"] = "invalid"
        result["details"].append("扩展名不受支持或文件内容与扩展名不一致")
        return result
    try:
        if actual == "docx":
            with zipfile.ZipFile(path) as archive:
                root = ElementTree.fromstring(archive.read("word/document.xml"))
                text = "".join(node.text or "" for node in root.iter() if node.tag.endswith("}t"))
            result["text_characters"] = len(text)
        elif actual == "pdf":
            try:
                from pypdf import PdfReader
                from pypdf.errors import PdfReadError
            except ImportError:
                result["details"].append("未安装 pypdf，PDF 内容未检查")
                return result
            try:
                document = PdfReader(str(path), strict=True)
                result["pages"] = len(document.pages)
                result["text_characters"] = sum(len(page.extract_text() or "") for page in document.pages)
            except PdfReadError:
                result["status"] = "invalid"
                result["details"].append("PDF 内容损坏或无法解析")
                return result
        elif actual == "image":
            try:
                import pytesseract
                from PIL import Image
            except ImportError:
                result["details"].append("未安装 OCR 组件，图片文字未检查")
                return result
            try:
                with Image.open(path) as image:
                    image.verify()
                with Image.open(path) as image:
                    text = pytesseract.image_to_string(image, lang="eng")
                result["text_characters"] = len(text)
            except pytesseract.pytesseract.TesseractNotFoundError:
                result["details"].append("未安装 OCR 组件，图片文字未检查")
                return result
        else:
            probe = shutil.which("ffprobe")
            if not probe:
                result["details"].append("未安装 ffprobe，音频时长未检查")
                return result
            completed = subprocess.run([probe, "-v", "error", "-show_entries", "format=duration",
                                        "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                                       capture_output=True, text=True, timeout=30, check=True)
            result["duration_seconds"] = float(completed.stdout.strip())
            if result["duration_seconds"] <= 0:
                raise ValueError("音频时长无效")
    except (OSError, ValueError, KeyError, ElementTree.ParseError, zipfile.BadZipFile,
            subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        result["status"] = "invalid"
        result["details"].append(f"文件无法完整读取：{type(error).__name__}")
        return result
    if actual != "audio" and result.get("text_characters", 0) == 0:
        result["details"].append("没有提取到文字，需要人工检查扫描质量或排版")
    else:
        result["details"].append("基础读取成功；题目、答案和音频对应关系仍须人工核对")
    return result


def inspect(paths: list[Path]) -> dict:
    files = sorted({item for path in paths for item in (path.rglob("*") if path.is_dir() else [path])
                    if item.is_file() and item.suffix.lower() in FORMATS})
    return {"ready_for_mock": False, "reason": "M0 只做基础检查，不能验证题目与答案对齐或音频分段",
            "files": [inspect_file(path) for path in files]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    for path in args.paths:
        if not path.exists():
            parser.error(f"路径不存在：{path}")
    report = json.dumps(inspect(args.paths), ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report + "\n", encoding="utf-8")
    else:
        print(report)


if __name__ == "__main__":
    main()

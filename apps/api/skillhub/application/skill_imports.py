from __future__ import annotations

from base64 import b64decode, b64encode
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from json import dumps
from pathlib import PurePosixPath
from re import fullmatch
from zipfile import BadZipFile, ZipFile

from skillhub.domain.errors import InvariantError


MAX_BUNDLE_FILES = 100
MAX_BUNDLE_BYTES = 5 * 1024 * 1024


@dataclass(frozen=True)
class ImportedFile:
    path: str
    content: bytes


@dataclass(frozen=True)
class ParsedSkillBundle:
    slug: str
    description: str
    entry_path: str
    file_count: int
    digest: str
    manifest_text: str


def parse_skill_import_source(source: dict) -> ParsedSkillBundle:
    kind = source.get("kind")
    if kind == "files":
        files = _files_from_payload(source)
    elif kind == "zip":
        files = _files_from_zip(source)
    else:
        raise InvariantError("Skill import source kind must be 'files' or 'zip'.")
    return _parse_bundle(files)


def _files_from_payload(source: dict) -> list[ImportedFile]:
    raw_files = source.get("files")
    if not isinstance(raw_files, list) or not raw_files:
        raise InvariantError("Skill import requires at least one file.")
    files = []
    for raw_file in raw_files:
        path = raw_file.get("path") if isinstance(raw_file, dict) else None
        content_text = raw_file.get("content_text") if isinstance(raw_file, dict) else None
        content_base64 = raw_file.get("content_base64") if isinstance(raw_file, dict) else None
        if not isinstance(path, str):
            raise InvariantError("Each imported file needs path and content_text or content_base64.")
        if isinstance(content_text, str):
            content = content_text.encode("utf-8")
        elif isinstance(content_base64, str):
            try:
                content = b64decode(content_base64, validate=True)
            except ValueError as exc:
                raise InvariantError("Imported file content_base64 must be valid base64.") from exc
        else:
            raise InvariantError("Each imported file needs path and content_text or content_base64.")
        files.append(ImportedFile(path=_safe_path(path), content=content))
    return _normalize_root(files)


def _files_from_zip(source: dict) -> list[ImportedFile]:
    archive_text = source.get("zip_base64")
    if not isinstance(archive_text, str) or not archive_text:
        raise InvariantError("Zip import requires zip_base64.")
    try:
        archive_bytes = b64decode(archive_text, validate=True)
    except ValueError as exc:
        raise InvariantError("Zip import payload must be valid base64.") from exc
    if len(archive_bytes) > MAX_BUNDLE_BYTES:
        raise InvariantError("Skill bundle zip is too large.")
    try:
        with ZipFile(BytesIO(archive_bytes)) as archive:
            files = [
                ImportedFile(path=_safe_path(info.filename), content=archive.read(info))
                for info in archive.infolist()
                if not info.is_dir()
            ]
    except BadZipFile as exc:
        raise InvariantError("Skill import zip is not readable.") from exc
    return _normalize_root(files)


def _parse_bundle(files: list[ImportedFile]) -> ParsedSkillBundle:
    if len(files) > MAX_BUNDLE_FILES:
        raise InvariantError("Skill bundle has too many files.")
    total_size = sum(len(file.content) for file in files)
    if total_size > MAX_BUNDLE_BYTES:
        raise InvariantError("Skill bundle is too large.")

    entry = next((file for file in files if file.path == "SKILL.md"), None)
    if entry is None:
        raise InvariantError("Skill bundle must contain SKILL.md at its root.")
    try:
        skill_text = entry.content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InvariantError("SKILL.md must be UTF-8 text.") from exc
    metadata = _frontmatter(skill_text)
    slug = metadata.get("name", "")
    description = metadata.get("description", "")
    if not fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", slug):
        raise InvariantError("Skill name must be lowercase letters, numbers, and hyphens, up to 64 characters.")
    if not description.strip():
        raise InvariantError("Skill description is required.")
    if len(description) > 1024:
        raise InvariantError("Skill description must be 1024 characters or fewer.")

    manifest = {
        "entry_path": "SKILL.md",
        "metadata": {"name": slug, "description": description},
        "files": [_manifest_file(file) for file in sorted(files, key=lambda item: item.path)],
    }
    manifest_text = dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2)
    return ParsedSkillBundle(
        slug=slug,
        description=description,
        entry_path="SKILL.md",
        file_count=len(files),
        digest=sha256(manifest_text.encode("utf-8")).hexdigest(),
        manifest_text=manifest_text,
    )


def _frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise InvariantError("SKILL.md must start with YAML frontmatter.")
    metadata: dict[str, str] = {}
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            if index == 1:
                raise InvariantError("SKILL.md frontmatter cannot be empty.")
            return metadata
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip("\"'")
    raise InvariantError("SKILL.md frontmatter must end with ---.")


def _manifest_file(file: ImportedFile) -> dict[str, object]:
    digest = sha256(file.content).hexdigest()
    base = {"path": file.path, "sha256": digest, "size_bytes": len(file.content)}
    try:
        text = file.content.decode("utf-8")
    except UnicodeDecodeError:
        return {**base, "content_base64": b64encode(file.content).decode("ascii"), "binary": True}
    if "\x00" in text:
        return {**base, "content_base64": b64encode(file.content).decode("ascii"), "binary": True}
    return {**base, "content_text": text}


def _normalize_root(files: list[ImportedFile]) -> list[ImportedFile]:
    if not files:
        raise InvariantError("Skill import requires at least one file.")
    roots = {file.path.split("/", 1)[0] for file in files if "/" in file.path}
    has_root_files = any("/" not in file.path for file in files)
    if len(roots) == 1 and not has_root_files:
        root = next(iter(roots))
        return [ImportedFile(path=file.path[len(root) + 1 :], content=file.content) for file in files]
    return files


def _safe_path(path: str) -> str:
    normalized = path.replace("\\", "/").strip("/")
    candidate = PurePosixPath(normalized)
    if not normalized or candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        raise InvariantError("Skill import contains an unsafe file path.")
    return candidate.as_posix()

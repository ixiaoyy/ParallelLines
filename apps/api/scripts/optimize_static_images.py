"""Losslessly optimize tracked site images; preview by default, never upload assets."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from collections import Counter
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, PngImagePlugin, UnidentifiedImageError

ROOT = Path(__file__).resolve().parents[3]
IMAGE_ROOTS = (ROOT / "apps/web/public", ROOT / "static")
MAX_FILES = 2000
MAX_FRAMES = 1000
MAX_DECODED_PIXELS = 100_000_000
PROTECTED_NAMES = {"auth-mark", "match3-game-mark"}


@dataclass
class ImageSnapshot:
    """Decoded RGBA frames, timing and color metadata used for exact comparison."""

    frames: list[Image.Image]
    durations: list[int | float | None]
    loop: int | None
    background: tuple[int, ...] | None
    metadata: dict[str, bytes]


def image_paths(explicit_paths: list[str]) -> list[Path]:
    """Resolve explicit files or tracked PNG/WebP files within the two static roots."""

    names = explicit_paths
    if not names:
        result = subprocess.run(
            ["git", "ls-files", "-z", "--", "apps/web/public", "static"],
            cwd=ROOT,
            capture_output=True,
            check=True,
            timeout=30,
        )
        names = result.stdout.decode("utf-8").rstrip("\0").split("\0")
    paths = set()
    for name in names:
        path = (ROOT / name).resolve()
        if path.suffix.lower() not in {".png", ".webp"}:
            if explicit_paths:
                raise ValueError(f"PNG/WebP file required: {name}")
            continue
        if not any(path.is_relative_to(base) for base in IMAGE_ROOTS):
            raise ValueError(f"image must stay within the static roots: {name}")
        if not path.is_file():
            raise FileNotFoundError(path)
        paths.add(path)
    if len(paths) > MAX_FILES:
        raise ValueError(f"at most {MAX_FILES} files may be processed in one invocation")
    # 先输出新 PNG 的映射；同名 PNG 则等待已有 WebP 优化完成后再判断是否可复用。
    return sorted(paths, key=lambda path: (
        path.suffix.lower() != ".png" or path.with_suffix(".webp").exists(),
        path.suffix.lower() != ".webp",
        str(path),
    ))


def protected_asset(path: Path) -> bool:
    """Keep logos, favicons and named brand marks outside performance changes."""

    stem = path.stem.lower()
    return any(part in stem for part in ("logo", "favicon", "brand")) or stem in PROTECTED_NAMES


def decode_image(content: bytes) -> ImageSnapshot:
    """Decode bounded frames without discarding RGB values under transparent pixels."""

    with Image.open(BytesIO(content)) as image:
        count = getattr(image, "n_frames", 1)
        if count > MAX_FRAMES or image.width * image.height * count > MAX_DECODED_PIXELS:
            raise ValueError("image exceeds the bounded frame/pixel decoding budget")
        metadata = {
            key: value
            for key in ("icc_profile", "exif", "xmp")
            if (value := image.info.get(key))
        }
        loop = image.info.get("loop", 0) if count > 1 else None
        background = image.info.get("background") if count > 1 else None
        frames = []
        durations = []
        for index in range(count):
            image.seek(index)
            image.load()
            frames.append(image.convert("RGBA"))
            durations.append(image.info.get("duration") if count > 1 else None)
    return ImageSnapshot(frames, durations, loop, background, metadata)


def equivalent(source: ImageSnapshot, candidate: ImageSnapshot) -> bool:
    """Require RGBA, animation and retained ICC/EXIF/XMP metadata to stay identical."""

    # 相同 RGBA 不代表显示一致；ICC、EXIF 方向与 XMP 也必须完整保留。
    if (
        len(source.frames) != len(candidate.frames)
        or source.durations != candidate.durations
        or source.loop != candidate.loop
        or source.background != candidate.background
        or source.metadata != candidate.metadata
    ):
        return False
    for before, after in zip(source.frames, candidate.frames, strict=True):
        if before.size != after.size or before.tobytes() != after.tobytes():
            return False
    return True


def encode_webp(snapshot: ImageSnapshot) -> bytes:
    """Encode lossless WebP and preserve color metadata, animation timing and loop."""

    output = BytesIO()
    options = {
        "lossless": True,
        # 无损模式的 quality 仅控制搜索成本；常规 effort 避免大图最高档搜索耗时失控。
        "quality": 75,
        "method": 4,
        "exact": True,
        **snapshot.metadata,
    }
    if len(snapshot.frames) > 1:
        options.update(
            save_all=True,
            append_images=snapshot.frames[1:],
            duration=snapshot.durations,
            loop=snapshot.loop,
            background=snapshot.background or (0, 0, 0, 0),
            minimize_size=True,
            allow_mixed=False,
        )
    snapshot.frames[0].save(output, "WEBP", **options)
    return output.getvalue()


def encode_png(content: bytes) -> bytes:
    """Recompress persisted avatar PNGs without changing format or color metadata."""

    pnginfo = PngImagePlugin.PngInfo()
    preserved = {
        b"cHRM", b"cICP", b"gAMA", b"sBIT", b"sRGB", b"tIME", b"iTXt", b"tEXt", b"zTXt",
    }
    offset = 8
    while offset + 12 <= len(content):
        length = int.from_bytes(content[offset:offset + 4], "big")
        kind = content[offset + 4:offset + 8]
        if kind in preserved:
            pnginfo.add(kind, content[offset + 8:offset + 8 + length])
        offset += length + 12
    output = BytesIO()
    with Image.open(BytesIO(content)) as image:
        image.load()
        options = {key: image.info[key] for key in ("icc_profile", "exif", "dpi")
                   if key in image.info}
        image.save(output, "PNG", optimize=True, compress_level=9, pnginfo=pnginfo, **options)
    return output.getvalue()


def replace_atomically(target: Path, content: bytes, *, exists: bool) -> None:
    """Replace one validated image atomically; temporary bytes stay in project .tmp."""

    temporary_root = ROOT / ".tmp/image-optimization"
    temporary_root.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(suffix=target.suffix, dir=temporary_root)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
        if exists:
            temporary.replace(target)
        else:
            # 新路径用独占链接创建，避免压缩期间出现的同名文件被覆盖。
            os.link(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def optimize_image(path: Path, *, write: bool) -> dict:
    """Optimize one image only after exact decode checks and a strict byte reduction."""

    source_content = path.read_bytes()
    relative = path.relative_to(ROOT).as_posix()
    result = {
        "source": relative,
        "target": relative,
        "status": "skipped",
        "reason": "",
        "original_bytes": len(source_content),
        "optimized_bytes": len(source_content),
        "saved_bytes": 0,
    }
    if protected_asset(path):
        with Image.open(BytesIO(source_content)) as image:
            result.update(width=image.width, height=image.height,
                          frames=getattr(image, "n_frames", 1))
        result["reason"] = "protected_brand_asset"
        return result
    snapshot = decode_image(source_content)
    result.update(
        width=snapshot.frames[0].width,
        height=snapshot.frames[0].height,
        frames=len(snapshot.frames),
        durations_ms=snapshot.durations,
        loop=snapshot.loop,
    )
    # 头像路径已持久化于数据库，不能只生成没有调用方的新扩展名资源。
    keep_png = path.suffix.lower() == ".png" and path.parent == ROOT / "apps/web/public/avatars"
    target = path if keep_png else path.with_suffix(".webp")
    target_existed = target.exists()
    candidate = None
    if target != path and target_existed:
        # 旧同名 WebP 可能是另一版图片，像素不同就保留双方，绝不以 PNG 覆盖它。
        candidate = target.read_bytes()
        if not equivalent(snapshot, decode_image(candidate)):
            result["reason"] = "existing_webp_has_different_rgba_animation_or_metadata"
            return result
        result["reason"] = "reuse_existing_equivalent_webp"
    else:
        candidate = encode_png(source_content) if keep_png else encode_webp(snapshot)
        if not equivalent(snapshot, decode_image(candidate)):
            # 动画编码器未必保留透明像素隐藏 RGB；不降低逐字节相等的验收条件。
            result["reason"] = "encoder_changed_rgba_animation_or_metadata"
            return result
        result["reason"] = "lossless_png" if keep_png else "lossless_webp"
    result["candidate_bytes"] = len(candidate)
    if len(candidate) >= len(source_content):
        result["reason"] = "no_byte_reduction"
        return result
    result.update(
        target=target.relative_to(ROOT).as_posix(),
        status="optimized" if write else "would_optimize",
        optimized_bytes=len(candidate),
        saved_bytes=len(source_content) - len(candidate),
        exact_rgba_and_animation=True,
        exact_rgba_animation_and_metadata=True,
    )
    if write and (target == path or not target_existed):
        # 处理期间有人改动源文件就终止该项，不能覆盖其他工作；PNG 原文件始终保留。
        if path.read_bytes() != source_content:
            raise RuntimeError(f"source changed while optimizing: {relative}")
        replace_atomically(target, candidate, exists=target_existed)
        if not equivalent(snapshot, decode_image(target.read_bytes())):
            raise RuntimeError(f"written image failed exact verification: {relative}")
    elif write and target.read_bytes() != candidate:
        raise RuntimeError(f"reused target changed while optimizing: {relative}")
    return result


def parse_args() -> argparse.Namespace:
    """Parse local-only optimization options; image writes require explicit --write."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths", nargs="*", help="Explicit PNG/WebP files relative to repository root"
    )
    parser.add_argument(
        "--write", action="store_true", help="Write smaller exactly equivalent images"
    )
    parser.add_argument(
        "--report", type=Path, help="Write a JSON report, including in preview mode"
    )
    return parser.parse_args()


def main() -> int:
    """Process a bounded local inventory and report successful changes and safe skips."""

    args = parse_args()
    results = []
    for path in image_paths(args.paths):
        try:
            result = optimize_image(path, write=args.write)
        except (OSError, ValueError, RuntimeError, Image.DecompressionBombError,
                UnidentifiedImageError) as error:
            result = {
                "source": path.relative_to(ROOT).as_posix(),
                "status": "error",
                "reason": f"{type(error).__name__}: {error}",
            }
        results.append(result)
        print(
            f"{result['status']}: {result['source']} -> {result.get('target', '-')} "
            f"{result.get('original_bytes', '-')} -> {result.get('optimized_bytes', '-')} B "
            f"({result['reason']})",
            flush=True,
        )
    summary = {
        "files": len(results),
        "statuses": dict(Counter(item["status"] for item in results)),
        "reasons": dict(Counter(item["reason"] for item in results)),
        "source_bytes": sum(item.get("original_bytes", 0) for item in results),
        "delivery_bytes": sum(item.get("optimized_bytes", 0) for item in results),
        "saved_bytes": sum(item.get("saved_bytes", 0) for item in results),
    }
    report = {"write": args.write, "contract": "exact_rgba_animation_metadata", "summary": summary,
              "images": results}
    if args.report:
        target = (ROOT / args.report).resolve()
        if not target.is_relative_to(ROOT):
            raise ValueError("report path must stay within the repository")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return int(any(item["status"] == "error" for item in results))


if __name__ == "__main__":
    raise SystemExit(main())

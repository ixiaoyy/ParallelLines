"""从正式 Logo 等比导出站点图标；仅离线使用，不加入 Web 构建或新增运行依赖。

在已有 Pillow 环境运行本脚本。默认预览，--write 写入，--check 核对已提交产物。
"""

from __future__ import annotations

import argparse
import base64
from io import BytesIO
from pathlib import Path

from PIL import Image

PUBLIC = Path(__file__).resolve().parents[1] / "public"
ICON_SIZES = {"favicon.png": 96, "apple-touch-icon.png": 180, "app-icon-192.png": 192}


def build_icons() -> dict[Path, bytes]:
    """返回正式 Logo 的方形图标字节，不裁切、重绘、补底或修改源文件。"""

    with Image.open(PUBLIC / "logo-lines-mark.png") as source:
        if source.width != source.height:
            raise ValueError("Formal site logo must be square; do not crop it automatically")
        logo = source.convert("RGBA")
        color_profile = source.info.get("icc_profile")
    outputs = {}
    for filename, size in ICON_SIZES.items():
        image = logo.resize((size, size), Image.Resampling.LANCZOS)
        stream = BytesIO()
        # PNG 保留透明度和完整颜色；只做无损编码优化，不改用兼容性不同的格式。
        image.save(stream, format="PNG", optimize=True, compress_level=9, icc_profile=color_profile)
        outputs[PUBLIC / filename] = stream.getvalue()
    encoded = base64.b64encode(outputs[PUBLIC / "favicon.png"]).decode("ascii")
    # 保留后台默认 SVG 地址；内嵌相同 PNG，避免另画图形或依赖 SVG 内的外部请求。
    outputs[PUBLIC / "favicon.svg"] = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96" viewBox="0 0 96 96">\n'
        f'  <image width="96" height="96" href="data:image/png;base64,{encoded}" />\n'
        '</svg>\n'
    ).encode()
    return outputs


def main() -> int:
    """按显式模式预览、写入或检查本地四个图标；检查不一致时返回非零。"""

    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="Write the derived icon assets")
    mode.add_argument("--check", action="store_true", help="Fail if derived assets differ")
    args = parser.parse_args()
    mismatches = []
    for target, content in build_icons().items():
        existing = target.read_bytes() if target.is_file() else None
        # Windows checkout 可能转换 SVG 文本行尾；内嵌 PNG 字节和图形内容仍须完全相同。
        if existing is not None and target.suffix == ".svg":
            existing = existing.replace(b"\r\n", b"\n")
        matches = existing == content
        if not matches:
            mismatches.append(target.name)
            if args.write:
                target.write_bytes(content)
        status = "unchanged" if matches else "written" if args.write else "would_update"
        print(f"{status}: {target.name} ({len(content)} bytes)")
    return int(args.check and bool(mismatches))


if __name__ == "__main__":
    raise SystemExit(main())

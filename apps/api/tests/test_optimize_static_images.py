"""Local image-optimizer contracts; run with unittest without database fixtures."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from io import BytesIO, StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image, PngImagePlugin

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = PROJECT_ROOT / "apps/api/scripts/optimize_static_images.py"
SPEC = importlib.util.spec_from_file_location("static_image_optimizer", SCRIPT)
optimizer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = optimizer
SPEC.loader.exec_module(optimizer)


class StaticImageOptimizerTests(unittest.TestCase):
    def setUp(self):
        temporary_root = PROJECT_ROOT / ".tmp/image-optimization/tests"
        temporary_root.mkdir(parents=True, exist_ok=True)
        self.directory = TemporaryDirectory(dir=temporary_root)
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        roots = (self.root / "apps/web/public", self.root / "static")
        self.addCleanup(patch.stopall)
        patch.object(optimizer, "ROOT", self.root).start()
        patch.object(optimizer, "IMAGE_ROOTS", roots).start()

    def save_png(self, name="sample.png", *, image=None, **options):
        """Create one fixture inside the permitted roots and return its path."""

        path = self.root / "apps/web/public" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if image is None:
            image = Image.new("RGBA", (128, 128), (30, 77, 99, 200))
        image.save(path, "PNG", compress_level=0, **options)
        return path

    def test_default_cli_is_dry_run_and_preserves_png(self):
        source = self.save_png()
        original = source.read_bytes()
        with patch.object(sys, "argv", [str(SCRIPT), str(source)]):
            with redirect_stdout(StringIO()):
                self.assertEqual(optimizer.main(), 0)
        self.assertEqual(source.read_bytes(), original)
        self.assertFalse(source.with_suffix(".webp").exists())

    def test_write_requires_a_smaller_equivalent_file_and_keeps_png(self):
        source = self.save_png()
        original = source.read_bytes()
        result = optimizer.optimize_image(source, write=True)
        target = source.with_suffix(".webp")
        self.assertEqual(result["status"], "optimized")
        self.assertLess(target.stat().st_size, len(original))
        self.assertEqual(source.read_bytes(), original)
        self.assertTrue(optimizer.equivalent(
            optimizer.decode_image(original), optimizer.decode_image(target.read_bytes())
        ))

    def test_larger_candidate_is_not_written(self):
        source = self.save_png()
        original = source.read_bytes()
        snapshot = optimizer.decode_image(original)
        candidate = optimizer.encode_webp(snapshot) + b"\0" * (len(original) + 1)
        self.assertTrue(optimizer.equivalent(snapshot, optimizer.decode_image(candidate)))
        with patch.object(optimizer, "encode_webp", return_value=candidate):
            result = optimizer.optimize_image(source, write=True)
        self.assertEqual(result["reason"], "no_byte_reduction")
        self.assertEqual(source.read_bytes(), original)
        self.assertFalse(source.with_suffix(".webp").exists())

    def test_hidden_rgb_under_transparency_is_preserved(self):
        image = Image.new("RGBA", (32, 32), (39, 81, 122, 0))
        image.putpixel((1, 1), (214, 37, 82, 177))
        source = self.save_png(image=image)
        snapshot = optimizer.decode_image(source.read_bytes())
        self.assertTrue(optimizer.equivalent(
            snapshot, optimizer.decode_image(optimizer.encode_webp(snapshot))
        ))

    def test_animation_preserves_every_frame_duration_and_loop(self):
        frames = [Image.new("RGBA", (40, 40), color) for color in ("red", "blue", "green")]
        output = BytesIO()
        frames[0].save(
            output, "WEBP", save_all=True, append_images=frames[1:],
            duration=[73, 141, 225], loop=3, lossless=True,
        )
        snapshot = optimizer.decode_image(output.getvalue())
        candidate = optimizer.decode_image(optimizer.encode_webp(snapshot))
        self.assertEqual(len(candidate.frames), 3)
        self.assertEqual(candidate.durations, [73, 141, 225])
        self.assertEqual(candidate.loop, 3)
        self.assertTrue(optimizer.equivalent(snapshot, candidate))
        self.assertFalse(optimizer.equivalent(snapshot, replace(candidate, loop=0)))
        self.assertFalse(optimizer.equivalent(
            snapshot, replace(candidate, durations=[74, 141, 225])
        ))
        changed_frames = [frame.copy() for frame in candidate.frames]
        changed_frames[1].putpixel((0, 0), (11, 22, 33, 255))
        self.assertFalse(optimizer.equivalent(
            snapshot, replace(candidate, frames=changed_frames)
        ))

    def test_existing_different_webp_is_never_overwritten(self):
        source = self.save_png(image=Image.new("RGBA", (128, 128), "red"))
        other = self.save_png("other.png", image=Image.new("RGBA", (128, 128), "blue"))
        target = source.with_suffix(".webp")
        target.write_bytes(optimizer.encode_webp(optimizer.decode_image(other.read_bytes())))
        original = target.read_bytes()
        result = optimizer.optimize_image(source, write=True)
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(target.read_bytes(), original)

    def test_equivalent_existing_webp_is_reused_without_overwriting(self):
        source = self.save_png()
        target = source.with_suffix(".webp")
        target.write_bytes(optimizer.encode_webp(optimizer.decode_image(source.read_bytes())))
        original = target.read_bytes()
        result = optimizer.optimize_image(source, write=True)
        self.assertEqual(result["reason"], "reuse_existing_equivalent_webp")
        self.assertEqual(target.read_bytes(), original)

    def test_same_pixels_with_different_icc_or_exif_cannot_be_reused(self):
        for field in ("icc_profile", "exif"):
            with self.subTest(field=field):
                if field == "exif":
                    before, after = Image.Exif(), Image.Exif()
                    before[0x010E], after[0x010E] = "source", "different"
                    before, after = before.tobytes(), after.tobytes()
                else:
                    before, after = b"source-icc", b"different-icc"
                image = Image.new("RGBA", (128, 128), "red")
                source = self.save_png(f"{field}.png", image=image, **{field: before})
                target = source.with_suffix(".webp")
                image.save(target, "WEBP", lossless=True, exact=True, **{field: after})
                original = target.read_bytes()
                self.assertEqual(
                    optimizer.decode_image(source.read_bytes()).frames[0].tobytes(),
                    optimizer.decode_image(original).frames[0].tobytes(),
                )
                result = optimizer.optimize_image(source, write=True)
                self.assertEqual(result["status"], "skipped")
                self.assertIn("metadata", result["reason"])
                self.assertEqual(target.read_bytes(), original)

    def test_png_avatar_keeps_its_persisted_path_and_color_metadata(self):
        info = PngImagePlugin.PngInfo()
        info.add(b"sRGB", bytes([0]))
        info.add(b"gAMA", (45455).to_bytes(4, "big"))
        source = self.save_png("avatars/person.png", pnginfo=info, dpi=(96, 96))
        original = source.read_bytes()
        result = optimizer.optimize_image(source, write=True)
        self.assertEqual(result["reason"], "lossless_png")
        self.assertLess(source.stat().st_size, len(original))
        self.assertFalse(source.with_suffix(".webp").exists())
        self.assertTrue(optimizer.equivalent(
            optimizer.decode_image(original), optimizer.decode_image(source.read_bytes())
        ))
        with Image.open(BytesIO(original)) as before, Image.open(source) as after:
            self.assertEqual(before.info, after.info)

    def test_brand_assets_are_untouched(self):
        for name in ("logo-lines-mark", "favicon", "auth-mark", "match3-game-mark"):
            with self.subTest(name=name):
                source = self.save_png(f"{name}.png")
                original = source.read_bytes()
                result = optimizer.optimize_image(source, write=True)
                self.assertEqual(result["reason"], "protected_brand_asset")
                self.assertEqual(source.read_bytes(), original)
                self.assertFalse(source.with_suffix(".webp").exists())


if __name__ == "__main__":
    unittest.main()

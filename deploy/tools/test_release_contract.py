"""只验证本地 receipt 与人工 tar，不访问网络或执行归档内容。"""

import copy
import importlib.util
import io
from pathlib import Path
import tarfile
import tempfile
import unittest


SPEC = importlib.util.spec_from_file_location("release_contract", Path(__file__).with_name("release_contract.py"))
CONTRACT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTRACT)


class ReleaseContractTests(unittest.TestCase):
    def receipt(self):
        tag = "site-" + "a" * 40
        return tag, {"schema": 1, "applicationRevision": "a" * 40, "expectedTitle": "平行线工具箱",
                     "nginxImage": "nginx@sha256:" + "b" * 64, "coreVersion": "test-core",
                     "coreSourceURL": "https://example.org/source.tar.gz", "bundle": {
                         "file": "toolbox-dist.tar.gz", "url": CONTRACT.SOURCE_REPOSITORY + "/releases/download/" + tag + "/toolbox-dist.tar.gz",
                         "sha256": "c" * 64, "bytes": 100}}

    def test_valid_receipt_and_immutable_revision(self):
        tag, data = self.receipt()
        self.assertEqual(CONTRACT.validate_receipt(data, tag), data)
        changed = copy.deepcopy(data)
        changed["applicationRevision"] = "d" * 40
        with self.assertRaisesRegex(CONTRACT.ContractError, "revision_mismatch"):
            CONTRACT.validate_receipt(changed, tag)

    def test_only_the_exact_release_bundle_and_official_digest_are_allowed(self):
        tag, data = self.receipt()
        for field, value in (("nginxImage", "attacker/nginx@sha256:" + "b" * 64), ("schema", True)):
            changed = copy.deepcopy(data)
            changed[field] = value
            with self.assertRaises(CONTRACT.ContractError):
                CONTRACT.validate_receipt(changed, tag)
        for field, value in (("url", "https://example.org/bundle"), ("bytes", True), ("sha256", "***")):
            changed = copy.deepcopy(data)
            changed["bundle"][field] = value
            with self.assertRaises(CONTRACT.ContractError):
                CONTRACT.validate_receipt(changed, tag)

    def archive(self, directory, additional=()):
        output = Path(directory) / "bundle.tar.gz"
        with tarfile.open(output, "w:gz") as archive:
            for name in sorted(CONTRACT.REQUIRED_FILES):
                entry = tarfile.TarInfo(name)
                entry.size = 4
                archive.addfile(entry, io.BytesIO(b"data"))
            for entry in additional:
                archive.addfile(entry, io.BytesIO(b"x" * entry.size) if entry.isreg() else None)
        return output

    def test_safe_extract_keeps_the_contract_tree(self):
        with tempfile.TemporaryDirectory() as temporary:
            archive = self.archive(temporary)
            target = Path(temporary) / "new-release"
            summary = CONTRACT.safe_extract_bundle(archive, target)
            self.assertEqual(summary["members"], len(CONTRACT.REQUIRED_FILES))
            self.assertEqual((target / "dist/index.html").read_bytes(), b"data")

    def test_path_traversal_links_and_duplicates_are_rejected_before_creating_target(self):
        for name, kind in (("../escape", tarfile.REGTYPE), ("/absolute", tarfile.REGTYPE),
                           ("dist\\escape", tarfile.REGTYPE), ("dist/link", tarfile.SYMTYPE),
                           ("dist/hard", tarfile.LNKTYPE), ("dist/index.html", tarfile.REGTYPE)):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                entry = tarfile.TarInfo(name)
                entry.type = kind
                entry.linkname = "/etc/passwd"
                archive = self.archive(temporary, [entry])
                target = Path(temporary) / "new-release"
                with self.assertRaises(CONTRACT.ContractError):
                    CONTRACT.safe_extract_bundle(archive, target)
                self.assertFalse(target.exists())

    def test_size_and_required_file_constraints(self):
        entry = tarfile.TarInfo("dist/oversized")
        entry.size = CONTRACT.MAX_BUNDLE + 1
        with self.assertRaisesRegex(CONTRACT.ContractError, "size_invalid"):
            CONTRACT.member_name(entry)
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "empty.tar.gz"
            with tarfile.open(archive, "w:gz"):
                pass
            with self.assertRaisesRegex(CONTRACT.ContractError, "required_file_missing"):
                CONTRACT.safe_extract_bundle(archive, Path(temporary) / "new-release")


if __name__ == "__main__":
    unittest.main()

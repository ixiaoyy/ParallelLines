"""比较显式本地 fixture 保存的渲染结果；不打开浏览器或连接任何接口。"""

import json
from pathlib import Path


root = Path(__file__).resolve().parents[2]
output = root / ".tmp/performance-main-baseline-20261103"
before = json.loads((output / "level4-before.json").read_text(encoding="utf-8"))
after = json.loads((output / "level4-after.json").read_text(encoding="utf-8"))
assert before["viewport"] == after["viewport"], "viewports differ"
assert len(before["results"]) == len(after["results"]) == 8
for original, candidate in zip(before["results"], after["results"]):
    assert original["name"] == candidate["name"], "fixture order differs"
    assert original["snapshot"] == candidate["snapshot"], original["name"]
    assert candidate["snapshot"]["glError"] == 0, original["name"]
print("PASS: 8 frozen scenes match pixels, GPU instances, object/support data and VP; not FPS/playthrough acceptance.")

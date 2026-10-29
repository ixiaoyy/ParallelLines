"""Approved initial AI dimension/weight contract; registration is explicit.

No migration seeds these objects or any assessment. Previously collected scores
under other definitions must be reassessed or explicitly mapped with provenance.
"""

from app.schemas.catalog_ai_ratings import AiRuleInput, AiWeightSchemeInput

# Keep the accepted source's visual-only definition intact. Registration is
# performed by its import bundle; independent audiovisual scores are not mapped.
PUBLIC_AI_WEIGHT_VERSION = "complexity40-content30-gameplay15-controls10-visual5-20261029-v1"

CURRENT_AI_RULE = AiRuleInput.model_validate({
    "version": "catalog-ai-quality-dimensions-v1",
    "dimensions": [
        {
            "key": "visible_system_complexity", "label": "可见制作/系统复杂度",
            "definition": "已观察到的机制、状态约束及其交互复杂度；不推断源码、工时或制作成本。",
            "required": True,
        },
        {
            "key": "content_depth_scope", "label": "内容深度体量",
            "definition": "实际验证范围内的内容结构、目标变化、系统纵深与体量，注明未覆盖部分。",
            "required": True,
        },
        {
            "key": "gameplay", "label": "玩法体验",
            "definition": "实际游玩中决策、挑战、反馈和循环的体验，以证据支持数值评分。",
            "required": True,
        },
        {
            "key": "controls_completion", "label": "操作与完成度",
            "definition": "已体验的输入、引导、流程衔接、稳定性和恢复能力。",
            "required": True,
        },
        {
            "key": "audiovisual", "label": "视听表现",
            "definition": "已体验的视觉、声音、信息辨识和一致性；未体验声音时必须注明限制。",
            "required": True,
        },
    ],
})

CURRENT_AI_WEIGHT_SCHEME = AiWeightSchemeInput.model_validate({
    "version": "catalog-ai-40-30-15-10-5-v1",
    "rule_version": CURRENT_AI_RULE.version,
    "weights": {
        "visible_system_complexity": "0.40", "content_depth_scope": "0.30",
        "gameplay": "0.15", "controls_completion": "0.10", "audiovisual": "0.05",
    },
})

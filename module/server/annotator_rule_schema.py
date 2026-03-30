from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from typing import Any

RULE_TYPE_SCHEMAS: OrderedDict[str, dict[str, Any]] = OrderedDict(
    {
        "image": {
            "type": "image",
            "label": "RuleImage",
            "capabilities": {
                "supports_test": True,
                "supports_crop": True,
                "supports_image_preview": True,
                "shared_roi_back": False,
            },
            "fields": [
                {"key": "itemName", "label": "itemName", "control": "text", "default": "new"},
                {
                    "key": "imageName",
                    "label": "imageName",
                    "control": "text",
                    "default": "",
                    "auto_from_item_name": True,
                },
                {
                    "key": "method",
                    "label": "method",
                    "control": "select",
                    "default": "Template matching",
                    "options": ["Template matching", "Sift Flann"],
                },
                {
                    "key": "threshold",
                    "label": "threshold",
                    "control": "number",
                    "default": 0.8,
                    "step": 0.01,
                    "min": 0,
                    "max": 1,
                    "integer": False,
                },
                {"key": "description", "label": "description", "control": "textarea", "default": "", "full": True},
            ],
        },
        "ocr": {
            "type": "ocr",
            "label": "RuleOcr",
            "capabilities": {
                "supports_test": True,
                "supports_crop": False,
                "supports_image_preview": False,
                "shared_roi_back": False,
            },
            "fields": [
                {"key": "itemName", "label": "itemName", "control": "text", "default": "new"},
                {
                    "key": "mode",
                    "label": "mode",
                    "control": "select",
                    "default": "Single",
                    "options": ["Single", "Full", "Digit", "DigitCounter", "Duration", "Quantity"],
                },
                {"key": "method", "label": "method", "control": "text", "default": "Default"},
                {"key": "keyword", "label": "keyword", "control": "text", "default": ""},
                {"key": "description", "label": "description", "control": "textarea", "default": "", "full": True},
            ],
        },
        "click": {
            "type": "click",
            "label": "RuleClick",
            "capabilities": {
                "supports_test": False,
                "supports_crop": False,
                "supports_image_preview": False,
                "shared_roi_back": False,
            },
            "fields": [
                {"key": "itemName", "label": "itemName", "control": "text", "default": "new"},
                {"key": "description", "label": "description", "control": "textarea", "default": "", "full": True},
            ],
        },
        "swipe": {
            "type": "swipe",
            "label": "RuleSwipe",
            "capabilities": {
                "supports_test": False,
                "supports_crop": False,
                "supports_image_preview": False,
                "shared_roi_back": False,
            },
            "fields": [
                {"key": "itemName", "label": "itemName", "control": "text", "default": "new"},
                {
                    "key": "mode",
                    "label": "mode",
                    "control": "select",
                    "default": "default",
                    "options": ["default", "vector"],
                },
                {"key": "description", "label": "description", "control": "textarea", "default": "", "full": True},
            ],
        },
        "long_click": {
            "type": "long_click",
            "label": "RuleLongClick",
            "capabilities": {
                "supports_test": False,
                "supports_crop": False,
                "supports_image_preview": False,
                "shared_roi_back": False,
            },
            "fields": [
                {"key": "itemName", "label": "itemName", "control": "text", "default": "new"},
                {
                    "key": "duration",
                    "label": "duration(ms)",
                    "control": "number",
                    "default": 1000,
                    "min": 1,
                    "step": 1,
                    "integer": True,
                },
                {"key": "description", "label": "description", "control": "textarea", "default": "", "full": True},
            ],
        },
        "list": {
            "type": "list",
            "label": "RuleList",
            "capabilities": {
                "supports_test": True,
                "supports_crop": True,
                "supports_image_preview": True,
                "shared_roi_back": True,
            },
            "fields": [
                {"key": "itemName", "label": "itemName", "control": "text", "default": "new"},
            ],
            "meta_fields": [
                {"key": "name", "label": "list.name", "control": "text", "default": "list_name"},
                {
                    "key": "direction",
                    "label": "list.direction",
                    "control": "select",
                    "default": "vertical",
                    "options": ["vertical", "horizontal"],
                },
                {
                    "key": "type",
                    "label": "list.type",
                    "control": "select",
                    "default": "image",
                    "options": ["image", "ocr"],
                },
                {"key": "description", "label": "list.description", "control": "text", "default": ""},
            ],
        },
    }
)


ROI_DEFAULT = "0,0,100,100"


def get_rule_types() -> list[str]:
    return list(RULE_TYPE_SCHEMAS.keys())


def get_rule_schema(rule_type: str) -> dict[str, Any]:
    schema = RULE_TYPE_SCHEMAS.get(str(rule_type or "").strip())
    if not schema:
        schema = RULE_TYPE_SCHEMAS["image"]
    return deepcopy(schema)


def get_rule_schemas() -> list[dict[str, Any]]:
    return [get_rule_schema(rule_type) for rule_type in get_rule_types()]


def get_schema_payload() -> dict[str, Any]:
    return {
        "rule_types": get_rule_types(),
        "schemas": {rule_type: get_rule_schema(rule_type) for rule_type in get_rule_types()},
    }


def _field_defaults(fields: list[dict[str, Any]]) -> dict[str, Any]:
    return {field["key"]: deepcopy(field.get("default")) for field in fields}


def default_rule(rule_type: str) -> dict[str, Any]:
    schema = get_rule_schema(rule_type)
    rule = _field_defaults(schema.get("fields", []))
    rule["roiFront"] = ROI_DEFAULT
    if rule_type != "list":
        rule["roiBack"] = ROI_DEFAULT
    return rule


def default_list_meta() -> dict[str, Any]:
    schema = get_rule_schema("list")
    meta = _field_defaults(schema.get("meta_fields", []))
    meta["roiBack"] = ROI_DEFAULT
    return meta


def merge_rule_with_defaults(rule_type: str, rule: dict[str, Any] | None) -> dict[str, Any]:
    merged = default_rule(rule_type)
    if isinstance(rule, dict):
        merged.update(rule)
    if rule_type == "list":
        merged.pop("description", None)
    return merged


def merge_list_meta_with_defaults(meta: dict[str, Any] | None) -> dict[str, Any]:
    merged = default_list_meta()
    if isinstance(meta, dict):
        merged.update(meta)
    return merged


def field_default(rule_type: str, key: str, fallback: Any = None) -> Any:
    schema = get_rule_schema(rule_type)
    fields = list(schema.get("fields", [])) + list(schema.get("meta_fields", []))
    for field in fields:
        if field.get("key") == key:
            return deepcopy(field.get("default"))
    return fallback


def field_options(rule_type: str, key: str) -> list[str]:
    schema = get_rule_schema(rule_type)
    fields = list(schema.get("fields", [])) + list(schema.get("meta_fields", []))
    for field in fields:
        if field.get("key") == key:
            return list(field.get("options", []))
    return []

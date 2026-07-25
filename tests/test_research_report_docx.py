from __future__ import annotations

import importlib.util
import json
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

from docx import Document


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "generate_research_report_docx.py"
SPEC = importlib.util.spec_from_file_location("generate_research_report_docx", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS = {"w": W_NS}

EXPECTED_TOC = [
    ("摘要", "i"),
    ("第 1 章 绪论", "1"),
    ("第 2 章 相关技术", "3"),
    ("第 3 章 数据与知识库构建", "4"),
    ("第 4 章 系统总体架构", "6"),
    ("第 5 章 核心方法", "8"),
    ("第 6 章 系统实现", "13"),
    ("第 7 章 实验设计与结果", "15"),
    ("第 8 章 总结与展望", "25"),
    ("参考文献", "26"),
    ("附录 A 可复现实验命令", "27"),
]


def w_attr(name: str) -> str:
    return f"{{{W_NS}}}{name}"


def test_final_research_report_docx_is_current() -> None:
    MODULE.check(MODULE.DEFAULT_OUTPUT, MODULE.DEFAULT_MANIFEST)


def test_static_toc_matches_render_verified_page_labels() -> None:
    expected_entries = [
        {"heading": heading, "page_label": page_label}
        for heading, page_label in EXPECTED_TOC
    ]
    manifest = json.loads(MODULE.DEFAULT_MANIFEST.read_text(encoding="utf-8"))

    assert MODULE.STATIC_TOC_PAGE_LABELS == dict(EXPECTED_TOC[1:])
    assert manifest["toc"] == {
        "mode": "static_render_verified",
        "entries": expected_entries,
    }

    paragraph_texts = [paragraph.text for paragraph in Document(MODULE.DEFAULT_OUTPUT).paragraphs]
    toc_start = paragraph_texts.index("目录") + 1
    assert paragraph_texts[toc_start : toc_start + len(EXPECTED_TOC)] == [
        f"{heading}\t{page_label}" for heading, page_label in EXPECTED_TOC
    ]


def test_each_ordered_list_restarts_from_one() -> None:
    with ZipFile(MODULE.DEFAULT_OUTPUT) as archive:
        document_root = ET.fromstring(archive.read("word/document.xml"))
        numbering_root = ET.fromstring(archive.read("word/numbering.xml"))

    referenced_num_ids = Counter(
        node.get(w_attr("val"))
        for node in document_root.findall(".//w:numPr/w:numId", NS)
    )
    abstract_formats = {
        node.get(w_attr("abstractNumId")): node.find(".//w:numFmt", NS).get(w_attr("val"))
        for node in numbering_root.findall("w:abstractNum", NS)
    }

    ordered_instances: list[tuple[int, int, str | None]] = []
    for node in numbering_root.findall("w:num", NS):
        num_id = node.get(w_attr("numId"))
        abstract_id = node.find("w:abstractNumId", NS).get(w_attr("val"))
        if abstract_formats.get(abstract_id) != "decimal" or not referenced_num_ids[num_id]:
            continue
        start_override = node.find("w:lvlOverride/w:startOverride", NS)
        ordered_instances.append(
            (
                int(num_id),
                referenced_num_ids[num_id],
                None if start_override is None else start_override.get(w_attr("val")),
            )
        )

    ordered_instances.sort()
    expected_item_counts = [
        len(node["children"])
        for node in MODULE.parse_source()
        if node.get("type") == "list" and node.get("ordered")
    ]

    assert [item_count for _, item_count, _ in ordered_instances] == expected_item_counts
    assert all(start_override == "1" for _, _, start_override in ordered_instances)
    assert len({num_id for num_id, _, _ in ordered_instances}) == len(expected_item_counts)

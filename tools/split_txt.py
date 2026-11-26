#!/usr/bin/env python3
"""Organize the Shen Ce archive by its original volumes and record headings."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


VOLUME_VALUES = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}
VOLUME_HEADING = re.compile(r"^卷([一二三四五六七八九十]+)\u3000(.+)$")
YEAR_HEADING = re.compile(r"^——\s*(永嘉.+?年)[（(].*[）)]——$")
DATE_HEADING = re.compile(
    r"^(?P<year>永嘉[^\u3000\s]+?年)"
    r"(?P<month>正月|[一二三四五六七八九十]+月)[^\u3000\s]*\u3000"
)

RECORD_SPECS = {
    4: [("案", re.compile(r"^【案 第 (\d+) 号】"), 100)],
    5: [("关系", re.compile(r"^【关系 第 (\d+) 号】"), 100)],
    6: [("书信", re.compile(r"^〔书 第 (\d+) 通〕"), 100)],
    7: [("武学", re.compile(r"^【武学 第 (\d+) 则】"), 100)],
    8: [
        ("器物", re.compile(r"^【器物 第 (\d+) 则】"), 100),
        ("方药", re.compile(r"^【方 第 (\d+) 则】"), 100),
    ],
    9: [
        ("异闻", re.compile(r"^【异闻 第 .+? 说】"), 50),
        ("遗文", re.compile(r"^【遗文 第 .+? 篇】"), 50),
        ("后人评", re.compile(r"^【后人评 第 .+? 则】"), 50),
    ],
}


def parse_volume_heading(line: bytes) -> tuple[int, str] | None:
    text = line.decode("utf-8").strip()
    if text.count("\u3000") != 1:
        return None
    match = VOLUME_HEADING.match(text)
    if match is None:
        return None

    digits, title = match.groups()
    if digits in VOLUME_VALUES:
        number = VOLUME_VALUES[digits]
    elif digits.startswith("十"):
        number = 10 + VOLUME_VALUES.get(digits[1:], 0)
    elif digits.endswith("十"):
        number = VOLUME_VALUES[digits[:-1]] * 10
    else:
        number = 0
    return number, title


def safe_part(value: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", value).strip(" .")


class KnowledgeBaseWriter:
    def __init__(self, output: Path) -> None:
        if output.exists() and any(output.iterdir()):
            raise SystemExit(f"Output directory is not empty: {output}")
        output.mkdir(parents=True, exist_ok=True)
        self.output = output
        self.files: list[dict] = []
        self.source_hash = hashlib.sha256()
        self.source_bytes = 0
        self.source_lines = 0
        self.volume_details: dict[int, tuple[str, str]] = {}
        self.item_counts: dict[str, int] = {}

    def read_source_line(self, raw: bytes) -> int:
        self.source_hash.update(raw)
        self.source_bytes += len(raw)
        self.source_lines += 1
        return self.source_lines

    def write_piece(
        self,
        relative_path: str,
        content: bytes,
        *,
        volume: int,
        kind: str,
        source_start: int,
        source_end: int,
        title: str = "",
    ) -> None:
        if not content:
            return
        path = self.output / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        self.files.append(
            {
                "path": path.relative_to(self.output).as_posix(),
                "volume": volume,
                "kind": kind,
                "title": title,
                "source_line_start": source_start,
                "source_line_end": source_end,
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )

    def folder(self, volume: int, title: str) -> str:
        if volume == 1:
            return "01-目录与体例"
        short_title = title.split("（", 1)[0].strip()
        return f"{volume:02d}-{safe_part(short_title)}"

    def finish(self) -> dict:
        manifest = {
            "source_file": "沈策古风剧情设定完整版(1).txt",
            "source_bytes": self.source_bytes,
            "source_lines": self.source_lines,
            "source_sha256": self.source_hash.hexdigest(),
            "file_count": len(self.files),
            "volumes": [
                {
                    "number": number,
                    "title": title,
                    "folder": folder,
                    "file_count": sum(1 for item in self.files if item["volume"] == number),
                    "item_counts": {
                        key: count
                        for key, count in self.item_counts.items()
                        if key.startswith(f"{number}:")
                    },
                }
                for number, (title, folder) in sorted(self.volume_details.items())
            ],
            "files": self.files,
        }
        (self.output / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        write_indexes(self.output, manifest)
        return manifest


class SectionCollector:
    def __init__(
        self,
        writer: KnowledgeBaseWriter,
        volume: int,
        title: str,
        kind: str,
    ) -> None:
        self.writer = writer
        self.volume = volume
        self.title = title
        self.folder = writer.folder(volume, title)
        self.kind = kind
        self.preamble = bytearray()
        self.preamble_start = 0
        self.record = bytearray()
        self.record_start = 0
        self.record_end = 0
        self.record_group = ""
        self.record_id = 0
        self.record_kind = ""
        self.record_title = ""
        self.record_counts: dict[str, int] = {}
        self.found_record = False

    def add(self, raw: bytes, line_number: int) -> None:
        text = raw.decode("utf-8").strip()
        for group, pattern, group_size in RECORD_SPECS.get(self.volume, []):
            match = pattern.match(text)
            if match:
                self.flush_record()
                if not self.found_record:
                    self.write_preamble()
                self.found_record = True
                self.record = bytearray(raw)
                self.record_start = line_number
                self.record_end = line_number
                self.record_group = group
                self.record_kind = group
                self.record_title = text
                if match.lastindex:
                    self.record_id = int(match.group(1))
                else:
                    counter_key = f"{self.volume}:{group}"
                    self.record_id = self.record_counts.get(counter_key, 0) + 1
                key = f"{self.volume}:{group}"
                self.record_counts[key] = self.record_counts.get(key, 0) + 1
                return

        if self.record:
            self.record.extend(raw)
            self.record_end = line_number
        else:
            if not self.preamble:
                self.preamble_start = line_number
            self.preamble.extend(raw)

    def write_preamble(self) -> None:
        if not self.preamble:
            return
        self.writer.write_piece(
            f"{self.folder}/00-卷首.txt",
            bytes(self.preamble),
            volume=self.volume,
            kind="卷首",
            source_start=self.preamble_start,
            source_end=self.preamble_start + bytes(self.preamble).count(b"\n") - 1,
            title=self.title,
        )
        self.preamble.clear()

    def flush_record(self) -> None:
        if not self.record:
            return
        count_key = f"{self.volume}:{self.record_group}"
        group_size = next(
            size
            for group, _, size in RECORD_SPECS[self.volume]
            if group == self.record_group
        )
        if self.record_group in {"异闻", "遗文", "后人评"}:
            sequence_number = self.record_counts[count_key]
        else:
            sequence_number = self.record_id
        if self.volume == 5:
            group_start = (sequence_number // group_size) * group_size
            group_end = group_start + group_size - 1
        else:
            group_start = ((sequence_number - 1) // group_size) * group_size + 1
            group_end = group_start + group_size - 1
        group_folder = f"{group_start:04d}-{group_end:04d}"
        base_name = f"{self.record_group}-{sequence_number:04d}.txt"
        path = f"{self.folder}/{self.record_group}/{group_folder}/{base_name}"
        self.writer.write_piece(
            path,
            bytes(self.record),
            volume=self.volume,
            kind=self.record_kind,
            source_start=self.record_start,
            source_end=self.record_end,
            title=self.record_title,
        )
        self.record.clear()

    def finish(self) -> None:
        self.flush_record()
        if not self.found_record:
            self.write_preamble()
        elif self.preamble:
            self.write_preamble()
        self.writer.item_counts.update(self.record_counts)


class ProfileCollector:
    def __init__(self, writer: KnowledgeBaseWriter, volume: int, title: str) -> None:
        self.writer = writer
        self.volume = volume
        self.title = title
        self.folder = writer.folder(volume, title)
        self.preamble = bytearray()
        self.preamble_start = 0
        self.section = bytearray()
        self.section_start = 0
        self.section_title = ""
        self.section_number = 0
        self.section_end = 0

    def add(self, raw: bytes, line_number: int) -> None:
        text = raw.decode("utf-8").strip()
        match = re.match(r"^([一二三四五六七八九十]+)、(.+)$", text)
        if match:
            self.flush_section()
            if not self.section_title:
                self.write_preamble()
            self.section_number += 1
            self.section_title = match.group(2)
            self.section_start = line_number
            self.section_end = line_number
            self.section = bytearray(raw)
            return
        if self.section:
            self.section.extend(raw)
            self.section_end = line_number
        else:
            if not self.preamble:
                self.preamble_start = line_number
            self.preamble.extend(raw)

    def write_preamble(self) -> None:
        if not self.preamble:
            return
        count = self.preamble.count(b"\n")
        self.writer.write_piece(
            f"{self.folder}/00-卷首.txt",
            bytes(self.preamble),
            volume=self.volume,
            kind="卷首",
            source_start=self.preamble_start,
            source_end=self.preamble_start + count - 1,
            title=self.title,
        )
        self.preamble.clear()

    def flush_section(self) -> None:
        if not self.section:
            return
        name = safe_part(self.section_title)
        self.writer.write_piece(
            f"{self.folder}/{self.section_number:02d}-{name}.txt",
            bytes(self.section),
            volume=self.volume,
            kind="人物小节",
            source_start=self.section_start,
            source_end=self.section_end,
            title=self.section_title,
        )
        self.section.clear()

    def finish(self) -> None:
        self.flush_section()
        self.write_preamble()


class ChronicleCollector:
    def __init__(self, writer: KnowledgeBaseWriter, volume: int, title: str) -> None:
        self.writer = writer
        self.volume = volume
        self.title = title
        self.folder = writer.folder(volume, title)
        self.preamble = bytearray()
        self.preamble_start = 0
        self.pending = bytearray()
        self.pending_start = 0
        self.current_year = ""
        self.current_month = ""
        self.month_data = bytearray()
        self.month_start = 0
        self.month_end = 0

    def add(self, raw: bytes, line_number: int) -> None:
        text = raw.decode("utf-8").strip()
        year_heading = YEAR_HEADING.match(text)
        if year_heading:
            self.flush_month()
            self.write_preamble()
            self.current_year = year_heading.group(1)
            self.pending = bytearray(raw)
            self.pending_start = line_number
            return

        date_heading = DATE_HEADING.match(text)
        if date_heading:
            year = date_heading.group("year")
            month = date_heading.group("month")
            if self.month_data and (year, month) != (self.current_year, self.current_month):
                self.flush_month()
            if not self.month_data:
                self.current_year = year
                self.current_month = month
                self.month_start = self.pending_start or line_number
                self.month_data = self.pending
                self.pending = bytearray()
                self.pending_start = 0
            self.month_data.extend(raw)
            self.month_end = line_number
            return

        if self.month_data:
            self.month_data.extend(raw)
            self.month_end = line_number
        elif self.current_year:
            if not self.pending:
                self.pending_start = line_number
            self.pending.extend(raw)
        else:
            if not self.preamble:
                self.preamble_start = line_number
            self.preamble.extend(raw)

    def flush_month(self) -> None:
        if not self.month_data:
            return
        year_folder = safe_part(self.current_year)
        relative = f"{self.folder}/{year_folder}/{self.current_month}.txt"
        self.writer.write_piece(
            relative,
            bytes(self.month_data),
            volume=self.volume,
            kind="日记月卷",
            source_start=self.month_start,
            source_end=self.month_end,
            title=f"{self.current_year} {self.current_month}",
        )
        self.month_data.clear()
        self.current_month = ""
        self.month_start = 0
        self.month_end = 0

    def write_preamble(self) -> None:
        if not self.preamble:
            return
        self.writer.write_piece(
            f"{self.folder}/00-卷首.txt",
            bytes(self.preamble),
            volume=self.volume,
            kind="卷首",
            source_start=self.preamble_start,
            source_end=self.preamble_start + bytes(self.preamble).count(b"\n") - 1,
            title=self.title,
        )
        self.preamble.clear()

    def finish(self) -> None:
        self.flush_month()
        self.write_preamble()
        if self.pending:
            count = self.pending.count(b"\n")
            relative = f"{self.folder}/00-卷尾.txt"
            self.writer.write_piece(
                relative,
                bytes(self.pending),
                volume=self.volume,
                kind="卷尾",
                source_start=self.pending_start,
                source_end=self.pending_start + count - 1,
                title=self.title,
            )


def write_indexes(output: Path, manifest: dict) -> None:
    by_directory: dict[str, list[dict]] = {}
    directory_names: set[str] = set()
    for file_info in manifest["files"]:
        item_path = Path(file_info["path"])
        parent = str(item_path.parent).replace("\\", "/")
        by_directory.setdefault(parent, []).append(file_info)
        while parent != ".":
            directory_names.add(parent)
            parent = str(Path(parent).parent).replace("\\", "/")

    ordered_directories = sorted(
        directory_names,
        key=lambda directory: (directory.count("/"), directory),
        reverse=True,
    )
    for directory in ordered_directories:
        items = by_directory.get(directory, [])
        path = output / directory
        child_directories = sorted(
            child
            for child in path.iterdir()
            if child.is_dir()
        )
        lines = [f"# {path.name}", ""]
        if child_directories:
            lines.extend(["| 下级目录 | 条目数 |", "| --- | ---: |"])
            for child in child_directories:
                child_prefix = str(child.relative_to(output)).replace("\\", "/") + "/"
                count = sum(
                    1
                    for file_info in manifest["files"]
                    if file_info["path"].startswith(child_prefix)
                )
                lines.append(
                    f"| [{child.name}](./{child.name}/README.md) | {count} |"
                )
            lines.append("")
        if items:
            lines.extend(["| 文件 | 原文行号 | 原文条目 |", "| --- | ---: | --- |"])
            for item in items:
                file_path = Path(item["path"])
                lines.append(
                    f"| [{file_path.name}](./{file_path.name}) | "
                    f"{item['source_line_start']}–{item['source_line_end']} | "
                    f"{item['title']} |"
                )
        (path / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    root_lines = [
        "# 沈策剧情知识库",
        "",
        "目录沿用原文卷次和条目类型。卷三与卷十按纪年中的年月归档；卷四至卷九按原文编号，将案牍、人物、书信、武学、器物、方药、异闻、遗文和后人评各自拆成独立文本条目。",
        "",
        "所有 TXT 片段保留原文内容与顺序。索引列出原始文件的行号，`manifest.json` 记录源文件 SHA-256、条目路径、行号和校验值。",
        "",
        "| 原卷 | 内容 | 文件数 |",
        "| --- | --- | ---: |",
    ]
    for volume in manifest["volumes"]:
        folder = volume["folder"]
        lines = [
            f"| 卷{volume['number']} {volume['title']} | "
            f"[{folder}](./{folder}/README.md) | {volume['file_count']} |"
        ]
        root_lines.extend(lines)
    root_lines.extend(
        [
            "",
            f"源文件 `{manifest['source_file']}`，{manifest['source_bytes']:,} 字节，"
            f"{manifest['source_lines']:,} 行，共 {manifest['file_count']:,} 个文本条目。",
        ]
    )
    (output / "README.md").write_text("\n".join(root_lines) + "\n", encoding="utf-8")


def build_knowledge_base(source: Path, output: Path) -> dict:
    writer = KnowledgeBaseWriter(output)
    collector = None
    current_volume = 1

    def finish_collector() -> None:
        nonlocal collector
        if collector is not None:
            collector.finish()
            collector = None

    with source.open("rb") as stream:
        for raw in stream:
            line_number = writer.read_source_line(raw)
            heading = parse_volume_heading(raw)
            if heading is not None:
                finish_collector()
                current_volume, title = heading
                folder = writer.folder(current_volume, title)
                writer.volume_details[current_volume] = (title, folder)
                if current_volume == 2:
                    collector = ProfileCollector(writer, current_volume, title)
                elif current_volume in (3, 10):
                    collector = ChronicleCollector(writer, current_volume, title)
                elif current_volume in RECORD_SPECS:
                    collector = SectionCollector(writer, current_volume, title, "条目")
                else:
                    collector = SectionCollector(writer, current_volume, title, "正文")

            if collector is None:
                if not writer.files and current_volume == 1:
                    if current_volume not in writer.volume_details:
                        title = "目录与体例"
                        folder = writer.folder(1, title)
                        writer.volume_details[1] = (title, folder)
                        collector = SectionCollector(writer, 1, title, "卷首")
                if collector is None:
                    raise RuntimeError(f"No section for source line {line_number}")
            collector.add(raw, line_number)

    finish_collector()
    return writer.finish()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Path to the original UTF-8 TXT file")
    parser.add_argument("output", type=Path, help="Output knowledge-base directory")
    args = parser.parse_args()
    manifest = build_knowledge_base(args.source, args.output)
    print(
        f"Created {manifest['file_count']:,} structured text files across "
        f"{len(manifest['volumes'])} volume folders from {manifest['source_lines']:,} source lines."
    )
    print(f"Source SHA-256: {manifest['source_sha256']}")


if __name__ == "__main__":
    main()

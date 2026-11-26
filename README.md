# 沈策古风剧情设定知识库

本仓库将《沈策古风剧情设定完整版》整理成按卷次、年月和原文条目编号浏览的知识库。原文共 935,682 行、100,683,627 字节，现拆分为 4,963 份 TXT 条目。拆分保留了原文内容和顺序，每份 TXT 都能在索引中查到对应原文行号。

## 文件结构

- [知识库总索引](./knowledge-base/README.md) 按卷次列出目录和条目数量。
- `knowledge-base/01-目录与体例/` 收录开篇总纲、目录和体例说明。
- `knowledge-base/02-本传/` 将人物本传按“身、性、技、病、癖、言”六节拆分。
- `knowledge-base/03-编年/` 按永嘉年号与月份归档逐日日记。
- `knowledge-base/04-案牍/` 按案卷编号拆分案件记录。
- `knowledge-base/05-关系/` 按人物档案编号拆分关系条目。
- `knowledge-base/06-书简/` 按书信编号拆分书简。
- `knowledge-base/07-武学/` 按招式编号拆分武学条目。
- `knowledge-base/08-器物/` 分开整理器物与方药，并按原文编号建档。
- `knowledge-base/09-异闻/` 分开整理异闻、遗文和后人评。
- `knowledge-base/10-后编/` 按永嘉年号与月份归档后编日记。
- `knowledge-base/manifest.json` 记录源文件 SHA-256、每份文件的行号和校验值。
- `tools/split_txt.py` 按原文结构重新生成知识库。

案牍、人物、书信、武学、器物、方药、异闻、遗文和后人评各自按原文编号拆成单条文件。编年卷按原文的年份和月份分组。分组目录中的 `README.md` 提供该组的条目索引。

## 下载

可在 [v2.0.0 Release](https://github.com/bilbillm/shence-ancient-story-settings/releases/tag/v2.0.0) 下载打包后的知识库。原始单文件 TXT 保留在 [v1.0.0 Release](https://github.com/bilbillm/shence-ancient-story-settings/releases/tag/v1.0.0)。

## 重新生成

将原始 TXT 路径作为第一个参数，并为输出目录指定一个尚不存在或为空的路径。

```powershell
python -X utf8 tools/split_txt.py "路径\沈策古风剧情设定完整版(1).txt" "knowledge-base-new"
```

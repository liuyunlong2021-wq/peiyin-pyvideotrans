import json
import re
import shutil
from pathlib import Path

from videotrans.task.taskcfg import SrtItem
from videotrans.util.help_srt import get_srt_from_list, get_subtitle_from_srt, is_srt_string


def _cell(value):
    return str(value or "").replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>").strip()


def _uncell(value):
    value = value.strip().replace("<br>", "\n")
    return value.replace("\\|", "|").replace("\\\\", "\\")


def _split_row(line):
    cells, current, escaped = [], [], False
    for char in line.strip().strip("|"):
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            current.append(char)
            escaped = True
        elif char == "|":
            cells.append(_uncell("".join(current)))
            current = []
        else:
            current.append(char)
    cells.append(_uncell("".join(current)))
    return cells


def _table(path, headers):
    path = Path(path)
    lines = path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if _split_row(line) == headers:
            rows = []
            for line_number, row in enumerate(lines[index + 2:], start=index + 3):
                if not row.strip().startswith("|"):
                    break
                cells = _split_row(row)
                if len(cells) != len(headers):
                    raise ValueError(f"{path}: Markdown 第{line_number}行应有{len(headers)}列，实际{len(cells)}列")
                rows.append(dict(zip(headers, cells)))
            return rows
    raise ValueError(f"{path}: 缺少表头 {' | '.join(headers)}")


def set_document_status(path, status):
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(r"(?m)^- 状态：.*$", f"- 状态：{status}", text, count=1)
    if count != 1:
        raise ValueError(f"{path}: 缺少状态字段")
    path.write_text(updated, encoding="utf-8")
    return path


def read_strict_srt(path):
    path = Path(path)
    try:
        content = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        content = path.read_text(encoding="gbk")
    if not is_srt_string(content):
        raise ValueError(f"字幕为空或格式无效：{path}")
    subtitles = get_subtitle_from_srt(path)
    if not subtitles or any(not item["text"].strip() or item["end_time"] <= item["start_time"]
                            for item in subtitles):
        raise ValueError(f"字幕为空、时间错误或格式无效：{path}")
    return subtitles


def import_recognition_srt(project, episode, srt_file, model="", speakers=None, events=None,
                           write_derived=True, page_file=None, update_state=True):
    from videotrans.util.production_project import ensure_episode, episode_name, update_stage

    project, episode = Path(project), episode_name(episode)
    ensure_episode(project, episode)
    subtitles = read_strict_srt(srt_file)
    speakers = speakers or []
    events = events or []
    lines = [
        f"# {episode}中文识别", "", f"- 来源字幕：[识别.srt](../../../.raw/media/文件/{episode}/识别.srt)",
        f"- 识别模型：{_cell(model) or '未记录'}", "- 状态：待校对", "",
        "| 行 | 开始 | 结束 | 中文原文 | 音频说话人 | 声音事件 |", "|---:|---:|---:|---|---|---|",
    ]
    for index, item in enumerate(subtitles):
        speaker = speakers[index] if index < len(speakers) else item.get('spk', '')
        event = events[index] if index < len(events) else ''
        lines.append(f"| {item['line']} | {item['startraw']} | {item['endraw']} | {_cell(item['text'])} | {_cell(speaker)} | {_cell(event)} |")
    page = Path(page_file) if page_file else project / "wiki/集数" / episode / "中文识别.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if write_derived:
        destination = project / ".raw/media/文件" / episode / "识别.srt"
        destination.write_text(get_srt_from_list(subtitles), encoding="utf-8")
    if update_state:
        update_stage(project, episode, "中文识别", "待校对", invalidate_downstream=True)
    return page


def recognition_rows(project, episode):
    from videotrans.util.production_project import episode_name

    path = Path(project) / "wiki/集数" / episode_name(episode) / "中文识别.md"
    headers = ["行", "开始", "结束", "中文原文", "音频说话人", "声音事件"]
    rows = _table(path, headers)
    result = []
    for expected, row in enumerate(rows, start=1):
        try:
            line = int(row["行"])
        except ValueError as error:
            raise ValueError(f"{path}: 字幕行号必须是数字：{row['行']}") from error
        if line != expected:
            raise ValueError(f"{path}: 第{expected}条字幕的行号应为{expected}，实际为{line}")
        pattern = r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})"
        start, end = re.fullmatch(pattern, row["开始"]), re.fullmatch(pattern, row["结束"])
        if not start or not end:
            raise ValueError(f"{path}: 第{line}行时间格式错误")
        to_ms = lambda match: (((int(match[1]) * 60 + int(match[2])) * 60 + int(match[3])) * 1000
                               + int(match[4]))
        if to_ms(end) <= to_ms(start):
            raise ValueError(f"{path}: 第{line}行结束时间必须晚于开始时间")
        if not row["中文原文"].strip():
            raise ValueError(f"{path}: 第{line}行中文原文不能为空")
        result.append(row)
    if not result:
        raise ValueError(f"{path}: 没有字幕数据")
    return result


def export_recognition_srt(project, episode, destination=None):
    from videotrans.util.production_project import episode_name

    project, episode = Path(project), episode_name(episode)
    items = [SrtItem(line=int(row["行"]), startraw=row["开始"], endraw=row["结束"], text=row["中文原文"])
             for row in recognition_rows(project, episode)]
    destination = Path(destination) if destination else project / ".raw/media/文件" / episode / "识别.srt"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(get_srt_from_list(items), encoding="utf-8")
    return destination


def import_translation_srt(project, episode, target_srt, model="", assignments=None, emotions=None, turns=None,
                           page_file=None, update_state=True):
    from videotrans.util.production_project import episode_name, update_stage

    project, episode = Path(project), episode_name(episode)
    source, target = recognition_rows(project, episode), get_subtitle_from_srt(target_srt)
    if len(source) != len(target):
        raise ValueError(f"翻译字幕共{len(target)}行，中文识别共{len(source)}行，必须严格一一对应")
    count = len(source)
    assignments = assignments or [row["音频说话人"] or f"Speaker{index}" for index, row in enumerate(source, 1)]
    emotions = emotions or ["neutral"] * count
    turns = turns or [False] * count
    if not all(len(values) == count for values in (assignments, emotions, turns)):
        raise ValueError("人物、情绪和接上句数组必须与字幕行数一致")
    lines = [
        f"# {episode}翻译与轮次", "", f"- 中文来源：[[集数/{episode}/中文识别]]",
        f"- 翻译模型：{_cell(model) or '未记录'}", "- 状态：待校对", "",
        "| 行 | 角色 | 情绪 | 接上句 | 英文台词 | 中文原文 |", "|---:|---|---|---|---|---|",
    ]
    for index, (zh, en) in enumerate(zip(source, target)):
        role = _cell(assignments[index])
        if role and not role.startswith("Speaker"):
            role = f"[[角色/{role}/配音档案]]"
        lines.append(
            f"| {index + 1} | {role} | {_cell(emotions[index])} | {'是' if turns[index] else '否'} | "
            f"{_cell(en['text'])} | {_cell(zh['中文原文'])} |")
    page = Path(page_file) if page_file else project / "wiki/集数" / episode / "翻译与轮次.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if update_state:
        update_stage(project, episode, "剧情翻译与轮次", "待校对", invalidate_downstream=True)
    return page


def ensure_character_pages(project, character, episode=None):
    folder = Path(project) / "wiki/角色" / character
    folder.mkdir(parents=True, exist_ok=True)
    profile = folder / "角色档案.md"
    voice = folder / "配音档案.md"
    if not profile.exists():
        profile.write_text(f"# {character}角色档案\n\n- 角色名：{character}\n- 出现集数：\n", encoding="utf-8")
    if episode:
        link = f"[[集数/{episode}/翻译与轮次]]"
        text = profile.read_text(encoding="utf-8")
        if link not in text:
            text = re.sub(r"(?m)^- 出现集数：(.*)$", lambda match: f"- 出现集数：{match.group(1).strip()} {link}".rstrip(), text)
            profile.write_text(text, encoding="utf-8")
    if not voice.exists():
        voice.write_text(
            f"# {character}配音档案\n\n- 角色：[[角色/{character}/角色档案]]\n- 默认身份参考：\n\n"
            "| 情绪 | 参考音频 | 参考文本 | 来源 | 时长 | 状态 | 备注 |\n"
            "|---|---|---|---|---:|---|---|\n", encoding="utf-8")
    return voice


def build_voice_library_snapshot(project, destination):
    from videotrans.util.production_project import validate_media

    project, destination = Path(project).resolve(), Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "refs").mkdir(exist_ok=True)
    (destination / "embeddings").mkdir(exist_ok=True)
    characters = []
    headers = ["情绪", "参考音频", "参考文本", "来源", "时长", "状态", "备注"]
    for profile in sorted((project / "wiki/角色").glob("*/配音档案.md")):
        performances = []
        for index, row in enumerate(_table(profile, headers), start=1):
            if row["状态"] != "已确认":
                continue
            if not row["情绪"].strip():
                raise ValueError(f"{profile}: 第{index}条已确认参考音缺少情绪")
            if not row["参考文本"].strip():
                raise ValueError(f"{profile}: 第{index}条已确认参考音缺少参考文本")
            match = re.search(r"\]\((.*?)\)", row["参考音频"])
            if not match:
                raise ValueError(f"{profile}: 第{index}条已确认参考音缺少 Markdown 文件链接")
            audio = (profile.parent / match.group(1)).resolve()
            if not audio.is_file() or project not in audio.parents:
                raise ValueError(f"{profile}: 参考音不存在或不在项目内：{audio}")
            validate_media(audio, audio=True)
            stem = f"{profile.parent.name}_{row['情绪'] or 'neutral'}_{index:02d}"
            audio_name = f"{stem}{audio.suffix.lower() or '.wav'}"
            shutil.copy2(audio, destination / "refs" / audio_name)
            embedding = audio.with_suffix(".npy")
            embedding_name = ""
            if embedding.is_file():
                embedding_name = f"{stem}.npy"
                shutil.copy2(embedding, destination / "embeddings" / embedding_name)
            duration = re.sub(r"[^0-9.]", "", row["时长"])
            if float(duration or 0) <= 0:
                raise ValueError(f"{profile}: 第{index}条已确认参考音时长必须大于 0")
            performances.append({
                "id": stem, "audio": f"refs/{audio_name}",
                "embedding": f"embeddings/{embedding_name}" if embedding_name else "",
                "text": row["参考文本"], "duration_ms": int(float(duration or 0) * 1000),
                "emotion": row["情绪"] or "neutral", "events": [],
                "source": {"episode": row["来源"], "line_start": None, "line_end": None},
                "approved": True,
            })
        if performances:
            characters.append({
                "id": profile.parent.name, "name": profile.parent.name,
                "identity_reference": performances[0]["audio"], "performances": performances,
            })
    (destination / "library.json").write_text(
        json.dumps({"version": 1, "characters": characters}, ensure_ascii=False, indent=2), encoding="utf-8")
    return destination


def export_translation_task(project, episode, output_dir=None):
    from videotrans.util.production_project import episode_name

    project, episode = Path(project), episode_name(episode)
    page = project / "wiki/集数" / episode / "翻译与轮次.md"
    headers = ["行", "角色", "情绪", "接上句", "英文台词", "中文原文"]
    rows, source = _table(page, headers), recognition_rows(project, episode)
    if len(rows) != len(source):
        raise ValueError(f"{page}: 翻译共{len(rows)}行，中文识别共{len(source)}行")
    assignments, emotions, turns, items = [], [], [], []
    for expected, (row, zh) in enumerate(zip(rows, source), start=1):
        try:
            line = int(row["行"])
        except ValueError as error:
            raise ValueError(f"{page}: 行号必须是数字：{row['行']}") from error
        if line != expected:
            raise ValueError(f"{page}: 第{expected}条字幕的行号应为{expected}，实际为{line}")
        role = re.sub(r"^\[\[角色/(.*?)/配音档案\]\]$", r"\1", row["角色"]).strip()
        if not role:
            raise ValueError(f"{page}: 第{line}行角色不能为空")
        if role:
            ensure_character_pages(project, role, episode)
        emotion = row["情绪"].strip() or "neutral"
        join_value = row["接上句"].strip()
        if join_value not in ("是", "否", "true", "false", "True", "False", "1", "0"):
            raise ValueError(f"{page}: 第{line}行接上句只能填写“是”或“否”")
        joined = join_value in ("是", "true", "True", "1")
        if joined and line == 1:
            raise ValueError(f"{page}: 第1行不能接上句")
        if joined and (role != assignments[-1] or emotion != emotions[-1]):
            raise ValueError(f"{page}: 第{line}行接上句要求与第{line - 1}行人物和情绪一致")
        if not row["英文台词"].strip():
            raise ValueError(f"{page}: 第{line}行英文台词不能为空")
        assignments.append(role)
        emotions.append(emotion)
        turns.append(joined and line > 1)
        items.append(SrtItem(line=line, startraw=zh["开始"], endraw=zh["结束"], text=row["英文台词"]))
    output_dir = Path(output_dir) if output_dir else project / ".raw/media/文件" / episode
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "英文.srt").write_text(get_srt_from_list(items), encoding="utf-8")
    for name, values in (("speaker_assignments.json", assignments), ("emotion_overrides.json", emotions), ("turns.json", turns)):
        (output_dir / name).write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding="utf-8")
    snapshot = build_voice_library_snapshot(project, output_dir / "voice-library")
    (output_dir / "voice_library.json").write_text(
        json.dumps({"path": snapshot.as_posix(), "add_current": False}, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_dir / "英文.srt"


def write_dubbing_page(project, episode, queue, turn_files, reference_files, page_file=None):
    from videotrans.util.production_project import episode_name

    project, episode = Path(project), episode_name(episode)
    lines = [
        f"# {episode}英文配音", "", f"- 翻译来源：[[集数/{episode}/翻译与轮次]]",
        f"- 英文总轨：[英文配音.wav](../../../.raw/media/音频/{episode}/英文配音.wav)",
        "- 状态：已完成", "",
        "| 轮次 | 字幕行 | 角色 | 情绪 | 参考音 | 英文音频 | 状态 |",
        "|---:|---|---|---|---|---|---|",
    ]
    for index, (item, turn_file, reference_file) in enumerate(
            zip(queue, turn_files, reference_files), start=1):
        children = item.get("_subtitle_items") or []
        first = int(item.get("line", index))
        last = int(children[-1].get("line", first)) if children else first
        subtitle_lines = str(first) if first == last else f"{first}-{last}"
        character = str(item.get("_speaker") or "未标注").strip()
        role = f"[[角色/{character}/配音档案]]" \
            if (project / "wiki/角色" / character / "配音档案.md").is_file() else character
        turn_link = f"../../../.raw/media/音频/{episode}/英文配音/{Path(turn_file).name}"
        ref_link = f"../../../.raw/media/音频/{episode}/英文配音/{Path(reference_file).name}"
        lines.append(
            f"| {index} | {subtitle_lines} | {_cell(role)} | {_cell(item.get('emotion') or 'neutral')} | "
            f"[{Path(reference_file).name}]({ref_link}) | [{Path(turn_file).name}]({turn_link}) | 已完成 |")
    page = Path(page_file) if page_file else project / "wiki/集数" / episode / "英文配音.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return page


def write_calibration_page(project, episode, final=False, page_file=None):
    from videotrans.util.production_project import episode_name

    project, episode = Path(project), episode_name(episode)
    lines = [
        f"# {episode}字幕校准与合成", "",
        f"- 英文总轨：[英文配音.wav](../../../.raw/media/音频/{episode}/英文配音.wav)",
        f"- 机器校准字幕：[英文-机器校准.srt](../../../.raw/media/文件/{episode}/英文-机器校准.srt)",
        f"- 已确认字幕：[英文-已确认.srt](../../../.raw/media/文件/{episode}/英文-已确认.srt)",
        "- 硬字幕：华康黑体 W9，92px 白字，4px #151210 描边，2px 阴影，底部 25%，居中，去标点",
    ]
    if final:
        lines.extend((
            f"- 最终视频：[最终视频.mp4](../../../.raw/media/视频/{episode}/最终视频.mp4)",
            "- 状态：已完成",
        ))
    else:
        lines.append("- 状态：已确认")
    page = Path(page_file) if page_file else project / "wiki/集数" / episode / "字幕校准与合成.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return page

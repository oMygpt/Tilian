import os
import re
import argparse
from pathlib import Path

def normalize_text(s):
    return s.replace("\r\n", "\n").replace("\r", "\n")

def chinese_numeral_to_int(s):
    units = {"零":0,"〇":0,"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9}
    ten = "十"
    if not any(ch in s for ch in units) and ten not in s:
        return None
    if s == ten:
        return 10
    total = 0
    if ten in s:
        parts = s.split(ten)
        left = parts[0]
        right = parts[1] if len(parts) > 1 else ""
        l = units.get(left, 1) if left != "" else 1
        r = units.get(right, 0) if right != "" else 0
        total = l * 10 + r
    else:
        total = sum(units.get(ch, 0) for ch in s)
    return total if total > 0 else None

def extract_number(title):
    m = re.search(r"(\d+)", title)
    if m:
        return int(m.group(1))
    m2 = re.search(r"第([一二三四五六七八九十零〇]+)章", title)
    if m2:
        return chinese_numeral_to_int(m2.group(1))
    m3 = re.search(r"Chapter\s+(\d+)", title, re.IGNORECASE)
    if m3:
        return int(m3.group(1))
    return None

def is_md_heading(line):
    return bool(re.match(r"^\s*#{1,6}\s+", line))

def clean_title(line):
    return re.sub(r"^\s*#{1,6}\s+", "", line).strip()

def header_confidence(line, prev_blank, next_blank):
    score = 0.0
    lm = line.strip()
    strong = bool(re.match(r"^(第[一二三四五六七八九十零〇0-9]+章|Chapter\s+\d+|CHAPTER\s+\d+|附录\s*[A-Za-z0-9一二三四五六七八九十零〇]?)", lm))
    if strong:
        score += 1.0
    if is_md_heading(line):
        score += 0.8
    isolation = 0
    if prev_blank >= 1:
        isolation += 0.15
    if next_blank >= 1:
        isolation += 0.15
    score += isolation
    length = len(lm)
    if length > 120:
        score -= 0.5
    elif length > 80:
        score -= 0.2
    return score

def detect_toc_regions(lines, candidates):
    regions = []
    if not candidates:
        return regions
    n = len(lines)
    idxs = [i for i,_ in candidates]
    gaps = []
    for a,b in zip(idxs, idxs[1:]):
        gaps.append(b - a)
    if not gaps:
        return regions
    small_gap = 10
    cluster = []
    for i in range(len(idxs)):
        if not cluster:
            cluster = [idxs[i]]
        else:
            if idxs[i] - cluster[-1] <= small_gap:
                cluster.append(idxs[i])
            else:
                if len(cluster) >= 4 and (cluster[0] < n * 0.2):
                    regions.append((cluster[0], cluster[-1]))
                cluster = [idxs[i]]
    if len(cluster) >= 4 and (cluster[0] < n * 0.2):
        regions.append((cluster[0], cluster[-1]))
    return regions

def in_regions(pos, regions):
    for a,b in regions:
        if a <= pos <= b:
            return True
    return False

def should_ignore_line_as_toc(line):
    s = line.strip()
    if s.startswith("- ") or s.startswith("* "):
        if "](" in s:
            return True
    if re.match(r"^\s*\d+\.\s+\[.*\]\(.*\)", s):
        return True
    if re.match(r"^\s*目录\s*$", s) or re.match(r"^\s*Table of Contents\s*$", s, re.IGNORECASE):
        return True
    if re.match(r"^#\s*第[一二三四五六七八九十零〇0-9]+章.*\s\d+\s*$", s):
        return True
    return False

def select_chapter_heads(lines, granularity="chapter"):
    blank_counts_prev = []
    c = 0
    for line in lines:
        if line.strip() == "":
            c += 1
        else:
            c = 0
        blank_counts_prev.append(c)
    blank_counts_next = [0]*len(lines)
    c = 0
    for i in range(len(lines)-1, -1, -1):
        if lines[i].strip() == "":
            c += 1
        else:
            c = 0
        blank_counts_next[i] = c
    candidates = []
    for i,line in enumerate(lines):
        if should_ignore_line_as_toc(line):
            continue
        conf = header_confidence(line, blank_counts_prev[i], blank_counts_next[i])
        if conf >= 0.8:
            title = clean_title(line) if is_md_heading(line) else line.strip()
            num = extract_number(title)
            level = 0
            m = re.match(r"^(\s*#{1,6})\s+", line)
            if m:
                level = len(m.group(1).strip())
            if granularity == "chapter":
                strong_chapter = bool(re.match(r"^(第[一二三四五六七八九十零〇0-9]+章|Chapter\s+\d+|CHAPTER\s+\d+|附录\s*[A-Za-z0-9一二三四五六七八九十零〇]?)", title))
                if is_md_heading(line) and level == 1 and strong_chapter:
                    candidates.append((i, conf, title, num, level))
            else:
                section_num = bool(re.match(r"^\d+(\.\d+)+", title))
                if strong_chapter or section_num or (level <= 2 and is_md_heading(line)):
                    candidates.append((i, conf, title, num, level))
    regions = detect_toc_regions(lines, [(i,conf) for i,conf,_,_,_ in candidates])
    filtered = [x for x in candidates if not in_regions(x[0], regions)]
    if not filtered:
        fallback = []
        for i,line in enumerate(lines):
            if is_md_heading(line):
                title = clean_title(line)
                level = len(re.match(r"^(\s*#{1,6})\s+", line).group(1).strip())
                if level == 1:
                    if granularity == "chapter":
                        if re.match(r"^(第[一二三四五六七八九十零〇0-9]+章|Chapter\s+\d+|CHAPTER\s+\d+|附录\s*[A-Za-z0-9一二三四五六七八九十零〇]?)", title):
                            fallback.append((i, 0.7, title, extract_number(title), level))
                    else:
                        fallback.append((i, 0.7, title, extract_number(title), level))
        filtered = fallback
    filtered.sort(key=lambda x: x[0])
    seq_adjusted = []
    last_num = None
    for i,conf,title,num,level in filtered:
        adj = conf
        if num is not None:
            if last_num is None:
                adj += 0.1
            else:
                if num == last_num or num == last_num + 1:
                    adj += 0.2
                else:
                    adj -= 0.2
            last_num = num
        seq_adjusted.append((i, adj, title, num, level))
    heads = [x for x in seq_adjusted if x[1] >= 0.8]
    if not heads and seq_adjusted:
        heads = seq_adjusted
    primary = []
    for h in heads:
        i,conf,title,num,level = h
        if granularity == "chapter":
            if level == 1 and re.match(r"^(第[一二三四五六七八九十零〇0-9]+章|Chapter\s+\d+|CHAPTER\s+\d+|附录\s*[A-Za-z0-9一二三四五六七八九十零〇]?)", title):
                primary.append(h)
        else:
            if num is not None or level <= 2:
                primary.append(h)
    if not primary:
        primary = heads
    primary.sort(key=lambda x: x[0])
    return primary

def parse_toc_chapters(lines):
    toc = []
    for i, line in enumerate(lines):
        s = line.strip()
        m = re.match(r"^#\s*(第[一二三四五六七八九十零〇0-9]+章)\s+(.*?)\s(\d+)\s*$", s)
        if m:
            raw = m.group(1)
            title = m.group(2)
            num = extract_number(raw)
            if num is not None:
                toc.append((num, title, i))
    return toc

def find_body_chapter_starts(lines, toc_entries):
    starts = []
    n = len(lines)
    toc_map = {num: title for (num, title, _) in toc_entries}
    for (num, _title, _idx) in toc_entries:
        found = None
        pat_num_h1 = re.compile(rf"^#\s*{num}\b")
        pat_ch_h1 = re.compile(r"^#\s*第[一二三四五六七八九十零〇0-9]+章(?!.*\s\d+\s*$)")
        for j in range(n):
            s = lines[j].strip()
            if pat_num_h1.match(s):
                found = j
                break
        if found is None:
            for j in range(n):
                s = lines[j].strip()
                if pat_ch_h1.match(s):
                    if extract_number(clean_title(s)) == num:
                        found = j
                        break
        if found is not None:
            pretty_title = f"第{num}章 {toc_map.get(num, '').strip()}".strip()
            starts.append((found, 1.0, pretty_title, num, 1))
    starts.sort(key=lambda x: x[0])
    return starts

def sanitize_filename(s):
    s = re.sub(r"[\\/:*?\"<>|]", "_", s)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > 80:
        s = s[:80]
    return s

def segment_file(src_path, out_dir, granularity="chapter"):
    text = Path(src_path).read_text(encoding="utf-8", errors="ignore")
    text = normalize_text(text)
    lines = text.split("\n")
    heads = select_chapter_heads(lines, granularity=granularity)
    if granularity == "chapter":
        toc_entries = parse_toc_chapters(lines)
        body_starts = find_body_chapter_starts(lines, toc_entries)
        if body_starts:
            heads = body_starts
    if not heads:
        base = Path(src_path).stem
        name = sanitize_filename(base)
        out = Path(out_dir) / f"{name}__chapter_1__full.md"
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        Path(out).write_text(text, encoding="utf-8")
        return [str(out)]
    starts = [h[0] for h in heads]
    chunks = []
    for idx, start in enumerate(starts):
        end = starts[idx+1] if idx+1 < len(starts) else len(lines)
        chunk_lines = lines[start:end]
        title = heads[idx][2]
        num = heads[idx][3]
        base = Path(src_path).stem
        idx_str = str(idx+1)
        title_part = sanitize_filename(title) or f"chapter_{idx_str}"
        fn = f"{base}__chapter_{idx_str}__{title_part}.md"
        out = Path(out_dir) / fn
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        Path(out).write_text("\n".join(chunk_lines), encoding="utf-8")
        chunks.append(str(out))
    return chunks

def process_folder(src_dir, out_dir, granularity="chapter"):
    created = []
    src_path = Path(src_dir)
    out_dir_abs = str(Path(out_dir).resolve())
    if src_path.is_file() and src_path.suffix.lower() == ".md":
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        created.extend(segment_file(str(src_path), Path(out_dir), granularity=granularity))
        return created
    for root, _, files in os.walk(src_dir):
        if str(Path(root).resolve()).startswith(out_dir_abs):
            continue
        for f in files:
            if f.lower().endswith(".md"):
                p = os.path.join(root, f)
                rel_root = os.path.relpath(root, src_dir)
                target_dir = Path(out_dir) / rel_root
                created.extend(segment_file(p, target_dir, granularity=granularity))
    return created

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", required=True)
    parser.add_argument("--out", default="segmented_md")
    parser.add_argument("--granularity", choices=["chapter","section"], default="chapter")
    args = parser.parse_args()
    created = process_folder(args.src, args.out, granularity=args.granularity)
    for p in created:
        print(p)

if __name__ == "__main__":
    main()

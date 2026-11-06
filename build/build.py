#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""备考刷题 构建脚本：合并解析切片 → 注入数据 → 语法检查 → 产出成品"""
import json, io, os, glob, re, subprocess, sys, hashlib

BUILD = os.path.dirname(os.path.abspath(__file__))
SRC_TXT = os.path.join(BUILD, "data")   # 题库源数据（nk/fk/jj/kf.json + snapshot + slices）
APP = os.path.join(BUILD, "..")
BANK_META = [
    ("nk", "内控类", "#2563eb"),
    ("fk", "风控类", "#ea580c"),
    ("jj", "纪检类", "#dc2626"),
    ("kf", "客服类", "#059669"),
]
EXAM_DATE = "2026-11-28"

def step(msg): print(f"· {msg}")

def merge():
    """把 /tmp/tiku/slices 里补写的 analysis 合并回主 JSON，并做完整性 diff"""
    snap = json.load(io.open(f"{SRC_TXT}/snapshot.json", encoding="utf-8"))
    updates = {}
    for pat in ("slices/*.json", "slices2/*.json"):
        for f in glob.glob(f"{SRC_TXT}/{pat}"):
            for q in json.load(io.open(f, encoding="utf-8")):
                if (q.get("analysis") or "").strip():
                    updates[q["id"]] = q["analysis"]
    step(f"待合并解析 {len(updates)} 条")
    bad_len, empty = [], []
    total_merged = 0
    for bid, name, _c in BANK_META:
        p = f"{SRC_TXT}/{bid}.json"
        d = json.load(io.open(p, encoding="utf-8"))
        for q in d["questions"]:
            s = snap.get(q["id"])
            assert s, f"{q['id']} 不在快照"
            # 完整性：除 analysis 外所有字段必须与快照一致
            cur = [q["stem"], q["options"], q["answer"], q["basis"], q["type"]]
            if cur != s:
                raise SystemExit(f"完整性校验失败 {q['id']}:\n快照 {s}\n现状 {cur}")
            if q["id"] in updates:
                q["analysis"] = updates[q["id"]]; total_merged += 1
            a = (q["analysis"] or "").strip()
            if a in ("", "略"):
                empty.append(q["id"])
            elif len(a) < 15:
                bad_len.append(q["id"])
        json.dump(d, io.open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 跨库唯一性 + 前缀归属
    seen = {}
    for bid, name, _c in BANK_META:
        d = json.load(io.open(f"{SRC_TXT}/{bid}.json", encoding="utf-8"))
        for q in d["questions"]:
            if q["id"] in seen:
                raise SystemExit(f"重复题目 id: {q['id']}")
            seen[q["id"]] = bid
            if not q["id"].startswith(bid + "-"):
                raise SystemExit(f"id 前缀与库不符: {q['id']}")
    step(f"id 唯一性校验通过（{len(seen)} 题）")
    step(f"已合并 {total_merged} 条；空解析 {len(empty)}；过短 {len(bad_len)}")
    if empty: print("  空解析:", empty[:10])
    if bad_len: print("  过短:", bad_len[:10])
    return len(empty)

def build_data_js():
    banks = []
    for bid, name, color in BANK_META:
        d = json.load(io.open(f"{SRC_TXT}/{bid}.json", encoding="utf-8"))
        qs = []
        for q in d["questions"]:
            qs.append({"id": q["id"], "t": q["type"], "s": q["stem"],
                       "o": q["options"], "a": q["answer"],
                       "x": q["analysis"] or "", "b": q["basis"] or ""})
        banks.append({"id": bid, "name": name, "color": color, "questions": qs})
    payload = json.dumps({"examDate": EXAM_DATE, "banks": banks},
                         ensure_ascii=False, separators=(",", ":"))
    if "</script" in payload or "<!--" in payload:
        raise SystemExit("题库数据含有 </script 或 <!--，会破坏 HTML 结构")
    return f'window.__TIKU__={payload};'

def check_syntax(html):
    """抽出每个 <script> 块跑 node --check"""
    blocks = re.findall(r"<script[^>]*>(.*?)</script>", html, re.S)
    ok = True
    for i, b in enumerate(blocks):
        if not b.strip() or "/*__" in b:
            continue
        p = f"/tmp/bk_block_{i}.js"
        io.open(p, "w", encoding="utf-8").write(b)
        r = subprocess.run(["node", "--check", p], capture_output=True, text=True)
        if r.returncode != 0:
            ok = False
            print(f"  ✗ script块{i} 语法错误:\n{r.stderr[:800]}")
    return ok

def main():
    print("== 备考刷题 构建 ==")
    empty = merge()
    data_js = build_data_js()
    step(f"数据体积 {len(data_js)/1024:.0f} KB")
    src = io.open(os.path.join(BUILD, "src_app.html"), encoding="utf-8").read()
    lf = io.open(os.path.join(BUILD, "localforage.min.js"), encoding="utf-8").read()
    out = (src.replace("/*__LF_INJECT__*/", lf)
              .replace("/*__DATA_INJECT__*/", data_js))
    if "__DATA_INJECT__" in out or "__LF_INJECT__" in out:
        raise SystemExit("注入失败：占位符仍在")
    step(f"script 语法检查（node --check）…")
    if not check_syntax(out):
        raise SystemExit("语法检查未通过，停止产出")
    step("语法全部通过")
    mobile = os.path.join(APP, "备考刷题_手机版.html")
    io.open(mobile, "w", encoding="utf-8").write(out)
    io.open(os.path.join(APP, "index.html"), "w", encoding="utf-8").write(out)
    step(f"产出 {mobile}  ({len(out)/1024:.0f} KB)")
    print(f"结果: {'完整' if empty==0 else f'警告:仍有{empty}条空解析'}")

if __name__ == "__main__":
    main()

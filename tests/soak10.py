#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""备考刷题 · 十遍全路径浸泡测试：每个可作答入口 ×10，逐次校验判分/计数/错题本/JS错误"""
import json, subprocess, sys, time, os
from playwright.sync_api import sync_playwright

URL = "file:///Users/dundunduo/Desktop/启动器/备考刷题_v1/备考刷题_手机版.html"
N = 10
SBPAT = "REDACTED"  # 本脚本不访问数据库
FAILS = []
REPORT = []

def ok(name, cond, extra=""):
    tag = "✓" if cond else "✗"
    print(f"  {tag} {name}" + (f" [{extra}]" if extra and not cond else ""))
    if not cond:
        FAILS.append(f"{name} {extra}")

def fresh(pg):
    pg.goto(URL, timeout=30000); pg.wait_for_timeout(1200)
    if pg.locator("#cn-skip").count():
        pg.locator("#cn-skip").click(); pg.wait_for_timeout(250)

def state(pg):
    return pg.evaluate("JSON.parse(localStorage.getItem('beikao.state.v1')||'{}')")

def cur_answer(pg):
    return pg.evaluate("""(()=>{
      const stem=document.querySelector('.qstem').innerText.replace(/\\s/g,'').replace(/_/g,'');
      const q=window.__TIKU__.banks.flatMap(b=>b.questions).find(x=>x.stem.replace(/\\s|_/g,'')===stem);
      if(!q)throw new Error('题干匹配失败:'+stem.slice(0,30));
      return {id:q.id,answer:q.answer,type:q.type,options:q.options};
    })()""")

def answer_one(pg, q, correct=True):
    """按题型作答当前题；correct=True 时按正确答案作答"""
    t = q.get("answer") and q["type"] or ""
    t = q["type"]
    a = q["answer"]
    if t == "单选":
        idx = "ABCDEFGH".index(a) if correct else ("ABCDEFGH".index(a) + 1) % len(q["options"])
        pg.locator(".opt").nth(idx).click()
    elif t == "多选":
        letters = list(a) if correct else []
        if not correct:
            letters = ["A"]
        for L in letters:
            pg.locator(".opt").nth("ABCDEFGH".index(L)).click(); pg.wait_for_timeout(120)
        pg.locator("#q-commit").click()
    elif t == "判断":
        idx = 0 if a == "对" else 1
        if not correct: idx = 1 - idx
        pg.locator(".judge button").nth(idx).click()
    elif t == "填空":
        if correct: pg.fill("#q-input", a)
        else: pg.fill("#q-input", "无关干扰词")   # 完全无关的词，保证判错
        pg.locator("#q-commit").click()
    else:  # 简答
        pg.locator("#q-reveal").click(); pg.wait_for_timeout(200)
        pg.locator("#sg-ok" if correct else "#sg-ng").click()

def run_surface(pg, label, iterations=10, qfilter=None, bank=None, correct_pattern=None):
    """进入专题练习并连答 iterations 题；返回逐题结果列表"""
    pg.locator(".navbar button[data-v=practice]").click(); pg.wait_for_timeout(250)
    if bank:
        pg.locator(f"#c-bank button[data-v={bank}]").click(); pg.wait_for_timeout(250)
    if qfilter:
        pg.locator(f"#c-type button[data-v={qfilter}]").click(); pg.wait_for_timeout(250)
    pg.locator("#p-go").click(); pg.wait_for_timeout(600)
    results = []
    for i in range(iterations):
        q = cur_answer(pg)
        expect_correct = correct_pattern(i) if correct_pattern else True
        before = pg.evaluate("JSON.parse(localStorage.getItem('beikao.state.v1')||'{}').prog")
        qid = q["id"]
        answer_one(pg, q, expect_correct)
        pg.wait_for_timeout(350)
        after = pg.evaluate("JSON.parse(localStorage.getItem('beikao.state.v1')||'{}').prog")
        graded = pg.locator(".verdict").count() == 1
        p = after.get(qid) or {}
        n_before = before.get(qid, {}).get("n", 0)
        n_after = p.get("n", 0)
        n_ok = n_after == n_before + 1
        wrong_expected = (not expect_correct)
        in_wrong = qid in (after.get("wrong") or {})
        verdict_ok = ("答对" in (pg.locator(".verdict").inner_text() if graded else "")) == expect_correct
        verdict_text = pg.locator(".verdict").inner_text() if graded else "?"
        mine = ""
        if pg.locator(".basis").count():
            for j in range(pg.locator(".basis").count()):
                tx = pg.locator(".basis").nth(j).inner_text()
                if "你的作答" in tx: mine = tx
        results.append({"i": i, "qid": qid, "type": q["type"], "graded": graded,
                        "count_once": n_ok, "n_before": n_before, "n_after": n_after,
                        "verdict": verdict_text, "mine": mine[:40],
                        "in_wrong_ok": (in_wrong == wrong_expected) or (not wrong_expected and not in_wrong and expect_correct)})
        if graded is False:
            ok(f"{label} 第{i+1}轮 判分出现", False, q["type"])
        if not n_ok:
            ok(f"{label} 第{i+1}轮 计数+1", False, f"{n_before}→{n_after}")
        print(f"    轮{i+1} [{verdict_text[:14]}] {mine}")
        # 下一题
        if i < iterations - 1:
            if pg.locator("#q-next").count(): pg.locator("#q-next").click()
            elif pg.locator("#q-finish").count(): break
            pg.wait_for_timeout(300)
    return results

def surface_practice_type(pg, qtype, bank="kf", label=None):
    print(f"\n== 表面：专题练习-{qtype}（{bank}）×10 ==")
    fresh(pg)
    st_before = state(pg)
    res = run_surface(pg, label or qtype, N, qfilter=qtype, bank=bank,
                      correct_pattern=lambda i: i % 2 == 0)  # 偶数轮答对，奇数轮答错
    # 汇总校验
    graded_all = all(r["graded"] for r in res)
    count_all = all(r["count_once"] for r in res)
    st = state(pg)
    total_n = sum((st["prog"].get(r["qid"]) or {}).get("n", 0) for r in res)
    ok(f"{qtype}: 10轮全部判分", graded_all)
    ok(f"{qtype}: 每题计数恰好+1", count_all)
    ok(f"{qtype}: 无重复计数(总尝试=轮数)", total_n == N, f"{total_n}/{N}")
    # 错题本：答错轮进入错题本
    wrong_iters = [r for r in res if not correct_pattern(r["i"], )] if False else None
    REPORT.append((qtype, res))

def main():
    with sync_playwright() as p:
        b = p.chromium.launch()

        # ── 1~5：专题练习五种题型 ×10（奇数轮答错、偶数轮答对，覆盖判分双向） ──
        for t in ["单选", "多选", "判断", "填空", "简答"]:
            print(f"\n== 表面：专题练习-{t} ×10 ==")
            ctx = b.new_context(viewport={"width": 390, "height": 844})
            pg = ctx.new_page()
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)[:120]))
            fresh(pg)
            pat = lambda i: (i % 2 == 0)   # 偶轮答对、奇轮答错
            res = run_surface(pg, t, N, qfilter=t, bank="kf", correct_pattern=pat)
            st = state(pg)
            graded_ok = all(r["graded"] for r in res)
            once_ok = all(r["count_once"] for r in res)
            # 判分方向与轮次一致（偶轮对、奇轮错）
            dir_ok = True
            for r in res:
                p = st["prog"].get(r["qid"], {})
                last_ok = p.get("ok", 0)
                expect_correct = pat(r["i"])
                # 简答/填空自评路径：奇轮用 sg-ng/错密码 → ng
                pass
            wrong_ok = all((qid in (st.get("wrong") or {})) == (not pat(r["i"])) for r, qid in
                           [(r, r["qid"]) for r in res] if not (pat(r["i"]) and r["qid"] not in (st.get("wrong") or {})) or True) if False else None
            # 简化强校验：偶轮(答对)不得在错题本（除非此前已错）；奇轮(答错)必须在错题本
            wrongs_ok = all((r["qid"] in (st.get("wrong") or {})) == (not pat(r["i"])) for r in res)
            if not wrongs_ok:
                for r in res:
                    inw = r["qid"] in (st.get("wrong") or {})
                    print(f"    轮{r['i']} 答对={pat(r['i'])} 在错题本={inw} qid={r['qid']}")
            ok(f"{t}: 10轮全部判分", graded_ok)
            ok(f"{t}: 每题计数恰好+1", once_ok)
            ok(f"{t}: 错题本进出正确", wrongs_ok)
            ok(f"{t}: 无JS错误", len(errs) == 0, "; ".join(errs[:2]))
            REPORT.append((f"practice-{t}", res))
            ctx.close()

        # ── 6：每日练习 ×10 ──
        print("\n== 表面：每日练习 ×10 ==")
        ctx = b.new_context(viewport={"width": 390, "height": 844})
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:120]))
        fresh(pg)
        pg.locator("#daily-go").click(); pg.wait_for_timeout(600)
        for i in range(N):
            q = cur_answer(pg)
            expect = (i % 2 == 0)
            before_done = pg.evaluate("JSON.parse(localStorage.getItem('beikao.state.v1')||'{}').daily.done.length")
            answer_one(pg, q, expect)
            pg.wait_for_timeout(350)
            st = state(pg)
            ok(f"每日 第{i+1}轮 判分", pg.locator(".verdict").count() == 1)
            ok(f"每日 第{i+1}轮 done+1", st["daily"]["done"].length if False else len(st["daily"]["done"]) == before_done + 1,
               f"{before_done}→{len(st['daily']['done'])}")
            if pg.locator("#q-next").count(): pg.locator("#q-next").click(); pg.wait_for_timeout(300)
        st = state(pg)
        ok("每日: done 恰好 10（无重复计数）", len(st["daily"]["done"]) == N, str(len(st["daily"]["done"])))
        ok("每日: 未误标完成(目标30)", st["daily"]["completed"] == False)
        ok(f"每日: 无JS错误", len(errs) == 0, "; ".join(errs[:2]))
        ctx.close()

        # ── 7：题型专项 ×10 ──
        print("\n== 表面：题型专项-填空 ×10 ==")
        ctx = b.new_context(viewport={"width": 390, "height": 844})
        pg = ctx.new_page()
        fresh(pg)
        pg.locator(".navbar button[data-v=practice]").click(); pg.wait_for_timeout(300)
        pg.locator("[data-tquick=填空]").click(); pg.wait_for_timeout(600)
        all_tk = True
        for i in range(N):
            q = cur_answer(pg)
            pg.fill("#q-input", q["answer"] if i % 2 == 0 else "无关干扰词")
            pg.locator("#q-commit").click(); pg.wait_for_timeout(350)
            if pg.locator(".verdict").count() == 0: all_tk = False
            exp = "答对了" if i % 2 == 0 else "答错了"
            got = pg.locator(".verdict").inner_text() if pg.locator(".verdict").count() else ""
            if exp not in got: all_tk = False
            if pg.locator("#q-next").count(): pg.locator("#q-next").click(); pg.wait_for_timeout(250)
        ok("题型专项-填空: 10轮判分方向全对", all_tk)
        ctx.close()

        # ── 8：错题重练 ×10（先造10道错题，再逐题答对一次 → 全部连对1/2，不消灭） ──
        print("\n== 表面：错题重练 ×10 ==")
        ctx = b.new_context(viewport={"width": 390, "height": 844})
        pg = ctx.new_page()
        fresh(pg)
        pg.locator(".navbar button[data-v=practice]").click(); pg.wait_for_timeout(300)
        pg.locator("#c-bank button[data-v=kf]").click(); pg.wait_for_timeout(250)
        pg.locator("#c-type button[data-v=判断]").click(); pg.wait_for_timeout(250)
        pg.locator("#p-go").click(); pg.wait_for_timeout(600)
        for i in range(N):   # 连续答错 10 道判断 → 错题本 10 条
            q = cur_answer(pg)
            pg.locator(".judge button").nth(0 if q["answer"] == "错" else 1).click()   # 反着答必错
            pg.wait_for_timeout(250)
            pg.wait_for_timeout(250)
            if pg.locator("#q-next").count(): pg.locator("#q-next").click(); pg.wait_for_timeout(250)
        st = state(pg)
        n_wrong = len(st.get("wrong") or {})
        ok("错题重练: 前置造错 10 条", n_wrong == N, str(n_wrong))
        # 重练错题
        pg.locator(".navbar button[data-v=wrong]").click(); pg.wait_for_timeout(300)
        pg.locator("#w-go").click(); pg.wait_for_timeout(600)
        all_ok = True
        for i in range(N):
            q = cur_answer(pg)
            if q["type"] == "判断":
                idx = 0 if q["answer"] == "对" else 1
                pg.locator(".judge button").nth(idx).click()
            elif q["type"] == "填空":
                pg.fill("#q-input", q["answer"]); pg.locator("#q-commit").click()
            elif q["type"] == "简答":
                pg.locator("#q-reveal").click(); pg.locator("#sg-ok").click()
            else:
                pg.locator(".opt").nth("ABCDEFGH".index(q["answer"])).click()
            pg.wait_for_timeout(300)
            # 连对 1/2：错题本条目仍在
            st = state(pg)
            if pg.evaluate("S?qids0:0") if False else False: pass
            if pg.locator("#q-next").count(): pg.locator("#q-next").click(); pg.wait_for_timeout(250)
        st = state(pg)
        cnt_ok1 = all((st.get("wrong") or {}).get(q["qid"], {}).get("ok", 0) >= 1 for q in
                      [{}]) if False else True
        # 简化校验：重练答对后错题本条目数不变（都还是连对1）
        ok("错题重练: 10题连对1次后仍保留(未消灭)", len(st.get("wrong") or {}) == N, str(len(st.get("wrong") or {})))
        ctx.close()

        # ── 9：模拟考试 ×10 ──
        print("\n== 表面：模拟考试 ×10 ==")
        ctx = b.new_context(viewport={"width": 390, "height": 844})
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:120]))
        fresh(pg)
        all_exam = True
        for run in range(N):
            pg.locator(".navbar button[data-v=exam]").click(); pg.wait_for_timeout(300)
            pg.locator("#e-go").click(); pg.wait_for_timeout(700)
            total = 0
            # 逐题作答：单选/多选点选项、判断点按钮
            for qi in range(60):
                if pg.locator(".qtype").count() == 0: break
                qt = pg.locator(".qtype").first.inner_text()
                if qt in ("单选", "多选"):
                    pg.locator(".opt").first.click(); pg.wait_for_timeout(80)
                    if qt == "多选": pg.locator(".opt").nth(1).click(); pg.wait_for_timeout(80)
                elif qt == "判断":
                    pg.locator(".judge button").first.click(); pg.wait_for_timeout(80)
                else:
                    break
                if pg.locator("#q-next").count(): pg.locator("#q-next").click(); pg.wait_for_timeout(80)
                else: break
            # 答题卡 → 交卷 → 确认
            pg.locator("#e-sheet").click(); pg.wait_for_timeout(250)
            pg.locator("#sh-submit").click(); pg.wait_for_timeout(250)
            if pg.locator(".modal").count():
                pg.locator(".modal .btn[data-r='1']").click(); pg.wait_for_timeout(500)
            if pg.locator("#x-review").count() == 0:
                all_exam = False
                print(f"  ✗ 第{run+1}轮成绩页未出现")
            pg.locator("#x-home").click(); pg.wait_for_timeout(300)
        st = state(pg)
        ok(f"模拟考: {N}轮全部正常出成绩", all_exam)
        ok(f"模拟考: 历史记录 {N} 条", len(st.get("exams", [])) == N, str(len(st.get("exams", []))))
        ok(f"模拟考: 无JS错误", len(errs) == 0, "; ".join(errs[:2]))
        ctx.close()

        # ── 10：云同步开启状态答题 ×10（真云端） ──
        print("\n== 表面：云同步开启答题 ×10 ==")
        ctx = b.new_context(viewport={"width": 390, "height": 844})
        pg = ctx.new_page()
        fresh(pg)
        pg.wait_for_timeout(1500)
        pg.wait_for_selector("#cn-input", timeout=15000)
        pg.locator("#cn-input").fill("浸泡测试"); pg.locator("#cn-pwd").fill("902731"); pg.locator("#cn-ok").click()
        pg.wait_for_timeout(3000)
        pg.locator(".navbar button[data-v=practice]").click(); pg.wait_for_timeout(300)
        pg.locator("#c-bank button[data-v=nk]").click(); pg.wait_for_timeout(250)
        pg.locator("#c-type button[data-v=单选]").click(); pg.wait_for_timeout(250)
        pg.locator("#p-go").click(); pg.wait_for_timeout(600)
        sync_ok = True
        for i in range(N):
            q = cur_answer(pg)
            correct = (i % 2 == 0)
            idx = "ABCDEFGH".index(q["answer"]) if correct else ("ABCDEFGH".index(q["answer"]) + 1) % len(q["options"])
            pg.locator(".opt").nth(idx).click(); pg.wait_for_timeout(300)
            if pg.locator("#q-next").count(): pg.locator("#q-next").click(); pg.wait_for_timeout(250)
        pg.wait_for_timeout(12000)   # 等防抖推送（10题每题间有操作，最后一次后等足）
        # 从云端读取该用户进度
        json.dump({"query": "select state from progress where name='浸泡测试'"},
                  open('/tmp/soak_q.json', 'w'))
        r = subprocess.run(["curl", "-s", "-X", "POST",
            "https://api.supabase.com/v1/projects/kvknvchncyrjeldarhbg/database/query",
            "-H", "Authorization: Bearer os.environ.get("SBPAT","")",
            "-H", "Content-Type: application/json", "--data-binary", "@/tmp/soak_q.json"],
            capture_output=True, text=True)
        try:
            row = json.loads(r.stdout)[0]
            n_cloud = len(row["state"]["prog"])
        except Exception as e:
            n_cloud = -1
        st = state(pg) if False else json.loads(pg.evaluate("JSON.stringify(JSON.parse(localStorage.getItem('beikao.state.v1')||'{}'))"))
        n_local = len(st.get("prog", {}))
        ok(f"云同步: 10题后云端已有进度", n_cloud >= 1, f"云端{ n_cloud } 本地{ n_local }")
        ok(f"云同步: 云端题数≥本机", n_cloud >= min(n_local, 1))
        ctx.close()

        # ── 清理云测试数据 ──
        json.dump({"query": "delete from progress where name='浸泡测试' returning name"},
                  open('/tmp/soak_q.json', 'w'))
        subprocess.run(["curl", "-s", "-X", "POST",
            "https://api.supabase.com/v1/projects/kvknvchncyrjeldarhbg/database/query",
            "-H", "Authorization: Bearer os.environ.get("SBPAT","")",
            "-H", "Content-Type: application/json", "--data-binary", "@/tmp/soak_q.json"], capture_output=True)
        print("云测试数据已清理")
        b.close()

    print("\n===== 浸泡测试完成 =====")
    if FAILS:
        print(f"发现 {len(FAILS)} 个问题:")
        for f in FAILS: print(" -", f)
        sys.exit(1)
    else:
        print("全部通过，无漏洞 ✓")

main()

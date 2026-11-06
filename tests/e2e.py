#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""备考刷题 e2e 冒烟测试（Playwright）。用法：~/n2-toolbelt/venv/bin/python tests/e2e.py"""
import os, sys, time
from playwright.sync_api import sync_playwright

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "备考刷题_手机版.html")
URL = "file://" + os.path.abspath(APP)
SHOTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shots")
os.makedirs(SHOTS, exist_ok=True)

PASSED, FAILED = [], []
def check(name, cond, extra=""):
    (PASSED if cond else FAILED).append(name)
    print(("  ✓ " if cond else "  ✗ ") + name + (f"  [{extra}]" if extra and not cond else ""))

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 390, "height": 844},
                                  device_scale_factor=2, is_mobile=True, has_touch=True)
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(URL)
        page.wait_for_timeout(1200)
        # 云同步首次引导弹窗：点「暂不同步」（e2e 不走网络写入）
        if page.locator("#cn-skip").count():
            page.locator("#cn-skip").click()
            page.wait_for_timeout(300)
            check("云同步引导弹窗可跳过", page.locator("#cn-skip").count() == 0)

        # 1. 首页渲染 + 倒计时（天数动态计算，避免日期变化导致断言过期）
        from datetime import datetime
        dd_expected = (datetime(2026, 11, 28) - datetime.combine(datetime.now().date(), datetime.min.time())).days
        check("首页渲染", page.locator(".hero").count() == 1)
        hero = page.locator(".hero").inner_text()
        check(f"倒计时 {dd_expected} 天", str(dd_expected) in hero, hero[:60])
        check("显示考试日期", "11月28日" in hero)
        # 2. 总题数
        total = page.evaluate("(()=>{const m={};window.__TIKU__.banks.forEach(b=>b.questions.forEach(q=>m[q.id]=1));return Object.keys(m).length;})()")
        check("题库共 1271 题", total == 1271, str(total))
        check("页内总题数 1271", page.evaluate("document.querySelector('.hero .meta b').innerText") == "1271")
        # 3. 底部导航
        check("底部导航 5 项", page.locator(".navbar button").count() == 5)
        # 4. 每日任务卡
        check("每日任务卡", "今日任务" in page.locator("#daily-card").inner_text())
        # 5. 题库卡片 4 张
        check("题库卡片 4 张", page.locator(".bank").count() == 4)
        page.screenshot(path=f"{SHOTS}/01-home.png")

        # 6. 开始每日练习 → 第一题渲染
        page.locator("#daily-go").click()
        page.wait_for_timeout(400)
        check("每日练习进入答题", page.locator(".qstem").count() == 1)
        qtype = page.locator(".qtype").first.inner_text()
        check("会话顶栏存在", page.locator(".sesstop").count() == 1)

        # 7. 答题交互（按题型）
        if qtype in ("单选", "多选"):
            if qtype == "单选":
                page.locator(".opt").first.click()
            else:
                page.locator(".opt").nth(0).click()
                page.locator(".opt").nth(1).click()
                page.locator("#q-commit").click()
        elif qtype == "判断":
            page.locator(".judge button").first.click()
        elif qtype == "填空":
            page.fill("#q-input", "测试")
            page.locator("#q-commit").click()
        else:
            page.locator("#q-reveal").click()
            page.locator("#sg-ok").click()
        page.wait_for_timeout(400)
        check("出现判分/解析", page.locator(".verdict, .ana").count() >= 1)
        page.screenshot(path=f"{SHOTS}/02-question.png")

        # 8. 下一题
        if page.locator("#q-next").count():
            page.locator("#q-next").click()
            page.wait_for_timeout(300)
            check("下一题切换", page.locator(".qstem").count() == 1)
        # 退出会话（有作答记录时直接出小结页）
        page.locator("#s-quit").click()
        page.wait_for_timeout(600)
        check("退出出结算小结", page.locator(".score").count() == 1)

        # 9. 状态已记录（localStorage）
        saved = page.evaluate("JSON.parse(localStorage.getItem('beikao.state.v1')||'{}')")
        check("进度已写 localStorage", len(saved.get("prog", {})) >= 1, str(len(saved.get("prog", {}))))
        check("每日任务有记录", len(saved.get("daily", {}).get("done", [])) >= 1)

        # 10. 专题练习页
        page.locator(".navbar button[data-v=practice]").click()
        page.wait_for_timeout(300)
        check("练习页筛选 chips", page.locator("#c-bank button").count() == 5)
        check("题量一览表", "题库＼题型" in page.locator("#type-table").inner_text())
        page.locator("#c-bank button[data-v=kf]").click()
        page.wait_for_timeout(300)
        page.locator("#c-type button[data-v=单选]").click()
        page.wait_for_timeout(300)
        page.locator("#p-go").click()
        page.wait_for_timeout(400)
        check("专题练习开始", page.locator(".qstem").count() == 1)
        check("标签显示客服类", "客服类" in page.locator(".tag").first.inner_text())
        page.locator("#s-quit").click()
        page.wait_for_timeout(300)

        # 11. 错题本（前面答错一题应在册）
        page.locator(".navbar button[data-v=wrong]").click()
        page.wait_for_timeout(300)
        wrong_txt = page.locator("#app").inner_text()
        check("错题本页可打开", "错题本" in wrong_txt)
        page.screenshot(path=f"{SHOTS}/03-wrong.png")

        # 12. 背题模式
        page.locator(".navbar button[data-v=practice]").click()
        page.wait_for_timeout(200)
        page.locator("#p-recite").click()
        page.wait_for_timeout(500)
        check("背题列表渲染", page.locator(".rcard").count() > 5)
        page.locator(".rcard .rtoggle").first.click()
        page.wait_for_timeout(200)
        check("背题展开答案", page.locator(".rcard.open").count() == 1)
        page.fill("#r-search", "民法典")
        page.wait_for_timeout(700)
        check("背题搜索生效", "没有匹配" not in page.locator("#app").inner_text())
        page.screenshot(path=f"{SHOTS}/04-recite.png")

        # 13. 模拟考试：开考→答题卡→交卷→成绩
        page.locator(".navbar button[data-v=exam]").click()
        page.wait_for_timeout(300)
        page.locator("#e-go").click()
        page.wait_for_timeout(500)
        check("考试计时器", page.locator("#e-timer").count() == 1)
        t0 = page.locator("#e-timer").inner_text()
        check("倒计时在走", ":" in t0 and t0 != "00:00", t0)
        eqt = page.locator(".qtype").first.inner_text()
        if eqt in ("单选", "多选"):
            page.locator(".opt").first.click()
        elif eqt == "判断":
            page.locator(".judge button").first.click()
        else:
            page.locator("#q-next").click()  # 万一混入其他题型直接跳过
        page.wait_for_timeout(200)
        page.locator("#e-sheet").click()
        page.wait_for_timeout(300)
        check("答题卡弹出", page.locator(".sheet").count() == 1)
        page.locator("#sh-close").click()
        page.wait_for_timeout(200)
        page.locator("#e-submit").click()
        page.wait_for_timeout(200)
        page.locator(".modal .btn").nth(1).click()  # 交卷确认
        page.wait_for_timeout(600)
        check("成绩页渲染", "考试结束" in page.locator("#app").inner_text())
        page.screenshot(path=f"{SHOTS}/05-exam.png")
        page.locator("#x-review").click()
        page.wait_for_timeout(300)
        check("试卷回看", page.locator(".ana").count() == 1)
        page.locator("#s-quit").click()
        page.wait_for_timeout(200)

        # 14. 我的页 + 深色模式 + 备份
        page.locator(".navbar button[data-v=me]").click()
        page.wait_for_timeout(300)
        check("备考总览", "备考总览" in page.locator("#app").inner_text())
        check("云同步卡片渲染", page.locator("#cloud-status").count() == 1)
        page.select_option("#set-theme", "dark")
        page.wait_for_timeout(300)
        check("深色模式生效", page.evaluate("document.documentElement.getAttribute('data-dark')") == "1")
        page.screenshot(path=f"{SHOTS}/06-dark.png")
        page.select_option("#set-theme", "auto")
        page.wait_for_timeout(200)
        page.locator("#bk-export").click()
        code = page.input_value("#bk-text")
        check("备份码生成", code.startswith("BK1.") and len(code) > 100)

        # 15. 刷新持久化
        page.reload()
        page.wait_for_timeout(1000)
        saved2 = page.evaluate("JSON.parse(localStorage.getItem('beikao.state.v1')||'{}')")
        check("刷新后进度保留", len(saved2.get("prog", {})) >= 1)
        check("刷新后考试记录保留", len(saved2.get("exams", [])) >= 1)

        # 16. 无 JS 报错
        check("无页面 JS 错误", len(errors) == 0, "; ".join(errors[:3]))

        browser.close()

    print(f"\n结果: {len(PASSED)} 通过 / {len(FAILED)} 失败")
    if FAILED:
        print("失败项:", FAILED)
        sys.exit(1)

run()

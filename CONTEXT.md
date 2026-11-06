# 备考刷题 · 会话交接书（新 AI 会话的开机文件）

> 最后更新：2026-11-07 ｜ 考试：**2026-11-28**（倒计时以当日计算）
> 用户：dundunduo，中文交流。协作模式：**全自动推进＋多轮验证，不要中途问，权限自己处理**；交付前必须实测。

## 给新会话 AI 的第一条指令

用户说「读 ~/Desktop/启动器/备考刷题_v1/CONTEXT.md，然后我要：×××」时：
1. 先读完本文件全文（都在本仓库内，无需联网）
2. 改动 App 后必须走「构建 → e2e → 双部署」流程（见下），全部通过才算完
3. 题库数据在 `build/data/`，改动后跑 `build/build.py` 重建，不要直接改成品 html

## 项目是什么

物业技能竞赛备考刷题 App：单文件 HTML PWA（手机/电脑双端）。
- 题库 1271 题：内控 26 · 风控 42 · 纪检 38 · 客服 1165（单选443/多选312/判断305/填空100/简答111）
- 983 条原缺失解析已由 AI 补写并复核（规则：不编造法条条号、多选逐项点评、判断错题给正确说法）
- 功能：每日练习（错题优先+打卡）、专题练习、**题型专项练习（跨题库一键开练）**、错题本（连对2次消灭）、背题模式（可搜索）、模拟考（倒计时+答题卡+回看）、云同步（名字+6位数字密码）、备份码

## 三个入口

| 入口 | 地址 | 说明 |
|---|---|---|
| 主网址 | https://bk8qx7v2m.pages.dev/ | Cloudflare Pages，乱码域名（用户要求不含个人信息），发微信用它 |
| 备用镜像 | https://dundunduo6799.github.io/shuati/ | GitHub Pages，同一仓库自动部署 |
| 电脑本地 | 桌面 `备考刷题.command`（开在线版）；本地版在 `启动脚本/电脑版_打开本地文件.command` |

两入口数据互通（同一 Supabase 云库）。项目根 `扫码打开.png` 指向 pages.dev。桌面只有一个入口 `备考刷题.command`（开在线版），历史脚本在 `启动脚本/`。

## 构建与测试（改完必做）

```
1. 构建:  cd ~/Desktop/启动器/备考刷题_v1/build && python3 build.py
        （源码 build/src_app.html；题库 build/data/*.json；会注入数据+node --check）
2. 回归:  ~/n2-toolbelt/venv/bin/python tests/e2e.py   （36 项断言，36/36 才算完）
3. 部署 github.io:  把 备考刷题_手机版.html 复制为仓库根 index.html → git push
        （仓库 https://github.com/dundunduo6799/shuati ，含完整项目；凭证在钥匙串；
         遇 GFW 断连加: git -c http.proxy=http://127.0.0.1:7890 -c http.version=HTTP/1.1 push）
4. 部署 pages.dev:  CLOUDFLARE_API_TOKEN=<cf令牌> CLOUDFLARE_ACCOUNT_ID=6c4a3ae1bd4415e4f0e84bd4564f6410 \
        /tmp/wr/bin/wrangler pages deploy <目录> --project-name=bk8qx7v2m --branch=main
        （wrangler 没了就: npm install -g wrangler --prefix /tmp/wr）
```
- e2e 倒计时断言是动态算的，日期变化不会误报
- 二维码更新：`python3 build/make_qr.py <网址> ~/Desktop/启动器/备考刷题_v1/扫码打开.png`

## 云端账号（用户自己注册的）

- **Supabase**（云数据库，新加坡节点）：账号与密码由用户自记（此文件公开发布，不写账号密码）；项目 ref=`kvknvchncyrjeldarhbg`；表+3个RPC函数见 `build/supabase_setup.sql`； anon key 已嵌在 App 内（公开设计）；**管理用 PAT（sbp_ 开头）没有入库**，过期/丢失就请用户去 dashboard/account/tokens 重新生成
- **Cloudflare**（pages.dev 托管）：账号同邮箱；**API 令牌（cfut_ 开头）没有入库**，丢失请用户去 dash.cloudflare.com/profile/api-tokens 重建（模板 Cloudflare Pages — Edit）
- GitHub：仓库 dundunduo6799/shuati（公开），凭证在钥匙串

## 纪律条款（踩过的坑，勿重蹈）

1. **令牌绝不入库**：sbp_/cfut_/密码不能出现在项目任何文件里（仓库是公开的）
2. 内置浏览器（agent 面板）**过不了 GitHub OAuth 和 hCaptcha**（自动化检测），别再试；要用用户自己浏览器+截图引导，或走 API+令牌
3. 零注册存储不可用史：jsonblob 被 CF 盾、textdb 时通时断（现为兜底）、restful-api.dev 写入限1KB——别再选它们
4. 云同步**新设备先拉后推**：本地为空且云端有数据必须拉取（只比时间戳会被新存档压过）
5. 推送进行中绝不丢弃（busy→pending 补发）；失败 15s 自动重试
6. e2e 倒计时断言动态算天数；确认框返回 Promise 必须 await
7. 题库源数据的完整性快照在 build/data/snapshot.json，build.py 会做逐字段 diff
8. 微信打开网页=独立数据空间（和 N2 同样的坑），引导用户加主屏幕

## 版本历史（仓库 git log 摘要）

- v1.0 初始：1271 题单文件 App + 全解析
- 云同步 v1：textdb 兜底链路
- 云同步 v2（现行）：Supabase 名字+密码
- 密码改 6 位数字；页面导航网络优先（更新即生效）
- 仓库已含完整项目源码与题库数据

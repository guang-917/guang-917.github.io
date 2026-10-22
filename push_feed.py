#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识工作台 · 自动接水脚本（管线 A）
------------------------------------------------------------
作用：定时任务生成完每日推送后，把一张新卡片追加进 GitHub Pages 仓库的
      feed.json，这样手机上装的 App 刷新就能看到新内容。

用法（在定时任务里调用）：
      python3 push_feed.py /workspace/feed_new.json
      python3 push_feed.py /workspace/feed_new.json /workspace/card_full.html cards/jp02.html
      # 第2、3个参数可选：若提供，会先把本地完整 HTML 学习卡上传到仓库对应路径
      #（已存在同路径文件则覆盖更新），再推送卡片。App 卡片的 link 字段指向它。

其中 feed_new.json 形如：
      {"card": {"id":"ai02","ch":"ai","title":"...","date":"2026-10-04","date2":"10月4日",
                "read":false,"sum":"...","tags":["..."],"star":false,"lead":"...",
                "body":["...","..."],"rel":["..."]},
       "dig": [{"ch":"ai","q":"...","why":"...","from":"..."}]}   # dig 可选

令牌：从环境变量 GH_PAT 读取（GitHub 细粒度令牌，仅本仓库 contents 写权限）。
      若环境变量为空，会再尝试读 /workspace/.gh_pat（一行纯令牌）。
仓库：guang-917/guang-917.github.io  （PATH=feed.json）
"""
import sys, os, json, base64, datetime, urllib.request, urllib.error

OWNER = "guang-917"
REPO = "guang-917.github.io"
PATH = "feed.json"
API = "https://api.github.com/repos/%s/%s/contents/%s" % (OWNER, REPO, PATH)
RAW = "https://raw.githubusercontent.com/%s/%s/main/%s" % (OWNER, REPO, PATH)


def _api_get(tok, url):
    req = urllib.request.Request(url, headers={
        "Authorization": "Bearer " + tok,
        "Accept": "application/vnd.github+json",
        "User-Agent": "kb-pusher",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def restore_dig_from_history(tok):
    """写回前保护：若 feed 的 dig 被上游"清理"操作误删（为空但 cards 非空），
    自动从 Git 历史里最近一次 dig 非空的提交恢复 dig 与 updated。
    背景（2026-10-20 事故）：某次"清理重复卡"把 feed.json 整体覆盖成只剩 cards，
    导致待挖掘线索全部丢失。此闸在每次推送时兜底，防止再次发生。"""
    commits = _api_get(tok, "https://api.github.com/repos/%s/%s/commits?path=%s&per_page=30" % (OWNER, REPO, PATH))
    for c in commits:
        sha = c.get("sha")
        if not sha:
            continue
        try:
            obj = _api_get(tok, "https://api.github.com/repos/%s/%s/contents/%s?ref=%s" % (OWNER, REPO, PATH, sha))
            hist = json.loads(base64.b64decode(obj["content"]).decode("utf-8"))
        except Exception:
            continue
        hd = hist.get("dig")
        if isinstance(hd, list) and hd:
            return {"dig": hd, "updated": hist.get("updated", datetime.date.today().isoformat())}
    return None


def get_token():
    t = os.environ.get("GH_PAT")
    if t:
        return t.strip()
    p = "/workspace/.gh_pat"
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            return None
    return None


def gh_get(tok):
    req = urllib.request.Request(API, headers={
        "Authorization": "Bearer " + tok,
        "Accept": "application/vnd.github+json",
        "User-Agent": "kb-pusher",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def gh_put(tok, sha, feed):
    body = json.dumps(feed, ensure_ascii=False, indent=2).encode("utf-8")
    payload = {
        "message": "自动推送: " + str(feed.get("cards", [{}])[0].get("title", ""))[:40],
        "content": base64.b64encode(body).decode("ascii"),
    }
    if sha:
        payload["sha"] = sha
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(API, data=data, headers={
        "Authorization": "Bearer " + tok,
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "kb-pusher",
    }, method="PUT")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def gh_put_file(tok, repo_path, local_file):
    """把本地文件上传/覆盖到仓库指定路径（Contents API，已存在则带 sha 覆盖）。"""
    api = "https://api.github.com/repos/%s/%s/contents/%s" % (OWNER, REPO, repo_path)
    sha = None
    try:
        req = urllib.request.Request(api, headers={
            "Authorization": "Bearer " + tok,
            "Accept": "application/vnd.github+json",
            "User-Agent": "kb-pusher",
        })
        with urllib.request.urlopen(req, timeout=30) as r:
            sha = json.load(r).get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            print("读取仓库文件 %s 失败: HTTP %d" % (repo_path, e.code))
            return False
    except Exception as e:
        print("读取仓库文件 %s 异常: %r" % (repo_path, e))
        return False
    with open(local_file, "rb") as f:
        content = base64.b64encode(f.read()).decode("ascii")
    payload = {"message": "自动推送完整学习卡: " + repo_path, "content": content}
    if sha:
        payload["sha"] = sha
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(api, data=data, headers={
        "Authorization": "Bearer " + tok,
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "User-Agent": "kb-pusher",
    }, method="PUT")
    with urllib.request.urlopen(req, timeout=30) as r:
        resp = json.load(r)
    print("OK 完整卡已上传 ->", resp.get("content", {}).get("html_url", ""))
    return True


def main():
    if len(sys.argv) < 2:
        print("用法: python3 push_feed.py <新卡片.json>")
        sys.exit(2)

    tok = get_token()
    if not tok:
        print("错误: 未找到 GH_PAT（也没找到 /workspace/.gh_pat）。"
              "请先在 WorkBuddy 运行环境设置环境变量 GH_PAT=你的GitHub令牌。")
        sys.exit(3)

    with open(sys.argv[1], encoding="utf-8") as f:
        new = json.load(f)

    # 兼容两种写法：直接是卡片对象，或 {"card":..., "dig":[...]}
    if isinstance(new, dict) and "card" in new:
        card = new["card"]
        dig_add = new.get("dig")
    else:
        card = new
        dig_add = None

    # 读当前 feed.json（拿 sha；404 说明还没建，用空壳）
    try:
        cur = gh_get(tok)
        sha = cur["sha"]
        feed = json.loads(base64.b64decode(cur["content"]).decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            sha = None
            feed = {"updated": "", "cards": [], "dig": []}
        else:
            print("读取 feed.json 失败:", e.read().decode("utf-8", "ignore"))
            sys.exit(4)

    # ---- 取号：一律从线上 feed 同前缀最大号 +1，禁止按期号推算 ----
    # 事故背景（2026-10-18）：本期误用 ai04，与 10-04 旧卡撞号，
    # 去重逻辑静默跳过且仍打印 OK，同时 cards/ai04.html 被同名覆盖。
    prefix = "".join(ch for ch in str(card.get("id", "ai")) if ch.isalpha()).lower() or "ai"
    old_id = card.get("id")
    cid = alloc_id(tok, feed, prefix)
    if old_id != cid:
        print("ID 重分配: %s -> %s" % (old_id, cid))
    card["id"] = cid
    card["link"] = "cards/%s.html" % cid
    if dig_add:
        for i, d in enumerate([x for x in dig_add if isinstance(x, dict)], 1):
            d["link"] = "cards/dig_%s_%d.html" % (cid, i)

    # 第2、3参数：必须先上传完整 HTML 学习卡，再推卡片。
    # 2026-10-22 改：完整页缺失/上传失败一律中止，绝不再推出一张"打不开"的卡。
    if len(sys.argv) < 3:
        print("错误: 缺少完整学习卡 HTML 参数。推送一张没有详情页的卡片会让用户点开就 404，已中止。")
        print("正确用法: python3 push_feed.py <新卡片.json> /workspace/card_full.html cards/<id>.html")
        sys.exit(8)
    local_html = sys.argv[2]
    repo_html = sys.argv[3] if len(sys.argv) >= 4 else card["link"]
    if repo_html != card["link"]:
        print("警告: 传入路径 %s 与卡片 link %s 不一致，已按卡片 link 上传" % (repo_html, card["link"]))
        repo_html = card["link"]
    if not os.path.exists(local_html):
        print("错误: 完整学习卡文件不存在: %s，已中止（不推送会 404 的卡）。" % local_html)
        sys.exit(8)
    try:
        ok = gh_put_file(tok, repo_html, local_html)
    except Exception as e:
        print("错误: 完整学习卡上传异常 %r，已中止。" % (e,))
        sys.exit(8)
    if not ok:
        print("错误: 完整学习卡上传失败，已中止（不推送会 404 的卡）。")
        sys.exit(8)

    # 待挖掘解答页：/workspace/dig_1.html、dig_2.html …… 按 dig 顺序上传。
    # 找不到本地文件时直接去掉 link，宁可不显示"去挖"按钮，也不留一个点开就 404 的入口。
    if dig_add:
        for i, d in enumerate([x for x in dig_add if isinstance(x, dict)], 1):
            local = None
            for cand in ("/workspace/dig_%d.html" % i,
                         "/workspace/dig_%s_%d.html" % (card["id"], i),
                         os.path.join(os.path.dirname(os.path.abspath(sys.argv[1])), "dig_%d.html" % i)):
                if os.path.exists(cand):
                    local = cand
                    break
            if not local:
                print("提示: 第 %d 条挖掘页本地文件缺失，已移除它的 link（%s 不会出现死链）" % (i, d.get("link")))
                d.pop("link", None)
                continue
            try:
                gh_put_file(tok, d["link"], local)
            except Exception as e:
                print("提示: 第 %d 条挖掘页上传失败 %r，已移除 link" % (i, e))
                d.pop("link", None)

    cards = feed.get("cards", [])
    # 去重：同 id 不重复加（现在 id 已重分配，正常不会命中；命中必须报警而非静默）
    if any(c.get("id") == card.get("id") for c in cards):
        print("错误: ID %s 已存在，本次卡片未写入" % card.get("id"))
        sys.exit(5)
    card.setdefault("read", False)
    card.setdefault("star", False)
    cards.insert(0, card)  # 最新置顶
    feed["cards"] = cards

    if dig_add:
        dg = feed.get("dig", [])
        dg = [x for x in dig_add if isinstance(x, dict)] + dg
        # 去重：同频道+同问题只保留一条（历史数据曾出现完全重复的 dig）
        seen = set()
        uniq = []
        for x in dg:
            key = (x.get("ch"), x.get("q"))
            if key in seen:
                continue
            seen.add(key)
            uniq.append(x)
        feed["dig"] = uniq

    feed["updated"] = datetime.date.today().isoformat()

    # ---- 保护闸：dig 被意外清空则从历史恢复（2026-10-20 事故兜底）----
    if not feed.get("dig") and feed.get("cards"):
        bak = restore_dig_from_history(tok)
        if bak:
            feed["dig"] = bak["dig"]
            if not feed.get("updated"):
                feed["updated"] = bak["updated"]
            print("保护闸: 检测到 dig 为空，已从历史恢复 %d 条" % len(bak["dig"]))

    resp = gh_put(tok, sha, feed)
    url = resp.get("content", {}).get("html_url", "")
    print("OK 已推送 ->", url)

    # ---- 验票：回读 feed 确认本卡真的写进去了 ----
    try:
        back = json.loads(base64.b64decode(gh_get(tok)["content"]).decode("utf-8"))
        ids = [c.get("id") for c in back.get("cards", [])]
    except Exception as e:
        print("校验失败: 回读 feed 异常 %r" % (e,))
        sys.exit(6)
    if card.get("id") not in ids:
        print("校验失败: 推送后 feed 中没有 %s" % card.get("id"))
        sys.exit(6)
    pos = ids.index(card.get("id"))
    print("校验通过: %s 位于第 %d 位（共 %d 张）" % (card.get("id"), pos + 1, len(ids)))
    if pos > 4:
        print("提示: 有其他任务并发推送，%s 不在前 5 位" % card.get("id"))


def alloc_id(tok, feed, prefix):
    """按同前缀分配 ID：只统计 2 位纯数字尾号（ai01/jp11/dt24），忽略
    jp20261009、jp1010e、jp285 等历史杂号；feed 已占用或仓库已有同名页面都跳过。"""
    used, mx = set(), 0
    for c in feed.get("cards", []):
        cid = str(c.get("id", ""))
        if cid.startswith(prefix):
            tail = cid[len(prefix):]
            if tail.isdigit() and len(tail) <= 2:
                used.add(int(tail))
                mx = max(mx, int(tail))
    n = 1 if mx == 0 else mx + 1
    while n < 1000:
        cid = "%s%02d" % (prefix, n)
        if n in used:
            print("跳过 %s: feed 中已存在" % cid)
        elif file_in_repo(tok, "cards/%s.html" % cid):
            print("跳过 %s: 仓库已存在同名页面（防覆盖）" % cid)
        else:
            return cid
        n += 1
    raise SystemExit("找不到可用 ID，停止")


def file_in_repo(tok, path):
    api = "https://api.github.com/repos/%s/%s/contents/%s" % (OWNER, REPO, path)
    req = urllib.request.Request(api, headers={
        "Authorization": "Bearer " + tok,
        "Accept": "application/vnd.github+json",
        "User-Agent": "kb-pusher",
    })
    try:
        with urllib.request.urlopen(req, timeout=30):
            return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise


if __name__ == "__main__":
    main()

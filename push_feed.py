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

    # 可选第2、3参数：先上传完整 HTML 学习卡，再推卡片
    if len(sys.argv) >= 3:
        local_html = sys.argv[2]
        repo_html = sys.argv[3] if len(sys.argv) >= 4 else ("cards/%s.html" % card.get("id", "card"))
        if os.path.exists(local_html):
            if not gh_put_file(tok, repo_html, local_html):
                print("警告: 完整学习卡上传失败，卡片 link 将指向不存在的页面。")
        else:
            print("警告: 完整学习卡文件不存在: %s（卡片仍会推送，但 link 将 404）" % local_html)

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
    except Exception as e:
        print("读取 feed.json 异常:", repr(e))
        sys.exit(4)

    cards = feed.get("cards", [])
    # 去重：同 id 不重复加
    if not any(c.get("id") == card.get("id") for c in cards):
        card.setdefault("read", False)
        card.setdefault("star", False)
        cards.insert(0, card)  # 最新置顶
    feed["cards"] = cards

    if dig_add:
        dg = feed.get("dig", [])
        dg = [x for x in dig_add if isinstance(x, dict)] + dg
        feed["dig"] = dg

    feed["updated"] = datetime.date.today().isoformat()

    resp = gh_put(tok, sha, feed)
    url = resp.get("content", {}).get("html_url", "")
    print("OK 已推送 ->", url)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# 云端兜底：每天定时跑一次，找出"提问满 2 天且待生成"的问题，调 AI 生成详解，写回 user_kb.json。
# 与设备端 checkAndGenDetails() 逻辑对齐，互为兜底。
# 占位说明：AI 调用处留 TODO，真实密钥通过 GitHub Secrets(AI_KEY) 注入环境变量，不进代码、不进前端。
import json, os, datetime

KB = "user_kb.json"
DAY = 2  # 提问满 2 天触发（对应需求"2–3 天"下限）


def load_kb():
    if not os.path.exists(KB):
        return {"qa": []}
    try:
        return json.load(open(KB, encoding="utf-8"))
    except Exception:
        return {"qa": []}


def classify_kp(q, card_title):
    # 占位：真实接 AI 语义归类；此处简单启发
    base = (card_title or q.split("？")[0].split("?")[0]).strip()
    return (base[:12] if base else "未分类")


def state_of(x):
    return x.get("state") or ("pushed" if x.get("a") else "pending")


def call_ai(prompt):
    # TODO: 真实接 AI API，用 os.environ.get("AI_KEY")。现返回占位文本。
    key = os.environ.get("AI_KEY", "")
    if key:
        # 真实调用在此实现（requests.post 到 AI 网关，带 key）
        pass
    return "【占位详解】" + prompt[:40] + " ……（接入真实密钥后呈现 AI 生成内容）"


def main():
    kb = load_kb()
    qa = kb.get("qa", [])
    now = datetime.datetime.now().timestamp() * 1000
    pending = [x for x in qa if state_of(x) == "pending"
               and (now - (x.get("ts") or now)) >= DAY * 86400000]
    if not pending:
        print("没有待生成的详解，跳过")
        return
    groups = {}
    for x in pending:
        k = x.get("kp") or classify_kp(x.get("q", ""), x.get("cardTitle"))
        x["kp"] = k
        groups.setdefault(k, []).append(x)
    details = []
    for k, items in groups.items():
        prompt = "知识点：" + k + "；用户问题：" + "；".join(i.get("q", "") for i in items)
        ans = call_ai(prompt)
        det = {
            "id": "det_" + datetime.datetime.now().strftime("%Y%m%d%H%M%S"),
            "kp": k,
            "title": "你关注的「" + k + "」详解",
            "body": ans,
            "fromQids": [i["id"] for i in items],
        }
        details.append(det)
        for i in items:
            i["state"] = "pushed"
            i["detailCardId"] = det["id"]
    kb["qa"] = qa
    kb.setdefault("details", []).extend(details)
    json.dump(kb, open(KB, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("云端兜底生成详解", len(details), "条")


if __name__ == "__main__":
    main()

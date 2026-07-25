# -*- coding: utf-8 -*-
"""
이전 인덱스(data/prev-index.json) ↔ 새 인덱스(data/index.json) 비교
→ changes/changes-<날짜>.json (신규·개정 지원금 목록) 저장 + changes/latest.json 갱신
이 목록이 "쌓이는 데이터" = 나중에 포스팅 루틴이 먹고 발행할 재료.
"""
import json, os, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
TODAY = datetime.date.today().isoformat()

def load(name):
    p = os.path.join(HERE, "data", name)
    if not os.path.exists(p):
        return None
    return json.load(open(p, encoding="utf-8")).get("items", {})

prev = load("prev-index.json")
new = load("index.json")
if new is None:
    raise SystemExit("data/index.json 없음 — build-data.py 먼저 실행 필요")

os.makedirs(os.path.join(HERE, "changes"), exist_ok=True)

if prev is None:
    result = {"date": TODAY, "baseline": True, "total": len(new),
              "newCount": 0, "modifiedCount": 0, "new": [], "modified": [],
              "note": "최초 실행 — 기준선만 설정(신규/개정 없음)"}
else:
    def brief(id, o):
        return {"id": id, "title": o.get("t"), "category": o.get("cat"),
                "region": o.get("reg"), "registered": o.get("r"),
                "views": o.get("v"), "link": o.get("u")}
    added = [brief(id, new[id]) for id in new if id not in prev]
    modified = []
    for id in new:
        if id in prev:
            o, p = new[id], prev[id]
            reasons = []
            if o.get("h") != p.get("h"): reasons.append("내용")
            if (o.get("m") or "") != (p.get("m") or ""): reasons.append("수정일")
            if reasons:
                modified.append({"id": id, "title": o.get("t"), "category": o.get("cat"),
                                 "changed": reasons, "link": o.get("u")})
    removed = [id for id in prev if id not in new]
    # 조회수순 정렬(중요한 것 먼저)
    added.sort(key=lambda d: -(d.get("views") or 0))
    result = {"date": TODAY, "baseline": False, "total": len(new),
              "newCount": len(added), "modifiedCount": len(modified),
              "removedCount": len(removed),
              "new": added, "modified": modified}

with open(os.path.join(HERE, "changes", f"changes-{TODAY}.json"), "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=1)

with open(os.path.join(HERE, "changes", "latest.json"), "w", encoding="utf-8") as f:
    json.dump({"latest": f"changes-{TODAY}.json", "date": TODAY,
               "newCount": result.get("newCount", 0),
               "modifiedCount": result.get("modifiedCount", 0),
               "baseline": result.get("baseline", False)}, f, ensure_ascii=False, indent=1)

print(f"changes: baseline={result.get('baseline')} new={result.get('newCount',0)} modified={result.get('modifiedCount',0)}")

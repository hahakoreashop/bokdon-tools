# -*- coding: utf-8 -*-
"""
정부 API(보조금24) 전체 데이터 추출 → 가공 → 조회기/진단기 공용 데이터 생성
GitHub Actions(크론)에서 3일마다 실행. API 키는 환경변수 SERVICE_KEY 로 주입(공개 repo라 하드코딩 금지).
출력:
  data/subsidies.json                 전체 원본+가공 마스터 (gitignore, 임시)
  data/index.json                     경량 변경감지 인덱스 (커밋, diff-changes.py가 사용)
  subsidy-finder/subsidies.js         조회기/진단기용 경량본 (window.SUBSIDY_DATA)
"""
import json, io, os, time, datetime, zlib, urllib.request

KEY = os.environ.get("SERVICE_KEY", "").strip()
if not KEY:
    raise SystemExit("SERVICE_KEY 환경변수가 없습니다. (GitHub Actions secret 등록 필요)")
BASE = "https://api.odcloud.kr/api/gov24/v3"
PER = 100
HERE = os.path.dirname(os.path.abspath(__file__))
TODAY = datetime.date.today().isoformat()

def fetch(endpoint, page):
    url = f"{BASE}/{endpoint}?page={page}&perPage={PER}&serviceKey={KEY}"
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return json.load(r)
        except Exception:
            if attempt == 3: raise
            time.sleep(1.5)

def fetch_all(endpoint):
    first = fetch(endpoint, 1)
    total = first["totalCount"]
    pages = (total + PER - 1) // PER
    rows = list(first["data"])
    for p in range(2, pages + 1):
        rows += fetch(endpoint, p)["data"]
        if p % 20 == 0: print(f"  {endpoint} {p}/{pages}")
    print(f"  {endpoint} 완료: {len(rows)}건")
    return rows

SIDO = [
    ("서울특별시","서울"),("부산광역시","부산"),("대구광역시","대구"),("인천광역시","인천"),
    ("광주광역시","광주"),("대전광역시","대전"),("울산광역시","울산"),("세종특별자치시","세종"),
    ("경기도","경기"),("강원특별자치도","강원"),("강원도","강원"),("충청북도","충북"),
    ("충청남도","충남"),("전북특별자치도","전북"),("전라북도","전북"),("전라남도","전남"),
    ("경상북도","경북"),("경상남도","경남"),("제주특별자치도","제주"),
]
CENTRAL_TYPES = {"중앙행정기관", "공공기관"}
def region_of(rec):
    typ = rec.get("소관기관유형") or ""
    name = rec.get("소관기관명") or ""
    if typ in CENTRAL_TYPES: return "전국"
    for full, short in SIDO:
        if name.startswith(full): return short
    return "전국"

BUCKETS = [("영유아",0,5),("어린이",6,12),("청소년",13,19),("20대",20,29),
           ("30대",30,39),("40대",40,49),("50대",50,59),("60대이상",60,200)]
def age_buckets(lo, hi):
    if lo is None and hi is None: return ["전연령"]
    lo = 0 if lo is None else lo
    hi = 200 if (hi is None or hi >= 120) else hi
    out = [n for n, blo, bhi in BUCKETS if lo <= bhi and hi >= blo]
    return out or ["전연령"]

INCOME = [("0-50","JA0201"),("51-75","JA0202"),("76-100","JA0203"),
          ("101-200","JA0204"),("200+","JA0205")]
def income_of(c):
    return [key for key, code in INCOME if c.get(code) == "Y"]

TRAIT_MAP = {
    "JA0302":"임산부","JA0303":"출산입양","JA0313":"농업인","JA0314":"어업인",
    "JA0315":"축산업인","JA0316":"임업인","JA0317":"초등학생","JA0318":"중학생",
    "JA0319":"고등학생","JA0320":"대학생","JA0326":"근로자","JA0327":"구직자",
    "JA0328":"장애인","JA0329":"보훈대상","JA0330":"질병질환","JA0401":"다문화",
    "JA0402":"북한이탈","JA0403":"한부모","JA0404":"1인가구","JA0411":"다자녀",
    "JA0412":"무주택","JA0413":"신규전입","JA1101":"예비창업","JA1102":"소상공인",
    "JA1103":"폐업위기",
}
def traits_of(c):
    return [label for code, label in TRAIT_MAP.items() if c.get(code) == "Y"]

def clip(s, n):
    if not s: return ""
    s = str(s).replace("\r\n", "\n").strip()
    return s if len(s) <= n else s[:n].rstrip() + "…"

def main():
    print("[1/4] 목록 수집");        L = fetch_all("serviceList")
    print("[2/4] 지원조건 수집");     C = fetch_all("supportConditions")
    cond = {r.get("서비스ID"): r for r in C}

    print("[3/4] 조인·가공")
    items = []
    for x in L:
        c = cond.get(x.get("서비스ID"), {})
        lo, hi = c.get("JA0110"), c.get("JA0111")
        items.append({
            "id": x.get("서비스ID"),
            "title": x.get("서비스명"),
            "description": clip(x.get("서비스목적요약"), 200),
            "category": x.get("서비스분야"),
            "region": region_of(x),
            "orgType": x.get("소관기관유형"),
            "org": x.get("소관기관명"),
            "ageMin": lo, "ageMax": hi,
            "ages": age_buckets(lo, hi),
            "income": income_of(c),
            "traits": traits_of(c),
            "supportType": x.get("지원유형"),
            "deadline": clip(x.get("신청기한"), 80),
            "content": clip(x.get("지원내용"), 500),
            "target": clip(x.get("지원대상"), 500),
            "criteria": clip(x.get("선정기준"), 500),
            "method": clip(x.get("신청방법"), 200),
            "views": x.get("조회수") or 0,
            "modified": (x.get("수정일시") or "")[:8],
            "registered": (x.get("등록일시") or "")[:8],
            "link": x.get("상세조회URL") or "https://www.gov.kr",
        })

    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)

    # 마스터 (전체 필드) — gitignore, 임시
    io.open(os.path.join(HERE, "data", "subsidies.json"), "w", encoding="utf-8").write(
        json.dumps({"updated": TODAY, "count": len(items),
                    "source": "data.go.kr gov24/v3 (보조금24)", "items": items}, ensure_ascii=False))

    # 변경감지 인덱스 (경량, 커밋) — diff-changes.py 가 이걸 비교
    idx = {}
    for i in items:
        idx[i["id"]] = {
            "t": i["title"], "cat": i["category"], "reg": i["region"],
            "r": i["registered"], "m": i["modified"], "v": i["views"], "u": i["link"],
            "h": zlib.crc32(("|".join([i["content"], i["target"], i["criteria"], i["method"], i["deadline"]])).encode("utf-8")),
        }
    io.open(os.path.join(HERE, "data", "index.json"), "w", encoding="utf-8").write(
        json.dumps({"updated": TODAY, "count": len(idx), "items": idx}, ensure_ascii=False))

    # 조회기/진단기용 경량본 (인기순 정렬)
    light = []
    for i in items:
        light.append({k: i[k] for k in ("id","title","description","category","region","org",
            "ageMin","ageMax","ages","income","traits","supportType","deadline","views","link","registered","modified")})
        light[-1]["content"] = clip(i["content"], 220)
        light[-1]["target"]  = clip(i["target"], 220)
        light[-1]["method"]  = clip(i["method"], 120)
    light.sort(key=lambda d: -(d["views"] or 0))
    js = ("window.SUBSIDY_DATA=" + json.dumps(light, ensure_ascii=False) + ";\n"
          + f'window.SUBSIDY_META={{"count":{len(light)},"updated":"{TODAY}"}};\n')
    io.open(os.path.join(HERE, "subsidy-finder", "subsidies.js"), "w", encoding="utf-8").write(js)

    print(f"[4/4] 저장 완료: {len(items)}건 (updated={TODAY})")

if __name__ == "__main__":
    main()

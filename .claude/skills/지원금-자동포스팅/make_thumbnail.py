#!/usr/bin/env python3
"""복돈 브랜드 썸네일 생성기 (루틴/클라우드용, 1200x630 PNG, 네이비+골드+복 워터마크).
저작권 안전(직접 그림, 스톡사진 없음). Pillow 필요. 한글 폰트는 아래 순서로 자동 탐색한다.

사용: python3 make_thumbnail.py <out.png> "<태그>" "<제목>" "<부제>"
예:   python3 make_thumbnail.py cover.png "고용·취업 · 실업급여" "2026 구직급여 완전정리" "상한 68,100원 · 최대 270일"

루틴 사용법: 생성 후 base64로 인코딩해 창구 publish의 cover_b64 로 전송.
  python3 -c "import base64,sys;print(base64.b64encode(open('cover.png','rb').read()).decode())"

★실패해도 발행은 계속하라 — 이미지가 없으면 tags:["이미지대기"] 를 붙여 로컬에서 나중에 보완한다.
"""
import sys, os, io, urllib.request

W, H = 1200, 630
NAVY1 = (22, 48, 90); NAVY2 = (34, 68, 122)
GOLD = (193, 154, 62); GOLDL = (205, 184, 119); WHITE = (255, 255, 255)

# 한글 폰트 탐색 순서: ①리눅스 흔한 경로 ②로컬 캐시 ③우리 저장소에서 다운로드(허용 도메인)
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "C:/Windows/Fonts/malgunbd.ttf",
    "C:/Windows/Fonts/malgun.ttf",
    "/tmp/bokdon-font.ttf",
]
FONT_URL = "https://raw.githubusercontent.com/hahakoreashop/bokdon-tools/main/assets/font-ko.ttf"


def find_font():
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    # 저장소에서 받아 캐시
    try:
        dst = "/tmp/bokdon-font.ttf"
        urllib.request.urlretrieve(FONT_URL, dst)
        if os.path.getsize(dst) > 100000:
            return dst
    except Exception:
        pass
    return None


def main(out, tag, title, sub):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("SKIP: Pillow 없음 — 썸네일 생략하고 발행 계속(tags에 이미지대기 포함)")
        return 2

    fp = find_font()
    if not fp:
        print("SKIP: 한글 폰트 없음 — 썸네일 생략하고 발행 계속(tags에 이미지대기 포함)")
        return 3

    def font(size):
        try:
            return ImageFont.truetype(fp, size)
        except Exception:
            return ImageFont.load_default()

    img = Image.new("RGB", (W, H), NAVY1)
    d = ImageDraw.Draw(img, "RGBA")
    # 우측 상단 골드 글로우
    d.ellipse([W - 260, -160, W + 80, 180], fill=(193, 154, 62, 40))

    # ★'복' 워터마크 — 실제 글리프 폭을 재서 왼쪽 경계(WM_LEFT)를 확정한다.
    #   글자 영역은 이 경계를 절대 넘지 않는다(2026-08-06 수정: 제목이 워터마크를 타고 올라가 겹쳐 읽히던 문제).
    WM_SIZE, WM_X, WM_Y = 400, W - 300, H - 470
    try:
        wf = font(WM_SIZE)
        bbox = d.textbbox((WM_X, WM_Y), "복", font=wf)   # 실제 잉크 영역
        d.text((WM_X, WM_Y), "복", font=wf, fill=(255, 255, 255, 16))
        WM_LEFT = bbox[0]
    except Exception:
        WM_LEFT = W
    TEXT_RIGHT = max(560, WM_LEFT - 28)   # 글자가 쓸 수 있는 오른쪽 한계
    TEXT_W = TEXT_RIGHT - 70              # 왼쪽 여백 70 기준 사용 가능 폭

    # 좌상단 밴드(단색 보조 네이비)로 깊이감
    d.rectangle([0, 0, W, 8], fill=GOLD)

    # 태그 칩 — 칩 폭은 '글자 시작 x(124) + 글자폭 + 오른쪽 여백(26)'이어야 글자가 안 삐져나온다.
    # (구버전은 70+tw+52 라서 글자가 칩 테두리를 뚫고 나갔음 — 2026-07-29 수정)
    ft = font(30)
    tw = d.textlength(tag, font=ft)
    d.rounded_rectangle([70, 84, 124 + tw + 26, 142], radius=29,
                        fill=(255, 255, 255, 26), outline=(205, 184, 119, 140), width=2)
    d.ellipse([96, 108, 112, 124], fill=GOLD)
    d.text((124, 97), tag, font=ft, fill=GOLDL)

    # 제목 — 워터마크 왼쪽(TEXT_RIGHT)까지만 쓰고, 3줄에 안 들어가면 글자를 줄인다.
    def wrap(text, f):
        out, cur = [], ""
        for w in text.split(" "):
            t = (cur + " " + w).strip()
            if d.textlength(t, font=f) <= TEXT_W:
                cur = t
            else:
                if cur:
                    out.append(cur)
                cur = w
        if cur:
            out.append(cur)
        return out

    ts = 74
    while ts > 46:
        fT = font(ts)
        lines = wrap(title, fT)
        # 3줄 이내 + 어떤 줄도 폭을 넘지 않아야 통과(긴 단어 하나가 삐져나오는 경우 방지)
        if len(lines) <= 3 and all(d.textlength(l, font=fT) <= TEXT_W for l in lines):
            break
        ts -= 4
    fT = font(ts)
    lines = wrap(title, fT)[:3]
    lh = int(ts * 1.24)
    y = 210 if len(lines) <= 2 else 186
    for ln in lines:
        d.text((70, y), ln, font=fT, fill=WHITE)
        y += lh

    # 골드 구분선 + 부제 — 길면 폰트를 줄여 한 줄에 맞춘다(잘림·워터마크 침범 방지)
    d.rectangle([72, y + 6, 222, y + 12], fill=GOLD)
    fs = 40
    while fs > 24 and d.textlength(sub, font=font(fs)) > TEXT_W:
        fs -= 2
    d.text((70, y + 34), sub, font=font(fs), fill=GOLDL)

    # 하단 브랜드
    fB = font(34)
    d.text((70, H - 70), "복돈", font=fB, fill=WHITE)
    d.text((70 + d.textlength("복돈", font=fB) + 16, H - 66), "· bokdon.com", font=font(30), fill=(200, 214, 228))

    img.save(out, "PNG")
    print("OK saved %s %d bytes (font=%s)" % (out, os.path.getsize(out), os.path.basename(fp)))
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 5:
        print('usage: python3 make_thumbnail.py <out.png> "<태그>" "<제목>" "<부제>"')
        sys.exit(1)
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]))

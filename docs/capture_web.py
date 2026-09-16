"""
업무도우미 웹 페이지 스크린샷 자동 캡처 스크립트
실행: python docs/capture_web.py 아이디 비밀번호
"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "https://paint-crosschecker-9zdx3camn4jl8c7fvbafxk.streamlit.app/"
OUT = Path(__file__).parent / "screenshots" / "web"
OUT.mkdir(parents=True, exist_ok=True)

PAGES = [
    ("근무표",         "근무표"),
    ("근무 통계",      "근무 통계"),
    ("일일 작업 일지", "일일 작업 일지"),
    ("재고 현황",      "재고 현황"),
    ("입고 관리",      "입고 관리"),
    ("반품 관리",      "반품 관리"),
]

def wait(page, ms=3000):
    page.wait_for_timeout(ms)

def shot(page, name):
    path = str(OUT / f"{name}.png")
    page.screenshot(path=path, full_page=False)
    print(f"  ✓ {name}.png")

def get_app_frame(page):
    """Streamlit 앱 iframe 반환"""
    page.wait_for_timeout(1000)
    for frame in page.frames:
        try:
            inp = frame.locator("input[type='password']")
            if inp.count() > 0:
                return frame
        except Exception:
            pass
    return None

def click_nav(page, label):
    """사이드바 버튼 클릭"""
    for frame in page.frames:
        try:
            btn = frame.locator(f"button:has-text('{label}')")
            if btn.count() > 0:
                btn.first.click()
                return True
        except Exception:
            pass
    return False

def main():
    args = sys.argv[1:]
    if len(args) >= 2:
        uid, pw = args[0], args[1]
    elif len(args) == 1:
        uid, pw = "", args[0]
    else:
        uid = input("아이디: ")
        pw = input("비밀번호: ")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
        page = ctx.new_page()

        print("\n[1] 접속 중...")
        page.goto(URL, timeout=60000)

        # 절전 해제
        try:
            wake_btn = page.locator("button:has-text('Yes, get this app back up!')").first
            wake_btn.wait_for(timeout=5000)
            wake_btn.click()
            print("  절전 해제 클릭")
            wait(page, 8000)
        except Exception:
            pass

        wait(page, 6000)
        shot(page, "00_login")

        # 로그인
        print("[2] 로그인 중...")
        frame = get_app_frame(page)
        if frame is None:
            print("  앱 프레임을 찾지 못했습니다.")
            shot(page, "00_debug")
            browser.close()
            return

        # 아이디 입력 (있는 경우)
        if uid:
            try:
                id_inp = frame.locator("input[type='text']").first
                id_inp.fill(uid)
            except Exception:
                pass

        # 비밀번호 입력
        pw_inp = frame.locator("input[type='password']").first
        pw_inp.fill(pw)
        page.keyboard.press("Enter")
        wait(page, 6000)
        shot(page, "01_main")

        # 각 페이지 캡처
        for i, (label, key) in enumerate(PAGES, 2):
            print(f"[{i+1}] {label} 캡처 중...")
            try:
                click_nav(page, label)
                wait(page, 4000)
                shot(page, f"{i:02d}_{key.replace(' ', '_')}")

                if key == "재고 현황":
                    try:
                        for frame in page.frames:
                            tab = frame.locator("div[role='tab']:has-text('날짜별 이력')")
                            if tab.count() > 0:
                                tab.first.click()
                                wait(page, 2000)
                                shot(page, f"{i:02d}_{key.replace(' ', '_')}_날짜별")
                                break
                    except Exception:
                        pass
            except Exception as e:
                print(f"  {label} 오류: {e}")

        print(f"\n완료! 저장 위치: {OUT}")
        wait(page, 1000)
        browser.close()

if __name__ == "__main__":
    main()

"""
앱 mockup 스크린샷 캡처
실행: python docs/capture_app.py
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

HTML = Path(__file__).parent / "app_mockup.html"
OUT  = Path(__file__).parent / "screenshots" / "app"
OUT.mkdir(parents=True, exist_ok=True)

SCREENS = [
    ("screen-main",      "01_main_scan"),
    ("screen-sector",    "02_sector_select"),
    ("screen-inventory", "03_inventory"),
    ("screen-history",   "04_history"),
]

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        page = ctx.new_page()
        page.goto(f"file:///{HTML.as_posix()}", wait_until="load")
        page.wait_for_timeout(500)

        for elem_id, name in SCREENS:
            elem = page.locator(f"#{elem_id}")
            path = str(OUT / f"{name}.png")
            elem.screenshot(path=path)
            print(f"  ✓ {name}.png")

        browser.close()
        print(f"\n완료! 저장 위치: {OUT}")

if __name__ == "__main__":
    main()

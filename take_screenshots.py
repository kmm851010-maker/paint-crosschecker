"""
Playwright로 Streamlit 앱 주요 화면 자동 캡처
"""
import asyncio
import os
from playwright.async_api import async_playwright

OUT_DIR = r"C:\Users\Kang's Fam\Downloads\Telegram Desktop\KG OPS 스샷\web"
os.makedirs(OUT_DIR, exist_ok=True)

BASE = "http://localhost:8501"

async def shot(page, name, wait_ms=1500):
    await asyncio.sleep(wait_ms / 1000)
    path = os.path.join(OUT_DIR, f"{name}.png")
    await page.screenshot(path=path, full_page=False)
    print(f"  saved: {name}.png")
    return path

async def click_tab(page, label):
    """Streamlit 탭 클릭 (버튼 텍스트 포함 매칭)"""
    try:
        btn = page.get_by_role("tab", name=label, exact=False)
        await btn.first.click()
        await asyncio.sleep(1.2)
    except Exception as e:
        print(f"  tab '{label}' not found: {e}")

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            viewport={"width": 1280, "height": 900}
        )
        page = await ctx.new_page()
        print("Navigating to Streamlit app...")
        await page.goto(BASE, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(3)

        # 1. 초기 화면
        await shot(page, "01_main")

        # 2. 업무현황 / 작업일지
        await click_tab(page, "업무현황")
        await shot(page, "02_work_status")

        # 3. 근태관리
        await click_tab(page, "근태관리")
        await shot(page, "03_attendance")

        # 4. 재고현황
        await click_tab(page, "재고현황")
        await shot(page, "04_inventory_web")

        # 4b. 스크롤 다운
        await page.mouse.wheel(0, 400)
        await asyncio.sleep(0.8)
        await shot(page, "04b_inventory_web_scroll")

        # 5. 입고대조
        await click_tab(page, "입고")
        await shot(page, "05_crosscheck")

        await browser.close()
        print(f"\n캡처 완료! 저장 위치: {OUT_DIR}")

asyncio.run(main())

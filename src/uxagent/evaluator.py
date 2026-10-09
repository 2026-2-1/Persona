from __future__ import annotations

from urllib.parse import urlsplit


async def evaluate(page, evaluator_id: str) -> dict:
    if evaluator_id != "local-bag-detail-v1":
        return {"verification":"unknown", "reason":"unknown_evaluator"}
    if urlsplit(page.url).path.endswith("shop.html") is False:
        return {"verification":"failure", "reason":"not_on_shop_page"}
    try:
        state = await page.evaluate("""() => {const d=document.querySelector('#detail');const n=window.getActiveProduct?.();return {visible:!!d&&!d.classList.contains('hidden'),kind:n?.kind,color:n?.color,price:n?.price}}""")
        success = state["visible"] and state["kind"] == "가방" and state["color"] == "검정" and state["price"] <= 30000
        return {"verification":"success" if success else "failure", "reason":"matching_detail_visible" if success else "criteria_not_met"}
    except Exception as exc:
        return {"verification":"unknown", "reason":f"evaluator_error:{exc}"}

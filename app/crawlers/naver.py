"""NAVER crawler adapter over the existing Playwright implementation."""


def crawl_reviews(product_url: str, headless: bool = True) -> dict:
    # Playwright is imported lazily so API-only processes do not need a browser.
    from scripts.crawl_naver_reviews_playwright import (
        crawl_with_playwright,
        extract_product_id,
        import_playwright,
    )

    sync_playwright = import_playwright()
    if sync_playwright is None:
        raise RuntimeError("Playwright is not installed")

    product_id = extract_product_id(product_url)
    return crawl_with_playwright(
        sync_playwright,
        product_url,
        product_id,
        headless=headless,
    )

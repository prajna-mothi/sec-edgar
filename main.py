import os
import asyncio
import pandas as pd
from pyppeteer import launch

from sec_utils import (
    load_company_indices,
    fetch_target_company_cik,
    get_recent_10k_filings_url,
    fetch_html_url_from_filing,
)
from pdf_utils import html_to_pdf, CHROME_PATH

import logging

logging.basicConfig(level=logging.INFO)

COMPANIES = ["Apple", "Meta", "Alphabet", "Amazon", "Netflix", "Goldman Sachs"]
OUTPUT_DIR = "10k_pdfs"
CONCURRENT_PAGES = 3  # limiting concurrent open pages to avoid hanging


async def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    df = load_company_indices()
    if df.empty:
        logging.error("Could not load SEC company indices.")
        return

    browser = await launch(headless=True, executablePath=CHROME_PATH, args=["--no-sandbox"])
    semaphore = asyncio.Semaphore(CONCURRENT_PAGES)  # concurrency limit
    tasks = []

    for company in COMPANIES:
        cik = fetch_target_company_cik(df, company)
        if not cik:
            logging.warning(f"CIK not found for {company}")
            continue

        filings = get_recent_10k_filings_url(cik)
        if filings.empty:
            logging.warning(f"No 10-K filings found for {company}")
            continue

        for _, filing in filings.iterrows():
            url = fetch_html_url_from_filing(filing)
            accession = filing["accessionNumber"].replace("-", "")
            output_file = os.path.join(OUTPUT_DIR, f"{company}_10K_{accession}.pdf")

            async def sem_task(url=url, output_file=output_file):
                async with semaphore:
                    await html_to_pdf(browser, url, output_file)

            tasks.append(sem_task())

    if tasks:
        await asyncio.gather(*tasks)

    try:
        await browser.close()
    except Exception as e:
        logging.error(f"Error closing browser: {e}")

    


if __name__ == "__main__":
    asyncio.run(main())

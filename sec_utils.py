import os
import requests
import pandas as pd
import difflib
import re
import time
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO)
load_dotenv()

HEADERS = {
    'User-Agent': os.getenv("SEC_USER_AGENT")
}
def load_company_indices() -> pd.DataFrame:
    """Fetch company_tickers.json and return DataFrame with cik_str (10-digit)."""
    try:
        response = requests.get('https://www.sec.gov/files/company_tickers.json', headers=HEADERS)
        response.raise_for_status()
        data = response.json()
        df = pd.DataFrame.from_dict(data, orient='index')
        df['title'] = df['title'].astype(str).str.strip()
        df['cik_str'] = df['cik_str'].apply(lambda x: str(x).zfill(10))
        return df
    except Exception as e:
        logging.error(f"Error loading company indices: {e}")
        return pd.DataFrame(columns=['cik_str', 'ticker', 'title'])

def _similarity(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()

def fetch_target_company_cik(df: pd.DataFrame, company_name: str, threshold=0.6) -> str | None:
    """
    Given a DataFrame of company indices and a company name, return the CIK against the company name.
    """
    try:
        company_lower = company_name.strip().lower()
        if df.empty:
            return None

        
        df = df.copy()
        df['title_lower'] = df['title'].str.lower()

        # First, try exact match
        exact_match = df[df['title_lower'] == company_lower]
        if not exact_match.empty:
            return exact_match.iloc[0]['cik_str']

        # Next, try boundary match
        pattern = rf"\b{re.escape(company_lower)}\b"
        boundary_match = df[df['title_lower'].str.contains(pattern, regex=True, na=False)]
        if not boundary_match.empty:
            return boundary_match.iloc[0]['cik_str']

        # Next, try fuzzy matching
        candidates = df['title_lower'].tolist()
        fuzzy_matches = difflib.get_close_matches(company_lower, candidates, n=5, cutoff=threshold)
        if fuzzy_matches:
            best_match = max(fuzzy_matches, key=lambda x: _similarity(company_lower, x))
            match_row = df[df['title_lower'] == best_match]
            if not match_row.empty:
                return match_row.iloc[0]['cik_str']

        # not found
        return None
    except Exception as e:
        logging.error(f"Error fetching CIK for {company_name}: {e}")
        return None

def get_recent_10k_filings_url(cik: str, delay: float = 0.2) -> pd.DataFrame:
    """
    Fetch recent filings for a company by CIK and return DataFrame with only 10-K forms urls.
    """
    submissions_api_url = f'https://data.sec.gov/submissions/CIK{cik}.json'
    response = requests.get(submissions_api_url, headers=HEADERS)
    if response.status_code == 429:
        time.sleep(1)
        return get_recent_10k_filings_url(cik, delay)
    response.raise_for_status()
    data = response.json()

    # the JSON has data['filings']['recent']
    filings = pd.DataFrame.from_dict(data.get('filings', {}).get('recent', {}))
    if filings.empty:
        return pd.DataFrame()  # no filings

    filings_10k = filings[filings['form'] == '10-K'].copy()
    if filings_10k.empty:
        return pd.DataFrame()

    filings_10k['cik'] = cik

    # to avoid hitting rate limits
    time.sleep(delay)
    return filings_10k

def fetch_html_url_from_filing(filing: pd.Series) -> str:
    """
    Given a filing Series (row), construct and return the full HTML URL.
    """
    base_url = "https://www.sec.gov/Archives/edgar/data"
    accession_number = filing['accessionNumber'].replace("-", "") 
    primary_doc = filing['primaryDocument']
    full_url = f"{base_url}/{filing['cik']}/{accession_number}/{primary_doc}"
    logging.info(f"Constructed URL: {full_url}")
    return full_url

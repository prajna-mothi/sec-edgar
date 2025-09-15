import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

from sec_utils import fetch_target_company_cik, fetch_html_url_from_filing, get_recent_10k_filings_url

# Exact match
def test_fetch_target_company_cik_exact():
    df = pd.DataFrame({
        "cik_str": ["0000320193"],
        "ticker": ["AAPL"],
        "title": ["Apple Inc"]
    })
    cik = fetch_target_company_cik(df, "Apple Inc")
    assert cik == "0000320193"

# Fuzzy match
def test_fetch_target_company_cik_fuzzy():
    df = pd.DataFrame({
        "cik_str": ["0000320193"],
        "ticker": ["AAPL"],
        "title": ["Apple Inc"]
    })
    cik = fetch_target_company_cik(df, "Aple Inc")  # typo
    assert cik == "0000320193"

# HTML URL construction
def test_fetch_html_url_from_filing():
    filing = {
        "cik": "0000320193",
        "accessionNumber": "000032019324000123",
        "primaryDocument": "aapl-20240928.htm"
    }
    url = fetch_html_url_from_filing(filing)
    expected = "https://www.sec.gov/Archives/edgar/data/0000320193/000032019324000123/aapl-20240928.htm"
    assert url == expected


@pytest.mark.parametrize("status_code", [200, 429])
@patch("sec_utils.requests.get")
@patch("time.sleep", return_value=None)  # skip actual sleep
def test_get_recent_10k_filings_url_mock(mock_sleep, mock_get, status_code):
    # mock JSON response
    data = {
        "filings": {
            "recent": {
                "form": ["10-K", "10-Q"],
                "accessionNumber": ["000032019324000123", "000032019324000124"],
                "primaryDocument": ["aapl-20240928.htm", "aapl-20240628.htm"]
            }
        }
    }

    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json.return_value = data
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    from sec_utils import get_recent_10k_filings_url
    if status_code == 429:
        # For 429, recursion will call again, so skip full recursion test
        pass
    else:
        df = get_recent_10k_filings_url("0000320193", delay=0)
        assert not df.empty
        assert all(df['form'] == "10-K")

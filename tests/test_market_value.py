"""Market value scraper checks against trimmed copies of real portal responses
(captured 2026-10-15). No network: the portal is never called.

Run from the repo root:  python -m pytest tests
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.core.errors import BAD_INPUT, NOT_FOUND, PORTAL_DOWN, PortalError
from backend.routers import market_value as mv_router
from backend.scrapers.market_value import client

# Header + two data rows as the portal sends them, including the columns it
# comments out (apartment rate, classification) and the "Get" door-no button.
RATES_HTML = """
<table width="100%" class="table table-bordered table-responsive">
<tr>
  <th class="formhd1">S.No.</th><th class="formhd1">Ward-Block</th><th class="formhd1">Locality</th>
  <th class="formhd1">Land Value<br/>(Rs. per Sq.Yard)</th>
  <!--<th class="formhd1">Apartment value<br/> (Rs. per Sq.Ft)</th>-->
  <!--<th class="formhd1">Classification</th>-->
  <th class="formhd1">Effective Date<br>(dd/mm/yyyy)</th><th class="formhd1">Door No. Wise<br>Details - Rates</th>
</tr>
<tr>
  <td class="formbg2"><b>1.</td>
  <td class="formbg2"><b>0</b>
      -
      <b>4</b></td>
  <td class="formbg2">KOKAPET CHANDRA REDDY CIRCLE TO ORR SERVICE R</td>
  <td class="formbg2">        47,600</td>
  <!--<td class="formbg2">         6,600</td>-->
  <!--<td class="formbg2">02(Commercial)</td>-->
  <td class="formbg2">05/06/2026</td>
  <td class="formbg2">
    <input type="button" name="button" value="Get" class="btn btn-custom" onclick="getDetails('0', '4', 'KOKAPET CHANDRA REDDY CIRCLE TO ORR SERVICE R','        47,600')"/>
  </td>
</tr>
<tr>
  <td class="formbg2"><b>2.</td>
  <td class="formbg2"><b>0</b> - <b>4</b></td>
  <td class="formbg2">KOKAPET VILLAGE MAIN ROADS</td>
  <td class="formbg2">        27,000</td>
  <!--<td class="formbg2">         2,700</td>-->
  <!--<td class="formbg2">01(Residential)</td>-->
  <td class="formbg2">05/06/2026</td>
  <td class="formbg2"></td>
</tr>
</table>
"""

ERROR_MSG_HTML = """<!DOCTYPE html><html><head><title>JSP Page</title></head>
<body><center>  <h1>Error Msg</h1></center></body></html>"""


def _raises(user_message, fn, *args, **kwargs):
    with pytest.raises(PortalError) as info:
        fn(*args, **kwargs)
    assert info.value.user_message == user_message


def test_parses_only_the_columns_the_portal_shows():
    result = client._parse_rates(RATES_HTML)
    assert result["found"] is True
    assert result["rows"] == [
        {
            "ward_block": "0 - 4",
            "locality": "KOKAPET CHANDRA REDDY CIRCLE TO ORR SERVICE R",
            "land_rate_per_sq_yard": "47,600",
            "effective_date": "05/06/2026",
        },
        {
            "ward_block": "0 - 4",
            "locality": "KOKAPET VILLAGE MAIN ROADS",
            "land_rate_per_sq_yard": "27,000",
            "effective_date": "05/06/2026",
        },
    ]


def test_header_only_table_is_not_found():
    header_only = RATES_HTML.split("<tr>\n  <td")[0] + "</table>"
    _raises(NOT_FOUND, client._parse_rates, header_only)


def test_error_msg_page_is_bad_input():
    _raises(BAD_INPUT, client._parse_rates, ERROR_MSG_HTML)


def test_unknown_page_is_portal_error():
    _raises(PORTAL_DOWN, client._parse_rates, "<html><body>Service Unavailable</body></html>")


def test_pairs_are_parsed_like_the_browser():
    text = "1611/AMEERPET-1 & 6-3##1516024/BANDLAGUDA  (JAGIR)##1604/A/B##\n"
    assert client._parse_pairs(text) == [
        {"value": "1611", "label": "AMEERPET-1 & 6-3"},
        {"value": "1516024", "label": "BANDLAGUDA (JAGIR)"},
        {"value": "1604", "label": "A"},
    ]
    assert client._parse_pairs("") == []
    _raises(BAD_INPUT, client._parse_pairs, "Malicious")


def test_inputs_are_checked_before_the_portal():
    # "~" is the separator inside the portal's `codes` parameter.
    _raises(BAD_INPUT, client.search_hyderabad_localities, "1600001", "ab~c")
    _raises(BAD_INPUT, client.search_hyderabad_localities, "1600001", "ab")
    _raises(BAD_INPUT, client.fetch_rates, district_id="15_1", mandal_id="07", mandal="GANDIPET", village_id="x", village="KOKAPET")
    _raises(BAD_INPUT, client.fetch_rates, district_id="16_1", division_id="1600001", locality_id="1611", locality="")


@pytest.mark.parametrize("message, status", [(NOT_FOUND, 404), (BAD_INPUT, 400), (PORTAL_DOWN, 502)])
def test_router_maps_errors_to_status_codes(monkeypatch, message, status):
    def fail(**_):
        raise PortalError(message)

    monkeypatch.setattr(client, "fetch_rates", fail)
    app = FastAPI()
    app.include_router(mv_router.router)
    resp = TestClient(app).post("/api/market-value/search", json={"district_id": "15_1"})
    assert resp.status_code == status
    assert resp.json()["detail"] == message

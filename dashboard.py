from __future__ import annotations

import os
import hmac
import sqlite3
import urllib.parse
import urllib.request

import pandas as pd
import streamlit as st
import alpaca_trade_api as tradeapi

from event_engine import EventEngine


st.set_page_config(
    page_title="APEX Research Dashboard",
    layout="wide",
)

# This dashboard exposes account and trade information and can send an
# operational Telegram message. Require a separate secret before rendering.
dashboard_password = os.getenv("APEX_DASHBOARD_PASSWORD", "")
if not dashboard_password:
    st.error("Dashboard access is not configured.")
    st.stop()

if not st.session_state.get("apex_dashboard_authenticated", False):
    entered_password = st.text_input("Dashboard password", type="password")
    if st.button("Sign in"):
        if hmac.compare_digest(entered_password, dashboard_password):
            st.session_state["apex_dashboard_authenticated"] = True
            st.rerun()
        else:
            st.error("Invalid password.")
    st.stop()

st.title("APEX + JALWE — Research Dashboard")
st.caption(
    "APEX is research-only. Broker execution authority belongs only "
    "to JALWE V4 on Alpaca PAPER."
)


TELEGRAM_TOKEN = (
    os.getenv("TELEGRAM_TOKEN", "").strip()
    or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
)
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

APCA_API_KEY_ID = os.getenv("APCA_API_KEY_ID", "").strip()
APCA_API_SECRET_KEY = os.getenv("APCA_API_SECRET_KEY", "").strip()
APCA_API_BASE_URL = os.getenv(
    "APCA_API_BASE_URL",
    "https://paper-api.alpaca.markets",
).strip()


def paper_url_ready() -> bool:
    return (
        "paper-api.alpaca.markets"
        in APCA_API_BASE_URL.lower()
    )


def send_telegram_alert(message: str) -> tuple[bool, str]:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False, "Telegram is not configured."

    url = (
        "https://api.telegram.org/bot"
        + TELEGRAM_TOKEN
        + "/sendMessage"
    )
    payload = urllib.parse.urlencode(
        {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": str(message),
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        url=url,
        data=payload,
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=15,
        ) as response:
            if response.status == 200:
                return True, "OK"
            return False, f"HTTP {response.status}"
    except Exception as exc:
        return False, str(exc)


def paper_account_snapshot() -> tuple[dict | None, str | None]:
    if not APCA_API_KEY_ID or not APCA_API_SECRET_KEY:
        return None, "Alpaca PAPER credentials are not configured."

    if not paper_url_ready():
        return None, "Blocked: Alpaca URL is not PAPER."

    try:
        api = tradeapi.REST(
            APCA_API_KEY_ID,
            APCA_API_SECRET_KEY,
            APCA_API_BASE_URL,
            api_version="v2",
        )
        account = api.get_account()
        positions = api.list_positions()

        return {
            "equity": float(account.equity),
            "cash": float(account.cash),
            "positions": len(positions),
        }, None

    except Exception as exc:
        return None, str(exc)


def read_table(
    query: str,
    db_path: str = "jalwe_learning.db",
) -> pd.DataFrame:
    try:
        with sqlite3.connect(db_path) as conn:
            return pd.read_sql(query, conn)
    except Exception:
        return pd.DataFrame()


st.sidebar.header("Safety")
st.sidebar.success("APEX: RESEARCH ONLY")
st.sidebar.info("JALWE execution target: Alpaca PAPER only")
st.sidebar.write(
    "Paper URL: "
    + ("OK" if paper_url_ready() else "BLOCKED")
)

snapshot, account_error = paper_account_snapshot()

col1, col2, col3 = st.columns(3)

if snapshot is not None:
    col1.metric("PAPER Equity", f"${snapshot['equity']:,.2f}")
    col2.metric("PAPER Cash", f"${snapshot['cash']:,.2f}")
    col3.metric("Open PAPER Positions", snapshot["positions"])
else:
    col1.metric("PAPER Equity", "Unavailable")
    col2.metric("PAPER Cash", "Unavailable")
    col3.metric("Open PAPER Positions", "Unavailable")
    st.warning(
        "Alpaca PAPER account data unavailable: "
        + str(account_error)
    )


st.subheader("Macro / Event Context")
event_status = EventEngine().check_event_risk("PORTFOLIO")
st.info(
    f"Risk: {event_status.get('event_risk', 'UNKNOWN')}\n\n"
    f"Action: {event_status.get('action', 'REVIEW')}\n\n"
    f"Reason: {event_status.get('reason', '')}"
)


st.subheader("Legacy research database view")
active_df = read_table(
    """
    SELECT symbol, entry_price, stop_loss_price,
           highest_price, qty, status
    FROM active_trades_tracker
    WHERE status='ACTIVE'
    """
)

if active_df.empty:
    st.caption("No active legacy records available.")
else:
    st.dataframe(active_df, use_container_width=True)


closed_df = read_table(
    """
    SELECT symbol, entry_price, exit_price,
           profit_pct, result_status, timestamp
    FROM closed_trades_performance
    ORDER BY id DESC
    LIMIT 100
    """
)

if not closed_df.empty:
    st.dataframe(closed_df, use_container_width=True)


st.markdown("---")
if st.button("Send test Telegram alert"):
    ok, detail = send_telegram_alert(
        "APEX research dashboard test alert."
    )
    if ok:
        st.success("Telegram alert sent.")
    else:
        st.error("Telegram alert failed: " + detail)


st.caption(
    "No BUY/SELL controls are exposed by this dashboard."
)

STATUS_COLOR = {
    "approved": "green",
    "approve": "green",
    "passed": "green",
    "rejected": "red",
    "reject": "red",
    "failed": "red",
    "manual_review": "orange",
    "review": "orange",
    "partial": "orange",
    "pending": "gray",
}


def apply_global_styles() -> None:
    import streamlit as st

    st.markdown(
        """
        <style>
        .main .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
        }
        section[data-testid="stSidebar"] {
            border-right: 1px solid rgba(148, 163, 184, 0.2);
        }
        div[data-testid="stMetric"] {
            background: linear-gradient(135deg, rgba(248, 250, 252, 0.95), rgba(241, 245, 249, 0.8));
            border: 1px solid rgba(148, 163, 184, 0.22);
            border-radius: 16px;
            min-height: 112px;
            padding: 12px 14px;
            box-shadow: 0 6px 18px rgba(15, 23, 42, 0.05);
            display: flex;
            flex-direction: column;
            justify-content: center;
        }
        div[data-testid="stMetric"] label,
        div[data-testid="stMetric"] div {
            color: #000000;
        }
        div[data-testid="stMetricValue"] {
            font-size: clamp(0.9rem, 1.4vw, 1.25rem);
            line-height: 1.15;
            overflow-wrap: anywhere;
            word-break: break-word;
            white-space: normal;
        }
        div[data-testid="stMetricLabel"] {
            font-size: 0.78rem;
            line-height: 1.1;
            white-space: normal;
        }
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 18px;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
        }
        .stButton > button {
            border-radius: 12px;
            font-weight: 600;
        }
        .stSelectbox div[data-baseweb="select"],
        .stTextInput input,
        .stTextArea textarea {
            border-radius: 12px;
        }
        div[data-testid="stDataFrame"] {
            border-radius: 14px;
            overflow: hidden;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def status_badge(value: str | None) -> str:
    v = (value or "unknown").strip()
    color = STATUS_COLOR.get(v.lower(), "gray")
    return f":{color}[**{v}**]"


def severity_badge(value: str | None) -> str:
    color = {"high": "red", "medium": "orange", "low": "blue"}.get(
        (value or "").lower(), "gray"
    )
    return f":{color}[{value or 'unknown'}]"


def fmt_currency(amount, currency: str | None) -> str:
    if amount is None:
        return "-"
    return f"{currency or ''} {amount:,.2f}".strip()

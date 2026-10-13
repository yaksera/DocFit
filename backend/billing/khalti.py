"""Khalti ePayment (v2) client. Docs: https://docs.khalti.com/khalti-epayment/

Flow: initiate -> redirect the customer to payment_url -> Khalti redirects back to
return_url?pidx=... -> we confirm with the lookup API (never trust the query string).
"""
import requests
from django.conf import settings


class KhaltiError(Exception):
    pass


def _post(path: str, payload: dict) -> dict:
    if not settings.KHALTI_SECRET_KEY:
        raise KhaltiError("Online payment is not configured.")
    try:
        r = requests.post(settings.KHALTI_BASE_URL.rstrip("/") + "/" + path, json=payload, timeout=20,
                          headers={"Authorization": f"Key {settings.KHALTI_SECRET_KEY}"})
    except requests.RequestException as exc:
        raise KhaltiError("Could not reach Khalti. Please try again.") from exc
    try:
        data = r.json()
    except ValueError:
        data = {}
    if r.status_code >= 400:
        detail = data.get("detail") or data.get("error_key") or r.text[:200]
        raise KhaltiError(f"Khalti error: {detail}")
    return data


def initiate(*, amount_paisa: int, order_id: str, order_name: str, return_url: str, website_url: str,
             customer: dict) -> dict:
    payload = {"return_url": return_url, "website_url": website_url, "amount": amount_paisa,
               "purchase_order_id": order_id, "purchase_order_name": order_name}
    customer = {k: v for k, v in customer.items() if v}
    if customer:
        payload["customer_info"] = customer
    return _post("epayment/initiate/", payload)


def lookup(pidx: str) -> dict:
    return _post("epayment/lookup/", {"pidx": pidx})

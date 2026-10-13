import io
import zipfile
from datetime import timedelta
from unittest import mock

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import ApiKey, Organization, User
from billing.models import Payment, Plan
from jobs import processing
from jobs.models import Job

pytestmark = pytest.mark.django_db


@pytest.fixture
def queued(monkeypatch):
    """Capture enqueued jobs instead of starting workers; tests run them explicitly."""
    ids = []
    monkeypatch.setattr("jobs.runner.enqueue", lambda job_id: ids.append(job_id))
    return ids


def register(client, email="owner@abc.com", org="ABC Education Consultancy"):
    r = client.post("/api/auth/register", {"organization": org, "full_name": "Ram Thapa", "email": email,
                                           "password": "Kathmandu#2026", "phone": "9800000000"},
                    format="json")
    assert r.status_code == 201, r.data
    return r


@pytest.fixture
def owner():
    c = APIClient()
    register(c)
    return c


def upload(client, path, **data):
    with open(path, "rb") as f:
        name = path.split("\\")[-1].split("/")[-1]
        return client.post("/api/jobs", {"files": [f], **data}, format="multipart")


def test_register_login_me():
    c = APIClient()
    r = register(c)
    assert r.data["plan"]["code"] == "free"
    assert r.data["user"]["role"] == "owner"
    c.post("/api/auth/logout")
    assert c.get("/api/auth/me").status_code == 401
    r = c.post("/api/auth/login", {"email": "OWNER@abc.com", "password": "wrong"}, format="json")
    assert r.status_code == 400
    r = c.post("/api/auth/login", {"email": "OWNER@abc.com", "password": "Kathmandu#2026"}, format="json")
    assert r.status_code == 200
    assert c.get("/api/auth/me").data["usage"]["used"] == 0


def test_register_rejects_weak_password_and_duplicates():
    c = APIClient()
    r = c.post("/api/auth/register", {"organization": "X", "full_name": "A", "email": "a@x.com",
                                      "password": "12345678"}, format="json")
    assert r.status_code == 400 and r.data["detail"]
    register(c, email="dup@x.com")
    r = APIClient().post("/api/auth/register", {"organization": "Y", "full_name": "B", "email": "DUP@x.com",
                                                "password": "Kathmandu#2026"}, format="json")
    assert r.status_code == 400


def test_upload_process_download_preview(owner, queued, scan_pdf):
    r = upload(owner, scan_pdf, target_kb=300, label="Sita Shrestha")
    assert r.status_code == 201, r.data
    job_id = r.data[0]["id"]
    assert r.data[0]["status"] == "queued" and len(queued) == 1

    processing.process_job(queued[0])
    job = owner.get(f"/api/jobs/{job_id}").data
    assert job["status"] == "done", job
    assert job["met_target"] and job["output_bytes"] <= 300_000
    assert job["output_name"] == "scan-compressed.pdf"

    r = owner.get(f"/api/jobs/{job_id}/download")
    assert r.status_code == 200 and b"".join(r.streaming_content)[:5] == b"%PDF-"
    for side in ("before", "after"):
        r = owner.get(f"/api/jobs/{job_id}/preview/{side}?page=2&width=400")
        assert r.status_code == 200 and r["Content-Type"] == "image/jpeg"

    r = owner.post("/api/jobs/zip", {"ids": [job_id]}, format="json")
    assert zipfile.ZipFile(io.BytesIO(r.content)).namelist() == ["Sita Shrestha/scan-compressed.pdf"]

    assert owner.get("/api/jobs/stats").data["total_docs"] == 1
    assert owner.get("/api/auth/me").data["usage"]["used"] == 1


def test_merge_creates_one_job_otherwise_one_per_file(owner, queued, scan_pdf, digital_pdf):
    with open(scan_pdf, "rb") as a, open(digital_pdf, "rb") as b:
        r = owner.post("/api/jobs", {"files": [a, b], "merge": "true", "target": "1MB"}, format="multipart")
    assert r.status_code == 201 and len(r.data) == 1
    with open(scan_pdf, "rb") as a, open(digital_pdf, "rb") as b:
        r = owner.post("/api/jobs", {"files": [a, b], "target": "1MB"}, format="multipart")
    assert len(r.data) == 2
    processing.process_job(queued[0])
    assert Job.objects.get(pk=queued[0]).pages == 4


def test_rejects_bad_files(owner, queued, tmp_path):
    exe = tmp_path / "virus.exe"
    exe.write_bytes(b"MZ....")
    assert upload(owner, str(exe)).status_code == 400
    fake = tmp_path / "fake.pdf"
    fake.write_bytes(b"hello world")
    assert upload(owner, str(fake)).status_code == 400
    assert not queued


def test_password_retry_flow(owner, queued, locked_pdf):
    job_id = upload(owner, locked_pdf, target_kb=500).data[0]["id"]
    processing.process_job(queued[0])
    job = owner.get(f"/api/jobs/{job_id}").data
    assert job["status"] == "failed" and job["error_code"] == "password_required"
    r = owner.post(f"/api/jobs/{job_id}/retry", {"password": "1234"}, format="json")
    assert r.status_code == 200
    processing.process_job(queued[-1])
    job = Job.objects.get(pk=job_id)
    assert job.status == "done" and job.password == ""  # password is never kept


def test_monthly_quota(owner, queued, digital_pdf):
    org = Organization.objects.get()
    Plan.objects.filter(code="free").update(monthly_docs=1)
    assert upload(owner, digital_pdf).status_code == 201
    r = upload(owner, digital_pdf)
    assert r.status_code == 403 and "Upgrade" in r.data["detail"]
    assert org.docs_used() == 1


def test_upload_size_limit(owner, queued, scan_pdf):
    Plan.objects.filter(code="free").update(max_upload_mb=1)
    r = upload(owner, scan_pdf)
    assert r.status_code == 400 and "1 MB" in r.data["detail"]


def test_organizations_are_isolated(owner, queued, digital_pdf):
    job_id = upload(owner, digital_pdf).data[0]["id"]
    processing.process_job(queued[0])
    other = APIClient()
    register(other, email="other@xyz.com", org="XYZ Consultancy")
    assert other.get(f"/api/jobs/{job_id}").status_code == 404
    assert other.get(f"/api/jobs/{job_id}/download").status_code == 404
    assert other.get("/api/jobs").data["count"] == 0


def test_expired_files_are_purged(owner, queued, digital_pdf):
    job_id = upload(owner, digital_pdf).data[0]["id"]
    processing.process_job(queued[0])
    job = Job.objects.get(pk=job_id)
    assert job.dir.exists()
    Job.objects.filter(pk=job_id).update(expires_at=timezone.now() - timedelta(minutes=1))
    assert processing.purge_expired() == 1
    assert not job.dir.exists()
    assert owner.get(f"/api/jobs/{job_id}").data["status"] == "expired"
    assert owner.get(f"/api/jobs/{job_id}/download").status_code == 404


def test_team_invites_and_seats(owner):
    r = owner.post("/api/team/invites", {"role": "member"}, format="json")
    assert r.status_code == 403  # free plan has 1 seat
    org = Organization.objects.get()
    org.plan = Plan.objects.get(code="starter")
    org.plan_expires_at = timezone.now() + timedelta(days=30)
    org.save()
    r = owner.post("/api/team/invites", {"role": "member"}, format="json")
    assert r.status_code == 201
    token = r.data["url"].rsplit("/", 1)[1]

    staff = APIClient()
    assert staff.get(f"/api/invites/{token}").data["organization"] == "ABC Education Consultancy"
    r = staff.post(f"/api/invites/{token}", {"full_name": "Gita", "email": "gita@abc.com",
                                             "password": "Pokhara#2026"}, format="json")
    assert r.status_code == 201 and r.data["user"]["role"] == "member"
    assert staff.post(f"/api/invites/{token}", {"full_name": "X", "email": "x@abc.com",
                                                "password": "Pokhara#2026"}, format="json").status_code == 400
    # members cannot manage the team
    assert staff.post("/api/team/invites", {"role": "member"}, format="json").status_code == 403
    gita = User.objects.get(email="gita@abc.com")
    assert owner.delete(f"/api/team/members/{gita.pk}").status_code == 204
    assert not User.objects.get(pk=gita.pk).is_active


def test_expired_paid_plan_falls_back_to_free():
    org = Organization.objects.create(name="O", plan=Plan.objects.get(code="pro"),
                                      plan_expires_at=timezone.now() - timedelta(days=1))
    assert org.effective_plan.code == "free"


def test_api_key_auth(owner, queued, digital_pdf):
    assert owner.post("/api/keys", {"name": "CRM"}, format="json").status_code == 403  # free plan
    Organization.objects.update(plan=Plan.objects.get(code="pro"),
                                plan_expires_at=timezone.now() + timedelta(days=30))
    r = owner.post("/api/keys", {"name": "CRM"}, format="json")
    assert r.status_code == 201 and r.data["key"].startswith("dfk_")
    api = APIClient()
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['key']}")
    r = upload(api, digital_pdf, target="500KB")  # no CSRF needed with an API key
    assert r.status_code == 201 and r.data[0]["via_api"]
    owner.delete(f"/api/keys/{ApiKey.objects.get().pk}")
    assert api.get("/api/jobs").status_code == 401


def test_khalti_payment_activates_plan(owner, settings):
    settings.KHALTI_SECRET_KEY = "test_secret"
    with mock.patch("billing.khalti.initiate",
                    return_value={"pidx": "PIDX1", "payment_url": "https://pay.khalti.com/x"}):
        r = owner.post("/api/billing/khalti/initiate", {"plan": "starter", "months": 12}, format="json")
    assert r.status_code == 200 and r.data["payment_url"].startswith("https://")
    payment = Payment.objects.get()
    assert payment.amount_npr == 999 * 10  # yearly: 2 months free

    # Tampered/underpaid amount is rejected
    with mock.patch("billing.khalti.lookup", return_value={"status": "Completed", "total_amount": 100}):
        r = owner.get("/api/billing/khalti/return?pidx=PIDX1&status=Completed")
    assert "payment=failed" in r["Location"]
    Payment.objects.update(status="pending")

    with mock.patch("billing.khalti.lookup", return_value={
            "status": "Completed", "total_amount": 999_000, "transaction_id": "T1"}):
        r = owner.get("/api/billing/khalti/return?pidx=PIDX1")
        assert "payment=success" in r["Location"]
        owner.get("/api/billing/khalti/return?pidx=PIDX1")  # refresh: must not extend twice
    org = Organization.objects.get()
    assert org.plan.code == "starter"
    assert 363 <= (org.plan_expires_at - timezone.now()).days <= 365
    assert owner.get("/api/auth/me").data["plan"]["code"] == "starter"


def test_public_plans_and_spa():
    c = APIClient()
    codes = [p["code"] for p in c.get("/api/plans").data]
    assert codes == ["free", "starter", "pro"]
    assert c.get("/api/health").json() == {"ok": True}


def test_password_reset(mailoutbox, settings):
    register(APIClient())
    c = APIClient()
    assert c.post("/api/auth/password-reset", {"email": "nobody@x.com"}, format="json").status_code == 200
    assert not mailoutbox
    c.post("/api/auth/password-reset", {"email": "owner@abc.com"}, format="json")
    assert len(mailoutbox) == 1
    link = next(w for w in mailoutbox[0].body.split() if "/reset-password/" in w)
    uid, token = link.rstrip("/").split("/")[-2:]
    bad = c.post("/api/auth/password-reset/confirm", {"uid": uid, "token": "nope", "password": "Newpass#2026"},
                 format="json")
    assert bad.status_code == 400
    ok = c.post("/api/auth/password-reset/confirm", {"uid": uid, "token": token, "password": "Newpass#2026"},
                format="json")
    assert ok.status_code == 200
    r = c.post("/api/auth/login", {"email": "owner@abc.com", "password": "Newpass#2026"}, format="json")
    assert r.status_code == 200
    # links are single-use
    again = c.post("/api/auth/password-reset/confirm", {"uid": uid, "token": token, "password": "Other#20266"},
                   format="json")
    assert again.status_code == 400

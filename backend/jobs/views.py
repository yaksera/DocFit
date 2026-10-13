import io
import os
import zipfile
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.auth import HasOrganization

from . import previews, processing, runner
from .models import Job
from .serializers import JobCreateSerializer, JobSerializer, RetrySerializer

PDF_MAGIC = b"%PDF-"


def _org_jobs(request):
    return Job.objects.filter(organization=request.user.organization).select_related("user")


def _validate_upload(f) -> None:
    ext = os.path.splitext(f.name)[1].lower()
    if ext not in processing.ALLOWED_EXT:
        raise ValidationError({"files": f"{f.name}: unsupported file type. Upload PDF, JPG, PNG, "
                                         "HEIC, WebP or TIFF."})
    head = f.read(16)
    f.seek(0)
    if ext == ".pdf" and PDF_MAGIC not in head[:1024]:
        raise ValidationError({"files": f"{f.name} is not a real PDF file."})
    if f.size == 0:
        raise ValidationError({"files": f"{f.name} is empty."})


class JobListCreateView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, HasOrganization]
    serializer_class = JobSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_throttles(self):
        if self.request.method == "POST":
            self.throttle_scope = "uploads"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    def get_queryset(self):
        qs = _org_jobs(self.request)
        p = self.request.query_params
        if p.get("q"):
            qs = qs.filter(Q(label__icontains=p["q"]) | Q(input_names__icontains=p["q"]))
        if p.get("status"):
            qs = qs.filter(status=p["status"])
        if p.get("mine") == "1":
            qs = qs.filter(user=self.request.user)
        if p.get("ids"):
            qs = qs.filter(id__in=[i for i in p["ids"].split(",") if i][:100])
        return qs

    def post(self, request):
        org = request.user.organization
        plan = org.effective_plan
        files = request.FILES.getlist("files")
        if not files:
            raise ValidationError({"files": "Choose at least one file."})
        s = JobCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        for f in files:
            _validate_upload(f)

        groups = [files] if d["merge"] or len(files) == 1 else [[f] for f in files]
        if plan.monthly_docs and org.docs_used() + len(groups) > plan.monthly_docs:
            raise PermissionDenied(
                f"Your {plan.name} plan includes {plan.monthly_docs} documents per month and you have "
                f"used {org.docs_used()}. Upgrade your plan to continue.")
        limit = min(plan.max_upload_mb * 1024 * 1024, settings.MAX_UPLOAD_BYTES_HARD)
        for g in groups:
            if sum(f.size for f in g) > limit:
                raise ValidationError({"files": f"Uploads are limited to {plan.max_upload_mb} MB per job "
                                                f"on the {plan.name} plan."})

        target = d["target_bytes"] or org.default_target_kb * 1000
        expires = timezone.now() + timedelta(hours=plan.retention_hours)
        created = []
        with transaction.atomic():
            for g in groups:
                job = Job.objects.create(
                    organization=org, user=request.user, label=d.get("label", ""),
                    via_api=bool(request.auth), target_bytes=target, color_mode=d["color_mode"],
                    output_format=d["output_format"], clean_background=d["clean_background"],
                    password=d.get("password", ""), input_names=[f.name for f in g],
                    input_bytes=sum(f.size for f in g), expires_at=expires)
                job.input_dir.mkdir(parents=True, exist_ok=True)
                for i, f in enumerate(g):
                    ext = os.path.splitext(f.name)[1].lower()
                    with open(job.input_dir / f"{i:03d}{ext}", "wb") as out:
                        for chunk in f.chunks():
                            out.write(chunk)
                runner.enqueue(job.pk)
                created.append(job)
        return Response(JobSerializer(created, many=True).data, status=status.HTTP_201_CREATED)


class JobDetailView(APIView):
    permission_classes = [IsAuthenticated, HasOrganization]

    def get(self, request, pk):
        return Response(JobSerializer(get_object_or_404(_org_jobs(request), pk=pk)).data)

    def delete(self, request, pk):
        job = get_object_or_404(_org_jobs(request), pk=pk)
        if job.status == Job.Status.PROCESSING:
            raise ValidationError({"detail": "Wait for processing to finish before deleting."})
        processing.delete_files(job)
        job.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class JobRetryView(APIView):
    """Run a job again with new settings (another size, a PDF password...)."""
    permission_classes = [IsAuthenticated, HasOrganization]

    def post(self, request, pk):
        job = get_object_or_404(_org_jobs(request), pk=pk)
        if job.status in (Job.Status.QUEUED, Job.Status.PROCESSING):
            raise ValidationError({"detail": "This file is already being processed."})
        if not job.input_paths():
            raise ValidationError({"detail": "The original files were deleted. Upload them again."})
        s = RetrySerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        job.password = d.get("password", "")
        if d.get("target_kb"):
            job.target_bytes = d["target_kb"] * 1000
        if d.get("color_mode"):
            job.color_mode = d["color_mode"]
        job.status, job.progress, job.message, job.error, job.error_code = Job.Status.QUEUED, 0, "", "", ""
        job.warnings = []
        job.save()
        runner.enqueue(job.pk)
        return Response(JobSerializer(job).data)


class JobDownloadView(APIView):
    permission_classes = [IsAuthenticated, HasOrganization]

    def get(self, request, pk):
        job = get_object_or_404(_org_jobs(request), pk=pk)
        path = job.output_path() if job.status == Job.Status.DONE else None
        if not path:
            raise Http404("The file is not available (still processing, failed, or deleted).")
        return FileResponse(open(path, "rb"), as_attachment=True, filename=job.output_name,
                            content_type=job.content_type)


class JobPreviewView(APIView):
    permission_classes = [IsAuthenticated, HasOrganization]

    def get(self, request, pk, side):
        job = get_object_or_404(_org_jobs(request), pk=pk)
        try:
            page = max(0, int(request.query_params.get("page", 1)) - 1)
            width = max(200, min(int(request.query_params.get("width", 900)), previews.MAX_WIDTH))
        except ValueError:
            raise ValidationError({"detail": "Bad page or width."})
        try:
            if side == "before":
                paths = job.input_paths()
                if not paths:
                    raise Http404
                data = previews.render_sequence(paths, page, width)
            else:
                out = job.output_path() if job.status == Job.Status.DONE else None
                if not out:
                    raise Http404
                data = previews.render_output(out, page, width)
        except previews.PreviewUnavailable as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        resp = HttpResponse(data, content_type="image/jpeg")
        resp["Cache-Control"] = "private, max-age=600"
        return resp


class JobZipView(APIView):
    permission_classes = [IsAuthenticated, HasOrganization]

    def post(self, request):
        ids = request.data.get("ids") or []
        if not isinstance(ids, list) or not ids or len(ids) > 100:
            raise ValidationError({"detail": "Choose between 1 and 100 files."})
        jobs = _org_jobs(request).filter(pk__in=ids, status=Job.Status.DONE)
        buf = io.BytesIO()
        used: set[str] = set()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
            for job in jobs:
                path = job.output_path()
                if not path:
                    continue
                name, n = job.output_name, 1
                if job.label:
                    name = f"{job.label}/{name}"
                while name in used:
                    base, ext = os.path.splitext(job.output_name)
                    n += 1
                    name = f"{base} ({n}){ext}"
                used.add(name)
                z.write(path, name)
        if not used:
            raise Http404("None of these files are available any more.")
        resp = HttpResponse(buf.getvalue(), content_type="application/zip")
        resp["Content-Disposition"] = 'attachment; filename="docfit-files.zip"'
        return resp


class StatsView(APIView):
    permission_classes = [IsAuthenticated, HasOrganization]

    def get(self, request):
        org = request.user.organization
        done = _org_jobs(request).filter(status__in=[Job.Status.DONE, Job.Status.EXPIRED],
                                         output_bytes__isnull=False)
        month = done.filter(created_at__gte=org.period_start())
        agg = done.aggregate(n=Count("id"), inb=Sum("input_bytes"), outb=Sum("output_bytes"))
        return Response({
            "total_docs": agg["n"] or 0,
            "bytes_saved": max(0, (agg["inb"] or 0) - (agg["outb"] or 0)),
            "docs_this_month": month.count(),
            "fit_rate": round(100 * done.filter(met_target=True).count() / agg["n"]) if agg["n"] else None,
        })

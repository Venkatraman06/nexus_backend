import io
import logging

from django.http import HttpResponse
from django.template.loader import render_to_string
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.permissions import IsAuthenticated, HasKeycloakPermission
from apps.common.viewsets import BaseModelViewSet

from .filters import DocumentFilter
from .models import Document
from .serializers import (
    DocumentCreateSerializer,
    DocumentDetailSerializer,
    DocumentListSerializer,
    DocumentStatusSerializer,
)

logger = logging.getLogger(__name__)


class DocumentViewSet(BaseModelViewSet):
    queryset = Document.objects.select_related(
        "client", "project", "division"
    ).filter(is_deleted=False)

    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    filterset_class    = DocumentFilter
    search_fields      = ["document_number", "client_name", "client__name"]
    ordering_fields    = ["document_number", "created_at", "total_amount", "valid_until"]
    ordering           = ["-created_at"]

    PERMISSION_MAP = {
        "list":           "pmt.finance.document.view",
        "retrieve":       "pmt.finance.document.view",
        "create":         "pmt.finance.document.create",
        "update":         "pmt.finance.document.update",
        "partial_update": "pmt.finance.document.update",
        "destroy":        "pmt.finance.document.delete",
        "update_status":  "pmt.finance.document.update",
        "pdf":            "pmt.finance.document.view",
        "preview":        "pmt.finance.document.view",
    }

    def get_serializer_class(self):
        if self.action == "retrieve":
            return DocumentDetailSerializer
        if self.action in ("create", "update", "partial_update"):
            return DocumentCreateSerializer
        return DocumentListSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.action == "retrieve":
            qs = qs.prefetch_related("line_items")
        return qs

    # ── Status transition ────────────────────────────────────────────────────

    @action(detail=True, methods=["patch"], url_path="status")
    def update_status(self, request, pk=None):
        document = self.get_object()
        serializer = DocumentStatusSerializer(
            data=request.data,
            context={"document": document},
        )
        serializer.is_valid(raise_exception=True)
        document.status     = serializer.validated_data["status"]
        document.updated_by = request.user
        document.save(update_fields=["status", "updated_by", "updated_at"])
        return Response({
            "status":         document.status,
            "status_display": document.get_status_display(),
        })

    # ── PDF / Preview ────────────────────────────────────────────────────────

    def _render_document_html(self, document_id: str) -> str:
        doc = (
            Document.objects
            .prefetch_related("line_items")
            .select_related("client", "project", "division")
            .get(pk=document_id, is_deleted=False)
        )
        line_items = doc.line_items.filter(is_deleted=False)
        return render_to_string("finance/document_pdf.html", {
            "document":   doc,
            "line_items": line_items,
        })

    @action(detail=True, methods=["get"], url_path="preview")
    def preview(self, request, pk=None):
        self.get_object()  # permission + 404 check
        html = self._render_document_html(pk)
        return HttpResponse(html, content_type="text/html; charset=utf-8")

    @action(detail=True, methods=["get"], url_path="pdf")
    def pdf(self, request, pk=None):
        document = self.get_object()
        html     = self._render_document_html(pk)

        try:
            from xhtml2pdf import pisa  # optional dependency

            buffer = io.BytesIO()
            result = pisa.CreatePDF(io.StringIO(html), dest=buffer)
            if result.err:
                raise RuntimeError("xhtml2pdf conversion error")
            buffer.seek(0)
            response = HttpResponse(buffer.read(), content_type="application/pdf")
            response["Content-Disposition"] = (
                f'attachment; filename="{document.document_number}.pdf"'
            )
            return response
        except (ImportError, RuntimeError) as exc:
            logger.warning("PDF generation fell back to HTML: %s", exc)
            # Fallback: return print-ready HTML so the browser can print-to-PDF
            return HttpResponse(html, content_type="text/html; charset=utf-8")

from rest_framework import serializers

from .models import Document, DocumentLineItem, ALLOWED_STATUSES_BY_TYPE


class DocumentLineItemSerializer(serializers.ModelSerializer):
    class Meta:
        model  = DocumentLineItem
        fields = ["id", "description", "quantity", "rate", "gst_percentage", "amount", "sort_order"]
        read_only_fields = ["id", "amount"]


class DocumentListSerializer(serializers.ModelSerializer):
    document_type_display = serializers.CharField(source="get_document_type_display", read_only=True)
    status_display        = serializers.CharField(source="get_status_display",         read_only=True)
    project_name          = serializers.CharField(source="project.name",  read_only=True, default="")
    division_name         = serializers.CharField(source="division.name", read_only=True, default="")

    class Meta:
        model  = Document
        fields = [
            "id", "document_number",
            "document_type", "document_type_display",
            "client", "client_name",
            "project", "project_name",
            "division", "division_name",
            "currency", "status", "status_display",
            "valid_until", "subtotal", "gst_amount", "total_amount",
            "created_at", "updated_at",
        ]


class DocumentDetailSerializer(serializers.ModelSerializer):
    line_items            = DocumentLineItemSerializer(many=True, read_only=True)
    document_type_display = serializers.CharField(source="get_document_type_display", read_only=True)
    status_display        = serializers.CharField(source="get_status_display",         read_only=True)
    project_name          = serializers.CharField(source="project.name",  read_only=True, default="")
    division_name         = serializers.CharField(source="division.name", read_only=True, default="")

    class Meta:
        model  = Document
        fields = [
            "id", "document_number",
            "document_type", "document_type_display",
            "client", "client_name", "client_email", "client_gst_number",
            "billing_address", "shipping_address",
            "project", "project_name",
            "division", "division_name",
            "currency", "status", "status_display",
            "valid_until", "notes",
            "subtotal", "gst_amount", "total_amount",
            "line_items",
            "created_at", "updated_at",
        ]


class DocumentCreateSerializer(serializers.ModelSerializer):
    line_items = DocumentLineItemSerializer(many=True)

    class Meta:
        model  = Document
        fields = [
            "document_type", "client", "project", "division",
            "currency", "status", "valid_until", "notes",
            "billing_address", "shipping_address",
            "line_items",
        ]

    def validate(self, data):
        doc_type = data.get("document_type") or (self.instance.document_type if self.instance else None)
        status   = data.get("status", "draft")
        if doc_type and status:
            allowed = ALLOWED_STATUSES_BY_TYPE.get(doc_type, set())
            if status not in allowed:
                raise serializers.ValidationError(
                    {"status": f"'{status}' is not a valid status for '{doc_type}'."}
                )
        return data

    def create(self, validated_data):
        line_items_data = validated_data.pop("line_items", [])
        client = validated_data["client"]

        # Snapshot client fields
        validated_data.setdefault("client_name",       client.name)
        validated_data.setdefault("client_email",      client.contact_email)
        validated_data.setdefault("client_gst_number", client.gst_number)
        if not validated_data.get("billing_address"):
            validated_data["billing_address"]  = client.formatted_address or client.address or ""
        if not validated_data.get("shipping_address"):
            validated_data["shipping_address"] = client.formatted_address or client.address or ""

        validated_data["document_number"] = Document.generate_document_number(
            validated_data["document_type"]
        )

        document = Document.objects.create(**validated_data)

        for i, item_data in enumerate(line_items_data):
            item_data.setdefault("sort_order", i)
            DocumentLineItem.objects.create(document=document, **item_data)

        document.recalculate_totals()
        return document

    def update(self, instance, validated_data):
        line_items_data = validated_data.pop("line_items", None)

        # document_type is immutable after creation
        validated_data.pop("document_type", None)

        # Re-snapshot if client changed
        new_client = validated_data.get("client")
        if new_client and new_client != instance.client:
            validated_data["client_name"]       = new_client.name
            validated_data["client_email"]      = new_client.contact_email
            validated_data["client_gst_number"] = new_client.gst_number
            if not validated_data.get("billing_address"):
                validated_data["billing_address"]  = new_client.formatted_address or new_client.address or ""
            if not validated_data.get("shipping_address"):
                validated_data["shipping_address"] = new_client.formatted_address or new_client.address or ""

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if line_items_data is not None:
            instance.line_items.all().delete()
            for i, item_data in enumerate(line_items_data):
                item_data.setdefault("sort_order", i)
                DocumentLineItem.objects.create(document=instance, **item_data)
            instance.recalculate_totals()

        return instance


class DocumentStatusSerializer(serializers.Serializer):
    status = serializers.CharField()

    def validate_status(self, value: str) -> str:
        doc = self.context.get("document")
        if doc:
            allowed = ALLOWED_STATUSES_BY_TYPE.get(doc.document_type, set())
            if value not in allowed:
                raise serializers.ValidationError(
                    f"'{value}' is not valid for '{doc.document_type}'."
                )
        return value

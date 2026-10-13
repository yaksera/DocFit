from rest_framework import serializers

from engine import parse_size

from .models import Job

TARGET_MIN, TARGET_MAX = 20_000, 100_000_000


class JobSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    files_available = serializers.BooleanField(read_only=True)
    user_name = serializers.SerializerMethodField()
    ratio = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = ["id", "display_name", "label", "input_names", "input_bytes", "target_bytes",
                  "color_mode", "output_format", "clean_background", "status", "progress", "message",
                  "error", "error_code", "output_name", "output_bytes", "pages", "met_target",
                  "text_quality", "warnings", "ratio", "files_available", "user_name", "via_api",
                  "created_at", "started_at", "finished_at", "expires_at"]
        read_only_fields = fields

    def get_user_name(self, obj):
        return (obj.user.full_name or obj.user.email) if obj.user else ""

    def get_ratio(self, obj):
        if obj.output_bytes:
            return round(obj.input_bytes / obj.output_bytes, 1)
        return None


class JobCreateSerializer(serializers.Serializer):
    target = serializers.CharField(required=False, help_text="e.g. 4MB, 500KB")
    target_kb = serializers.IntegerField(required=False)
    color_mode = serializers.ChoiceField(["auto", "color", "gray", "bw"], default="auto")
    output_format = serializers.ChoiceField(["pdf", "jpg"], default="pdf")
    clean_background = serializers.BooleanField(default=True)
    merge = serializers.BooleanField(default=False)
    password = serializers.CharField(required=False, allow_blank=True, max_length=200)
    label = serializers.CharField(required=False, allow_blank=True, max_length=120)

    def validate(self, attrs):
        if attrs.get("target"):
            try:
                target = parse_size(attrs["target"])
            except ValueError as exc:
                raise serializers.ValidationError({"target": str(exc)})
        elif attrs.get("target_kb"):
            target = attrs["target_kb"] * 1000
        else:
            target = None
        if target is not None and not TARGET_MIN <= target <= TARGET_MAX:
            raise serializers.ValidationError({"target": "The size limit must be between 20 KB and 100 MB."})
        attrs["target_bytes"] = target
        return attrs


class RetrySerializer(serializers.Serializer):
    password = serializers.CharField(required=False, allow_blank=True, max_length=200)
    target_kb = serializers.IntegerField(required=False, min_value=20, max_value=100_000)
    color_mode = serializers.ChoiceField(["auto", "color", "gray", "bw"], required=False)

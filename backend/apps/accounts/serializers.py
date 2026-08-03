from django.contrib.auth.password_validation import validate_password
from django.conf import settings
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import PERMISSION_CHOICES, AuditLog, Organization, Role, User


class OrganizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "slug", "is_active", "threat_level", "created_at"]
        read_only_fields = ["created_at"]


class RoleSerializer(serializers.ModelSerializer):
    user_count = serializers.IntegerField(source="users.count", read_only=True)

    class Meta:
        model = Role
        fields = [
            "id",
            "name",
            "description",
            "permissions",
            "is_system",
            "user_count",
        ]
        read_only_fields = ["is_system"]

    def validate_permissions(self, value):
        valid = {code for code, _ in PERMISSION_CHOICES}
        bad = [v for v in value if v not in valid]
        if bad:
            raise serializers.ValidationError(f"کدهای دسترسی نامعتبر: {bad}")
        return value


class UserSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source="role.name", read_only=True)
    permissions = serializers.SerializerMethodField()
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "display_name",
            "phone",
            "role",
            "role_name",
            "is_active",
            "is_superuser",
            "permissions",
            "password",
            "last_login",
        ]
        read_only_fields = ["last_login", "is_superuser"]

    def get_permissions(self, obj):
        return obj.get_permissions()

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        request = self.context.get("request")
        if request and not request.user.is_superuser:
            validated_data["organization"] = request.user.organization
        user = User(**validated_data)
        if password:
            validate_password(password)
            user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            validate_password(password)
            instance.set_password(password)
        instance.save()
        return instance


class MeSerializer(serializers.ModelSerializer):
    permissions = serializers.SerializerMethodField()
    features = serializers.SerializerMethodField()
    organization = OrganizationSerializer(read_only=True)
    role_name = serializers.CharField(source="role.name", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "display_name",
            "phone",
            "role",
            "role_name",
            "organization",
            "is_superuser",
            "permissions",
            "features",
        ]

    def get_permissions(self, obj):
        return obj.get_permissions()

    def get_features(self, obj):
        return dict(getattr(settings, "FEATURE_FLAGS", {}))


class AuditLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "username",
            "action",
            "target",
            "ip",
            "detail",
            "created_at",
        ]


class PersianTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Adds user profile info to the token response."""

    default_error_messages = {
        "no_active_account": "نام کاربری یا گذرواژه نادرست است."
    }

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = MeSerializer(self.user).data
        return data

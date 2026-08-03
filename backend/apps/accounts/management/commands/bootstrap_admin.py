"""Create the non-demo organization, admin role and first operator account."""

import getpass
import os

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from apps.accounts.models import PERMISSION_CHOICES, Organization, Role, User


class Command(BaseCommand):
    help = "Create or repair the initial organization and administrator without demo data."

    def add_arguments(self, parser):
        parser.add_argument("--username", default=os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin"))
        parser.add_argument("--email", default=os.environ.get("DJANGO_SUPERUSER_EMAIL", ""))
        parser.add_argument("--organization", default="PersianSecure")
        parser.add_argument("--organization-slug", default="")
        parser.add_argument("--noinput", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        username = options["username"].strip()
        if not username:
            raise CommandError("A non-empty --username is required.")

        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
        existing = User.objects.filter(username=username).first()
        if not existing and not password and not options["noinput"]:
            password = getpass.getpass("Administrator password: ")
            confirm = getpass.getpass("Administrator password (again): ")
            if password != confirm:
                raise CommandError("Passwords do not match.")
        if not existing and not password:
            raise CommandError(
                "Set DJANGO_SUPERUSER_PASSWORD or run without --noinput to enter it securely."
            )

        if password:
            try:
                validate_password(password, user=existing)
            except ValidationError as exc:
                raise CommandError(" ".join(exc.messages)) from exc

        org_name = options["organization"].strip() or "PersianSecure"
        org_slug = options["organization_slug"].strip() or slugify(org_name) or "persiansecure"
        org, _ = Organization.objects.get_or_create(
            slug=org_slug,
            defaults={"name": org_name},
        )
        admin_role, _ = Role.objects.get_or_create(
            organization=org,
            name="System administrator",
            defaults={
                "permissions": [code for code, _ in PERMISSION_CHOICES],
                "is_system": True,
            },
        )

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": options["email"],
                "organization": org,
                "role": admin_role,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        user.organization = org
        user.role = admin_role
        user.is_staff = True
        user.is_superuser = True
        if options["email"]:
            user.email = options["email"]
        if password:
            user.set_password(password)
        user.save()

        verb = "created" if created else "updated"
        self.stdout.write(self.style.SUCCESS(f"Administrator '{username}' {verb} for '{org.name}'."))

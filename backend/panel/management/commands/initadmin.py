import os
import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create or update the initial admin user from environment variables."

    def resolve_password(self):
        configured = os.getenv("ADMIN_PASSWORD", "").strip()
        weak_values = {"", "change-me", "changeme", "admin", "password"}
        if configured and configured not in weak_values:
            return configured, False

        password_file = settings.DATA_DIR / "admin_password"
        if password_file.exists():
            saved = password_file.read_text().strip()
            if saved:
                return saved, True

        generated = secrets.token_urlsafe(24)
        password_file.write_text(generated)
        try:
            password_file.chmod(0o600)
        except OSError:
            pass
        return generated, True

    def handle(self, *args, **options):
        username = os.getenv("ADMIN_USERNAME", "admin")
        password, generated_password = self.resolve_password()
        email = os.getenv("ADMIN_EMAIL", "")
        User = get_user_model()
        user, created = User.objects.get_or_create(username=username, defaults={"email": email, "is_staff": True, "is_superuser": True})
        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()
        action = "created" if created else "updated"
        self.stdout.write(self.style.SUCCESS(f"Admin user {username!r} {action}."))
        if generated_password:
            self.stdout.write(self.style.WARNING(f"Admin password stored at {settings.DATA_DIR / 'admin_password'}."))

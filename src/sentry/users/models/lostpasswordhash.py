from __future__ import annotations

from collections.abc import Iterable
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from sentry.backup.scopes import RelocationScope
from sentry.db.models import FlexibleForeignKey, Model, control_silo_model, sane_repr
from sentry.users.services.user.model import RpcUser
from sentry.utils.http import absolute_uri
from sentry.utils.security import get_secure_token

if TYPE_CHECKING:
    from sentry.users.models.user import User
    from sentry.users.services.lost_password_hash import RpcLostPasswordHash


@control_silo_model
class LostPasswordHash(Model):
    __relocation_scope__ = RelocationScope.Excluded

    user = FlexibleForeignKey(settings.AUTH_USER_MODEL, unique=True)
    hash = models.CharField(max_length=32)
    date_added = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label = "sentry"
        db_table = "sentry_lostpasswordhash"

    __repr__ = sane_repr("user_id", "hash")

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.hash:
            self.set_hash()
        super().save(*args, **kwargs)

    def set_hash(self) -> None:
        self.hash = get_secure_token()

    def is_valid(self) -> bool:
        return self.date_added > timezone.now() - timedelta(hours=1)

    @classmethod
    def send_recover_password_email(cls, user: User, hash: str, ip_address: str) -> None:
        extra = {
            "ip_address": ip_address,
        }
        cls._send_email("recover_password", user, hash, extra)

    @classmethod
    def send_relocate_account_email(
        cls, user: User | RpcUser, hash: str, orgs: Iterable[str]
    ) -> None:
        cls._send_email("relocate_account", user, hash, {"orgs": orgs})

    @classmethod
    def send_set_password_email(cls, user: User | RpcUser, hash: str, **kwargs: Any) -> None:
        cls._send_email("set_password", user, hash, extra=kwargs)

    @classmethod
    def _send_email(cls, mode: str, user: User | RpcUser, hash: str, extra: dict[str, Any]) -> None:
        from sentry import options
        from sentry.http import get_server_hostname
        from sentry.utils.email import MessageBuilder

        context = {
            "user": user,
            "domain": get_server_hostname(),
            "url": cls.get_lostpassword_url(user.id, hash, mode),
            "datetime": timezone.now(),
            **extra,
        }

        subject = "Password Recovery"
        template = "recover_account"
        if mode == "set_password":
            subject = "Set Password for your Sentry.io Account"
            template = "set_password"
        elif mode == "relocate_account":
            template = "relocate_account"
            subject = "Set Username and Password for Your Relocated Sentry.io Account"

        msg = MessageBuilder(
            subject="{}{}".format(options.get("mail.subject-prefix"), subject),
            template=f"sentry/emails/{template}.txt",
            html_template=f"sentry/emails/{template}.html",
            type="user.password_recovery",
            context=context,
        )
        msg.send_async([user.email])

    # Duplicated from RpcLostPasswordHash
    def get_absolute_url(self, mode: str = "recover") -> str:
        return LostPasswordHash.get_lostpassword_url(self.user_id, self.hash, mode)

    @classmethod
    def get_lostpassword_url(self, user_id: int, hash: str, mode: str = "recover") -> str:
        url_key = "sentry-account-recover-confirm"
        if mode == "set_password":
            url_key = "sentry-account-set-password-confirm"
        elif mode == "relocate_account":
            url_key = "sentry-account-relocate-confirm"

        return absolute_uri(reverse(url_key, args=[user_id, hash]))

    @classmethod
    def for_user(cls, user: User) -> RpcLostPasswordHash:
        from sentry.users.services.lost_password_hash import lost_password_hash_service

        password_hash = lost_password_hash_service.get_or_create(user_id=user.id)
        return password_hash

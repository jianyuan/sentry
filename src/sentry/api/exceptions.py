from __future__ import annotations

from django.contrib.auth import REDIRECT_FIELD_NAME
from django.http.request import HttpRequest
from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import APIException

from sentry.models.organization import Organization
from sentry.organizations.services.organization.model import RpcOrganization
from sentry.utils.auth import construct_link_with_query
from sentry.utils.http import is_using_customer_domain


class ResourceDoesNotExist(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = "The requested resource does not exist"


class SentryAPIException(APIException):
    code = ""
    message = ""

    def __init__(self, code=None, message=None, detail=None, **kwargs):
        # Note that we no longer call the base `__init__` here. This is because
        # DRF now forces all detail messages that subclass `APIException` to a
        # string, which breaks our format.
        # https://www.django-rest-framework.org/community/3.0-announcement/#miscellaneous-notes
        if detail is None:
            detail = {
                "code": code or self.code,
                "message": message or self.message,
                "extra": kwargs,
            }

        self.detail = {"detail": detail}


class BadRequest(SentryAPIException):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "invalid-request"
    message = "Invalid request"


class ParameterValidationError(SentryAPIException):
    status_code = status.HTTP_400_BAD_REQUEST
    code = "parameter-validation-error"

    def __init__(self, message: str, context: list[str] | None = None) -> None:
        super().__init__(message=message, context=".".join(context or []))


class SsoRequired(SentryAPIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "sso-required"
    message = "Must login via SSO"

    def __init__(
        self,
        organization: Organization | RpcOrganization,
        request: HttpRequest,
        after_login_redirect=None,
    ):
        login_url = reverse("sentry-auth-organization", args=[organization.slug])
        if is_using_customer_domain(request):
            login_url = organization.absolute_url(path=login_url)

        if after_login_redirect:
            query_params = {REDIRECT_FIELD_NAME: after_login_redirect}
            login_url = construct_link_with_query(path=login_url, query_params=query_params)

        super().__init__(loginUrl=login_url)


class MemberDisabledOverLimit(SentryAPIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "member-disabled-over-limit"
    message = "Organization over member limit"

    def __init__(self, organization):
        super().__init__(
            next=reverse("sentry-organization-disabled-member", args=[organization.slug])
        )


class SuperuserRequired(SentryAPIException):
    status_code = status.HTTP_403_FORBIDDEN
    code = "superuser-required"
    message = "You need to re-authenticate for superuser."


class StaffRequired(SentryAPIException):
    status_code = status.HTTP_403_FORBIDDEN
    code = "staff-required"
    message = "You need to re-authenticate for staff."


class DataSecrecyError(SentryAPIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "data-secrecy"


class SudoRequired(SentryAPIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "sudo-required"
    message = "Account verification required."

    def __init__(self, user):
        super().__init__(username=user.username)


class PrimaryEmailVerificationRequired(SentryAPIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "primary-email-verification-required"
    message = "Primary email verification required."

    def __init__(self, user):
        super().__init__(username=user.username)


class TwoFactorRequired(SentryAPIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "2fa-required"
    message = "Organization requires two-factor authentication to be enabled"


class ConflictError(APIException):
    status_code = status.HTTP_409_CONFLICT


class InvalidRepository(Exception):
    pass


class RequestTimeout(SentryAPIException):
    status_code = status.HTTP_408_REQUEST_TIMEOUT
    code = "request-timeout"
    message = "Proxied request timed out"

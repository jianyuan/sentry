from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence

import requests
from django.http import HttpRequest
from jwt import ExpiredSignatureError, InvalidSignatureError

from sentry.integrations.models.integration import Integration
from sentry.integrations.services.integration.model import RpcIntegration
from sentry.integrations.services.integration.service import integration_service
from sentry.silo.base import control_silo_function
from sentry.utils import jwt
from sentry.utils.http import absolute_uri, percent_encode


class AtlassianConnectValidationError(Exception):
    pass


def get_query_hash(
    uri: str, method: str, query_params: Mapping[str, str | Sequence[str]] | None = None
) -> str:
    # see
    # https://developer.atlassian.com/static/connect/docs/latest/concepts/understanding-jwt.html#qsh
    uri = uri.rstrip("/")
    method = method.upper()
    if query_params is None:
        query_params = {}

    sorted_query = []
    for k, v in sorted(query_params.items()):
        # don't include jwt query param
        if k != "jwt":
            if isinstance(v, str):
                param_val = percent_encode(v)
            else:
                param_val = ",".join(percent_encode(val) for val in v)
            sorted_query.append(f"{percent_encode(k)}={param_val}")

    query_string = "{}&{}&{}".format(method, uri, "&".join(sorted_query))
    return hashlib.sha256(query_string.encode("utf8")).hexdigest()


def get_token(request: HttpRequest) -> str:
    try:
        # request.headers = {"Authorization": "JWT abc123def456"}
        auth_header: str = request.META["HTTP_AUTHORIZATION"]
        return auth_header.split(" ", 1)[1]
    except (KeyError, IndexError):
        raise AtlassianConnectValidationError("Missing/Invalid authorization header")


def get_integration_from_jwt(
    token: str | None,
    path: str,
    provider: str,
    query_params: Mapping[str, str] | None,
    method: str = "GET",
) -> RpcIntegration:
    # https://developer.atlassian.com/static/connect/docs/latest/concepts/authentication.html
    # Extract the JWT token from the request's jwt query
    # parameter or the authorization header.
    if token is None:
        raise AtlassianConnectValidationError("No token parameter")
    # Decode the JWT token, without verification. This gives
    # you a header JSON object, a claims JSON object, and a signature.
    claims = jwt.peek_claims(token)
    headers = jwt.peek_header(token)

    # Extract the issuer ('iss') claim from the decoded, unverified
    # claims object. This is the clientKey for the tenant - an identifier
    # for the Atlassian application making the call
    issuer = claims.get("iss")
    # Look up the sharedSecret for the clientKey, as stored
    # by the add-on during the installation handshake
    integration = integration_service.get_integration(provider=provider, external_id=issuer)
    if not integration:
        raise AtlassianConnectValidationError("No integration found")
    # Verify the signature with the sharedSecret and the algorithm specified in the header's
    # alg field.  We only need the token + shared secret and do not want to provide an
    # audience to the JWT validation that is require to match.  Bitbucket does give us an
    # audience claim however, so disable verification of this.
    key_id = headers.get("kid")
    try:
        # We only authenticate asymmetrically (through the CDN) if the event provides a key ID
        # in its JWT headers. This should only appear for install/uninstall events.

        decoded_claims = (
            authenticate_asymmetric_jwt(token, key_id)
            if key_id
            else jwt.decode(token, integration.metadata["shared_secret"], audience=False)
        )
    except InvalidSignatureError as e:
        raise AtlassianConnectValidationError("Signature is invalid") from e
    except ExpiredSignatureError as e:
        raise AtlassianConnectValidationError("Signature is expired") from e

    verify_claims(decoded_claims, path, query_params, method)

    return integration


def verify_claims(
    claims: Mapping[str, str],
    path: str,
    query_params: Mapping[str, str] | None,
    method: str,
) -> None:
    # Verify the query has not been tampered by Creating a Query Hash
    # and comparing it against the qsh claim on the verified token.
    qsh = get_query_hash(path, method, query_params)
    if qsh != claims["qsh"]:
        raise AtlassianConnectValidationError("Query hash mismatch")


def authenticate_asymmetric_jwt(token: str | None, key_id: str) -> dict[str, str]:
    """
    Allows for Atlassian Connect installation lifecycle security improvements (i.e. verified senders)
    See: https://community.developer.atlassian.com/t/action-required-atlassian-connect-installation-lifecycle-security-improvements/49046
    """
    if token is None:
        raise AtlassianConnectValidationError("No token parameter")
    headers = jwt.peek_header(token)
    key_response = requests.get(f"https://connect-install-keys.atlassian.com/{key_id}")
    public_key = key_response.content.decode("utf-8").strip()
    decoded_claims = jwt.decode(
        token, public_key, audience=absolute_uri(), algorithms=[headers.get("alg")]
    )
    if not decoded_claims:
        raise AtlassianConnectValidationError("Unable to verify asymmetric installation JWT")
    return decoded_claims


def get_integration_from_request(request: HttpRequest, provider: str) -> RpcIntegration:
    return get_integration_from_jwt(request.GET.get("jwt"), request.path, provider, request.GET)


@control_silo_function
def parse_integration_from_request(request: HttpRequest, provider: str) -> Integration | None:
    token = (
        get_token(request=request)
        if request.META.get("HTTP_AUTHORIZATION") is not None
        else request.GET.get("jwt")
    )
    rpc_integration = get_integration_from_jwt(
        token=token,
        path=request.path,
        provider=provider,
        query_params=request.GET,
        method=request.method if request.method else "POST",
    )
    return Integration.objects.filter(id=rpc_integration.id).first()

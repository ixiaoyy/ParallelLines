import hashlib
import hmac
from types import SimpleNamespace

import pytest
from starlette.requests import Request

from app.core.exceptions import AppError
from app.services.catalog import RATING_UNAVAILABLE_MESSAGE, CatalogService

VALID_JWT = "unit-test-jwt-key-with-at-least-32-characters"
DERIVATION_CONTEXT = b"catalog-rating-ip-key-v1"


def service(explicit_key="", jwt_key=VALID_JWT):
    """只构造摘要计算所需设置；不创建数据库会话，不读取环境密钥。"""

    return CatalogService(
        None,
        SimpleNamespace(catalog_rating_ip_secret=explicit_key, jwt_secret_key=jwt_key),
    )


def request(ip="192.0.2.9", *, method="GET", direct_ip="198.51.100.8", headers=()):
    """构造只含测试 IP 的本地请求，覆盖代理头与直连地址。"""

    request_headers = list(headers)
    if ip is not None:
        request_headers.append((b"x-real-ip", ip.encode("ascii")))
    return Request(
        {
            "type": "http",
            "method": method,
            "path": "/api/v1/catalog",
            "headers": request_headers,
            "client": (direct_ip, 12345) if direct_ip is not None else None,
        }
    )


@pytest.mark.parametrize(
    "explicit_key",
    [
        "dedicated-rating-test-key-over-32-characters",
        "  dedicated-rating-test-key-over-32-characters\t ",
        "a" * 31 + " ",
        " " * 32,
        "测试" * 16,
    ],
)
def test_explicit_key_matches_historical_digest_including_whitespace(explicit_key):
    expected = hmac.new(explicit_key.encode("utf-8"), b"192.0.2.9", hashlib.sha256).hexdigest()
    # 显式密钥沿用原字符串长度检查和原始字节；JWT 是否可用不影响历史身份。
    assert service(explicit_key, "")._ip_digest(request(), required=True) == expected
    assert service(explicit_key, "rotated-jwt-test-key-with-at-least-32-characters")._ip_digest(
        request(), required=False
    ) == expected


@pytest.mark.parametrize("explicit_key", ["short", "a" * 31, " a ", " "])
def test_short_explicit_key_cannot_be_bypassed_by_valid_jwt(explicit_key):
    catalog = service(explicit_key)
    assert catalog._ip_digest(request(), required=False) is None
    with pytest.raises(AppError) as error:
        catalog._ip_digest(request(), required=True)
    assert error.value.status_code == 503
    assert error.value.code == "catalog_rating_unavailable"
    assert error.value.message == RATING_UNAVAILABLE_MESSAGE


def test_empty_explicit_key_derives_stable_separate_purpose_identity():
    derived_key = hmac.new(
        VALID_JWT.encode("utf-8"), DERIVATION_CONTEXT, hashlib.sha256
    ).hexdigest().encode("ascii")
    expected = hmac.new(derived_key, b"192.0.2.9", hashlib.sha256).hexdigest()
    raw_jwt_digest = hmac.new(VALID_JWT.encode("utf-8"), b"192.0.2.9", hashlib.sha256).hexdigest()
    catalog = service()
    assert catalog._ip_digest(request(), required=True) == expected
    assert catalog._ip_digest(request(), required=False) == expected
    assert service()._ip_digest(request(), required=True) == expected
    assert expected != raw_jwt_digest


@pytest.mark.parametrize("jwt_key", ["", "short", "a" * 31, "change-me-" + "x" * 40])
def test_missing_short_or_default_jwt_keeps_existing_unavailable_behavior(jwt_key):
    catalog = service(jwt_key=jwt_key)
    assert catalog._ip_digest(request(), required=False) is None
    with pytest.raises(AppError) as error:
        catalog._ip_digest(request(), required=True)
    assert error.value.status_code == 503
    assert error.value.message == RATING_UNAVAILABLE_MESSAGE


@pytest.mark.parametrize("explicit_key", ["", "dedicated-rating-test-key-over-32-characters"])
@pytest.mark.parametrize(
    ("address", "normalized"),
    [
        ("2001:0db8:0000:0000:0000:0000:0000:0001", "2001:db8::1"),
        ("::ffff:192.0.2.9", "192.0.2.9"),
        ("::ffff:c000:209", "192.0.2.9"),
    ],
)
def test_ip_normalization_is_unchanged(explicit_key, address, normalized):
    catalog = service(explicit_key)
    assert catalog._ip_digest(request(address), required=True) == catalog._ip_digest(
        request(normalized), required=True
    )


def test_real_ip_header_precedence_and_direct_connection_fallback():
    catalog = service()
    expected = catalog._ip_digest(request("192.0.2.9"), required=True)
    assert catalog._ip_digest(request(None, direct_ip="192.0.2.9"), required=True) == expected
    assert catalog._ip_digest(
        request("192.0.2.9", headers=[(b"x-forwarded-for", b"203.0.113.77")]), required=True
    ) == expected


@pytest.mark.parametrize("address", ["invalid-ip", "192.0.2.9, 203.0.113.1", " 192.0.2.9 "])
def test_invalid_real_ip_still_fails_without_using_client_address(address):
    catalog = service()
    assert catalog._ip_digest(request(address), required=False) is None
    with pytest.raises(AppError) as error:
        catalog._ip_digest(request(address), required=True)
    assert error.value.status_code == 503
    assert error.value.message == RATING_UNAVAILABLE_MESSAGE


def test_request_without_any_ip_keeps_required_behavior():
    catalog = service()
    assert catalog._ip_digest(request(None, direct_ip=None), required=False) is None
    with pytest.raises(AppError) as error:
        catalog._ip_digest(request(None, direct_ip=None), required=True)
    assert error.value.status_code == 503


@pytest.mark.parametrize("explicit_key", ["", "dedicated-rating-test-key-over-32-characters"])
def test_catalog_get_and_rating_post_use_same_visitor_identity(explicit_key):
    catalog = service(explicit_key)
    get_digest = catalog._ip_digest(request(method="GET"), required=False)
    post_digest = catalog._ip_digest(request(method="POST"), required=True)
    assert get_digest is not None
    assert get_digest == post_digest


def test_jwt_rotation_changes_only_fallback_identity():
    before = service()._ip_digest(request(), required=True)
    after = service(jwt_key="rotated-jwt-test-key-with-at-least-32-characters")._ip_digest(
        request(), required=True
    )
    assert before != after


def test_fixing_derived_hex_key_preserves_identity_when_jwt_rotates():
    derived_hex = hmac.new(
        VALID_JWT.encode("utf-8"), DERIVATION_CONTEXT, hashlib.sha256
    ).hexdigest()
    fallback_digest = service()._ip_digest(request(), required=True)
    assert len(derived_hex) == 64
    assert service(explicit_key=derived_hex)._ip_digest(request(), required=True) == fallback_digest
    pinned_after_rotation = service(
        explicit_key=derived_hex, jwt_key="rotated-jwt-test-key-with-at-least-32-characters"
    )
    assert pinned_after_rotation._ip_digest(request(), required=True) == fallback_digest

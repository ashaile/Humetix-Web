#!/usr/bin/env python3
"""Lightweight smoke test runner for Humetix Flask app.

Default mode is read-only checks.
If --admin-password is provided (or ADMIN_PASSWORD env var exists),
admin login + protected page checks are included.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from http.cookiejar import CookieJar
from typing import Iterable


CSRF_RE = re.compile(r'name=["\']csrf_token["\']\s+value=["\']([^"\']+)["\']')


@dataclass
class Result:
    name: str
    ok: bool
    status: str
    url: str
    detail: str = ""


class HttpClient:
    def __init__(self, base_url: str, timeout: int = 8) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.cookie_jar = CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie_jar)
        )

    def request(
        self,
        path: str,
        method: str = "GET",
        data: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int | None, str, bytes, str | None]:
        url = f"{self.base_url}{path}"
        body = None
        req_headers = {"User-Agent": "humetix-smoke/1.0"}
        if headers:
            req_headers.update(headers)

        if data is not None:
            body = urllib.parse.urlencode(data).encode("utf-8")
            req_headers.setdefault(
                "Content-Type", "application/x-www-form-urlencoded; charset=utf-8"
            )

        req = urllib.request.Request(
            url=url,
            data=body,
            headers=req_headers,
            method=method.upper(),
        )

        try:
            resp = self.opener.open(req, timeout=self.timeout)
            return (
                int(getattr(resp, "status", 200)),
                resp.geturl(),
                resp.read(),
                None,
            )
        except urllib.error.HTTPError as err:
            return err.code, err.geturl(), err.read(), None
        except urllib.error.URLError as err:
            return None, url, b"", str(err.reason)


def extract_csrf_token(html: bytes) -> str | None:
    match = CSRF_RE.search(html.decode("utf-8", errors="ignore"))
    if match:
        return match.group(1)
    return None


def run_case(
    client: HttpClient,
    name: str,
    path: str,
    expected_statuses: Iterable[int],
    expect_final_contains: str | None = None,
) -> Result:
    status, final_url, _body, err = client.request(path)
    if err:
        return Result(name=name, ok=False, status="NA", url=final_url, detail=err)

    ok = status in set(expected_statuses)
    detail = ""
    if expect_final_contains and expect_final_contains not in final_url:
        ok = False
        detail = f"unexpected final_url={final_url}"
    return Result(name=name, ok=ok, status=str(status), url=final_url, detail=detail)


def run_public_checks(client: HttpClient) -> list[Result]:
    checks = [
        ("home", "/", {200}, None),
        ("privacy", "/privacy", {200}, None),
        ("health", "/health", {200, 503}, None),
        ("login_page", "/login", {200}, None),
        ("apply_page", "/apply", {200}, None),
        ("attendance_page", "/attendance", {200}, None),
        ("advance_page", "/advance", {200}, None),
        ("favicon", "/static/images/favicon.svg", {200}, None),
        ("admin_redirect", "/humetix_master_99", {200}, "/login"),
    ]
    return [run_case(client, *c) for c in checks]


def run_admin_checks(client: HttpClient, admin_password: str) -> list[Result]:
    results: list[Result] = []

    status, final_url, body, err = client.request("/login")
    if err or status != 200:
        results.append(
            Result(
                name="admin_login_get",
                ok=False,
                status="NA" if err else str(status),
                url=final_url,
                detail=err or "failed to load login page",
            )
        )
        return results

    csrf_token = extract_csrf_token(body)
    if not csrf_token:
        results.append(
            Result(
                name="admin_login_get",
                ok=False,
                status=str(status),
                url=final_url,
                detail="csrf token not found",
            )
        )
        return results

    post_data = {"password": admin_password, "csrf_token": csrf_token}
    login_status, login_final_url, login_body, login_err = client.request(
        "/login", method="POST", data=post_data
    )
    if login_err:
        results.append(
            Result(
                name="admin_login_post",
                ok=False,
                status="NA",
                url=login_final_url,
                detail=login_err,
            )
        )
        return results

    login_text = login_body.decode("utf-8", errors="ignore")
    login_ok = (
        login_status in {200, 302}
        and (
            "/humetix_master_99" in login_final_url
            or "관리자 페이지" in login_text
            or "admin" in login_final_url
        )
    )
    results.append(
        Result(
            name="admin_login_post",
            ok=login_ok,
            status=str(login_status),
            url=login_final_url,
            detail="" if login_ok else "login appears to have failed",
        )
    )

    if not login_ok:
        return results

    protected_checks = [
        ("admin_main", "/humetix_master_99"),
        ("admin_employees", "/admin/employees"),
        ("admin_attendance", "/admin/attendance"),
        ("admin_advance", "/admin/advance"),
        ("admin_payslip", "/admin/payslip"),
        ("admin_inquiries", "/inquiries"),
    ]

    for name, path in protected_checks:
        results.append(run_case(client, name, path, {200}))

    results.append(run_case(client, "admin_logout", "/logout", {200}, expect_final_contains="/"))
    return results


def print_report(base_url: str, results: list[Result]) -> int:
    print(f"BASE URL: {base_url}")
    print("-" * 92)
    print(f"{'RESULT':<8} {'STATUS':<6} {'NAME':<22} {'FINAL URL':<42} DETAIL")
    print("-" * 92)

    failures = 0
    for r in results:
        marker = "PASS" if r.ok else "FAIL"
        if not r.ok:
            failures += 1
        detail = r.detail.strip()
        print(f"{marker:<8} {r.status:<6} {r.name:<22} {r.url:<42} {detail}")

    print("-" * 92)
    print(f"TOTAL={len(results)} PASS={len(results) - failures} FAIL={failures}")
    return 1 if failures else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Humetix smoke test runner")
    parser.add_argument(
        "--base-url",
        default="http://localhost:5000",
        help="Target base URL (default: http://localhost:5000)",
    )
    parser.add_argument(
        "--admin-password",
        default=os.environ.get("ADMIN_PASSWORD", ""),
        help="Admin password for protected-page smoke tests",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    client = HttpClient(args.base_url)

    results = run_public_checks(client)
    if args.admin_password:
        results.extend(run_admin_checks(client, args.admin_password))
    else:
        results.append(
            Result(
                name="admin_checks",
                ok=True,
                status="SKIP",
                url=args.base_url,
                detail="admin password not provided; protected checks skipped",
            )
        )

    return print_report(args.base_url, results)


if __name__ == "__main__":
    sys.exit(main())

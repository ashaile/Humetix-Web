"""
Solapi SMS 발송 서비스
"""
import logging
import os
import re

logger = logging.getLogger(__name__)


def _clean_phone(phone: str) -> str:
    """전화번호에서 숫자만 추출 (010-1234-5678 → 01012345678)."""
    return re.sub(r"[^0-9]", "", phone)


def send_sms(to: str, text: str) -> dict:
    """
    SMS/LMS 문자 발송.
    - to: 수신번호 (010-xxxx-xxxx 또는 01012345678)
    - text: 메시지 내용 (45자 이하 SMS, 초과 시 자동 LMS)
    - 반환: {"success": True/False, "detail": ...}
    """
    api_key = os.environ.get("SOLAPI_API_KEY", "")
    api_secret = os.environ.get("SOLAPI_API_SECRET", "")
    sender = os.environ.get("SOLAPI_SENDER_NUMBER", "")

    if not all([api_key, api_secret, sender]):
        logger.warning("[SMS] Solapi 설정 누락 — SOLAPI_API_KEY, SOLAPI_API_SECRET, SOLAPI_SENDER_NUMBER 확인")
        return {"success": False, "detail": "SMS 설정이 완료되지 않았습니다."}

    to_clean = _clean_phone(to)
    sender_clean = _clean_phone(sender)

    if not to_clean:
        return {"success": False, "detail": "수신번호가 없습니다."}

    try:
        from solapi import SolapiMessageService
        from solapi.model import RequestMessage

        svc = SolapiMessageService(api_key=api_key, api_secret=api_secret)
        msg = RequestMessage(from_=sender_clean, to=to_clean, text=text)
        resp = svc.send(msg)

        success_cnt = resp.group_info.count.registered_success
        failed_cnt = resp.group_info.count.registered_failed
        logger.info(f"[SMS] 발송 완료 → {to_clean} (성공:{success_cnt}, 실패:{failed_cnt})")

        return {
            "success": success_cnt > 0,
            "detail": f"성공:{success_cnt}, 실패:{failed_cnt}",
            "group_id": resp.group_info.group_id,
        }
    except Exception as e:
        logger.error(f"[SMS] 발송 실패 → {to_clean}: {e}")
        return {"success": False, "detail": str(e)}


def send_contract_link(to: str, worker_name: str, contract_title: str, sign_url: str) -> dict:
    """계약서 서명 링크 SMS 발송."""
    text = (
        f"{worker_name}님, 계약서가 도착했습니다.\n"
        f"계약명: {contract_title}\n"
        f"서명 링크: {sign_url}\n"
        f"위 링크를 눌러 서명을 완료해주세요."
    )
    return send_sms(to, text)

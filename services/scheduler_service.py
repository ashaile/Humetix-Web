"""APScheduler 기반 예약발송 서비스.

매분 실행되어 scheduled_at 시각이 도래한 계약의 SMS를 자동 발송한다.
gunicorn --preload 모드에서 단일 스케줄러만 동작하도록 설계.
"""

import logging
import os
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(daemon=True)


def _get_base_url(app):
    """서명 링크 기본 URL을 결정한다.

    우선순위: BASE_URL 환경변수 > SERVER_NAME 설정 > 기본값
    """
    base = os.environ.get("BASE_URL", "").rstrip("/")
    if base:
        return base
    server_name = app.config.get("SERVER_NAME")
    if server_name:
        scheme = app.config.get("PREFERRED_URL_SCHEME", "https")
        return f"{scheme}://{server_name}"
    return "https://humetix.com"


def _process_scheduled_contracts(app):
    """예약 시각이 도래한 계약을 처리한다 (SMS 발송 + 상태 변경)."""
    with app.app_context():
        from models import Contract, ContractAuditLog, db
        from services.sms_service import send_contract_link

        now = datetime.now()
        contracts = Contract.query.filter(
            Contract.status == "scheduled",
            Contract.scheduled_at <= now,
        ).all()

        if not contracts:
            return

        base_url = _get_base_url(app)
        logger.info("[예약발송] %d건 처리 시작 (base_url=%s)", len(contracts), base_url)

        for contract in contracts:
            sent_count = 0
            for p in contract.participants:
                if p.status != "pending" or not p.phone:
                    continue
                try:
                    sign_url = f"{base_url}/sign/{p.sign_token}"
                    result = send_contract_link(
                        to=p.phone,
                        worker_name=p.name,
                        contract_title=contract.title,
                        sign_url=sign_url,
                    )
                    if result.get("success"):
                        sent_count += 1
                        logger.info(
                            "[예약발송] SMS 발송 성공: contract=%d, %s (%s)",
                            contract.id, p.name, p.phone,
                        )
                    else:
                        logger.warning(
                            "[예약발송] SMS 발송 실패: contract=%d, %s — %s",
                            contract.id, p.name, result.get("detail"),
                        )
                except Exception as e:
                    logger.error("[예약발송] SMS 오류: contract=%d, %s — %s", contract.id, p.name, e)

            # 상태 변경: scheduled → pending
            contract.status = "pending"

            log = ContractAuditLog(
                contract_id=contract.id,
                action="예약 발송 완료",
                actor="시스템",
                detail=f"예약시각: {contract.scheduled_at.strftime('%Y-%m-%d %H:%M')}, SMS {sent_count}건 발송",
            )
            db.session.add(log)

        db.session.commit()
        logger.info("[예약발송] %d건 처리 완료", len(contracts))


def init_scheduler(app):
    """Flask 앱에 APScheduler를 연결하고 예약발송 작업을 등록한다.

    환경변수 SCHEDULER_DISABLED=1 로 비활성화 가능 (gunicorn 멀티워커 시 활용).
    """
    if scheduler.running:
        return
    if os.environ.get("SCHEDULER_DISABLED", "") == "1":
        logger.info("[스케줄러] SCHEDULER_DISABLED=1 — 스케줄러 비활성화")
        return

    scheduler.add_job(
        func=_process_scheduled_contracts,
        trigger="interval",
        seconds=60,
        args=[app],
        id="contract_scheduled_send",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info("[스케줄러] APScheduler 시작 — 예약발송 체크 주기: 60초")

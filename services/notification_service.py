import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

class NotificationService:
    @staticmethod
    def send_admin_notification(application_data):
        """
        새로운 지원서 접수 시 관리자에게 이메일 및 SMS 알림을 보냅니다.
        환경 변수가 설정되어 있지 않으면 로그만 출력합니다.
        """
        name = application_data.get('info', {}).get('name', '알 수 없음')
        phone = application_data.get('info', {}).get('phone', '알 수 없음')

        message = f"[신규 지원서 접수] 이름: {name} / 연락처: {phone}"

        # 1. 이메일 알림
        NotificationService.send_email(
            subject="[Humetix] 신규 지원서가 접수되었습니다.",
            body=message
        )

        # 2. SMS 알림
        NotificationService.send_sms(message)

    @staticmethod
    def send_email(subject, body):
        smtp_user = os.environ.get('SMTP_USER')
        smtp_pass = os.environ.get('SMTP_PASS')
        admin_email = os.environ.get('ADMIN_EMAIL')

        if not all([smtp_user, smtp_pass, admin_email]):
            logger.info(f"[MOCK EMAIL] To: {admin_email} | Subject: {subject} | Body: {body}")
            logger.info("  => SMTP 설정이 누락되어 실제 메일은 발송되지 않았습니다.")
            return

        try:
            msg = MIMEMultipart()
            msg['From'] = smtp_user
            msg['To'] = admin_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain', 'utf-8'))

            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)

            logger.info(f"[EMAIL SENT] To: {admin_email} | Subject: {subject}")
        except Exception as e:
            logger.error(f"[EMAIL FAILED] {e}")

    @staticmethod
    def send_sms(message):
        sms_api_key = os.environ.get('SMS_API_KEY')
        admin_phone = os.environ.get('ADMIN_PHONE')

        if not all([sms_api_key, admin_phone]):
            logger.info(f"[MOCK SMS] To: {admin_phone} | Msg: {message}")
            logger.info("  => SMS API 설정이 누락되어 실제 문자는 발송되지 않았습니다.")
            return

        try:
            # CoolSMS / Aligo 등 API 연동 시 여기에 구현
            # 현재는 API 키가 설정되면 로그만 출력
            logger.info(f"[SMS READY] To: {admin_phone} | Msg: {message}")
            logger.info("  => SMS API 연동이 필요합니다. (CoolSMS/Aligo)")
        except Exception as e:
            logger.error(f"[SMS FAILED] {e}")

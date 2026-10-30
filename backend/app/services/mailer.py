import os
import smtplib
from email.message import EmailMessage
import requests


def is_production_mailer_configured():
    return bool(os.environ.get('RESEND_API_KEY') or os.environ.get('SMTP_HOST'))


def send_transactional_email(to_email, subject, text_body, html_body=None):
    """Envía un correo transaccional mediante Resend API o SMTP estándar.
    En desarrollo local (sin credenciales configuradas), registra el mensaje en consola
    y devuelve (True, 'dev_fallback') para permitir pruebas completas sin servidor externo.
    """
    if not to_email:
        return False, 'missing_recipient'

    from_email = os.environ.get('MAIL_FROM', 'BeerMap <no-reply@beermap.app>')
    resend_key = os.environ.get('RESEND_API_KEY')

    if resend_key:
        try:
            payload = {
                'from': from_email,
                'to': [to_email],
                'subject': subject,
                'text': text_body,
            }
            if html_body:
                payload['html'] = html_body
            resp = requests.post(
                'https://api.resend.com/emails',
                headers={
                    'Authorization': f'Bearer {resend_key}',
                    'Content-Type': 'application/json',
                },
                json=payload,
                timeout=8,
            )
            if 200 <= resp.status_code < 300:
                return True, 'resend'
            return False, f'resend_error_{resp.status_code}'
        except Exception as exc:
            return False, f'resend_exception:{exc}'

    smtp_host = os.environ.get('SMTP_HOST')
    if smtp_host:
        try:
            smtp_port = int(os.environ.get('SMTP_PORT', '587'))
            smtp_user = os.environ.get('SMTP_USER', '')
            smtp_pass = os.environ.get('SMTP_PASSWORD', '')
            msg = EmailMessage()
            msg['Subject'] = subject
            msg['From'] = from_email
            msg['To'] = to_email
            msg.set_content(text_body)
            if html_body:
                msg.add_alternative(html_body, subtype='html')

            with smtplib.SMTP(smtp_host, smtp_port, timeout=8) as server:
                if os.environ.get('SMTP_TLS', '1') == '1':
                    server.starttls()
                if smtp_user:
                    server.login(smtp_user, smtp_pass)
                server.send_message(msg)
            return True, 'smtp'
        except Exception as exc:
            return False, f'smtp_exception:{exc}'

    # Modo desarrollo local sin proveedor externo configurado
    if os.environ.get('APP_ENV') == 'production':
        return False, 'no_mail_provider_in_production'

    print(f"\n[DEV-MAILER] To: {to_email} | Subject: {subject}\n{text_body}\n")
    return True, 'dev_console'


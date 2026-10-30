import hashlib
import hmac
import ipaddress
import re
import secrets
import socket
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import requests

# Proveedores de correo genéricos que jamás deben acreditar propiedad de un dominio corporativo
PUBLIC_EMAIL_DOMAINS = {
    'gmail.com', 'googlemail.com', 'hotmail.com', 'hotmail.es', 'outlook.com', 'outlook.es',
    'live.com', 'msn.com', 'yahoo.com', 'yahoo.es', 'icloud.com', 'me.com', 'proton.me',
    'protonmail.com', 'aol.com', 'gmx.com', 'gmx.es', 'zoho.com', 'mail.com', 'yandex.com',
    'local.dev', 'example.com', 'ejemplo.com'
}

MULTIPART_TLDS = {
    'co.uk', 'org.uk', 'com.es', 'nom.es', 'org.es', 'com.ar', 'com.mx', 'com.br', 'co.jp'
}


def extract_registrable_domain(url_or_email):
    """Extrae el dominio registrable base (ej. 'https://shop.laugarbrewery.com/es' -> 'laugarbrewery.com')."""
    if not url_or_email:
        return None
    raw = str(url_or_email).strip().lower()
    if '@' in raw and not raw.startswith(('http://', 'https://')):
        host = raw.rsplit('@', 1)[-1]
    else:
        if not raw.startswith(('http://', 'https://')):
            raw = 'https://' + raw
        parsed = urlparse(raw)
        host = (parsed.hostname or '').lower()

    host = host.strip('.')
    if host.startswith('www.'):
        host = host[4:]
    if not host or '.' not in host:
        return None

    parts = host.split('.')
    if len(parts) >= 3 and '.'.join(parts[-2:]) in MULTIPART_TLDS:
        return '.'.join(parts[-3:])
    if len(parts) >= 2:
        return '.'.join(parts[-2:])
    return None


def is_corporate_email_matching_website(email, website_url):
    """Comprueba que el email pertenezca exactamente al mismo dominio registrable que la web oficial,
    descartando dominios de correo gratuitos/públicos."""
    email_dom = extract_registrable_domain(email)
    site_dom = extract_registrable_domain(website_url)
    if not email_dom or not site_dom:
        return False
    if email_dom in PUBLIC_EMAIL_DOMAINS or site_dom in PUBLIC_EMAIL_DOMAINS:
        return False
    return email_dom == site_dom


def generate_otp_code():
    return f"{secrets.randbelow(900000) + 100000:06d}"


def hash_otp(code, secret_salt=''):
    payload = f"{secret_salt}:{str(code).strip()}".encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


def verify_otp(submitted_code, expected_hash, expires_at_iso, secret_salt=''):
    if not submitted_code or not expected_hash or not expires_at_iso:
        return False
    try:
        exp_dt = datetime.fromisoformat(expires_at_iso.replace('Z', '+00:00'))
        if datetime.now(timezone.utc) > exp_dt:
            return False
    except ValueError:
        return False
    calc = hash_otp(submitted_code, secret_salt=secret_salt)
    return hmac.compare_digest(calc, expected_hash)


def otp_expiry_iso(minutes=15):
    dt = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return dt.isoformat(timespec='seconds').replace('+00:00', 'Z')


def generate_meta_token():
    return f"bf-verify-{secrets.token_hex(12)}"


def generate_social_token():
    return f"#BF-{secrets.randbelow(9000) + 1000}"


def _is_safe_public_url(url):
    """Protección anti-SSRF: impide que la verificación web conecte con localhost o redes internas."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname:
            return False
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80))
        for info in infos:
            ip_str = info[4][0]
            ip_obj = ipaddress.ip_address(ip_str)
            if not ip_obj.is_global:
                return False
        return True
    except Exception:
        return False


def verify_website_token(website_url, expected_token):
    """Comprueba si el sitio oficial contiene el token en:
    1) /.well-known/beerfinder-verify.txt
    2) <meta name="beerfinder-verify" content="<token>"> en la portada.
    Devuelve (verified: bool, detail_message: str).
    """
    if not website_url or not expected_token:
        return False, "Falta la URL oficial o el código de verificación."

    parsed = urlparse(website_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    if not _is_safe_public_url(base_url):
        return False, "La URL de la entidad no apunta a un dominio público accesible."

    headers = {'User-Agent': 'BeerMap-VerificationBot/1.0'}

    # 1. Comprobar fichero .well-known
    well_known_url = f"{base_url}/.well-known/beerfinder-verify.txt"
    try:
        resp = requests.get(well_known_url, headers=headers, timeout=5, allow_redirects=True)
        if resp.status_code == 200 and expected_token in resp.text[:4096]:
            return True, "Código verificado mediante /.well-known/beerfinder-verify.txt"
    except requests.RequestException:
        pass

    # 2. Comprobar meta-tag en portada
    try:
        resp = requests.get(website_url, headers=headers, timeout=5, allow_redirects=True)
        if resp.status_code == 200:
            snippet = resp.text[:131072]
            pattern = re.compile(
                r'<meta[^>]+name=["\']beerfinder-verify["\'][^>]+content=["\']([^"\']+)["\']',
                re.IGNORECASE
            )
            alt_pattern = re.compile(
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']beerfinder-verify["\']',
                re.IGNORECASE
            )
            matches = pattern.findall(snippet) + alt_pattern.findall(snippet)
            if any(m.strip() == expected_token for m in matches):
                return True, "Código verificado mediante etiqueta <meta name='beerfinder-verify'>."
    except requests.RequestException:
        return False, "No se pudo conectar con el sitio web indicado."

    return False, "Todavía no hemos detectado la etiqueta <meta> ni el archivo .well-known en la web."


def _was_website_self_injected_recently(entity, requesting_user_id, hours=48):
    """Evita el ataque de auto-atestación: si el propio usuario creó la entidad o modificó su web
    hace menos de 48h, su coincidencia de dominio acredita control del dominio pero requiere 1 clic de Admin
    para confirmar que ese dominio pertenece realmente a la marca comercial."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)

    if entity.get('website_updated_by') == requesting_user_id and entity.get('website_updated_at'):
        try:
            dt = datetime.fromisoformat(entity['website_updated_at'].replace('Z', '+00:00'))
            if dt >= cutoff:
                return True
        except ValueError:
            return True

    if entity.get('created_by') == requesting_user_id and entity.get('created_at'):
        try:
            dt = datetime.fromisoformat(entity['created_at'].replace('Z', '+00:00'))
            if dt >= cutoff:
                return True
        except ValueError:
            return True

    return False


def can_auto_approve_claim(entity, requesting_user_id, competing_pending_count, proof_verified):
    """Determina si una reclamación con prueba técnica superada puede auto-aprobarse sin intervención humana."""
    if not proof_verified:
        return False
    if entity.get('owner_user_id') is not None:
        return False  # Disputa sobre entidad ya verificada -> siempre revisión Admin
    if competing_pending_count > 0:
        return False
    if _was_website_self_injected_recently(entity, requesting_user_id):
        return False
    return True


def evaluate_claim_trust(claim_dict, entity_dict, requester_dict, competing_pending_count=0):
    """Calcula un Trust Score (0-100) y una lista explicativa de señales [['success'|'warning', texto]]
    que se persiste en base de datos y guía al administrador."""
    score = 20
    signals = []

    if requester_dict and requester_dict.get('email_verified'):
        score += 15
        signals.append(['success', 'Email de cuenta verificado'])
    else:
        score -= 10
        signals.append(['warning', 'Email de cuenta sin verificar'])

    # Antigüedad de la cuenta
    created_at = (requester_dict or {}).get('created_at')
    if created_at:
        try:
            dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            age_days = (datetime.now(timezone.utc) - dt).days
            if age_days < 1:
                score -= 10
                signals.append(['warning', 'Cuenta creada hace menos de 24h'])
            elif age_days >= 14:
                score += 10
                signals.append(['success', f'Cuenta con {age_days} días de antigüedad'])
        except ValueError:
            pass

    method = claim_dict.get('verification_method', 'MANUAL')
    v_status = claim_dict.get('verification_status', 'PENDING_PROOF')
    website = (entity_dict or {}).get('website')
    req_email = claim_dict.get('verification_target') or (requester_dict or {}).get('email')

    if method == 'DOMAIN_EMAIL':
        if v_status == 'PROOF_VERIFIED':
            score += 45
            signals.append(['success', f'OTP verificado en correo corporativo ({claim_dict.get("verification_target")})'])
        else:
            signals.append(['warning', 'Pendiente de confirmar código OTP corporativo'])
    elif method == 'DNS_META':
        if v_status == 'PROOF_VERIFIED':
            score += 50
            signals.append(['success', 'Propiedad técnica del sitio web verificada (meta-tag / .well-known)'])
        else:
            signals.append(['warning', 'Token técnico web aún no comprobado'])
    elif method == 'SOCIAL_TOKEN':
        score += 15
        signals.append(['warning', f'Reto social generado ({claim_dict.get("verification_token")}): comprobar perfil enlazado'])
    elif method == 'DOCUMENT_UPLOAD' and claim_dict.get('evidence_file'):
        score += 20
        signals.append(['success', 'Documento acreditativo privado adjunto para revisión'])

    # Coincidencia pasiva email de cuenta <-> dominio de entidad
    if website and req_email and is_corporate_email_matching_website(req_email, website) and method not in ('DOMAIN_EMAIL',):
        score += 20
        signals.append(['success', 'El dominio del correo coincide con la web oficial'])

    # Alerta anti auto-atestación
    if entity_dict and requester_dict and _was_website_self_injected_recently(entity_dict, requester_dict.get('id')):
        score -= 15
        signals.append(['warning', 'Entidad o web dada de alta recientemente por el mismo solicitante (comprobar legitimidad de marca)'])

    if claim_dict.get('is_dispute') or (entity_dict and entity_dict.get('owner_user_id') is not None):
        score -= 20
        signals.append(['warning', 'Disputa sobre una entidad que ya tiene propietario actual'])

    if competing_pending_count > 0:
        score -= 15
        signals.append(['warning', f'Existen {competing_pending_count} reclamación(es) simultáneas en disputa'])

    final_score = max(0, min(100, score))
    return final_score, signals


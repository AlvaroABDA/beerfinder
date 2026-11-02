import json
import logging
import os
import base64
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pywebpush import webpush, WebPushException

logger = logging.getLogger(__name__)

VAPID_CLAIM_EMAIL = os.environ.get('VAPID_CLAIM_EMAIL', 'mailto:admin@beermap.app')
KEY_FILE_NAME = 'vapid_keys.json'


def _get_key_file_path():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    instance_dir = os.path.join(base_dir, 'instance')
    os.makedirs(instance_dir, exist_ok=True)
    return os.path.join(instance_dir, KEY_FILE_NAME)


def get_or_create_vapid_keys():
    """Obtiene el par de claves VAPID para Web Push, creándolas de forma persistente si no existen."""
    env_pub = os.environ.get('VAPID_PUBLIC_KEY')
    env_priv = os.environ.get('VAPID_PRIVATE_KEY')
    if env_pub and env_priv:
        return {'public_key': env_pub.strip(), 'private_key': env_priv.strip()}

    key_path = _get_key_file_path()
    if os.path.isfile(key_path):
        try:
            with open(key_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get('public_key') and data.get('private_key'):
                    return data
        except Exception as e:
            logger.warning(f"No se pudo leer {key_path}: {e}")

    # Generación de par de claves EC P-256 (estándar RFC 8292 para Web Push)
    private_key = ec.generate_private_key(ec.SECP256R1())
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode('utf-8')

    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    public_b64 = base64.urlsafe_b64encode(public_bytes).decode('utf-8').rstrip('=')

    keys = {'public_key': public_b64, 'private_key': private_pem}
    try:
        with open(key_path, 'w', encoding='utf-8') as f:
            json.dump(keys, f, indent=2)
    except Exception as e:
        logger.warning(f"No se pudo guardar {key_path}: {e}")

    return keys


def get_vapid_public_key():
    keys = get_or_create_vapid_keys()
    return keys.get('public_key', '')


def send_web_push(subscription, payload):
    """Envía una notificación Web Push a un suscriptor individual.
    Si el endpoint devuelve 404 o 410 (suscripción cancelada o caducada), se elimina de la base de datos."""
    keys = get_or_create_vapid_keys()
    private_key = keys.get('private_key')
    if not private_key:
        return False, "Clave VAPID privada no configurada"

    sub_info = {
        'endpoint': subscription.endpoint,
        'keys': {
            'p256dh': subscription.p256dh,
            'auth': subscription.auth,
        },
    }

    claim_email = os.environ.get('VAPID_CLAIM_EMAIL', VAPID_CLAIM_EMAIL)
    if not claim_email.startswith('mailto:'):
        claim_email = f'mailto:{claim_email}'

    vapid_claims = {'sub': claim_email}

    data_str = json.dumps(payload, ensure_ascii=False) if isinstance(payload, dict) else str(payload)

    try:
        webpush(
            subscription_info=sub_info,
            data=data_str,
            vapid_private_key=private_key,
            vapid_claims=vapid_claims,
            ttl=86400,
        )
        return True, "Enviado con éxito"
    except WebPushException as ex:
        status_code = getattr(getattr(ex, 'response', None), 'status_code', None)
        logger.warning(f"Error Web Push para {subscription.id}: {ex} (status={status_code})")
        if status_code in (404, 410):
            try:
                from ..models import db
                db.session.delete(subscription)
                db.session.commit()
            except Exception:
                pass
            return False, "Suscripción caducada (eliminada)"
        return False, str(ex)
    except Exception as ex:
        logger.error(f"Excepción general enviando Web Push: {ex}")
        return False, str(ex)


def notify_eligible_subscribers_for_event(event_id, origin_url=None):
    """Localiza los suscriptores elegibles (geocercanía + afinidad de paladar, sin spam)
    y les envía una notificación push."""
    try:
        from .. import data_access
    except ImportError:
        import data_access

    ev = data_access.get_event(event_id)
    if not ev:
        return 0, "Evento no encontrado"

    venue = ev.get('venue')
    venue_name = venue.get('name') if venue else 'Local cervecero'

    eligible = data_access.get_eligible_push_subscriptions_for_event(event_id)
    if not eligible:
        return 0, "No hay suscriptores en el radio o con afinidad para este evento"

    date_str = ev.get('event_date', '').replace('T', ' ')
    if len(date_str) > 16:
        date_str = date_str[:16]

    sent_count = 0
    target_path = f"/event/{ev['id']}"
    click_url = f"{origin_url.rstrip('/')}{target_path}" if origin_url else target_path

    for item in eligible:
        sub = item['subscription']
        has_affinity = item.get('has_affinity', False)

        title = f"🍺 {ev['event_type_label']}: {ev['title']}"
        body_parts = [venue_name, date_str]
        if has_affinity:
            body_parts.append("🎯 Afín a tu paladar cervecero")

        payload = {
            'title': title,
            'body': ' • '.join(body_parts),
            'icon': '/static/icons/icon-192.png',
            'badge': '/static/icons/icon-192.png',
            'data': {
                'url': click_url,
                'event_id': ev['id'],
            },
        }

        ok, _ = send_web_push(sub, payload)
        if ok:
            sent_count += 1

    return sent_count, f"Notificación enviada a {sent_count} usuarios afines"


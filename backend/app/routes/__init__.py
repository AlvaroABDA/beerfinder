from flask import Blueprint, current_app, jsonify, render_template, send_from_directory
from sqlalchemy import text

from ..models import db

bp = Blueprint('routes', __name__)


def can_edit_entity(entity, user_id, is_admin=False):
    """Regla de gobernanza:
    - ADMIN siempre puede editar.
    - Si la entidad tiene propietario verificado (owner_user_id), SOLO ese propietario puede editarla.
    - Si la entidad aún es huérfana (owner_user_id is None), su creador comunitario (created_by) puede editarla.
    """
    if is_admin:
        return True
    if not user_id or not entity:
        return False
    owner_id = entity.get('owner_user_id')
    if owner_id is not None:
        return int(owner_id) == int(user_id)
    creator_id = entity.get('created_by')
    return creator_id is not None and int(creator_id) == int(user_id)


def can_access_b2b_venue(venue, user_id, is_admin=False):
    """Herramientas B2B (Modo TV, Cartelería QR, analítica de demanda):
    reservadas exclusivamente al propietario verificado del local o a ADMIN."""
    if is_admin:
        return True
    if not user_id or not venue:
        return False
    owner_id = venue.get('owner_user_id')
    return owner_id is not None and int(owner_id) == int(user_id)


def fmt_distance(distance_km):
    if distance_km is None:
        return None
    if distance_km < 1.0:
        return f"{int(round(distance_km * 1000))} m"
    return f"{round(distance_km, 1)} km"


def fmt_walking_time(distance_km):
    if distance_km is None or distance_km > 4.0:
        return None
    mins = max(1, int(round((distance_km / 4.8) * 60)))
    return f"{mins} min"


def entity_display_info(entity_type, entity_id):
    """Devuelve (nombre, url, entidad_dict) para enriquecer vistas de reclamaciones y perfil."""
    from flask import url_for
    from .. import data_access

    if entity_type == 'venue':
        ent = data_access.get_venue(entity_id)
        return (ent['name'] if ent else f"Local #{entity_id}", url_for('routes.venue_view', id=entity_id), ent)
    if entity_type == 'brand':
        ent = data_access.get_fabricante(entity_id)
        return (ent['name'] if ent else f"Marca #{entity_id}", url_for('routes.fabricante_view', id=entity_id), ent)
    if entity_type == 'beer':
        ent = data_access.get_beer(entity_id)
        return (ent['name'] if ent else f"Cerveza #{entity_id}", url_for('routes.beer_view', id=entity_id), ent)
    return (f"{entity_type} #{entity_id}", '#', None)


@bp.route('/sw.js')
def service_worker():
    resp = send_from_directory(current_app.static_folder, 'sw.js', mimetype='application/javascript')
    resp.headers['Cache-Control'] = 'no-cache'
    return resp


@bp.route('/offline')
def offline():
    return render_template('offline.html')


@bp.route('/health')
def health_check():
    try:
        db.session.execute(text('SELECT 1'))
        return jsonify({'status': 'ok', 'db': 'connected'}), 200
    except Exception:
        return jsonify({'status': 'degraded', 'db': 'unreachable'}), 503


@bp.route('/.well-known/assetlinks.json')
def android_asset_links():
    """Digital Asset Links para empaquetado Android TWA (Google Play / Bubblewrap) sin barra de navegador."""
    import os
    pkg = (os.environ.get('ANDROID_PACKAGE_NAME') or '').strip()
    raw_fps = (os.environ.get('ANDROID_SHA256_CERT_FINGERPRINTS') or '').strip()
    fingerprints = [fp.strip() for fp in raw_fps.split(',') if fp.strip()]
    if not pkg or not fingerprints:
        return jsonify([]), 200
    return jsonify([
        {
            'relation': ['delegate_permission/common.handle_all_urls'],
            'target': {
                'namespace': 'android_app',
                'package_name': pkg,
                'sha256_cert_fingerprints': fingerprints,
            },
        }
    ]), 200


@bp.after_app_request
def add_cache_control(response):
    if response.mimetype == 'text/html':
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response


# Registrar sub-módulos sobre el mismo blueprint para mantener intactos todos los endpoints url_for('routes.*')
from . import auth_routes, catalog_routes, api_routes, claims_routes, admin_routes  # noqa: E402,F401


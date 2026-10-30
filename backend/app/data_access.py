import json
import math
import os
from datetime import datetime, timedelta, timezone
import requests
from flask import url_for

from .models import (
    db, utc_now_iso, parse_abv,
    User, Venue, Fabricante, BeerFamily, BeerStyle, Tag, Beer, BeerTag,
    Availability, Claim, UserBeerPreference, UserPreference, AuditLog, GeocodingCache
)
from .services import storage

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')


def is_active(item):
    """Un registro se considera activo salvo que 'active' sea explícitamente False."""
    if item is None:
        return False
    val = item.get('active') if hasattr(item, 'get') else getattr(item, 'active', True)
    return val is not False


def sanitize_url(url):
    """Permite únicamente esquemas http(s) para impedir vectores XSS (javascript:, data:, etc.)."""
    if not url:
        return None
    url = str(url).strip()
    if not url:
        return None
    if not url.lower().startswith(('http://', 'https://')):
        return None
    return url


def sanitize_instagram(handle):
    if not handle:
        return None
    h = str(handle).strip()
    if 'instagram.com/' in h.lower():
        h = h.rstrip('/').rsplit('/', 1)[-1]
    h = h.lstrip('@').strip()
    return h[:100] if h else None


def save_uploaded_image(file_storage, subfolder):
    return storage.save_public_image(file_storage, subfolder)


def resolve_media_url(subfolder, filename):
    """Resuelve una imagen guardada tanto si es URL CDN/S3 como si es fichero local en static/."""
    if not filename or filename in ('default.png', 'default_beer.png'):
        return None
    if filename.startswith(('http://', 'https://')):
        return filename
    if filename.startswith('public/'):
        cdn_base = (os.environ.get('PUBLIC_CDN_URL') or '').rstrip('/')
        if cdn_base:
            return f"{cdn_base}/{filename}"
    return url_for('static', filename=f"images/{subfolder}/{filename}")


def haversine(lat1, lon1, lat2, lon2):
    r_earth = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r_earth * c


def bounding_box(lat, lon, radius_km):
    """Caja envolvente rápida en SQL antes de calcular Haversine exacto."""
    lat_delta = radius_km / 111.0
    cos_lat = max(0.01, abs(math.cos(math.radians(lat))))
    lon_delta = radius_km / (111.320 * cos_lat)
    return lat - lat_delta, lat + lat_delta, lon - lon_delta, lon + lon_delta


def geocode_address(address):
    """Geocodifica una dirección consultando primero la caché en BD y con timeout estricto."""
    if not address or not str(address).strip():
        return None, None
    norm = ' '.join(str(address).strip().lower().split())
    cached = GeocodingCache.query.filter_by(query_normalized=norm).first()
    if cached:
        return cached.latitude, cached.longitude

    if os.environ.get('DISABLE_EXTERNAL_GEOCODING') == '1':
        return None, None

    url = 'https://nominatim.openstreetmap.org/search'
    params = {'q': address, 'format': 'json', 'limit': 1}
    lat, lon = None, None
    try:
        resp = requests.get(
            url,
            params=params,
            headers={'User-Agent': os.environ.get('GEOCODER_USER_AGENT', 'BeerMap-SaaS/1.0')},
            timeout=4,
        )
        if resp.status_code == 200:
            data = resp.json()
            if data:
                lat, lon = float(data[0]['lat']), float(data[0]['lon'])
    except Exception:
        return None, None

    try:
        db.session.add(GeocodingCache(query_normalized=norm, latitude=lat, longitude=lon))
        db.session.commit()
    except Exception:
        db.session.rollback()
    return lat, lon


def log_audit(actor_user_id, action, entity_type=None, entity_id=None, details=None):
    entry = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        created_at=utc_now_iso(),
    )
    db.session.add(entry)


# ==============================================================================
# 1. USUARIOS
# ==============================================================================

def get_user_by_id(user_id):
    if not user_id:
        return None
    u = db.session.get(User, int(user_id))
    return u.to_dict() if u else None


def get_user_orm(user_id):
    return db.session.get(User, int(user_id)) if user_id else None


def get_user_by_username(username):
    if not username:
        return None
    u = User.query.filter(db.func.lower(User.username) == username.strip().lower()).first()
    return u.to_dict() if u else None


def get_user_by_email(email):
    if not email:
        return None
    u = User.query.filter(db.func.lower(User.email) == email.strip().lower()).first()
    return u.to_dict() if u else None


def list_users(q=None):
    query = User.query
    if q:
        like_q = f"%{q.strip()}%"
        query = query.filter(db.or_(User.username.ilike(like_q), User.email.ilike(like_q)))
    return [u.to_dict() for u in query.order_by(User.id.asc()).all()]


def create_user(username, email, password_hash, role='USER'):
    safe_role = 'ADMIN' if role == 'ADMIN' else 'USER'
    u = User(
        username=username.strip(),
        email=email.strip().lower(),
        password=password_hash,
        role=safe_role,
        status='ACTIVE',
        email_verified=False,
        max_distance=20.0,
        created_at=utc_now_iso(),
    )
    db.session.add(u)
    db.session.commit()
    return u.to_dict()


def update_user_fields(user_id, **fields):
    u = db.session.get(User, int(user_id))
    if not u:
        return None
    allowed = {
        'username', 'email', 'password', 'role', 'status',
        'email_verified', 'email_otp_hash', 'email_otp_expires_at', 'max_distance'
    }
    for k, v in fields.items():
        if k in allowed:
            if k == 'role' and v not in ('USER', 'ADMIN'):
                v = 'USER'
            setattr(u, k, v)
    db.session.commit()
    return u.to_dict()


def delete_user_by_id(user_id):
    u = db.session.get(User, int(user_id))
    if not u:
        return False
    db.session.delete(u)
    db.session.commit()
    return True


# ==============================================================================
# 2. FABRICANTES / MARCAS
# ==============================================================================

def get_fabricante(fab_id):
    f = db.session.get(Fabricante, int(fab_id)) if fab_id else None
    return f.to_dict() if f else None


def find_fabricante_by_name(name):
    if not name or not str(name).strip():
        return None
    f = Fabricante.query.filter(db.func.lower(Fabricante.name) == str(name).strip().lower()).first()
    return f.to_dict() if f else None


def get_or_create_fabricante(name, created_by=None):
    """Asegura integridad relacional: vincula o crea automáticamente el Fabricante cuando se da de alta una cerveza."""
    if not name or not str(name).strip():
        return None
    clean_name = str(name).strip()
    existing = Fabricante.query.filter(db.func.lower(Fabricante.name) == clean_name.lower()).first()
    if existing:
        return existing
    new_fab = Fabricante(
        name=clean_name,
        country='',
        description='',
        created_by=created_by,
        owner_user_id=None,
        active=True,
        created_at=utc_now_iso(),
    )
    db.session.add(new_fab)
    db.session.flush()
    return new_fab


def list_fabricantes(q=None, only_active=False):
    query = Fabricante.query
    if only_active:
        query = query.filter(Fabricante.active.is_(True))
    if q:
        like_q = f"%{q.strip()}%"
        query = query.filter(db.or_(Fabricante.name.ilike(like_q), Fabricante.country.ilike(like_q)))
    return [f.to_dict() for f in query.order_by(Fabricante.name.asc()).all()]


def create_fabricante(data, created_by=None):
    now = utc_now_iso()
    website = sanitize_url(data.get('website'))
    fab = Fabricante(
        name=(data.get('name') or '').strip(),
        country=(data.get('country') or '').strip(),
        description=(data.get('description') or '').strip(),
        website=website,
        instagram_handle=sanitize_instagram(data.get('instagram_handle')),
        email=(data.get('email') or '').strip() or None,
        phone=(data.get('phone') or '').strip() or None,
        logo=data.get('logo') or None,
        created_by=created_by,
        owner_user_id=None,
        website_updated_at=now if website else None,
        website_updated_by=created_by if website else None,
        active=True,
        created_at=now,
    )
    db.session.add(fab)
    db.session.commit()
    return fab.to_dict()


def update_fabricante(fab_id, data, actor_user_id=None):
    fab = db.session.get(Fabricante, int(fab_id))
    if not fab:
        return None
    old_name = fab.name
    old_web = fab.website

    if 'name' in data and data['name']:
        fab.name = data['name'].strip()
    if 'country' in data:
        fab.country = (data['country'] or '').strip()
    if 'description' in data:
        fab.description = (data['description'] or '').strip()
    if 'website' in data:
        new_web = sanitize_url(data.get('website'))
        if new_web != old_web:
            fab.website = new_web
            fab.website_updated_at = utc_now_iso()
            fab.website_updated_by = actor_user_id
    if 'instagram_handle' in data:
        fab.instagram_handle = sanitize_instagram(data.get('instagram_handle'))
    if 'email' in data:
        fab.email = (data['email'] or '').strip() or None
    if 'phone' in data:
        fab.phone = (data['phone'] or '').strip() or None
    if data.get('logo'):
        fab.logo = data['logo']
    if 'active' in data:
        fab.active = bool(data['active'])

    # Mantener sincronizado el nombre legible en sus cervezas vinculadas
    if fab.name != old_name:
        Beer.query.filter_by(fabricante_id=fab.id).update({'brewery': fab.name})

    db.session.commit()
    return fab.to_dict()


def delete_fabricante_by_id(fab_id):
    fab = db.session.get(Fabricante, int(fab_id))
    if not fab:
        return False
    db.session.delete(fab)
    db.session.commit()
    return True


def adopt_orphan_beers_for_brand(fab_id, owner_user_id):
    """Permite al propietario verificado de una marca adoptar en 1 clic sus cervezas huérfanas."""
    fab = db.session.get(Fabricante, int(fab_id))
    if not fab or fab.owner_user_id != owner_user_id:
        return 0
    now = utc_now_iso()
    orphan_beers = Beer.query.filter(
        db.or_(
            Beer.fabricante_id == fab.id,
            db.func.lower(Beer.brewery) == fab.name.lower()
        ),
        Beer.owner_user_id.is_(None)
    ).all()
    for b in orphan_beers:
        b.fabricante_id = fab.id
        b.brewery = fab.name
        b.owner_user_id = owner_user_id
        b.verified_at = now
    log_audit(
        actor_user_id=owner_user_id,
        action='BRAND_CATALOG_ADOPTED',
        entity_type='brand',
        entity_id=fab.id,
        details=f"Adoptadas {len(orphan_beers)} cervezas huérfanas de {fab.name}."
    )
    db.session.commit()
    return len(orphan_beers)


# ==============================================================================
# 3. LOCALES / BARES (VENUES)
# ==============================================================================

def get_venue(venue_id):
    v = db.session.get(Venue, int(venue_id)) if venue_id else None
    return v.to_dict() if v else None


def list_venues(q=None, only_active=False):
    query = Venue.query
    if only_active:
        query = query.filter(Venue.active.is_(True))
    if q:
        like_q = f"%{q.strip()}%"
        query = query.filter(db.or_(Venue.name.ilike(like_q), Venue.city.ilike(like_q)))
    return [v.to_dict() for v in query.order_by(Venue.id.asc()).all()]


def create_venue(data, created_by=None):
    now = utc_now_iso()
    website = sanitize_url(data.get('website'))
    lat = data.get('latitude')
    lon = data.get('longitude')
    ven = Venue(
        name=(data.get('name') or '').strip(),
        address=(data.get('address') or '').strip(),
        city=(data.get('city') or '').strip(),
        description=(data.get('description') or '').strip(),
        website=website,
        instagram_handle=sanitize_instagram(data.get('instagram_handle')),
        phone=(data.get('phone') or '').strip() or None,
        latitude=float(lat) if lat not in (None, '') else None,
        longitude=float(lon) if lon not in (None, '') else None,
        created_by=created_by,
        owner_user_id=None,
        website_updated_at=now if website else None,
        website_updated_by=created_by if website else None,
        active=True,
        created_at=now,
    )
    db.session.add(ven)
    db.session.commit()
    return ven.to_dict()


def update_venue(venue_id, data, actor_user_id=None):
    ven = db.session.get(Venue, int(venue_id))
    if not ven:
        return None
    old_web = ven.website
    if 'name' in data and data['name']:
        ven.name = data['name'].strip()
    if 'city' in data:
        ven.city = (data['city'] or '').strip()
    if 'address' in data:
        ven.address = (data['address'] or '').strip()
    if 'description' in data:
        ven.description = (data['description'] or '').strip()
    if 'website' in data:
        new_web = sanitize_url(data.get('website'))
        if new_web != old_web:
            ven.website = new_web
            ven.website_updated_at = utc_now_iso()
            ven.website_updated_by = actor_user_id
    if 'instagram_handle' in data:
        ven.instagram_handle = sanitize_instagram(data.get('instagram_handle'))
    if 'phone' in data:
        ven.phone = (data['phone'] or '').strip() or None
    if 'latitude' in data:
        lat = data.get('latitude')
        ven.latitude = float(lat) if lat not in (None, '') else None
    if 'longitude' in data:
        lon = data.get('longitude')
        ven.longitude = float(lon) if lon not in (None, '') else None
    if 'active' in data:
        ven.active = bool(data['active'])
    db.session.commit()
    return ven.to_dict()


def delete_venue_by_id(venue_id):
    ven = db.session.get(Venue, int(venue_id))
    if not ven:
        return False
    db.session.delete(ven)
    db.session.commit()
    return True


def list_venues_within_radius(user_lat, user_lon, radius_km=50.0, only_active=True):
    """Filtra primero mediante caja envolvente indexada en SQL y luego ordena por Haversine exacto."""
    min_lat, max_lat, min_lon, max_lon = bounding_box(user_lat, user_lon, radius_km)
    query = Venue.query.filter(
        Venue.latitude.isnot(None),
        Venue.longitude.isnot(None),
        Venue.latitude.between(min_lat, max_lat),
        Venue.longitude.between(min_lon, max_lon),
    )
    if only_active:
        query = query.filter(Venue.active.is_(True))

    candidates = query.all()
    results = []
    for v in candidates:
        d = haversine(user_lat, user_lon, v.latitude, v.longitude)
        if d <= radius_km:
            vd = v.to_dict()
            vd['distance_km'] = d
            results.append(vd)
    results.sort(key=lambda x: x['distance_km'])
    return results


# ==============================================================================
# 4. TAXONOMÍA Y CERVEZAS
# ==============================================================================

def list_beer_families():
    return [f.to_dict() for f in BeerFamily.query.order_by(BeerFamily.name.asc()).all()]


def create_beer_family(name, description=''):
    fam = BeerFamily(name=name.strip(), description=(description or '').strip())
    db.session.add(fam)
    db.session.commit()
    return fam.to_dict()


def list_beer_styles():
    return [s.to_dict() for s in BeerStyle.query.order_by(BeerStyle.name.asc()).all()]


def get_beer_style(style_id):
    s = db.session.get(BeerStyle, int(style_id)) if style_id else None
    return s.to_dict() if s else None


def create_beer_style(family_id, name, description='', color='#F59E0B'):
    st = BeerStyle(
        family_id=int(family_id),
        name=name.strip(),
        description=(description or '').strip(),
        color=color or '#F59E0B',
    )
    db.session.add(st)
    db.session.commit()
    return st.to_dict()


def list_tags():
    return [t.to_dict() for t in Tag.query.order_by(Tag.name.asc()).all()]


def create_tag(name, icon='🏷️', description=''):
    t = Tag(name=name.strip(), icon=icon or '🏷️', description=description or '')
    db.session.add(t)
    db.session.commit()
    return t.to_dict()


def get_beer(beer_id):
    b = db.session.get(Beer, int(beer_id)) if beer_id else None
    return b.to_dict() if b else None


def list_beers(q=None, only_active=False, fabricante_id=None, style_id=None):
    query = Beer.query
    if only_active:
        query = query.filter(Beer.active.is_(True))
    if fabricante_id is not None:
        query = query.filter(Beer.fabricante_id == int(fabricante_id))
    if style_id is not None:
        query = query.filter(Beer.style_id == int(style_id))
    if q:
        like_q = f"%{q.strip()}%"
        query = query.filter(
            db.or_(Beer.name.ilike(like_q), Beer.brewery.ilike(like_q), Beer.style.ilike(like_q))
        )
    return [b.to_dict() for b in query.order_by(Beer.id.asc()).all()]


def create_beer(data, tag_ids=None, created_by=None):
    brewery_name = (data.get('brewery') or '').strip()
    fab = get_or_create_fabricante(brewery_name, created_by=created_by)
    style_id = int(data['style_id']) if data.get('style_id') else None
    family_id = int(data['family_id']) if data.get('family_id') else None
    style_obj = db.session.get(BeerStyle, style_id) if style_id else None
    if style_obj and not family_id:
        family_id = style_obj.family_id

    # Si el creador ya es el propietario verificado de esa marca, hereda la propiedad automáticamente
    auto_owner = created_by if (fab and fab.owner_user_id and fab.owner_user_id == created_by) else None

    abv_raw = (data.get('abv') or '').strip()
    beer = Beer(
        name=(data.get('name') or '').strip(),
        brewery=fab.name if fab else brewery_name,
        fabricante_id=fab.id if fab else None,
        style=style_obj.name if style_obj else (data.get('style') or ''),
        family_id=family_id,
        style_id=style_id,
        abv=abv_raw,
        abv_num=parse_abv(abv_raw),
        description=(data.get('description') or '').strip(),
        image=data.get('image') or None,
        created_by=created_by,
        owner_user_id=auto_owner,
        verified_at=utc_now_iso() if auto_owner else None,
        active=True,
        created_at=utc_now_iso(),
    )
    db.session.add(beer)
    db.session.flush()

    if tag_ids:
        for tid in {int(t) for t in tag_ids if str(t).isdigit()}:
            db.session.add(BeerTag(beer_id=beer.id, tag_id=tid))

    db.session.commit()
    return beer.to_dict()


def update_beer(beer_id, data, tag_ids=None):
    beer = db.session.get(Beer, int(beer_id))
    if not beer:
        return None

    if 'name' in data and data['name']:
        beer.name = data['name'].strip()
    if 'brewery' in data and data['brewery'] is not None:
        fab = get_or_create_fabricante(data['brewery'], created_by=beer.created_by)
        beer.brewery = fab.name if fab else data['brewery'].strip()
        beer.fabricante_id = fab.id if fab else None
    if 'family_id' in data:
        beer.family_id = int(data['family_id']) if data.get('family_id') else None
    if 'style_id' in data:
        sid = int(data['style_id']) if data.get('style_id') else None
        beer.style_id = sid
        st = db.session.get(BeerStyle, sid) if sid else None
        if st:
            beer.style = st.name
            if not beer.family_id:
                beer.family_id = st.family_id
    if 'abv' in data:
        beer.abv = (data.get('abv') or '').strip()
        beer.abv_num = parse_abv(beer.abv)
    if 'description' in data:
        beer.description = (data.get('description') or '').strip()
    if data.get('image'):
        beer.image = data['image']
    if 'active' in data:
        beer.active = bool(data['active'])

    if tag_ids is not None:
        BeerTag.query.filter_by(beer_id=beer.id).delete()
        for tid in {int(t) for t in tag_ids if str(t).isdigit()}:
            db.session.add(BeerTag(beer_id=beer.id, tag_id=tid))

    db.session.commit()
    return beer.to_dict()


def delete_beer_by_id(beer_id):
    beer = db.session.get(Beer, int(beer_id))
    if not beer:
        return False
    db.session.delete(beer)
    db.session.commit()
    return True


def get_beer_tag_ids(beer_id):
    return [bt.tag_id for bt in BeerTag.query.filter_by(beer_id=int(beer_id)).all()]


def get_beer_tags_map(beer_ids=None):
    """Devuelve {beer_id: [tag_id, ...]} en una sola consulta SQL."""
    query = BeerTag.query
    if beer_ids is not None:
        if not beer_ids:
            return {}
        query = query.filter(BeerTag.beer_id.in_(beer_ids))
    mapping = {}
    for bt in query.all():
        mapping.setdefault(bt.beer_id, []).append(bt.tag_id)
    return mapping


# ==============================================================================
# 5. DISPONIBILIDAD / PIZARRAS DE GRIFOS (NO DESTRUCTIVA)
# ==============================================================================

FRESHNESS_COMMUNITY_DAYS = 14  # Los reportes en bares sin dueño caducan visualmente a los 14 días sin borrarse de BD


def _latest_availabilities_query(venue_id=None, beer_id=None):
    query = Availability.query
    if venue_id is not None:
        query = query.filter(Availability.venue_id == int(venue_id))
    if beer_id is not None:
        query = query.filter(Availability.beer_id == int(beer_id))
    return query.order_by(Availability.last_updated.desc(), Availability.id.desc())


def _is_entry_fresh(last_updated_iso, is_verified_venue):
    """Las pizarras de locales verificados son oficiales y permanecen vigentes hasta que el hostelero cambie el barril.
    En locales huérfanos (crowdsourcing), los reportes antiguos (>14 días) se ignoran en búsquedas activas sin borrar el histórico."""
    if is_verified_venue or not last_updated_iso:
        return True
    try:
        dt = datetime.fromisoformat(last_updated_iso.replace('Z', '+00:00'))
        return (datetime.now(timezone.utc) - dt) <= timedelta(days=FRESHNESS_COMMUNITY_DAYS)
    except ValueError:
        return True


def get_consolidated_availabilities(venue_id=None, beer_id=None, only_available=False):
    """Consolida el último estado conocido por cada par (venue_id, beer_id) sin destruir filas históricas."""
    venues_owner_map = {
        vid: owner_id for vid, owner_id in db.session.query(Venue.id, Venue.owner_user_id).all()
    }
    records = _latest_availabilities_query(venue_id=venue_id, beer_id=beer_id).all()
    seen = set()
    consolidated = []
    for rec in records:
        pair = (rec.venue_id, rec.beer_id)
        if pair in seen:
            continue
        seen.add(pair)
        is_verified_venue = venues_owner_map.get(rec.venue_id) is not None
        if not _is_entry_fresh(rec.last_updated, is_verified_venue):
            continue
        if only_available and rec.status != 'AVAILABLE':
            continue
        d = rec.to_dict()
        d['is_verified_venue'] = is_verified_venue
        consolidated.append(d)
    return consolidated


def get_venue_taplist(venue_id):
    """Lista enriquecida de cervezas del local lista para venue_view y venue_tv."""
    venue = db.session.get(Venue, int(venue_id))
    if not venue:
        return []
    is_verified = venue.owner_user_id is not None
    all_logs = _latest_availabilities_query(venue_id=venue_id).all()

    seen_beers = set()
    latest_per_beer = []
    history_map = {}
    for log in all_logs:
        history_map.setdefault(log.beer_id, []).append(log.to_dict())
        if log.beer_id not in seen_beers:
            seen_beers.add(log.beer_id)
            if _is_entry_fresh(log.last_updated, is_verified):
                latest_per_beer.append(log)

    if not latest_per_beer:
        return []

    beer_ids = [a.beer_id for a in latest_per_beer]
    beers_by_id = {b.id: b.to_dict() for b in Beer.query.filter(Beer.id.in_(beer_ids)).all()}
    styles_by_id = {s.id: s.to_dict() for s in BeerStyle.query.all()}

    taplist = []
    for idx, a in enumerate(latest_per_beer, start=1):
        beer = beers_by_id.get(a.beer_id)
        if not beer or not is_active(beer):
            continue
        style_info = styles_by_id.get(beer.get('style_id'), {})
        item = dict(beer)
        item['availability_id'] = a.id
        item['status'] = a.status
        item['tap_number'] = a.tap_number or idx
        item['price'] = a.price
        item['serving_type'] = a.serving_type or 'DRAFT'
        item['community_soldout_reports'] = a.community_soldout_reports or 0
        item['last_updated'] = a.last_updated
        item['style_color'] = style_info.get('color') or '#F59E0B'
        item['style_name'] = style_info.get('name') or beer.get('style') or 'Artesana'
        item['image_url'] = resolve_media_url('beers', beer.get('image'))
        item['history'] = history_map.get(a.beer_id, [])[:5]
        taplist.append(item)
    return taplist


def set_venue_beer_availability(venue_id, beer_id, user_id, status='AVAILABLE', serving_type='DRAFT', price=None, tap_number=None):
    """Registra un nuevo estado en la pizarra reseteando avisos comunitarios si vuelve a estar AVAILABLE."""
    entry = Availability(
        venue_id=int(venue_id),
        beer_id=int(beer_id),
        user_id=user_id,
        created_by=user_id,
        status=status,
        serving_type=serving_type or 'DRAFT',
        price=float(price) if price not in (None, '') else None,
        tap_number=int(tap_number) if tap_number not in (None, '') else None,
        community_soldout_reports=0,
        soldout_reporters_json='[]',
        last_updated=utc_now_iso(),
    )
    db.session.add(entry)
    db.session.commit()
    return entry.to_dict()


def count_user_venue_updates_today(user_id, venue_id, beer_id):
    today_prefix = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    return Availability.query.filter(
        Availability.user_id == int(user_id),
        Availability.venue_id == int(venue_id),
        Availability.beer_id == int(beer_id),
        Availability.last_updated.like(f"{today_prefix}%"),
    ).count()


def report_community_soldout_on_verified_venue(venue_id, beer_id, reporter_user_id):
    """En bares verificados, los clientes no apagan el grifo directamente: emiten un aviso comunitario único."""
    latest = _latest_availabilities_query(venue_id=venue_id, beer_id=beer_id).first()
    if not latest or latest.status != 'AVAILABLE':
        return False, "Esta cerveza ya no figura como disponible."

    try:
        reporters = json.loads(latest.soldout_reporters_json or '[]')
    except (ValueError, TypeError):
        reporters = []

    if reporter_user_id in reporters:
        return False, "Ya habías enviado un aviso sobre este barril."

    reporters.append(reporter_user_id)
    latest.soldout_reporters_json = json.dumps(reporters)
    latest.community_soldout_reports = len(reporters)
    db.session.commit()
    return True, latest.community_soldout_reports


def nearest_venue_for_beer(beer_id, availabilities, venues_by_id, user_lat, user_lon):
    min_dist = None
    nearest_venue = None
    for a in availabilities:
        if a['beer_id'] != beer_id or a.get('status') != 'AVAILABLE':
            continue
        v = venues_by_id.get(a['venue_id'])
        if not v or v.get('latitude') is None or v.get('longitude') is None:
            continue
        d = haversine(user_lat, user_lon, v['latitude'], v['longitude'])
        if min_dist is None or d < min_dist:
            min_dist = d
            nearest_venue = v
    return min_dist, nearest_venue


# ==============================================================================
# 6. PREFERENCIAS Y RADAR VARIANTE B
# ==============================================================================

VALID_BEER_PREFS = {'DISLIKE', 'WISHLIST', 'LIKE'}


def get_user_beer_preference(user_id, beer_id):
    if not user_id or not beer_id:
        return None
    p = UserBeerPreference.query.filter_by(user_id=int(user_id), beer_id=int(beer_id)).first()
    return p.to_dict() if p else None


def list_user_beer_preferences(user_id):
    if not user_id:
        return []
    rows = (
        UserBeerPreference.query
        .filter_by(user_id=int(user_id))
        .order_by(UserBeerPreference.updated_at.desc())
        .all()
    )
    return [r.to_dict() for r in rows]


def upsert_user_beer_preference(user_id, beer_id, preference, notify_nearby=None):
    """Implementa la Variante B:
    - 'WISHLIST' ('Quiero probarla'): activa automáticamente notify_nearby = True.
    - 'LIKE' ('Me gusta'): mantiene notify_nearby si ya estaba en LIKE, o usa el valor explícito (por defecto False al pasar de WISHLIST a LIKE salvo que el usuario active la campana).
    - 'DISLIKE' ('No es para mí'): fuerza notify_nearby = False.
    """
    if preference not in VALID_BEER_PREFS:
        raise ValueError(f"Preferencia inválida: {preference}")

    now = utc_now_iso()
    rec = UserBeerPreference.query.filter_by(user_id=int(user_id), beer_id=int(beer_id)).first()

    if preference == 'WISHLIST':
        resolved_notify = True
    elif preference == 'DISLIKE':
        resolved_notify = False
    else:  # 'LIKE'
        if notify_nearby is not None:
            resolved_notify = bool(notify_nearby)
        elif rec and rec.preference == 'LIKE':
            resolved_notify = bool(rec.notify_nearby)
        else:
            resolved_notify = False

    if rec:
        rec.preference = preference
        rec.notify_nearby = resolved_notify
        rec.updated_at = now
    else:
        rec = UserBeerPreference(
            user_id=int(user_id),
            beer_id=int(beer_id),
            preference=preference,
            notify_nearby=resolved_notify,
            created_at=now,
            updated_at=now,
        )
        db.session.add(rec)

    db.session.commit()
    return rec.to_dict()


def toggle_user_beer_radar(user_id, beer_id):
    """Conmuta el aviso de cercanía (🔔) para una cerveza que le gusta al usuario, o la añade como WISHLIST."""
    now = utc_now_iso()
    rec = UserBeerPreference.query.filter_by(user_id=int(user_id), beer_id=int(beer_id)).first()
    if not rec:
        rec = UserBeerPreference(
            user_id=int(user_id),
            beer_id=int(beer_id),
            preference='WISHLIST',
            notify_nearby=True,
            created_at=now,
            updated_at=now,
        )
        db.session.add(rec)
    else:
        if rec.preference == 'DISLIKE':
            rec.preference = 'WISHLIST'
            rec.notify_nearby = True
        elif rec.preference == 'WISHLIST':
            # Si desactiva radar estando en "Quiero probarla", la borramos a estado neutro
            db.session.delete(rec)
            db.session.commit()
            return {'preference': None, 'notify_nearby': False}
        else:  # LIKE
            rec.notify_nearby = not bool(rec.notify_nearby)
        rec.updated_at = now

    db.session.commit()
    return rec.to_dict()


def clear_user_beer_preference(user_id, beer_id):
    rec = UserBeerPreference.query.filter_by(user_id=int(user_id), beer_id=int(beer_id)).first()
    if rec:
        db.session.delete(rec)
        db.session.commit()
    return True


def get_user_radar_beer_ids(user_id):
    if not user_id:
        return set()
    rows = UserBeerPreference.query.filter_by(user_id=int(user_id), notify_nearby=True).all()
    return {r.beer_id for r in rows}


def get_radar_matches_for_user(user_id, user_lat=None, user_lon=None, radius_km=None):
    """Ambient Radar: cruza las cervezas con notify_nearby=True del usuario frente a los bares activos
    dentro de su radio (sin requerir bares favoritos). Si no hay ubicación, devuelve coincidencias activas generales."""
    if not user_id:
        return []

    radar_prefs = {
        r.beer_id: r.preference
        for r in UserBeerPreference.query.filter_by(user_id=int(user_id), notify_nearby=True).all()
    }
    if not radar_prefs:
        return []

    if radius_km is None:
        u = db.session.get(User, int(user_id))
        radius_km = (u.max_distance if u and u.max_distance else 20.0)

    if user_lat is not None and user_lon is not None:
        nearby_venues = list_venues_within_radius(user_lat, user_lon, radius_km=radius_km, only_active=True)
    else:
        nearby_venues = list_venues(only_active=True)
        for v in nearby_venues:
            v['distance_km'] = None

    if not nearby_venues:
        return []

    venues_by_id = {v['id']: v for v in nearby_venues}
    avail = get_consolidated_availabilities(only_available=True)

    matched_beers = {
        b.id: b.to_dict()
        for b in Beer.query.filter(Beer.id.in_(radar_prefs.keys()), Beer.active.is_(True)).all()
    }
    styles_by_id = {s.id: s.to_dict() for s in BeerStyle.query.all()}

    hits = []
    seen_pairs = set()
    for a in avail:
        bid = a['beer_id']
        vid = a['venue_id']
        if bid not in matched_beers or vid not in venues_by_id:
            continue
        if (bid, vid) in seen_pairs:
            continue
        seen_pairs.add((bid, vid))

        beer = matched_beers[bid]
        venue = venues_by_id[vid]
        style = styles_by_id.get(beer.get('style_id'), {})
        hits.append({
            'beer_id': bid,
            'beer_name': beer['name'],
            'brewery': beer.get('brewery', ''),
            'style': style.get('name') or beer.get('style') or '',
            'style_color': style.get('color') or '#F59E0B',
            'image_url': resolve_media_url('beers', beer.get('image')),
            'beer_url': url_for('routes.beer_view', id=bid),
            'radar_kind': radar_prefs[bid],  # 'WISHLIST' o 'LIKE'
            'venue_id': vid,
            'venue_name': venue['name'],
            'venue_url': url_for('routes.venue_view', id=vid),
            'distance_km': venue.get('distance_km'),
        })

    hits.sort(key=lambda h: (h['distance_km'] if h['distance_km'] is not None else 999999, h['beer_name']))
    return hits


def count_radar_demand_for_beers(beer_ids):
    """Métrica B2B SaaS: cuántos usuarios distintos tienen estas cervezas activas en su Radar."""
    if not beer_ids:
        return 0
    return (
        db.session.query(db.func.count(db.distinct(UserBeerPreference.user_id)))
        .filter(
            UserBeerPreference.beer_id.in_(beer_ids),
            UserBeerPreference.notify_nearby.is_(True)
        )
        .scalar() or 0
    )


def list_user_palate_preferences(user_id):
    if not user_id:
        return []
    return [p.to_dict() for p in UserPreference.query.filter_by(user_id=int(user_id)).all()]


def replace_user_palate_preferences(user_id, items):
    UserPreference.query.filter_by(user_id=int(user_id)).delete()
    seen = set()
    for item in items:
        ttype = item.get('target_type')
        tid = int(item.get('target_id'))
        pref = item.get('preference')
        if ttype in ('FAMILY', 'STYLE', 'TAG') and pref in ('LIKE', 'DISLIKE') and (ttype, tid) not in seen:
            seen.add((ttype, tid))
            db.session.add(UserPreference(
                user_id=int(user_id),
                target_type=ttype,
                target_id=tid,
                preference=pref,
            ))
    db.session.commit()


# ==============================================================================
# 7. RECLAMACIONES, PROPIEDAD Y AUDITORÍA
# ==============================================================================

def get_entity_model_and_record(entity_type, entity_id):
    mapping = {'beer': Beer, 'venue': Venue, 'brand': Fabricante}
    cls = mapping.get(entity_type)
    if not cls:
        return None, None
    rec = db.session.get(cls, int(entity_id))
    return cls, rec


def get_claim(claim_id):
    c = db.session.get(Claim, int(claim_id)) if claim_id else None
    return c.to_dict() if c else None


def get_claim_orm(claim_id):
    return db.session.get(Claim, int(claim_id)) if claim_id else None


def list_claims(requesting_user_id=None, status=None):
    query = Claim.query
    if requesting_user_id is not None:
        query = query.filter_by(requesting_user_id=int(requesting_user_id))
    if status is not None:
        query = query.filter_by(status=status)
    return [c.to_dict() for c in query.order_by(Claim.created_at.desc(), Claim.id.desc()).all()]


def count_competing_pending_claims(entity_type, entity_id, exclude_claim_id=None, exclude_user_id=None):
    query = Claim.query.filter_by(entity_type=entity_type, entity_id=int(entity_id), status='PENDING')
    if exclude_claim_id is not None:
        query = query.filter(Claim.id != int(exclude_claim_id))
    if exclude_user_id is not None:
        query = query.filter(Claim.requesting_user_id != int(exclude_user_id))
    return query.count()


def approve_claim_atomic(claim_orm, resolved_by_user_id=None, resolution_note=None, auto_approved=False):
    """Asigna la propiedad a la entidad, cierra reclamaciones competidoras y registra auditoría en una sola transacción."""
    _, entity = get_entity_model_and_record(claim_orm.entity_type, claim_orm.entity_id)
    if not entity:
        return False

    now = utc_now_iso()
    entity.owner_user_id = claim_orm.requesting_user_id
    entity.verified_at = now

    claim_orm.status = 'APPROVED'
    claim_orm.resolved_at = now
    claim_orm.resolved_by = resolved_by_user_id
    if resolution_note:
        claim_orm.resolution_note = resolution_note

    # Rechazar otras solicitudes pendientes sobre la misma entidad conservando el motivo real
    others = Claim.query.filter(
        Claim.id != claim_orm.id,
        Claim.entity_type == claim_orm.entity_type,
        Claim.entity_id == claim_orm.entity_id,
        Claim.status == 'PENDING',
    ).all()
    for oc in others:
        oc.status = 'REJECTED'
        oc.resolved_at = now
        oc.resolved_by = resolved_by_user_id
        oc.resolution_note = 'Otra reclamación acreditada fue aprobada para esta entidad.'

    log_audit(
        actor_user_id=resolved_by_user_id or claim_orm.requesting_user_id,
        action='CLAIM_AUTO_APPROVED' if auto_approved else 'CLAIM_APPROVED',
        entity_type=claim_orm.entity_type,
        entity_id=claim_orm.entity_id,
        details=f"Propiedad asignada a user_id={claim_orm.requesting_user_id} (método={claim_orm.verification_method})."
    )
    db.session.commit()
    return True


def reject_claim_atomic(claim_orm, resolved_by_user_id, resolution_note):
    now = utc_now_iso()
    claim_orm.status = 'REJECTED'
    claim_orm.resolved_at = now
    claim_orm.resolved_by = resolved_by_user_id
    claim_orm.resolution_note = resolution_note
    log_audit(
        actor_user_id=resolved_by_user_id,
        action='CLAIM_REJECTED',
        entity_type=claim_orm.entity_type,
        entity_id=claim_orm.entity_id,
        details=resolution_note,
    )
    db.session.commit()
    return True


def revoke_ownership_atomic(entity_type, entity_id, admin_user_id):
    _, entity = get_entity_model_and_record(entity_type, entity_id)
    if not entity:
        return False
    prev_owner = entity.owner_user_id
    entity.owner_user_id = None
    entity.verified_at = None
    log_audit(
        actor_user_id=admin_user_id,
        action='OWNERSHIP_REVOKED',
        entity_type=entity_type,
        entity_id=int(entity_id),
        details=f"Propiedad revocada (propietario previo user_id={prev_owner}).",
    )
    db.session.commit()
    return True

import json
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def parse_abv(raw_abv):
    """Convierte cadenas ABV como '10,5', '8.2%' o 6.4 a float seguro."""
    if raw_abv is None:
        return None
    cleaned = str(raw_abv).strip().replace('%', '').replace(',', '.')
    if not cleaned:
        return None
    try:
        return round(float(cleaned), 2)
    except ValueError:
        return None


class DictLikeMixin:
    """Permite que los modelos de SQLAlchemy se comporten tanto como objetos
    (item.name) como diccionarios (item['name'], item.get('key', default)),
    facilitando la serialización JSON y el uso en plantillas Jinja2."""

    def __getitem__(self, key):
        if not hasattr(self, key):
            raise KeyError(key)
        return getattr(self, key)

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def get(self, key, default=None):
        val = getattr(self, key, None)
        return val if val is not None else default

    def to_dict(self):
        result = {}
        for c in self.__table__.columns:
            val = getattr(self, c.name)
            if isinstance(val, datetime):
                result[c.name] = val.isoformat()
            else:
                result[c.name] = val
        return result


class User(db.Model, DictLikeMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='USER', nullable=False)  # 'USER' | 'ADMIN'
    status = db.Column(db.String(20), default='ACTIVE', nullable=False)  # 'ACTIVE' | 'INACTIVE'
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    email_otp_hash = db.Column(db.String(255), nullable=True)
    email_otp_expires_at = db.Column(db.String(50), nullable=True)
    max_distance = db.Column(db.Float, default=20.0)
    created_at = db.Column(db.String(50), default=utc_now_iso)

    def __repr__(self):
        return f'<User {self.username}>'


class Venue(db.Model, DictLikeMixin):
    __tablename__ = 'venues'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, index=True)
    address = db.Column(db.String(255))
    city = db.Column(db.String(100), index=True)
    description = db.Column(db.Text)
    website = db.Column(db.String(255), nullable=True)
    instagram_handle = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    latitude = db.Column(db.Float, index=True)
    longitude = db.Column(db.Float, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    owner_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    verified_at = db.Column(db.String(50), nullable=True)
    website_updated_at = db.Column(db.String(50), nullable=True)
    website_updated_by = db.Column(db.Integer, nullable=True)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.String(50), default=utc_now_iso)

    def __repr__(self):
        return f'<Venue {self.name}>'


class Fabricante(db.Model, DictLikeMixin):
    __tablename__ = 'fabricantes'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, index=True)
    country = db.Column(db.String(100))
    description = db.Column(db.Text)
    logo = db.Column(db.String(255))
    website = db.Column(db.String(255))
    instagram_handle = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(50))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    owner_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    verified_at = db.Column(db.String(50), nullable=True)
    website_updated_at = db.Column(db.String(50), nullable=True)
    website_updated_by = db.Column(db.Integer, nullable=True)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.String(50), default=utc_now_iso)

    def __repr__(self):
        return f'<Fabricante {self.name}>'


class BeerFamily(db.Model, DictLikeMixin):
    __tablename__ = 'beer_families'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)

    def __repr__(self):
        return f'<BeerFamily {self.name}>'


class BeerStyle(db.Model, DictLikeMixin):
    __tablename__ = 'beer_styles'

    id = db.Column(db.Integer, primary_key=True)
    family_id = db.Column(db.Integer, db.ForeignKey('beer_families.id', ondelete='CASCADE'), nullable=True, index=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)
    color = db.Column(db.String(20), default='#F3E066')

    def __repr__(self):
        return f'<BeerStyle {self.name}>'


class Tag(db.Model, DictLikeMixin):
    __tablename__ = 'tags'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, unique=True)
    description = db.Column(db.Text)
    icon = db.Column(db.String(20), default='🍺')

    def __repr__(self):
        return f'<Tag {self.name}>'


class Beer(db.Model, DictLikeMixin):
    __tablename__ = 'beers'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, index=True)
    brewery = db.Column(db.String(150), index=True)
    fabricante_id = db.Column(db.Integer, db.ForeignKey('fabricantes.id', ondelete='SET NULL'), nullable=True, index=True)
    style = db.Column(db.String(100), index=True)
    family_id = db.Column(db.Integer, db.ForeignKey('beer_families.id', ondelete='SET NULL'), nullable=True)
    style_id = db.Column(db.Integer, db.ForeignKey('beer_styles.id', ondelete='SET NULL'), nullable=True, index=True)
    abv = db.Column(db.String(20))
    abv_num = db.Column(db.Float, nullable=True)
    ibu = db.Column(db.Integer, nullable=True)
    description = db.Column(db.Text)
    image = db.Column(db.String(255))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    owner_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    verified_at = db.Column(db.String(50), nullable=True)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.String(50), default=utc_now_iso)

    def __repr__(self):
        return f'<Beer {self.name}>'


class BeerTag(db.Model, DictLikeMixin):
    __tablename__ = 'beer_tags'

    beer_id = db.Column(db.Integer, db.ForeignKey('beers.id', ondelete='CASCADE'), primary_key=True)
    tag_id = db.Column(db.Integer, db.ForeignKey('tags.id', ondelete='CASCADE'), primary_key=True)


class Availability(db.Model, DictLikeMixin):
    __tablename__ = 'availabilities'

    id = db.Column(db.Integer, primary_key=True)
    venue_id = db.Column(db.Integer, db.ForeignKey('venues.id', ondelete='CASCADE'), nullable=False, index=True)
    beer_id = db.Column(db.Integer, db.ForeignKey('beers.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    owner_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    status = db.Column(db.String(30), default='AVAILABLE', nullable=False)  # 'AVAILABLE' | 'SOLD_OUT'
    tap_number = db.Column(db.Integer, nullable=True)
    price = db.Column(db.Float, nullable=True)
    serving_type = db.Column(db.String(20), default='DRAFT')
    community_soldout_reports = db.Column(db.Integer, default=0, nullable=False)
    soldout_reporters_json = db.Column(db.Text, default='[]')
    last_updated = db.Column(db.String(50), default=utc_now_iso, index=True)


class Claim(db.Model, DictLikeMixin):
    __tablename__ = 'claims'

    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String(30), nullable=False, index=True)  # 'venue' | 'brand' | 'beer'
    entity_id = db.Column(db.Integer, nullable=False, index=True)
    requesting_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    status = db.Column(db.String(20), default='PENDING', nullable=False, index=True)  # 'PENDING' | 'APPROVED' | 'REJECTED'
    is_dispute = db.Column(db.Boolean, default=False, nullable=False)
    verification_method = db.Column(db.String(30), default='MANUAL', nullable=False)  # 'DOMAIN_EMAIL' | 'DNS_META' | 'SOCIAL_TOKEN' | 'DOCUMENT_UPLOAD' | 'MANUAL'
    verification_target = db.Column(db.String(255), nullable=True)
    verification_token = db.Column(db.String(255), nullable=True)
    verification_token_expires_at = db.Column(db.String(50), nullable=True)
    verification_status = db.Column(db.String(30), default='PENDING_PROOF', nullable=False)  # 'PENDING_PROOF' | 'CODE_SENT' | 'PROOF_VERIFIED'
    evidence_file = db.Column(db.String(255), nullable=True)
    justification = db.Column(db.Text)
    evidence_url = db.Column(db.String(255))
    trust_score = db.Column(db.Integer, default=0, nullable=False)
    trust_signals_json = db.Column(db.Text, default='[]')
    resolution_note = db.Column(db.Text)
    created_at = db.Column(db.String(50), default=utc_now_iso)
    resolved_at = db.Column(db.String(50), nullable=True)
    resolved_by = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)

    @property
    def trust_signals(self):
        try:
            return json.loads(self.trust_signals_json or '[]')
        except (ValueError, TypeError):
            return []

    def to_dict(self):
        d = super().to_dict()
        d['trust_signals'] = self.trust_signals
        return d


class UserBeerPreference(db.Model, DictLikeMixin):
    """Variante B del Radar:
    preference: 'DISLIKE' | 'WISHLIST' (Quiero probarla) | 'LIKE' (Me gusta)
    notify_nearby: True siempre que sea 'WISHLIST', y conmutable opcionalmente en 'LIKE'.
    """
    __tablename__ = 'user_beer_preferences'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'beer_id', name='uq_user_beer_pref'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    beer_id = db.Column(db.Integer, db.ForeignKey('beers.id', ondelete='CASCADE'), nullable=False, index=True)
    preference = db.Column(db.String(20), nullable=False)  # 'DISLIKE' | 'WISHLIST' | 'LIKE'
    notify_nearby = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at = db.Column(db.String(50), default=utc_now_iso)
    updated_at = db.Column(db.String(50), default=utc_now_iso)


class UserPreference(db.Model, DictLikeMixin):
    __tablename__ = 'user_preferences'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'target_type', 'target_id', name='uq_user_palate_pref'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    target_type = db.Column(db.String(20), nullable=False)  # 'FAMILY' | 'STYLE' | 'TAG'
    target_id = db.Column(db.Integer, nullable=False)
    preference = db.Column(db.String(20), nullable=False)  # 'LIKE' | 'DISLIKE'


class AuditLog(db.Model, DictLikeMixin):
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    actor_user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    action = db.Column(db.String(60), nullable=False, index=True)
    entity_type = db.Column(db.String(30), nullable=True)
    entity_id = db.Column(db.Integer, nullable=True)
    details = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.String(50), default=utc_now_iso)


class GeocodingCache(db.Model, DictLikeMixin):
    __tablename__ = 'geocoding_cache'

    id = db.Column(db.Integer, primary_key=True)
    query_normalized = db.Column(db.String(255), unique=True, nullable=False, index=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.String(50), default=utc_now_iso)

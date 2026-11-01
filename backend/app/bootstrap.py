import os
from sqlalchemy import Boolean, Float, Integer, inspect, text

from . import auth, data_access
from .models import (
    Beer,
    BeerFamily,
    BeerStyle,
    Tag,
    User,
    UserBeerPreference,
    UserPreference,
    db,
    parse_abv,
)

DEFAULT_FAMILIES = [
    (1, "Lager", "Fermentación baja, limpia y fresca."),
    (2, "Ale", "Fermentación alta, con más cuerpo y complejidad aromática."),
    (3, "Wheat", "Elaboradas con una proporción alta de trigo, turbias y de textura suave."),
    (4, "Sour", "Ácidas y refrescantes, acidificadas de forma controlada."),
    (5, "Belgian", "Tradición belga: especiadas, frutales y a menudo de alta graduación."),
    (6, "Specialty", "Estilos especiales: ahumadas, barleywine o experimentales."),
    (7, "Sin alcohol", "Cervezas con contenido de alcohol mínimo o nulo (0,0%-0,5%)."),
    (8, "Fermentación espontánea", "Fermentadas con levaduras salvajes del ambiente."),
]

DEFAULT_STYLES = [
    (1, "Pilsner", "Fresca y ligera, con un amargor floral y especiado característico del lúpulo noble.", "#F3E066"),
    (1, "Pale Lager", "Ligera y muy bebible, con perfil de malta suave y lúpulo discreto.", "#F5E28C"),
    (1, "Helles", "Centrada en la malta, con notas a pan o galleta, amargor muy bajo y final suave.", "#F8D568"),
    (1, "Kellerbier", "Lager sin filtrar servida directamente de bodega, turbia y con carácter a levadura.", "#E8C24C"),
    (1, "Bock", "Fuerte y robusta, con sabores intensos a malta caramelizada y tostada.", "#8B4A2B"),
    (1, "Doppelbock", "Versión más fuerte y densa de la Bock, con notas a pasas y caramelo oscuro.", "#6B3419"),
    (1, "Märzen", "Cuerpo medio, perfil maltoso y tostado con dulzor inicial y final seco.", "#C87F3B"),
    (1, "Vienna Lager", "Lager ámbar de cuerpo medio con carácter tostado suave y final limpio.", "#C1793F"),
    (1, "Kölsch", "Híbrida de Colonia: dorada, ligera y sutilmente afrutada.", "#F2DE7E"),
    (2, "Pale Ale", "Equilibrio entre malta y lúpulo, con notas frutales, terrosas o florales.", "#E8A33D"),
    (2, "American Pale Ale", "Pale Ale con lúpulos americanos de perfil cítrico y resinoso.", "#E39A3C"),
    (2, "IPA", "Alto amargor y fuerte presencia de aromas a lúpulo cítrico, resinoso o tropical.", "#E0912E"),
    (2, "Session IPA", "Todo el aroma a lúpulo de una IPA con menor graduación y cuerpo ligero.", "#E8B23D"),
    (2, "New England IPA", "IPA turbia, jugosa y sedosa con explosión de lúpulo tropical.", "#F0C24A"),
    (2, "Double IPA", "IPA de mayor graduación e intensidad de lúpulo y malta.", "#D9852B"),
    (2, "Triple IPA", "Versión extrema de la IPA, corpulenta y con carga masiva de lúpulo.", "#C97A28"),
    (2, "West Coast IPA", "IPA seca y muy lupulada, con notas resinosas, cítricas y de pino.", "#DD8A2E"),
    (2, "English IPA", "IPA equilibrada y maltosa con lúpulos nobles terrosos y florales.", "#D28A3A"),
    (2, "Red IPA", "IPA con maltas caramelo que aportan color rojizo y fondo tostado.", "#B4552E"),
    (2, "Black IPA", "El aroma lupulado de una IPA combinado con maltas oscuras tostadas.", "#2B1B12"),
    (2, "Amber Ale", "Dulzor de caramelo de maltas tostadas balanceado con amargor moderado.", "#B5651D"),
    (2, "Red Ale", "Ale rojiza-cobriza con notas a caramelo y amargor equilibrado.", "#A8461E"),
    (2, "Irish Red Ale", "Ale rojiza suave con toque tostado ligero y final seco.", "#9C4A1F"),
    (2, "Brown Ale", "Sabores a nuez, caramelo y chocolate ligero con bajo amargor.", "#6F4423"),
    (2, "English Bitter", "Ale inglesa ligera-media, muy equilibrada y de perfil terroso.", "#C1812E"),
    (2, "Porter", "Notas marcadas a chocolate, caramelo y café tostado con cuerpo medio.", "#3B2418"),
    (2, "Stout", "Cuerpo denso y sabores potentes a café expreso y chocolate amargo.", "#140D0A"),
    (2, "Milk Stout", "Stout sedosa con lactosa y notas dulces a chocolate con leche.", "#241611"),
    (2, "Imperial Stout", "Stout intensa de alta graduación con notas a cacao puro, café y licor.", "#0D0806"),
    (3, "Weissbier", "Trigo alemana sedosa con notas clásicas a plátano y clavo.", "#F6D87A"),
    (3, "Hefeweizen", "Trigo turbia sin filtrar rica en ésteres frutales y fenoles especiados.", "#F3D26E"),
    (3, "Witbier", "Trigo belga elaborada con cilantro y piel de naranja, cítrica y refrescante.", "#F2E4A8"),
    (4, "Berliner Weisse", "Trigo ácida, muy ligera, seca y sumamente refrescante.", "#EFE39A"),
    (4, "Gose", "Ácida con un toque salino y coriandro, muy viva y refrescante.", "#E9DE8C"),
    (4, "Fruit Sour", "Base ácida fermentada o infusionada con fruta natural.", "#D66B7A"),
    (5, "Belgian Blonde", "Belga dorada, suave, ligeramente dulce y especiada.", "#F0CB5C"),
    (5, "Belgian Dubbel", "Belga tostada con notas a fruta madura y caramelo oscuro.", "#7A3E1D"),
    (5, "Belgian Tripel", "Compleja, frutal y especiada, de alta graduación pero final seco.", "#E8C158"),
    (5, "Belgian Quadrupel", "Belga oscura potente, densa y rica en fruta confitada.", "#5C2C12"),
    (5, "Saison", "Ale rústica, muy atenuada, seca y especiada.", "#E4B94E"),
    (5, "Belgian Strong Ale", "Ale belga compleja de alta graduación.", "#C9932E"),
    (6, "Barleywine", "Ale licorosa de guarda, densa y intensamente maltosa.", "#7A3B14"),
    (6, "Smoked Beer", "Elaborada con malta secada al humo de madera.", "#4A3020"),
    (6, "Experimental", "Elaboraciones fuera de estilo clásico con técnicas o ingredientes singulares.", "#8A5A2E"),
    (7, "Sin alcohol", "Cerveza de graduación mínima o nula (0,0%-0,5%).", "#E8C158"),
    (8, "Lambic", "Fermentación espontánea con perfil complejo, ácido y silvestre.", "#D4B33C"),
]

DEFAULT_TAGS = [
    ("Hoppy", "🌿", ""),
    ("Hazy", "🌫️", ""),
    ("Amarga", "🍋", ""),
    ("Dulce", "🍯", ""),
    ("Cítrica", "🍊", ""),
    ("Tropical", "🍍", ""),
    ("Frutal", "🍓", ""),
    ("Tostada", "🔥", ""),
    ("Malteada", "🌾", ""),
    ("Ácida", "🍏", ""),
    ("Suave", "🕊️", ""),
    ("Intensa", "💥", ""),
    ("Sin gluten", "🚫🌾", ""),
    ("Ecológica", "🌱", ""),
    ("Artesanal", "🛠️", ""),
    ("Chocolate", "🍫", ""),
    ("Café", "☕", ""),
    ("Refrescante", "💧", ""),
    ("Seca", "🏜️", ""),
    ("Especiada", "🌶️", ""),
    ("Herbal", "🍃", ""),
    ("Cremosa", "🥛", ""),
    ("Floral", "🌸", ""),
    ("Barrica", "🛢️", "Envejecida o fermentada en barrica de madera."),
]


def _column_sql_definition(col, dialect):
    col_type = col.type.compile(dialect=dialect)
    is_postgres = dialect.name == 'postgresql'
    default_sql = ''
    if not col.nullable and col.default is not None and getattr(col.default, 'is_scalar', False):
        val = col.default.arg
        if isinstance(val, bool):
            lit = ('TRUE' if val else 'FALSE') if is_postgres else ('1' if val else '0')
            default_sql = f' NOT NULL DEFAULT {lit}'
        elif isinstance(val, (int, float)):
            default_sql = f' NOT NULL DEFAULT {val}'
        elif isinstance(val, str):
            safe = val.replace("'", "''")
            default_sql = f" NOT NULL DEFAULT '{safe}'"
    elif not col.nullable:
        if isinstance(col.type, Boolean):
            default_sql = f" NOT NULL DEFAULT {'FALSE' if is_postgres else '0'}"
        elif isinstance(col.type, (Integer, Float)):
            default_sql = ' NOT NULL DEFAULT 0'
        else:
            default_sql = " NOT NULL DEFAULT ''"
    return f'{col.name} {col_type}{default_sql}'


def bootstrap_database(app=None):
    """Inicializa tablas, sincroniza columnas/índices de forma idempotente (SQLite y PostgreSQL),
    siembra la taxonomía BJCP base si está vacía y crea el ADMIN inicial si se define por entorno."""
    if app is None:
        from . import create_app
        app = create_app({'DISABLE_EXTERNAL_GEOCODING': True})

    with app.app_context():
        db.create_all()
        inspector = inspect(db.engine)
        existing_tables = set(inspector.get_table_names())

        for table_name, table_obj in db.metadata.tables.items():
            if table_name not in existing_tables:
                continue
            existing_cols = {c['name'] for c in inspector.get_columns(table_name)}
            for col in table_obj.columns:
                if col.name not in existing_cols:
                    ddl = _column_sql_definition(col, db.engine.dialect)
                    db.session.execute(text(f'ALTER TABLE {table_name} ADD COLUMN {ddl}'))
        db.session.commit()

        # Deduplicación defensiva e índices únicos / espaciales
        seen_ubp = {}
        for row in UserBeerPreference.query.order_by(UserBeerPreference.id.desc()).all():
            key = (row.user_id, row.beer_id)
            if key in seen_ubp:
                db.session.delete(row)
            else:
                if row.preference == 'WISHLIST' and not row.notify_nearby:
                    row.notify_nearby = True
                seen_ubp[key] = row.id

        seen_up = {}
        for row in UserPreference.query.order_by(UserPreference.id.desc()).all():
            key = (row.user_id, row.target_type, row.target_id)
            if key in seen_up:
                db.session.delete(row)
            else:
                seen_up[key] = row.id
        db.session.commit()

        for stmt in (
            'CREATE UNIQUE INDEX IF NOT EXISTS uq_user_beer_pref ON user_beer_preferences (user_id, beer_id)',
            'CREATE UNIQUE INDEX IF NOT EXISTS uq_user_palate_pref ON user_preferences (user_id, target_type, target_id)',
            'CREATE INDEX IF NOT EXISTS ix_venues_lat_lon ON venues (latitude, longitude)',
        ):
            db.session.execute(text(stmt))
        db.session.commit()

        # Semilla base de taxonomía cervecera (solo en despliegues nuevos sin familias/estilos/tags)
        if BeerFamily.query.count() == 0:
            fam_id_map = {}
            for code_id, name, desc in DEFAULT_FAMILIES:
                f = BeerFamily(name=name, description=desc)
                db.session.add(f)
                db.session.flush()
                fam_id_map[code_id] = f.id
            for fam_code, st_name, st_desc, st_color in DEFAULT_STYLES:
                db.session.add(
                    BeerStyle(
                        family_id=fam_id_map.get(fam_code),
                        name=st_name,
                        description=st_desc,
                        color=st_color,
                    )
                )
            db.session.commit()

        if Tag.query.count() == 0:
            for t_name, t_icon, t_desc in DEFAULT_TAGS:
                db.session.add(Tag(name=t_name, icon=t_icon, description=t_desc))
            db.session.commit()

        # Normalización de cuentas y vinculación de fabricantes
        for u in User.query.all():
            if u.role not in ('USER', 'ADMIN'):
                u.role = 'USER'
            if u.role == 'ADMIN' and not u.email_verified:
                u.email_verified = True

        for b in Beer.query.all():
            parsed = parse_abv(b.abv)
            if b.abv_num != parsed:
                b.abv_num = parsed
            if not b.fabricante_id and b.brewery:
                fab = data_access.get_or_create_fabricante(b.brewery, created_by=b.created_by)
                if fab:
                    b.fabricante_id = fab.id
        db.session.commit()

        # Asegurar cuenta ADMIN inicial (local, PythonAnywhere o Cloud Run)
        admin_email = (os.environ.get('ADMIN_EMAIL') or 'admin@example.com').strip().lower()
        admin_password = os.environ.get('ADMIN_PASSWORD') or 'admin123'
        admin_username = (os.environ.get('ADMIN_USERNAME') or 'admin').strip()

        existing_admin = User.query.filter(
            (db.func.lower(User.email) == admin_email) | (db.func.lower(User.username) == admin_username.lower())
        ).first()

        if not existing_admin:
            db.session.add(
                User(
                    username=admin_username,
                    email=admin_email,
                    password=auth.hash_password(admin_password),
                    role='ADMIN',
                    status='ACTIVE',
                    email_verified=True,
                )
            )
            db.session.commit()
            print(f'[Bootstrap] Usuario administrador creado: {admin_username} ({admin_email})')
        else:
            changed = False
            if existing_admin.role != 'ADMIN':
                existing_admin.role = 'ADMIN'
                changed = True
            if existing_admin.status != 'ACTIVE':
                existing_admin.status = 'ACTIVE'
                changed = True
            if not existing_admin.email_verified:
                existing_admin.email_verified = True
                changed = True
            if os.environ.get('ADMIN_PASSWORD'):
                existing_admin.password = auth.hash_password(admin_password)
                changed = True
            if changed:
                db.session.commit()

if __name__ == '__main__':
    bootstrap_database()
    print('BeerMap DB bootstrap OK.')

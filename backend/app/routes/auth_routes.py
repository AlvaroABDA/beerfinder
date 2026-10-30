from flask import current_app, flash, jsonify, redirect, render_template, request, session, url_for

from .. import auth, data_access, security
from ..models import db
from ..services import mailer, verification
from . import bp, entity_display_info


def _issue_account_verification_otp(user_dict):
    """Genera un código OTP de 6 dígitos para verificar el correo de cuenta del usuario."""
    code = verification.generate_otp_code()
    salt = current_app.config['SECRET_KEY']
    otp_hash = verification.hash_otp(code, secret_salt=salt)
    expires_at = verification.otp_expiry_iso(minutes=15)

    data_access.update_user_fields(
        user_dict['id'],
        email_otp_hash=otp_hash,
        email_otp_expires_at=expires_at,
    )

    subject = "Tu código de verificación en BeerMap"
    body = (
        f"Hola {user_dict['username']},\n\n"
        f"Tu código de verificación de cuenta en BeerMap es: {code}\n"
        f"Caduca en 15 minutos.\n\n"
        f"¡Salud!\nEquipo BeerMap"
    )
    ok, channel = mailer.send_transactional_email(user_dict['email'], subject, body)
    return ok, channel, code


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if not security.check_rate_limit('login', limit=12, window_seconds=300):
            flash('Demasiados intentos de acceso. Espera unos minutos antes de reintentar.', 'error')
            return render_template('login.html', title='Iniciar Sesión'), 429

        identifier = (request.form.get('username') or '').strip()
        password = request.form.get('password') or ''

        user = data_access.get_user_by_username(identifier)
        if not user and '@' in identifier:
            user = data_access.get_user_by_email(identifier)

        if not user or not auth.verify_password(user, password):
            flash('Usuario o contraseña incorrectos.', 'error')
            return render_template('login.html', title='Iniciar Sesión')

        if user.get('status') != 'ACTIVE':
            flash('Tu cuenta no se encuentra activa. Contacta con administración.', 'error')
            return render_template('login.html', title='Iniciar Sesión')

        if auth.needs_rehash(user):
            user = data_access.update_user_fields(user['id'], password=auth.hash_password(password))

        auth.login_user(user)
        flash(f"¡Bienvenido de nuevo, {user['username']}!", 'success')
        return redirect(url_for('routes.index'))

    return render_template('login.html', title='Iniciar Sesión')


@bp.route('/logout')
def logout():
    auth.logout_user()
    flash('Has cerrado sesión correctamente.', 'info')
    return redirect(url_for('routes.index'))


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        if not security.check_rate_limit('register', limit=8, window_seconds=600):
            flash('Demasiados registros desde esta conexión. Inténtalo más tarde.', 'error')
            return render_template('register.html', title='Registro'), 429

        username = (request.form.get('username') or '').strip()
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''

        if len(username) < 3:
            flash('El nombre de usuario debe tener al menos 3 caracteres.', 'error')
            return render_template('register.html', title='Registro')
        if '@' not in email or '.' not in email.split('@')[-1]:
            flash('Introduce una dirección de correo válida.', 'error')
            return render_template('register.html', title='Registro')
        if len(password) < 6:
            flash('La contraseña debe tener al menos 6 caracteres.', 'error')
            return render_template('register.html', title='Registro')

        if data_access.get_user_by_username(username):
            flash('Ese nombre de usuario ya está en uso.', 'error')
            return render_template('register.html', title='Registro')
        if data_access.get_user_by_email(email):
            flash('Ya existe una cuenta registrada con ese correo electrónico.', 'error')
            return render_template('register.html', title='Registro')

        # Seguridad: se ignora cualquier parámetro 'role' enviado por cliente; todo registro nace como USER activo.
        new_user = data_access.create_user(
            username=username,
            email=email,
            password_hash=auth.hash_password(password),
            role='USER',
        )
        auth.login_user(new_user)

        ok, channel, code = _issue_account_verification_otp(new_user)
        if ok and channel == 'dev_console':
            flash(
                f"¡Cuenta creada! [Modo desarrollo] Tu código de verificación de email es: {code}",
                'info',
            )
        elif ok:
            flash('¡Cuenta creada! Te hemos enviado un código de 6 dígitos para verificar tu email.', 'success')
        else:
            flash('Cuenta creada. Puedes solicitar la verificación de tu correo desde tu Perfil.', 'info')

        return redirect(url_for('routes.profile'))

    return render_template('register.html', title='Registro')


@bp.route('/verify-email/send', methods=['POST'])
@auth.login_required
def send_email_verification():
    if not security.check_rate_limit('verify_email_send', limit=5, window_seconds=300):
        flash('Espera unos minutos antes de solicitar otro código.', 'error')
        return redirect(url_for('routes.profile'))

    user = auth.current_user()
    if not user:
        return redirect(url_for('routes.login'))
    if user.get('email_verified'):
        flash('Tu correo electrónico ya está verificado.', 'success')
        return redirect(url_for('routes.profile'))

    ok, channel, code = _issue_account_verification_otp(user)
    if ok and channel == 'dev_console':
        flash(f"[Modo desarrollo] Código OTP enviado a {user['email']}: {code}", 'info')
    elif ok:
        flash(f"Hemos enviado un nuevo código de 6 dígitos a {user['email']}.", 'success')
    else:
        flash('No se pudo enviar el correo en este momento. Revisa la configuración de correo.', 'error')
    return redirect(url_for('routes.profile'))


@bp.route('/verify-email/confirm', methods=['POST'])
@auth.login_required
def confirm_email_verification():
    if not security.check_rate_limit('verify_email_confirm', limit=10, window_seconds=300):
        flash('Demasiados intentos fallidos. Solicita un nuevo código en unos minutos.', 'error')
        return redirect(url_for('routes.profile'))

    user = auth.current_user()
    if not user:
        return redirect(url_for('routes.login'))

    submitted = (request.form.get('otp_code') or '').strip()
    is_valid = verification.verify_otp(
        submitted,
        user.get('email_otp_hash'),
        user.get('email_otp_expires_at'),
        secret_salt=current_app.config['SECRET_KEY'],
    )
    if not is_valid:
        flash('El código introducido es incorrecto o ha caducado.', 'error')
        return redirect(url_for('routes.profile'))

    data_access.update_user_fields(
        user['id'],
        email_verified=True,
        email_otp_hash=None,
        email_otp_expires_at=None,
    )
    data_access.log_audit(user['id'], 'USER_EMAIL_VERIFIED', 'user', user['id'], user['email'])
    db.session.commit()
    session['email_verified'] = True
    flash('¡Correo electrónico verificado! Ya puedes reclamar y gestionar marcas o locales.', 'success')
    return redirect(url_for('routes.profile'))


@bp.route('/profile')
@auth.login_required
def profile():
    user = auth.current_user()
    if not user:
        auth.logout_user()
        return redirect(url_for('routes.login'))

    uid = user['id']
    families = data_access.list_beer_families()
    styles = data_access.list_beer_styles()
    tags = data_access.list_tags()

    styles_by_family = {}
    styles_map = {}
    for s in styles:
        styles_map[s['id']] = s['name']
        if s.get('family_id'):
            styles_by_family.setdefault(s['family_id'], []).append(s)

    raw_prefs = data_access.list_user_palate_preferences(uid)
    user_prefs = {'FAMILY': {}, 'STYLE': {}, 'TAG': {}}
    for p in raw_prefs:
        ttype = p['target_type']
        if ttype in user_prefs:
            user_prefs[ttype][p['target_id']] = p['preference']

    # Entidades gestionadas o creadas por el usuario (mientras sigan sin otro propietario)
    all_venues = data_access.list_venues()
    my_venues = []
    for v in all_venues:
        is_owner = v.get('owner_user_id') == uid
        is_creator_unowned = (v.get('owner_user_id') is None and v.get('created_by') == uid)
        if is_owner or is_creator_unowned:
            vc = dict(v)
            vc['is_owner'] = is_owner
            taplist = data_access.get_venue_taplist(v['id'])
            vc['tap_count'] = sum(1 for b in taplist if b.get('status') == 'AVAILABLE')
            my_venues.append(vc)

    all_brands = data_access.list_fabricantes()
    all_beers = data_access.list_beers()
    my_brands = []
    for f in all_brands:
        is_owner = f.get('owner_user_id') == uid
        is_creator_unowned = (f.get('owner_user_id') is None and f.get('created_by') == uid)
        if is_owner or is_creator_unowned:
            fc = dict(f)
            fc['is_owner'] = is_owner
            fc['beer_count'] = sum(
                1 for b in all_beers
                if b.get('fabricante_id') == f['id'] or (b.get('brewery') or '').lower() == f['name'].lower()
            )
            my_brands.append(fc)

    my_beers = []
    for b in all_beers:
        is_owner = b.get('owner_user_id') == uid
        is_creator_unowned = (b.get('owner_user_id') is None and b.get('created_by') == uid)
        if is_owner or is_creator_unowned:
            bc = dict(b)
            bc['is_owner'] = is_owner
            bc['style_name'] = styles_map.get(b.get('style_id'), b.get('style') or '')
            bc['image_url'] = data_access.resolve_media_url('beers', b.get('image'))
            my_beers.append(bc)

    raw_claims = data_access.list_claims(requesting_user_id=uid)
    my_claims = []
    for c in raw_claims:
        ename, eurl, _ = entity_display_info(c['entity_type'], c['entity_id'])
        cc = dict(c)
        cc['entity_name'] = ename
        cc['entity_url'] = eurl
        my_claims.append(cc)

    beer_prefs = data_access.list_user_beer_preferences(uid)
    radar_count = sum(1 for p in beer_prefs if p.get('notify_nearby'))
    likes_count = sum(1 for p in beer_prefs if p.get('preference') == 'LIKE')

    return render_template(
        'profile.html',
        title='Mi Perfil',
        user=user,
        families=families,
        styles_by_family=styles_by_family,
        tags=tags,
        user_prefs=user_prefs,
        my_venues=my_venues,
        my_brands=my_brands,
        my_beers=my_beers,
        my_claims=my_claims,
        radar_count=radar_count,
        likes_count=likes_count,
    )


@bp.route('/api/user/settings', methods=['POST'])
@auth.login_required
def update_settings():
    uid = session.get('user_id')
    payload = request.get_json(silent=True) or {}
    if 'max_distance' in payload:
        try:
            dist = max(1.0, min(100.0, float(payload['max_distance'])))
            data_access.update_user_fields(uid, max_distance=dist)
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid max_distance'}), 400
    return jsonify({'status': 'success'})


@bp.route('/api/user/preferences', methods=['POST'])
@auth.login_required
def update_preference():
    uid = session.get('user_id')
    payload = request.get_json(silent=True)
    if isinstance(payload, list):
        data_access.replace_user_palate_preferences(uid, payload)
        return jsonify({'status': 'success'})
    if isinstance(payload, dict) and {'target_type', 'target_id', 'preference'} <= set(payload.keys()):
        existing = data_access.list_user_palate_preferences(uid)
        filtered = [
            p for p in existing
            if not (p['target_type'] == payload['target_type'] and int(p['target_id']) == int(payload['target_id']))
        ]
        if payload['preference'] in ('LIKE', 'DISLIKE'):
            filtered.append(payload)
        data_access.replace_user_palate_preferences(uid, filtered)
        return jsonify({'status': 'success'})
    return jsonify({'error': 'Invalid payload'}), 400


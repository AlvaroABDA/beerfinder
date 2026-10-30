import json
from flask import abort, current_app, flash, redirect, render_template, request, session, url_for

from .. import auth, data_access, security
from ..models import Claim, db, utc_now_iso
from ..services import mailer, storage, verification
from . import bp, entity_display_info

ALLOWED_METHODS = {'DOMAIN_EMAIL', 'DNS_META', 'SOCIAL_TOKEN', 'DOCUMENT_UPLOAD', 'MANUAL'}


def _redirect_entity(entity_type, entity_id):
    _, url, _ = entity_display_info(entity_type, entity_id)
    return redirect(url)


def _entity_with_fallback_website(entity_type, entity_dict):
    """Si se reclama una cerveza individual sin campo website propio, consulta la web de su marca vinculada."""
    if not entity_dict:
        return entity_dict
    if entity_type == 'beer' and not entity_dict.get('website'):
        fab = None
        if entity_dict.get('fabricante_id'):
            fab = data_access.get_fabricante(entity_dict['fabricante_id'])
        if not fab and entity_dict.get('brewery'):
            fab = data_access.find_fabricante_by_name(entity_dict['brewery'])
        if fab and fab.get('website'):
            enriched = dict(entity_dict)
            enriched['website'] = fab['website']
            enriched['website_updated_at'] = fab.get('website_updated_at')
            enriched['website_updated_by'] = fab.get('website_updated_by')
            return enriched
    return entity_dict


@bp.route('/claim/<entity_type>/<int:entity_id>', methods=['POST'])
@auth.login_required
def claim_entity(entity_type, entity_id):
    if entity_type not in ('venue', 'brand', 'beer'):
        abort(400)

    if not security.check_rate_limit('claim_submit', limit=6, window_seconds=600):
        flash('Has enviado demasiadas solicitudes seguidas. Espera unos minutos.', 'error')
        return _redirect_entity(entity_type, entity_id)

    uid = session.get('user_id')
    requester = data_access.get_user_by_id(uid)
    if not requester:
        return redirect(url_for('routes.login'))

    # Prerrequisito duro SaaS: el solicitante debe tener verificado el correo de su propia cuenta
    if not requester.get('email_verified'):
        flash('Antes de reclamar una marca o establecimiento, verifica tu correo electrónico en Mi Perfil.', 'warning')
        return redirect(url_for('routes.profile'))

    _, entity_orm = data_access.get_entity_model_and_record(entity_type, entity_id)
    if not entity_orm:
        abort(404)
    entity_dict = _entity_with_fallback_website(entity_type, entity_orm.to_dict())

    if entity_dict.get('owner_user_id') == uid:
        flash('Ya eres el propietario verificado de esta entidad.', 'info')
        return _redirect_entity(entity_type, entity_id)

    # Evitar duplicados pendientes del mismo usuario sobre la misma entidad
    existing_pending = Claim.query.filter_by(
        entity_type=entity_type,
        entity_id=entity_id,
        requesting_user_id=uid,
        status='PENDING',
    ).first()
    if existing_pending:
        flash('Ya tienes una solicitud de propiedad en curso para esta entidad.', 'info')
        return redirect(url_for('routes.my_claims'))

    already_owned = entity_dict.get('owner_user_id') is not None
    is_dispute = request.form.get('is_dispute') == '1'
    if already_owned and not is_dispute:
        flash('Esta entidad ya tiene propietario verificado. Si eres el titular legítimo, abre una disputa acreditada.', 'warning')
        return _redirect_entity(entity_type, entity_id)

    method = (request.form.get('verification_method') or 'MANUAL').upper()
    if method not in ALLOWED_METHODS:
        method = 'MANUAL'

    justification = (request.form.get('justification') or '').strip()
    evidence_url = data_access.sanitize_url(request.form.get('evidence_url'))
    v_target = None
    v_token = None
    v_expires = None
    v_status = 'PENDING_PROOF'
    evidence_file = None
    dev_otp_notice = None

    if method == 'DOMAIN_EMAIL':
        corp_email = (
            request.form.get('corporate_email')
            or request.form.get('verification_target')
            or requester.get('email')
            or ''
        ).strip().lower()
        website = entity_dict.get('website')
        if not website:
            flash('Esta ficha aún no tiene sitio web oficial asociado. Añádelo o elige verificación documental/social.', 'error')
            return _redirect_entity(entity_type, entity_id)
        if not verification.is_corporate_email_matching_website(corp_email, website):
            site_dom = verification.extract_registrable_domain(website) or website
            flash(
                f'Para verificación automática por email, la dirección debe pertenecer al dominio oficial (@{site_dom}). '
                f'Si usas Gmail u otro proveedor, selecciona Documento privado o Redes Sociales.',
                'error',
            )
            return _redirect_entity(entity_type, entity_id)

        otp_code = verification.generate_otp_code()
        v_target = corp_email
        v_token = verification.hash_otp(otp_code, secret_salt=current_app.config['SECRET_KEY'])
        v_expires = verification.otp_expiry_iso(minutes=20)
        v_status = 'CODE_SENT'

        ename, _, _ = entity_display_info(entity_type, entity_id)
        ok, channel = mailer.send_transactional_email(
            corp_email,
            f'Código de propiedad para {ename} en BeerMap',
            (
                f'Hola {requester["username"]},\n\n'
                f'Tu código para acreditar la propiedad de "{ename}" en BeerMap es: {otp_code}\n'
                f'Caduca en 20 minutos.\n'
            ),
        )
        if ok and channel == 'dev_console':
            dev_otp_notice = otp_code

    elif method == 'DNS_META':
        website = entity_dict.get('website')
        if not website:
            flash('Esta entidad no tiene una URL oficial configurada para verificar mediante etiqueta <meta>.', 'error')
            return _redirect_entity(entity_type, entity_id)
        v_target = website
        v_token = verification.generate_meta_token()
        v_status = 'CODE_SENT'

    elif method == 'SOCIAL_TOKEN':
        social_ref = (
            request.form.get('social_target')
            or request.form.get('verification_target')
            or entity_dict.get('instagram_handle')
            or evidence_url
            or ''
        ).strip()
        if not social_ref:
            flash('Indica el usuario de Instagram o enlace a la red social oficial del negocio.', 'error')
            return _redirect_entity(entity_type, entity_id)
        v_target = social_ref[:255]
        v_token = verification.generate_social_token()
        v_status = 'CODE_SENT'

    elif method == 'DOCUMENT_UPLOAD':
        uploaded = request.files.get('evidence_file')
        evidence_file = storage.save_private_evidence(uploaded)
        if not evidence_file:
            flash('Adjunta un documento acreditativo válido (PDF, PNG, JPG o WEBP, máx. 5 MB).', 'error')
            return _redirect_entity(entity_type, entity_id)
        v_status = 'PENDING_PROOF'

    else:  # MANUAL
        if not justification:
            flash('Explica brevemente tu vínculo con la marca o establecimiento.', 'error')
            return _redirect_entity(entity_type, entity_id)

    claim = Claim(
        entity_type=entity_type,
        entity_id=entity_id,
        requesting_user_id=uid,
        status='PENDING',
        is_dispute=bool(already_owned),
        verification_method=method,
        verification_target=v_target,
        verification_token=v_token,
        verification_token_expires_at=v_expires,
        verification_status=v_status,
        evidence_file=evidence_file,
        justification=justification or f'Solicitud mediante {method}',
        evidence_url=evidence_url,
        created_at=utc_now_iso(),
    )
    db.session.add(claim)
    db.session.flush()

    competing = data_access.count_competing_pending_claims(
        entity_type, entity_id, exclude_claim_id=claim.id
    )
    score, signals = verification.evaluate_claim_trust(
        claim.to_dict(), entity_dict, requester, competing_pending_count=competing
    )
    claim.trust_score = score
    claim.trust_signals_json = json.dumps(signals)

    data_access.log_audit(
        actor_user_id=uid,
        action='CLAIM_DISPUTE_OPENED' if already_owned else 'CLAIM_SUBMITTED',
        entity_type=entity_type,
        entity_id=entity_id,
        details=f'claim_id={claim.id}, method={method}, trust_score={score}',
    )
    db.session.commit()

    if dev_otp_notice:
        flash(
            f'Solicitud creada. [Modo desarrollo] Código OTP enviado a {v_target}: {dev_otp_notice}',
            'info',
        )
    elif method == 'DOMAIN_EMAIL':
        flash(f'Hemos enviado un código de 6 dígitos a {v_target}. Introdúcelo abajo para completar la verificación.', 'success')
    elif method == 'DNS_META':
        flash('Token técnico generado. Colócalo en tu web oficial y pulsa "Comprobar web ahora".', 'info')
    elif method == 'SOCIAL_TOKEN':
        flash(f'Código social {v_token} generado. Añádelo temporalmente a tu bio o envíanos un DM para validarlo.', 'info')
    else:
        flash('Solicitud de propiedad registrada correctamente y enviada a revisión.', 'success')

    return redirect(url_for('routes.my_claims'))


@bp.route('/claim/<int:claim_id>/verify_otp', methods=['POST'])
@auth.login_required
def verify_claim_otp(claim_id):
    if not security.check_rate_limit('claim_verify_otp', limit=8, window_seconds=300):
        flash('Demasiados intentos de validación. Espera unos minutos.', 'error')
        return redirect(url_for('routes.my_claims'))

    uid = session.get('user_id')
    claim = data_access.get_claim_orm(claim_id)
    if not claim or claim.requesting_user_id != uid:
        abort(404)
    if claim.status != 'PENDING' or claim.verification_method != 'DOMAIN_EMAIL':
        flash('Esta reclamación no admite verificación por código OTP.', 'warning')
        return redirect(url_for('routes.my_claims'))

    submitted = (request.form.get('otp_code') or '').strip()
    is_valid = verification.verify_otp(
        submitted,
        claim.verification_token,
        claim.verification_token_expires_at,
        secret_salt=current_app.config['SECRET_KEY'],
    )
    if not is_valid:
        flash('El código corporativo es incorrecto o ha expirado.', 'error')
        return redirect(url_for('routes.my_claims'))

    _, entity_orm = data_access.get_entity_model_and_record(claim.entity_type, claim.entity_id)
    if not entity_orm:
        abort(404)
    entity_dict = _entity_with_fallback_website(claim.entity_type, entity_orm.to_dict())
    requester = data_access.get_user_by_id(uid)

    claim.verification_status = 'PROOF_VERIFIED'
    claim.verification_token = None
    competing = data_access.count_competing_pending_claims(
        claim.entity_type, claim.entity_id, exclude_claim_id=claim.id
    )
    score, signals = verification.evaluate_claim_trust(
        claim.to_dict(), entity_dict, requester, competing_pending_count=competing
    )
    claim.trust_score = score
    claim.trust_signals_json = json.dumps(signals)

    if verification.can_auto_approve_claim(entity_dict, uid, competing, proof_verified=True):
        data_access.approve_claim_atomic(
            claim,
            resolved_by_user_id=None,
            resolution_note=f'Verificación automática superada mediante correo corporativo ({claim.verification_target}).',
            auto_approved=True,
        )
        flash('¡Propiedad verificada al instante! Ya gestionas oficialmente esta ficha.', 'success')
    else:
        data_access.log_audit(
            uid, 'CLAIM_PROOF_VERIFIED_HOLD', claim.entity_type, claim.entity_id,
            f'claim_id={claim.id} retenida para validación comercial de dominio.'
        )
        db.session.commit()
        flash(
            '¡Dominio corporativo verificado! Al tratarse de un alta reciente o en disputa, un administrador confirmará la titularidad en breve.',
            'info',
        )
    return redirect(url_for('routes.my_claims'))


@bp.route('/claim/<int:claim_id>/verify_web', methods=['POST'])
@auth.login_required
def verify_claim_web(claim_id):
    if not security.check_rate_limit('claim_verify_web', limit=6, window_seconds=300):
        flash('Espera unos minutos antes de volver a comprobar el sitio web.', 'error')
        return redirect(url_for('routes.my_claims'))

    uid = session.get('user_id')
    claim = data_access.get_claim_orm(claim_id)
    if not claim or claim.requesting_user_id != uid:
        abort(404)
    if claim.status != 'PENDING' or claim.verification_method != 'DNS_META':
        flash('Esta reclamación no utiliza verificación técnica web.', 'warning')
        return redirect(url_for('routes.my_claims'))

    _, entity_orm = data_access.get_entity_model_and_record(claim.entity_type, claim.entity_id)
    if not entity_orm:
        abort(404)
    entity_dict = _entity_with_fallback_website(claim.entity_type, entity_orm.to_dict())
    requester = data_access.get_user_by_id(uid)

    ok, detail = verification.verify_website_token(entity_dict.get('website'), claim.verification_token)
    if not ok:
        flash(detail, 'warning')
        return redirect(url_for('routes.my_claims'))

    claim.verification_status = 'PROOF_VERIFIED'
    competing = data_access.count_competing_pending_claims(
        claim.entity_type, claim.entity_id, exclude_claim_id=claim.id
    )
    score, signals = verification.evaluate_claim_trust(
        claim.to_dict(), entity_dict, requester, competing_pending_count=competing
    )
    claim.trust_score = score
    claim.trust_signals_json = json.dumps(signals)

    if verification.can_auto_approve_claim(entity_dict, uid, competing, proof_verified=True):
        data_access.approve_claim_atomic(
            claim,
            resolved_by_user_id=None,
            resolution_note=f'Verificación automática superada ({detail}).',
            auto_approved=True,
        )
        flash('¡Sitio web verificado! Propiedad oficial asignada automáticamente.', 'success')
    else:
        data_access.log_audit(
            uid, 'CLAIM_WEB_VERIFIED_HOLD', claim.entity_type, claim.entity_id,
            f'claim_id={claim.id}: {detail}'
        )
        db.session.commit()
        flash(f'{detail} Queda pendiente únicamente de confirmación final por un administrador.', 'info')

    return redirect(url_for('routes.my_claims'))


@bp.route('/my_claims')
@auth.login_required
def my_claims():
    uid = session.get('user_id')
    raw_claims = data_access.list_claims(requesting_user_id=uid)
    enriched = []
    for c in raw_claims:
        ename, eurl, ent = entity_display_info(c['entity_type'], c['entity_id'])
        ent_web = _entity_with_fallback_website(c['entity_type'], ent) if ent else None
        cc = dict(c)
        cc['entity_name'] = ename
        cc['entity_url'] = eurl
        cc['entity_website'] = (ent_web or {}).get('website')
        enriched.append(cc)
    return render_template('my_claims.html', title='Mis Reclamaciones', claims=enriched)

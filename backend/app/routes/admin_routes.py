import json
from flask import abort, flash, redirect, render_template, request, send_file, session, url_for

from .. import auth, data_access
from ..models import db
from ..services import storage, verification
from . import bp, entity_display_info


@bp.route('/admin')
@auth.admin_required
def admin():
    search_type = (request.args.get('type') or '').strip()
    q = (request.args.get('q') or '').strip()

    users = data_access.list_users(q=q if search_type == 'users' else None)
    venues = data_access.list_venues(q=q if search_type == 'venues' else None)
    beers = data_access.list_beers(q=q if search_type == 'beers' else None)
    fabricantes = data_access.list_fabricantes(q=q if search_type == 'fabricantes' else None)

    all_users_map = {u['id']: u for u in data_access.list_users()}
    raw_claims = data_access.list_claims()
    enriched_claims = []
    dirty_scores = False

    for c in raw_claims:
        ename, eurl, ent = entity_display_info(c['entity_type'], c['entity_id'])
        requester = all_users_map.get(c['requesting_user_id'], {})
        cc = dict(c)
        cc['entity_name'] = ename
        cc['entity_url'] = eurl
        cc['requesting_username'] = requester.get('username', f"Usuario #{c['requesting_user_id']}")
        cc['requesting_email'] = requester.get('email', '')

        # Recalcular señales en vivo para reclamaciones pendientes (por ejemplo si apareció otra disputa)
        if c['status'] == 'PENDING':
            competing = data_access.count_competing_pending_claims(
                c['entity_type'], c['entity_id'], exclude_claim_id=c['id']
            )
            score, signals = verification.evaluate_claim_trust(
                c, ent or {}, requester, competing_pending_count=competing
            )
            cc['trust_score'] = score
            cc['trust_signals'] = signals
            if score != c.get('trust_score') or signals != c.get('trust_signals'):
                orm_claim = data_access.get_claim_orm(c['id'])
                if orm_claim:
                    orm_claim.trust_score = score
                    orm_claim.trust_signals_json = json.dumps(signals)
                    dirty_scores = True
        enriched_claims.append(cc)

    if dirty_scores:
        db.session.commit()

    all_users_full = data_access.list_users()
    all_venues_full = data_access.list_venues()
    all_beers_full = data_access.list_beers()
    all_fabs_full = data_access.list_fabricantes()

    pending_users = [u for u in all_users_full if u.get('status') == 'PENDING']
    metrics = {
        'pending_claims': sum(1 for c in enriched_claims if c['status'] == 'PENDING'),
        'total_claims': sum(1 for c in enriched_claims if c['status'] in ('APPROVED', 'REJECTED')),
        'total_users': len(all_users_full),
        'pending_users': len(pending_users),
        'total_venues': len(all_venues_full),
        'active_venues': sum(1 for v in all_venues_full if data_access.is_active(v)),
        'total_beers': len(all_beers_full),
        'active_beers': sum(1 for b in all_beers_full if data_access.is_active(b)),
        'total_fabricantes': len(all_fabs_full),
    }

    return render_template(
        'admin.html',
        title='Panel de Administración',
        metrics=metrics,
        users=users,
        pending_users=pending_users,
        venues=venues,
        beers=beers,
        fabricantes=fabricantes,
        claims=enriched_claims,
        families=data_access.list_beer_families(),
        styles=data_access.list_beer_styles(),
        tags=data_access.list_tags(),
        search_type=search_type,
    )


@bp.route('/admin/claim/<int:claim_id>/evidence')
@auth.admin_required
def claim_evidence_download(claim_id):
    claim = data_access.get_claim(claim_id)
    if not claim or not claim.get('evidence_file'):
        abort(404)

    ev = claim['evidence_file']
    if ev.startswith('gs://'):
        buf, mimetype = storage.download_gcs_private_evidence(ev)
        if not buf:
            abort(404)
        return send_file(buf, mimetype=mimetype, as_attachment=False, download_name=ev.rsplit('/', 1)[-1])

    if ev.startswith('s3://'):
        parts = ev[5:].split('/', 1)
        client, _ = storage._s3_client()
        if client and len(parts) == 2:
            signed_url = client.generate_presigned_url(
                'get_object',
                Params={'Bucket': parts[0], 'Key': parts[1]},
                ExpiresIn=300,
            )
            return redirect(signed_url)
        abort(404)

    local_path = storage.get_private_evidence_path(ev)
    if not local_path:
        abort(404)
    return send_file(local_path, as_attachment=False)


@bp.route('/admin/claim/<int:claim_id>/<action>', methods=['POST'])
@auth.admin_required
def process_claim(claim_id, action):
    claim_orm = data_access.get_claim_orm(claim_id)
    if not claim_orm:
        abort(404)
    if claim_orm.status != 'PENDING':
        flash('Esta reclamación ya fue resuelta anteriormente.', 'info')
        return redirect(url_for('routes.admin', type='claims'))

    admin_id = session.get('user_id')
    if action == 'approve':
        note = (request.form.get('resolution_note') or '').strip() or 'Propiedad verificada y aprobada por administración.'
        ok = data_access.approve_claim_atomic(
            claim_orm,
            resolved_by_user_id=admin_id,
            resolution_note=note,
            auto_approved=False,
        )
        if ok:
            flash('Propiedad asignada con éxito.', 'success')
        else:
            flash('No se encontró la entidad reclamada.', 'error')
    elif action == 'reject':
        note = (request.form.get('resolution_note') or '').strip()
        if not note:
            flash('Debes indicar el motivo del rechazo.', 'error')
            return redirect(url_for('routes.admin', type='claims'))
        data_access.reject_claim_atomic(claim_orm, resolved_by_user_id=admin_id, resolution_note=note)
        flash('Reclamación rechazada.', 'info')
    else:
        abort(400)

    return redirect(url_for('routes.admin', type='claims'))


@bp.route('/admin/revoke/<entity_type>/<int:entity_id>', methods=['POST'])
@auth.admin_required
def revoke_ownership(entity_type, entity_id):
    if entity_type not in ('venue', 'brand', 'beer'):
        abort(400)
    ok = data_access.revoke_ownership_atomic(entity_type, entity_id, session.get('user_id'))
    if ok:
        flash('Propiedad verificada revocada.', 'info')
    else:
        flash('Entidad no encontrada.', 'error')
    tab_map = {'venue': 'venues', 'brand': 'fabricantes', 'beer': 'beers'}
    return redirect(url_for('routes.admin', type=tab_map.get(entity_type, 'claims')))


@bp.route('/admin/user/<int:user_id>/approve', methods=['POST'])
@auth.admin_required
def approve_user(user_id):
    data_access.update_user_fields(user_id, status='ACTIVE')
    flash('Usuario activado.', 'success')
    return redirect(url_for('routes.admin', type='users'))


@bp.route('/admin/user/<int:id>/edit', methods=['GET', 'POST'])
@auth.admin_required
def edit_user(id):
    user = data_access.get_user_by_id(id)
    if not user:
        abort(404)
    if request.method == 'POST':
        role = request.form.get('role')
        status = request.form.get('status')
        if status not in ('ACTIVE', 'INACTIVE'):
            status = 'ACTIVE'
        data_access.update_user_fields(
            id,
            username=(request.form.get('username') or user['username']).strip(),
            email=(request.form.get('email') or user['email']).strip().lower(),
            role='ADMIN' if role == 'ADMIN' else 'USER',
            status=status,
        )
        flash('Usuario actualizado.', 'success')
        return redirect(url_for('routes.admin', type='users'))
    return render_template('edit_user.html', title='Editar Usuario', user=user)


@bp.route('/admin/user/<int:id>/toggle', methods=['POST'])
@auth.admin_required
def toggle_user(id):
    if id == session.get('user_id'):
        flash('No puedes desactivar tu propia cuenta de administrador.', 'warning')
        return redirect(url_for('routes.admin', type='users'))
    u = data_access.get_user_by_id(id)
    if u:
        new_status = 'INACTIVE' if u.get('status') == 'ACTIVE' else 'ACTIVE'
        data_access.update_user_fields(id, status=new_status)
    return redirect(url_for('routes.admin', type='users'))


@bp.route('/admin/user/<int:id>/delete', methods=['POST'])
@auth.admin_required
def delete_user(id):
    if id == session.get('user_id'):
        flash('No puedes borrar tu propia cuenta activa.', 'warning')
        return redirect(url_for('routes.admin', type='users'))
    data_access.delete_user_by_id(id)
    flash('Usuario eliminado.', 'info')
    return redirect(url_for('routes.admin', type='users'))


@bp.route('/admin/venue/<int:id>/toggle', methods=['POST'])
@auth.admin_required
def toggle_venue(id):
    v = data_access.get_venue(id)
    if v:
        data_access.update_venue(id, {'active': not data_access.is_active(v)}, actor_user_id=session.get('user_id'))
    return redirect(url_for('routes.admin', type='venues'))


@bp.route('/admin/venue/<int:id>/delete', methods=['POST'])
@auth.admin_required
def delete_venue(id):
    data_access.delete_venue_by_id(id)
    flash('Local eliminado.', 'info')
    return redirect(url_for('routes.admin', type='venues'))


@bp.route('/admin/beer/<int:id>/toggle', methods=['POST'])
@auth.admin_required
def toggle_beer(id):
    b = data_access.get_beer(id)
    if b:
        data_access.update_beer(id, {'active': not data_access.is_active(b)})
    return redirect(url_for('routes.admin', type='beers'))


@bp.route('/admin/beer/<int:id>/delete', methods=['POST'])
@auth.admin_required
def delete_beer(id):
    data_access.delete_beer_by_id(id)
    flash('Cerveza eliminada.', 'info')
    return redirect(url_for('routes.admin', type='beers'))


@bp.route('/admin/fabricante/<int:id>/toggle', methods=['POST'])
@auth.admin_required
def toggle_fabricante(id):
    f = data_access.get_fabricante(id)
    if f:
        data_access.update_fabricante(id, {'active': not data_access.is_active(f)}, actor_user_id=session.get('user_id'))
    return redirect(url_for('routes.admin', type='fabricantes'))


@bp.route('/admin/fabricante/<int:id>/delete', methods=['POST'])
@auth.admin_required
def delete_fabricante(id):
    data_access.delete_fabricante_by_id(id)
    flash('Fabricante eliminado.', 'info')
    return redirect(url_for('routes.admin', type='fabricantes'))


@bp.route('/admin/taxonomy/family', methods=['POST'])
@auth.admin_required
def add_family():
    name = (request.form.get('name') or '').strip()
    if name:
        data_access.create_beer_family(name, request.form.get('description') or '')
        flash(f'Familia "{name}" añadida.', 'success')
    return redirect(url_for('routes.admin', type='taxonomy'))


@bp.route('/admin/taxonomy/style', methods=['POST'])
@auth.admin_required
def add_style():
    name = (request.form.get('name') or '').strip()
    fam_id = request.form.get('family_id')
    if name and fam_id:
        data_access.create_beer_style(
            fam_id,
            name,
            request.form.get('description') or '',
            request.form.get('color') or '#F59E0B',
        )
        flash(f'Estilo "{name}" añadido.', 'success')
    return redirect(url_for('routes.admin', type='taxonomy'))


@bp.route('/admin/taxonomy/tag', methods=['POST'])
@auth.admin_required
def add_tag():
    name = (request.form.get('name') or '').strip()
    if name:
        data_access.create_tag(name, request.form.get('icon') or '🏷️')
        flash(f'Tag "{name}" añadido.', 'success')
    return redirect(url_for('routes.admin', type='taxonomy'))


from flask import abort, flash, redirect, render_template, request, session, url_for

from .. import auth, data_access
from ..models import Claim
from . import bp, can_access_b2b_venue, can_edit_entity


@bp.route('/')
def index():
    venues = data_access.list_venues(only_active=True)[:3]
    return render_template('index.html', title='BeerMap', venues=venues)


@bp.route('/beers')
def beers_list():
    beers = data_access.list_beers(only_active=True)
    styles = data_access.list_beer_styles()
    tags = data_access.list_tags()
    return render_template('beers_list.html', title='Explorar Cervezas', beers=beers, styles=styles, tags=tags)


@bp.route('/map')
def map_view():
    uid = session.get('user_id')
    venues = data_access.list_venues(only_active=True)
    avail = data_access.get_consolidated_availabilities(only_available=True)
    radar_ids = data_access.get_user_radar_beer_ids(uid) if uid else set()
    beers_by_id = {b['id']: b['name'] for b in data_access.list_beers(only_active=True)} if radar_ids else {}

    avail_by_venue = {}
    radar_by_venue = {}
    for a in avail:
        vid = a['venue_id']
        bid = a['beer_id']
        avail_by_venue[vid] = avail_by_venue.get(vid, 0) + 1
        if bid in radar_ids and bid in beers_by_id:
            radar_by_venue.setdefault(vid, []).append(beers_by_id[bid])

    enriched_venues = []
    for v in venues:
        vc = dict(v)
        vc['available_count'] = avail_by_venue.get(v['id'], 0)
        vc['radar_beers'] = radar_by_venue.get(v['id'], [])
        enriched_venues.append(vc)

    return render_template('map.html', title='Mapa Cervecero', venues=enriched_venues)


@bp.route('/beer/new', methods=['GET', 'POST'])
@auth.login_required
def beer_new():
    uid = session.get('user_id')
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        brewery = (request.form.get('brewery') or '').strip()
        if not name or not brewery:
            flash('El nombre y el fabricante son obligatorios.', 'error')
            return redirect(url_for('routes.beer_new'))

        img_filename = None
        if 'image' in request.files and request.files['image'].filename:
            img_filename = data_access.save_uploaded_image(request.files['image'], 'beers')
            if not img_filename:
                flash('Formato de imagen no válido (usa PNG, JPG, GIF o WEBP).', 'error')
                return redirect(url_for('routes.beer_new'))

        tag_ids = request.form.getlist('tags')
        beer = data_access.create_beer(
            {
                'name': name,
                'brewery': brewery,
                'family_id': request.form.get('family_id') or None,
                'style_id': request.form.get('style_id') or None,
                'abv': request.form.get('abv') or '',
                'description': request.form.get('description') or '',
                'image': img_filename,
            },
            tag_ids=tag_ids,
            created_by=uid,
        )
        flash(f'Cerveza "{beer["name"]}" añadida al catálogo.', 'success')
        return redirect(url_for('routes.beer_view', id=beer['id']))

    return render_template(
        'beer_form.html',
        title='Añadir Cerveza',
        beer=None,
        fabricantes=data_access.list_fabricantes(only_active=True),
        families=data_access.list_beer_families(),
        styles=data_access.list_beer_styles(),
        tags=data_access.list_tags(),
        beer_tag_ids=[],
    )


@bp.route('/beer/<int:id>')
def beer_view(id):
    beer = data_access.get_beer(id)
    if not beer:
        abort(404)

    uid = session.get('user_id')
    is_admin = session.get('role') == 'ADMIN'
    if not data_access.is_active(beer) and not can_edit_entity(beer, uid, is_admin):
        abort(404)

    families_map = {f['id']: f['name'] for f in data_access.list_beer_families()}
    styles_map = {s['id']: s for s in data_access.list_beer_styles()}
    tags_map = {t['id']: t for t in data_access.list_tags()}

    style_info = styles_map.get(beer.get('style_id'), {})
    beer_enriched = dict(beer)
    beer_enriched['family_name'] = families_map.get(beer.get('family_id'), 'Sin clasificar')
    beer_enriched['style_name'] = style_info.get('name') or beer.get('style') or 'Artesana'
    beer_enriched['style_color'] = style_info.get('color') or '#F59E0B'
    beer_enriched['image_url'] = data_access.resolve_media_url('beers', beer.get('image'))
    beer_enriched['tags_list'] = [
        tags_map[tid] for tid in data_access.get_beer_tag_ids(id) if tid in tags_map
    ]

    linked_fabricante = None
    if beer.get('fabricante_id'):
        linked_fabricante = data_access.get_fabricante(beer['fabricante_id'])
    if not linked_fabricante and beer.get('brewery'):
        linked_fabricante = data_access.find_fabricante_by_name(beer['brewery'])

    user_pref_row = data_access.get_user_beer_preference(uid, id) if uid else None
    user_preference = user_pref_row['preference'] if user_pref_row else None
    notify_nearby = bool(user_pref_row.get('notify_nearby')) if user_pref_row else False

    can_edit = can_edit_entity(beer, uid, is_admin)
    is_brand_or_beer_owner = bool(
        is_admin
        or (uid and beer.get('owner_user_id') == uid)
        or (uid and linked_fabricante and linked_fabricante.get('owner_user_id') == uid)
    )
    radar_demand_count = data_access.count_radar_demand_for_beers([id]) if is_brand_or_beer_owner else 0

    has_pending_claim = False
    if uid:
        has_pending_claim = Claim.query.filter_by(
            entity_type='beer', entity_id=id, requesting_user_id=uid, status='PENDING'
        ).first() is not None

    return render_template(
        'beer_view.html',
        title=beer['name'],
        beer=beer_enriched,
        linked_fabricante=linked_fabricante,
        user_preference=user_preference,
        notify_nearby=notify_nearby,
        can_edit=can_edit,
        is_brand_or_beer_owner=is_brand_or_beer_owner,
        radar_demand_count=radar_demand_count,
        has_pending_claim=has_pending_claim,
    )


@bp.route('/beer/<int:id>/edit', methods=['GET', 'POST'])
@auth.login_required
def edit_beer(id):
    beer = data_access.get_beer(id)
    if not beer:
        abort(404)

    uid = session.get('user_id')
    is_admin = session.get('role') == 'ADMIN'
    if not can_edit_entity(beer, uid, is_admin):
        abort(403)

    if request.method == 'POST':
        img_filename = None
        if 'image' in request.files and request.files['image'].filename:
            img_filename = data_access.save_uploaded_image(request.files['image'], 'beers')
            if not img_filename:
                flash('Formato de imagen no válido.', 'error')
                return redirect(url_for('routes.edit_beer', id=id))

        update_data = {
            'name': request.form.get('name'),
            'brewery': request.form.get('brewery'),
            'family_id': request.form.get('family_id') or None,
            'style_id': request.form.get('style_id') or None,
            'abv': request.form.get('abv') or '',
            'description': request.form.get('description') or '',
        }
        if img_filename:
            update_data['image'] = img_filename

        data_access.update_beer(id, update_data, tag_ids=request.form.getlist('tags'))
        flash('Cerveza actualizada correctamente.', 'success')
        return redirect(url_for('routes.beer_view', id=id))

    return render_template(
        'beer_form.html',
        title=f"Editar {beer['name']}",
        beer=beer,
        fabricantes=data_access.list_fabricantes(),
        families=data_access.list_beer_families(),
        styles=data_access.list_beer_styles(),
        tags=data_access.list_tags(),
        beer_tag_ids=data_access.get_beer_tag_ids(id),
    )


@bp.route('/fabricante/new', methods=['GET', 'POST'])
@auth.login_required
def fabricante_new():
    uid = session.get('user_id')
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        if not name:
            flash('El nombre de la marca es obligatorio.', 'error')
            return redirect(url_for('routes.fabricante_new'))

        existing = data_access.find_fabricante_by_name(name)
        if existing:
            flash(f'La marca "{existing["name"]}" ya está registrada.', 'info')
            return redirect(url_for('routes.fabricante_view', id=existing['id']))

        logo_filename = None
        if 'logo' in request.files and request.files['logo'].filename:
            logo_filename = data_access.save_uploaded_image(request.files['logo'], 'fabricantes')
            if not logo_filename:
                flash('Formato de logotipo no válido.', 'error')
                return redirect(url_for('routes.fabricante_new'))

        fab = data_access.create_fabricante(
            {
                'name': name,
                'country': request.form.get('country') or '',
                'description': request.form.get('description') or '',
                'website': request.form.get('website') or '',
                'instagram_handle': request.form.get('instagram_handle') or '',
                'email': request.form.get('email') or '',
                'phone': request.form.get('phone') or '',
                'logo': logo_filename,
            },
            created_by=uid,
        )
        flash(f'Marca "{fab["name"]}" registrada con éxito.', 'success')
        if request.referrer and '/admin' in request.referrer:
            return redirect(url_for('routes.admin', type='fabricantes'))
        return redirect(url_for('routes.fabricante_view', id=fab['id']))

    return render_template('fabricante_new.html', title='Añadir Marca')


@bp.route('/fabricante/<int:id>')
def fabricante_view(id):
    fab = data_access.get_fabricante(id)
    if not fab:
        abort(404)

    uid = session.get('user_id')
    is_admin = session.get('role') == 'ADMIN'
    if not data_access.is_active(fab) and not can_edit_entity(fab, uid, is_admin):
        abort(404)

    all_beers = data_access.list_beers(only_active=not can_edit_entity(fab, uid, is_admin))
    brand_beers = []
    orphan_beers_count = 0
    for b in all_beers:
        if b.get('fabricante_id') == id or (b.get('brewery') or '').lower() == fab['name'].lower():
            bc = dict(b)
            bc['image_url'] = data_access.resolve_media_url('beers', b.get('image'))
            brand_beers.append(bc)
            if b.get('owner_user_id') is None:
                orphan_beers_count += 1

    is_verified_owner = bool(is_admin or (uid and fab.get('owner_user_id') == uid))
    radar_demand_count = (
        data_access.count_radar_demand_for_beers([b['id'] for b in brand_beers])
        if is_verified_owner and brand_beers else 0
    )

    has_pending_claim = False
    if uid:
        has_pending_claim = Claim.query.filter_by(
            entity_type='brand', entity_id=id, requesting_user_id=uid, status='PENDING'
        ).first() is not None

    return render_template(
        'fabricante_view.html',
        title=fab['name'],
        fabricante=fab,
        beers=brand_beers,
        can_edit=can_edit_entity(fab, uid, is_admin),
        is_verified_owner=is_verified_owner,
        orphan_beers_count=orphan_beers_count,
        radar_demand_count=radar_demand_count,
        has_pending_claim=has_pending_claim,
    )


@bp.route('/fabricante/<int:id>/adopt_beers', methods=['POST'])
@auth.login_required
def adopt_brand_beers(id):
    fab = data_access.get_fabricante(id)
    if not fab:
        abort(404)
    uid = session.get('user_id')
    is_admin = session.get('role') == 'ADMIN'

    target_owner = fab.get('owner_user_id')
    if not target_owner or (int(target_owner) != int(uid) and not is_admin):
        abort(403)

    adopted = data_access.adopt_orphan_beers_for_brand(id, target_owner)
    if adopted > 0:
        flash(f'¡Catálogo sincronizado! Se han vinculado y verificado {adopted} cerveza(s) bajo tu marca.', 'success')
    else:
        flash('Todas las cervezas de esta marca ya estaban vinculadas.', 'info')
    return redirect(url_for('routes.fabricante_view', id=id))


@bp.route('/admin/fabricante/<int:id>/edit', methods=['GET', 'POST'])
@auth.login_required
def edit_fabricante(id):
    fab = data_access.get_fabricante(id)
    if not fab:
        abort(404)

    uid = session.get('user_id')
    is_admin = session.get('role') == 'ADMIN'
    if not can_edit_entity(fab, uid, is_admin):
        abort(403)

    if request.method == 'POST':
        logo_filename = None
        if 'logo' in request.files and request.files['logo'].filename:
            logo_filename = data_access.save_uploaded_image(request.files['logo'], 'fabricantes')
            if not logo_filename:
                flash('Formato de logotipo no válido.', 'error')
                return redirect(url_for('routes.edit_fabricante', id=id))

        payload = {
            'name': request.form.get('name'),
            'country': request.form.get('country') or '',
            'description': request.form.get('description') or '',
            'website': request.form.get('website') or '',
            'instagram_handle': request.form.get('instagram_handle') or '',
            'email': request.form.get('email') or '',
            'phone': request.form.get('phone') or '',
        }
        if logo_filename:
            payload['logo'] = logo_filename

        data_access.update_fabricante(id, payload, actor_user_id=uid)
        flash('Marca actualizada correctamente.', 'success')
        return redirect(url_for('routes.fabricante_view', id=id))

    return render_template('edit_fabricante.html', title=f"Editar {fab['name']}", fabricante=fab)


@bp.route('/venue/new', methods=['GET', 'POST'])
@auth.login_required
def venue_new():
    uid = session.get('user_id')
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        address = (request.form.get('address') or '').strip()
        city = (request.form.get('city') or '').strip()
        if not name or not address or not city:
            flash('Nombre, dirección y ciudad son obligatorios.', 'error')
            return redirect(url_for('routes.venue_new'))

        lat_raw = (request.form.get('latitude') or '').strip().replace(',', '.')
        lon_raw = (request.form.get('longitude') or '').strip().replace(',', '.')
        lat, lon = None, None
        try:
            if lat_raw and lon_raw:
                lat, lon = float(lat_raw), float(lon_raw)
        except ValueError:
            lat, lon = None, None

        if lat is None or lon is None:
            lat, lon = data_access.geocode_address(f"{address}, {city}")

        venue = data_access.create_venue(
            {
                'name': name,
                'address': address,
                'city': city,
                'description': request.form.get('description') or '',
                'website': request.form.get('website') or '',
                'instagram_handle': request.form.get('instagram_handle') or '',
                'phone': request.form.get('phone') or '',
                'latitude': lat,
                'longitude': lon,
            },
            created_by=uid,
        )
        flash(f'Establecimiento "{venue["name"]}" añadido.', 'success')
        if request.referrer and '/admin' in request.referrer:
            return redirect(url_for('routes.admin', type='venues'))
        return redirect(url_for('routes.venue_view', id=venue['id']))

    return render_template('venue_new.html', title='Añadir Bar')


@bp.route('/venue/<int:id>')
def venue_view(id):
    venue = data_access.get_venue(id)
    if not venue:
        abort(404)

    uid = session.get('user_id')
    is_admin = session.get('role') == 'ADMIN'
    if not data_access.is_active(venue) and not can_edit_entity(venue, uid, is_admin):
        abort(404)

    available_beers = data_access.get_venue_taplist(id)
    all_beers = data_access.list_beers(only_active=True)

    is_verified_venue = venue.get('owner_user_id') is not None
    can_b2b = can_access_b2b_venue(venue, uid, is_admin)
    # Si el local está verificado, SOLO el hostelero propietario (o Admin) modifica su pizarra oficial.
    # Si el local es huérfano, cualquier usuario autenticado puede colaborar actualizando la pizarra.
    can_manage_taplist = can_b2b if is_verified_venue else bool(uid)

    radar_ids = data_access.get_user_radar_beer_ids(uid) if uid else set()
    for b in available_beers:
        b['in_user_radar'] = b['id'] in radar_ids

    radar_demand_count = (
        data_access.count_radar_demand_for_beers([b['id'] for b in available_beers])
        if can_b2b and available_beers else 0
    )

    has_pending_claim = False
    if uid:
        has_pending_claim = Claim.query.filter_by(
            entity_type='venue', entity_id=id, requesting_user_id=uid, status='PENDING'
        ).first() is not None

    return render_template(
        'venue_view.html',
        title=venue['name'],
        venue=venue,
        available_beers=available_beers,
        all_beers=all_beers,
        can_edit=can_edit_entity(venue, uid, is_admin),
        can_b2b=can_b2b,
        can_manage_taplist=can_manage_taplist,
        is_verified_venue=is_verified_venue,
        radar_demand_count=radar_demand_count,
        has_pending_claim=has_pending_claim,
    )


@bp.route('/admin/venue/<int:id>/edit', methods=['GET', 'POST'])
@auth.login_required
def edit_venue(id):
    venue = data_access.get_venue(id)
    if not venue:
        abort(404)

    uid = session.get('user_id')
    is_admin = session.get('role') == 'ADMIN'
    if not can_edit_entity(venue, uid, is_admin):
        abort(403)

    if request.method == 'POST':
        address = (request.form.get('address') or '').strip()
        city = (request.form.get('city') or '').strip()
        lat_raw = (request.form.get('latitude') or '').strip().replace(',', '.')
        lon_raw = (request.form.get('longitude') or '').strip().replace(',', '.')

        lat, lon = venue.get('latitude'), venue.get('longitude')
        try:
            if lat_raw and lon_raw:
                lat, lon = float(lat_raw), float(lon_raw)
        except ValueError:
            pass

        if (address != venue.get('address') or city != venue.get('city')) and (
            lat == venue.get('latitude') and lon == venue.get('longitude')
        ):
            g_lat, g_lon = data_access.geocode_address(f"{address}, {city}")
            if g_lat is not None and g_lon is not None:
                lat, lon = g_lat, g_lon

        data_access.update_venue(
            id,
            {
                'name': request.form.get('name'),
                'city': city,
                'address': address,
                'description': request.form.get('description') or '',
                'website': request.form.get('website') or '',
                'instagram_handle': request.form.get('instagram_handle') or '',
                'phone': request.form.get('phone') or '',
                'latitude': lat,
                'longitude': lon,
            },
            actor_user_id=uid,
        )
        flash('Establecimiento actualizado correctamente.', 'success')
        return redirect(url_for('routes.venue_view', id=id))

    return render_template('edit_venue.html', title=f"Editar {venue['name']}", venue=venue)


@bp.route('/venue/<int:id>/tv')
@auth.login_required
def venue_tv(id):
    venue = data_access.get_venue(id)
    if not venue:
        abort(404)
    if not can_access_b2b_venue(venue, session.get('user_id'), session.get('role') == 'ADMIN'):
        abort(403)
    beers = data_access.get_venue_taplist(id)
    return render_template('venue_tv.html', venue=venue, beers=beers)


@bp.route('/venue/<int:id>/qr')
@auth.login_required
def venue_qr_poster(id):
    venue = data_access.get_venue(id)
    if not venue:
        abort(404)
    if not can_access_b2b_venue(venue, session.get('user_id'), session.get('role') == 'ADMIN'):
        abort(403)
    return render_template('venue_qr_poster.html', venue=venue)


@bp.route('/venue/<int:venue_id>/beer/<int:beer_id>/status', methods=['POST'])
@auth.login_required
def update_status(venue_id, beer_id):
    venue = data_access.get_venue(venue_id)
    beer = data_access.get_beer(beer_id)
    if not venue or not beer:
        abort(404)

    uid = session.get('user_id')
    is_admin = session.get('role') == 'ADMIN'

    # Protección B2B: en un local verificado, terceros no pueden apagar ni encender grifos arbitrariamente
    if venue.get('owner_user_id') is not None and not can_access_b2b_venue(venue, uid, is_admin):
        abort(403)

    new_status = (request.form.get('status') or '').upper()
    if new_status not in ('AVAILABLE', 'SOLD_OUT'):
        abort(400)

    if venue.get('owner_user_id') is None and not is_admin:
        if data_access.count_user_venue_updates_today(uid, venue_id, beer_id) >= 2:
            flash('Ya has actualizado el estado de esta cerveza hoy en este local.', 'warning')
            return redirect(url_for('routes.venue_view', id=venue_id))

    data_access.set_venue_beer_availability(venue_id, beer_id, uid, status=new_status)
    flash('Estado de la pizarra actualizado.', 'success')
    return redirect(url_for('routes.venue_view', id=venue_id))


@bp.route('/venue/<int:venue_id>/add_beer', methods=['POST'])
@auth.login_required
def venue_add_beer(venue_id):
    venue = data_access.get_venue(venue_id)
    if not venue:
        abort(404)

    uid = session.get('user_id')
    is_admin = session.get('role') == 'ADMIN'

    if venue.get('owner_user_id') is not None and not can_access_b2b_venue(venue, uid, is_admin):
        abort(403)

    beer_id_raw = request.form.get('beer_id')
    if not beer_id_raw or not str(beer_id_raw).isdigit():
        flash('Selecciona una cerveza válida del catálogo.', 'error')
        return redirect(url_for('routes.venue_view', id=venue_id))

    beer_id = int(beer_id_raw)
    beer = data_access.get_beer(beer_id)
    if not beer:
        abort(404)

    serving_type = (request.form.get('serving_type') or 'DRAFT').upper()
    if serving_type not in ('DRAFT', 'CAN', 'BOTTLE'):
        serving_type = 'DRAFT'
    price = request.form.get('price') or None
    tap_number = request.form.get('tap_number') or None

    data_access.set_venue_beer_availability(
        venue_id=venue_id,
        beer_id=beer_id,
        user_id=uid,
        status='AVAILABLE',
        serving_type=serving_type,
        price=price,
        tap_number=tap_number,
    )
    flash(f'"{beer["name"]}" añadida a la pizarra de {venue["name"]}.', 'success')
    return redirect(url_for('routes.venue_view', id=venue_id))


@bp.route('/venue/<int:venue_id>/beer/<int:beer_id>/report_soldout', methods=['POST'])
@auth.login_required
def report_venue_beer_soldout(venue_id, beer_id):
    venue = data_access.get_venue(venue_id)
    if not venue:
        abort(404)

    uid = session.get('user_id')
    ok, result = data_access.report_community_soldout_on_verified_venue(venue_id, beer_id, uid)
    if ok:
        flash('¡Gracias! Hemos registrado tu aviso para que el local revise este barril.', 'success')
    else:
        flash(str(result), 'info')
    return redirect(url_for('routes.venue_view', id=venue_id))


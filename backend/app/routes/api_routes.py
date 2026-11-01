from flask import jsonify, request, session, url_for

from .. import data_access
from ..services.recommendation import RecommendationEngine
from . import bp, fmt_distance, fmt_walking_time


def _parse_coords():
    lat_str = request.args.get('lat')
    lon_str = request.args.get('lon')
    try:
        lat = float(lat_str) if lat_str and lat_str not in ('null', 'undefined', '') else None
        lon = float(lon_str) if lon_str and lon_str not in ('null', 'undefined', '') else None
        return lat, lon
    except ValueError:
        return None, None


@bp.route('/api/discover')
def api_discover():
    uid = session.get('user_id')
    user_lat, user_lon = _parse_coords()
    has_location = user_lat is not None and user_lon is not None

    max_dist = 20.0
    if uid:
        u = data_access.get_user_by_id(uid)
        if u and u.get('max_distance'):
            max_dist = float(u['max_distance'])

    # 1. Ambient Radar (Variante B): coincidencias silenciosas en tiempo real si el usuario tiene cervezas en radar
    radar_hits = []
    if uid:
        raw_hits = data_access.get_radar_matches_for_user(
            uid, user_lat=user_lat, user_lon=user_lon, radius_km=max_dist
        )
        for h in raw_hits[:6]:
            hc = dict(h)
            hc['distance_str'] = fmt_distance(h.get('distance_km'))
            hc['walking_str'] = fmt_walking_time(h.get('distance_km'))
            radar_hits.append(hc)

    # 2. Feed principal DESCUBRE (afinidad + cercanía, excluyendo cervezas descartadas)
    beers = data_access.list_beers(only_active=True)
    disliked_ids = set()
    if uid:
        for p in data_access.list_user_beer_preferences(uid):
            if p.get('preference') == 'DISLIKE':
                disliked_ids.add(p['beer_id'])

    candidate_beers = [b for b in beers if b['id'] not in disliked_ids]
    taste_scores = RecommendationEngine.score_beers(uid, candidate_beers) if uid else {}

    if has_location:
        avail = data_access.get_consolidated_availabilities(only_available=True)
        nearby_venues = data_access.list_venues_within_radius(user_lat, user_lon, radius_km=max_dist, only_active=True)
        venues_by_id = {v['id']: v for v in nearby_venues}
    else:
        avail = data_access.get_consolidated_availabilities(only_available=True)
        venues_by_id = {v['id']: v for v in data_access.list_venues(only_active=True)}

    styles_by_id = {s['id']: s for s in data_access.list_beer_styles()}
    tags_by_id = {t['id']: t['name'] for t in data_access.list_tags()}
    beer_tags_map = data_access.get_beer_tags_map([b['id'] for b in candidate_beers])

    ranked = []
    for b in candidate_beers:
        t_info = taste_scores.get(b['id'], {'score': 50, 'reason': None})
        t_score = t_info['score']

        nearest_venue = None
        min_dist = None
        if has_location:
            min_dist, nearest_venue = data_access.nearest_venue_for_beer(
                b['id'], avail, venues_by_id, user_lat, user_lon
            )
            if min_dist is not None:
                prox_score = max(0.0, 100.0 - (min(min_dist, max_dist) / max_dist) * 100.0)
                combined = 0.55 * t_score + 0.45 * prox_score
            else:
                combined = t_score * 0.65
        else:
            for a in avail:
                if a['beer_id'] == b['id'] and a['venue_id'] in venues_by_id:
                    nearest_venue = venues_by_id[a['venue_id']]
                    break
            combined = t_score + (10 if nearest_venue else 0)

        ranked.append((combined, b, t_info, min_dist, nearest_venue))

    ranked.sort(key=lambda x: x[0], reverse=True)
    results = []
    for _, b, t_info, min_dist, nearest_venue in ranked[:5]:
        style_obj = styles_by_id.get(b.get('style_id'), {})
        b_tags = [tags_by_id[tid] for tid in beer_tags_map.get(b['id'], []) if tid in tags_by_id]
        results.append({
            'id': b['id'],
            'name': b['name'],
            'brewery': b.get('brewery', ''),
            'style': style_obj.get('name') or b.get('style') or 'Artesana',
            'style_color': style_obj.get('color') or '#F59E0B',
            'abv': b.get('abv', ''),
            'image_url': data_access.resolve_media_url('beers', b.get('image')),
            'view_url': url_for('routes.beer_view', id=b['id']),
            'nearest_venue_name': nearest_venue['name'] if nearest_venue else None,
            'nearest_venue_url': url_for('routes.venue_view', id=nearest_venue['id']) if nearest_venue else None,
            'distance_km': round(min_dist, 2) if min_dist is not None else None,
            'distance_str': fmt_distance(min_dist),
            'walking_str': fmt_walking_time(min_dist),
            'score': t_info['score'],
            'reason': t_info['reason'],
            'tags': b_tags[:3],
        })

    return jsonify({
        'has_location': has_location,
        'radar_hits': radar_hits,
        'results': results,
    })


@bp.route('/api/explore')
def api_explore():
    uid = session.get('user_id')
    q = (request.args.get('q') or '').strip().lower()
    style_q = (request.args.get('style') or '').strip().lower()
    tag_q = (request.args.get('tag') or '').strip().lower()
    user_lat, user_lon = _parse_coords()

    beers = data_access.list_beers(only_active=True)
    styles_by_id = {s['id']: s for s in data_access.list_beer_styles()}
    tags_by_id = {t['id']: t['name'] for t in data_access.list_tags()}
    beer_tags_map = data_access.get_beer_tags_map([b['id'] for b in beers])

    filtered = []
    for b in beers:
        st_name = (styles_by_id.get(b.get('style_id'), {}).get('name') or b.get('style') or '')
        b_tag_names = [tags_by_id[tid] for tid in beer_tags_map.get(b['id'], []) if tid in tags_by_id]

        if q and (
            q not in b['name'].lower()
            and q not in (b.get('brewery') or '').lower()
            and q not in st_name.lower()
        ):
            continue
        if style_q and style_q not in st_name.lower():
            continue
        if tag_q and not any(tag_q in tn.lower() for tn in b_tag_names):
            continue
        filtered.append(b)

    taste_scores = RecommendationEngine.score_beers(uid, filtered) if uid else {}
    avail = data_access.get_consolidated_availabilities(only_available=True)
    venues_by_id = {v['id']: v for v in data_access.list_venues(only_active=True)}

    out = []
    for b in filtered:
        st = styles_by_id.get(b.get('style_id'), {})
        t_info = taste_scores.get(b['id'], {'score': 50, 'reason': None})
        b_tags = [tags_by_id[tid] for tid in beer_tags_map.get(b['id'], []) if tid in tags_by_id]

        min_dist = None
        if user_lat is not None and user_lon is not None:
            min_dist, _ = data_access.nearest_venue_for_beer(b['id'], avail, venues_by_id, user_lat, user_lon)

        out.append({
            'id': b['id'],
            'name': b['name'],
            'brewery': b.get('brewery', ''),
            'style': st.get('name') or b.get('style') or 'Artesana',
            'style_color': st.get('color') or '#F59E0B',
            'abv': b.get('abv', ''),
            'tags': b_tags,
            'image_url': data_access.resolve_media_url('beers', b.get('image')),
            'view_url': url_for('routes.beer_view', id=b['id']),
            'distance': round(min_dist, 2) if min_dist is not None else 9999,
            'distance_str': fmt_distance(min_dist) if min_dist is not None else None,
            'score': t_info['score'],
            'reason': t_info['reason'],
        })

    out.sort(key=lambda item: (item['distance'], -item['score']))
    return jsonify(out)


@bp.route('/api/beer/<int:id>/venues')
def api_beer_venues(id):
    user_lat, user_lon = _parse_coords()
    avail = data_access.get_consolidated_availabilities(beer_id=id, only_available=True)
    venues_by_id = {v['id']: v for v in data_access.list_venues(only_active=True)}

    results = []
    for a in avail:
        v = venues_by_id.get(a['venue_id'])
        if not v:
            continue
        dist = None
        if user_lat is not None and user_lon is not None and v.get('latitude') is not None and v.get('longitude') is not None:
            dist = data_access.haversine(user_lat, user_lon, v['latitude'], v['longitude'])
        results.append({
            'venue_id': v['id'],
            'name': v['name'],
            'city': v.get('city', ''),
            'address': v.get('address', ''),
            'is_verified_venue': bool(v.get('owner_user_id')),
            'serving_type': a.get('serving_type', 'DRAFT'),
            'price': a.get('price'),
            'last_updated': a.get('last_updated'),
            'distance_km': round(dist, 2) if dist is not None else None,
            'distance_str': fmt_distance(dist),
            'walking_str': fmt_walking_time(dist),
        })

    results.sort(key=lambda r: r['distance_km'] if r['distance_km'] is not None else 999999)
    return jsonify(results)


@bp.route('/api/nearby_venues')
def api_nearby_venues():
    uid = session.get('user_id')
    user_lat, user_lon = _parse_coords()
    limit = min(20, max(1, int(request.args.get('limit', 5))))
    if user_lat is None or user_lon is None:
        return jsonify([])

    venues = data_access.list_venues_within_radius(user_lat, user_lon, radius_km=50.0, only_active=True)[:limit]
    avail = data_access.get_consolidated_availabilities(only_available=True)
    radar_ids = data_access.get_user_radar_beer_ids(uid) if uid else set()

    counts = {}
    radar_counts = {}
    for a in avail:
        vid = a['venue_id']
        counts[vid] = counts.get(vid, 0) + 1
        if a['beer_id'] in radar_ids:
            radar_counts[vid] = radar_counts.get(vid, 0) + 1

    out = []
    for v in venues:
        dist = v.get('distance_km')
        out.append({
            'id': v['id'],
            'name': v['name'],
            'address': v.get('address', ''),
            'city': v.get('city', ''),
            'is_verified': bool(v.get('owner_user_id')),
            'available_count': counts.get(v['id'], 0),
            'radar_count': radar_counts.get(v['id'], 0),
            'distance_km': round(dist, 2) if dist is not None else None,
            'distance_str': fmt_distance(dist),
            'walking_str': fmt_walking_time(dist),
            'view_url': url_for('routes.venue_view', id=v['id']),
        })
    return jsonify(out)


@bp.route('/api/map_venues')
def api_map_venues():
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

    out = []
    for v in venues:
        if v.get('latitude') is None or v.get('longitude') is None:
            continue
        out.append({
            'id': v['id'],
            'name': v['name'],
            'address': v.get('address', ''),
            'city': v.get('city', ''),
            'latitude': v['latitude'],
            'longitude': v['longitude'],
            'is_verified': bool(v.get('owner_user_id')),
            'available_count': avail_by_venue.get(v['id'], 0),
            'radar_beers': radar_by_venue.get(v['id'], []),
        })
    return jsonify(out)


@bp.route('/api/venue/<int:id>/taplist')
def api_venue_taplist(id):
    venue = data_access.get_venue(id)
    if not venue or not data_access.is_active(venue):
        return jsonify({'error': 'Not found'}), 404
    return jsonify({
        'venue_id': id,
        'venue_name': venue['name'],
        'beers': data_access.get_venue_taplist(id),
    })


@bp.route('/api/style/<int:id>')
def api_style_info(id):
    style = data_access.get_beer_style(id)
    if not style:
        return jsonify({'error': 'Not found'}), 404
    families = {f['id']: f for f in data_access.list_beer_families()}
    fam = families.get(style.get('family_id'), {})
    examples = data_access.list_beers(only_active=True, style_id=id)[:5]
    return jsonify({
        'id': style['id'],
        'name': style['name'],
        'description': style.get('description', ''),
        'color': style.get('color', '#F59E0B'),
        'family_id': style.get('family_id'),
        'family_name': fam.get('name', 'General'),
        'family_description': fam.get('description', ''),
        'examples': [
            {'id': b['id'], 'name': b['name'], 'brewery': b.get('brewery', ''), 'abv': b.get('abv', '')}
            for b in examples
        ],
    })


@bp.route('/api/styles')
def api_styles_all():
    families = data_access.list_beer_families()
    styles = data_access.list_beer_styles()
    by_fam = {}
    for s in styles:
        by_fam.setdefault(s.get('family_id'), []).append({
            'id': s['id'],
            'name': s['name'],
            'description': s.get('description', ''),
            'color': s.get('color', '#F59E0B'),
        })
    result = []
    for f in families:
        f_styles = by_fam.get(f['id'], [])
        if f_styles:
            result.append({
                'family_id': f['id'],
                'family_name': f['name'],
                'family_description': f.get('description', ''),
                'styles': f_styles,
            })
    return jsonify(result)


@bp.route('/api/check_duplicate')
def check_duplicate():
    q = (request.args.get('q') or '').strip().lower()
    if len(q) < 3:
        return jsonify({'exists': False})

    for b in data_access.list_beers():
        if q == b['name'].lower() or (len(q) >= 4 and q in b['name'].lower()):
            return jsonify({'exists': True, 'type': 'cerveza', 'name': b['name'], 'id': b['id']})
    for v in data_access.list_venues():
        if q == v['name'].lower() or (len(q) >= 4 and q in v['name'].lower()):
            return jsonify({'exists': True, 'type': 'establecimiento', 'name': v['name'], 'id': v['id']})
    for f in data_access.list_fabricantes():
        if q == f['name'].lower() or (len(q) >= 4 and q in f['name'].lower()):
            return jsonify({'exists': True, 'type': 'fabricante', 'name': f['name'], 'id': f['id']})

    return jsonify({'exists': False})


@bp.route('/api/geocode')
def api_geocode():
    q = (request.args.get('q') or '').strip()
    if not q:
        return jsonify({'found': False, 'message': 'Consulta vacía'}), 400
    lat, lon = data_access.geocode_address(q)
    if lat is not None and lon is not None:
        return jsonify({'found': True, 'latitude': lat, 'longitude': lon, 'query': q})
    return jsonify({'found': False, 'message': 'No se encontraron coordenadas'}), 404




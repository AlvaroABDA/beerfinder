from flask import Blueprint, render_template, request, jsonify, session
from app import data_access
from app import auth
from app.services.recommendation import RecommendationEngine

beermatch_bp = Blueprint('beermatch', __name__, url_prefix='/beermatch')

PROXIMITY_MAX_KM = 20.0
WEIGHT_TASTE = 0.6
WEIGHT_PROXIMITY = 0.4


def _format_distance(distance_km):
    if distance_km is None:
        return None
    if distance_km < 1.0:
        return f"{int(round(distance_km * 1000))} m"
    return f"{round(distance_km, 1)} km"


@beermatch_bp.route('/')
@auth.login_required
def swipe_view():
    return render_template('beermatch/swipe.html', title="BeerMatch")


@beermatch_bp.route('/history')
@auth.login_required
def history_view():
    return render_template('beermatch/history.html', title="Mis Cervezas y Radar")


@beermatch_bp.route('/api/beers', methods=['GET'])
@auth.login_required
def get_unrated_beers():
    user_id = session.get('user_id')
    beers = data_access.list_beers(only_active=True)
    user_prefs = data_access.list_user_beer_preferences(user_id)
    all_styles_full = {s['id']: s for s in data_access.list_beer_styles()}
    styles = {sid: s['name'] for sid, s in all_styles_full.items()}

    # Excluir cervezas ya clasificadas (LIKE, DISLIKE o WISHLIST en radar)
    rated_beer_ids = {p['beer_id'] for p in user_prefs}
    unrated_beers = [b for b in beers if b['id'] not in rated_beer_ids]

    q = request.args.get('q', '').strip().lower()
    if q:
        unrated_beers = [
            b for b in unrated_beers
            if q in (b.get('name') or '').lower()
            or q in (b.get('brewery') or '').lower()
            or q in styles.get(b.get('style_id'), '').lower()
        ]

    sample_size = min(10, len(unrated_beers))

    lat_str = request.args.get('lat')
    lon_str = request.args.get('lon')
    try:
        user_lat = float(lat_str) if lat_str and lat_str not in ('null', 'undefined') else None
        user_lon = float(lon_str) if lon_str and lon_str not in ('null', 'undefined') else None
    except ValueError:
        user_lat, user_lon = None, None

    taste = RecommendationEngine.score_beers(user_id, unrated_beers)

    user_max_distance = PROXIMITY_MAX_KM
    user_obj = data_access.get_user_by_id(user_id)
    if user_obj and user_obj.get('max_distance'):
        user_max_distance = float(user_obj['max_distance'])

    if user_lat is not None and user_lon is not None:
        availabilities = data_access.get_consolidated_availabilities(only_available=True)
        venues_by_id = {
            v['id']: v
            for v in data_access.list_venues_within_radius(user_lat, user_lon, radius_km=user_max_distance, only_active=True)
        }
    else:
        availabilities, venues_by_id = [], {}

    scored_beers = []
    for b in unrated_beers:
        taste_score = taste.get(b['id'], {}).get('score', 50)
        if user_lat is not None and user_lon is not None:
            dist, _ = data_access.nearest_venue_for_beer(b['id'], availabilities, venues_by_id, user_lat, user_lon)
            if dist is not None:
                proximity_score = max(0.0, 100.0 - (min(dist, user_max_distance) / user_max_distance) * 100.0)
                combined = WEIGHT_TASTE * taste_score + WEIGHT_PROXIMITY * proximity_score
            else:
                combined = taste_score * 0.85
        else:
            combined = taste_score
        scored_beers.append((combined, b))

    scored_beers.sort(key=lambda x: x[0], reverse=True)
    selected_beers = [b for _, b in scored_beers[:sample_size]]

    tags_by_id = {t['id']: t['name'] for t in data_access.list_tags()}
    beer_tags_map = data_access.get_beer_tags_map([b['id'] for b in selected_beers])

    response_data = []
    for b in selected_beers:
        b_tag_names = [tags_by_id[tid] for tid in beer_tags_map.get(b['id'], []) if tid in tags_by_id]

        distance_km = None
        nearest_venue_name = None
        if user_lat is not None and user_lon is not None:
            distance_km, nearest_venue = data_access.nearest_venue_for_beer(
                b['id'], availabilities, venues_by_id, user_lat, user_lon
            )
            nearest_venue_name = nearest_venue.get('name') if nearest_venue else None

        response_data.append({
            'id': b['id'],
            'name': b['name'],
            'brewery': b.get('brewery', ''),
            'style': styles.get(b.get('style_id'), b.get('style') or 'Artesana'),
            'style_color': all_styles_full.get(b.get('style_id'), {}).get('color'),
            'abv': b.get('abv', ''),
            'image': b.get('image') or '',
            'image_url': data_access.resolve_media_url('beers', b.get('image')),
            'tags': b_tag_names[:4],
            'distance_km': round(distance_km, 1) if distance_km is not None else None,
            'distance_str': _format_distance(distance_km),
            'nearest_venue_name': nearest_venue_name,
            'score': taste.get(b['id'], {}).get('score', 50),
            'reason': taste.get(b['id'], {}).get('reason'),
        })

    return jsonify(response_data)


@beermatch_bp.route('/api/preferences', methods=['POST'])
@auth.login_required
def save_preference():
    """Guarda el estado Variante B ('DISLIKE' | 'WISHLIST' | 'LIKE' | 'CLEAR') y el indicador notify_nearby."""
    user_id = session.get('user_id')
    data = request.get_json(silent=True) or {}

    if 'beer_id' not in data or 'preference' not in data:
        return jsonify({'error': 'Bad Request'}), 400

    beer_id = int(data['beer_id'])
    preference = str(data['preference']).upper()
    notify_nearby = data.get('notify_nearby')

    if preference == 'CLEAR':
        data_access.clear_user_beer_preference(user_id, beer_id)
        return jsonify({'status': 'success', 'preference': None, 'notify_nearby': False})

    if preference not in data_access.VALID_BEER_PREFS:
        return jsonify({'error': 'Invalid preference value'}), 400

    saved = data_access.upsert_user_beer_preference(
        user_id=user_id,
        beer_id=beer_id,
        preference=preference,
        notify_nearby=notify_nearby,
    )
    return jsonify({
        'status': 'success',
        'preference': saved['preference'],
        'notify_nearby': bool(saved['notify_nearby']),
    })


@beermatch_bp.route('/api/radar', methods=['POST'])
@auth.login_required
def toggle_radar():
    """Conmuta el radar de proximidad (🔔) sobre una cerveza (Variante B)."""
    user_id = session.get('user_id')
    data = request.get_json(silent=True) or {}
    if 'beer_id' not in data:
        return jsonify({'error': 'Bad Request'}), 400

    beer_id = int(data['beer_id'])
    res = data_access.toggle_user_beer_radar(user_id, beer_id)
    return jsonify({
        'status': 'success',
        'preference': res.get('preference'),
        'notify_nearby': bool(res.get('notify_nearby')),
    })


@beermatch_bp.route('/api/history', methods=['GET'])
@auth.login_required
def get_history():
    user_id = session.get('user_id')
    user_prefs = data_access.list_user_beer_preferences(user_id)
    beers = {b['id']: b for b in data_access.list_beers()}
    styles = {s['id']: s['name'] for s in data_access.list_beer_styles()}

    q = request.args.get('q', '').strip().lower()

    history_data = []
    for p in user_prefs:
        beer = beers.get(p['beer_id'])
        if not beer:
            continue
        style_name = styles.get(beer.get('style_id'), beer.get('style') or 'Artesana')
        if q and q not in beer['name'].lower() and q not in style_name.lower() and q not in (beer.get('brewery') or '').lower():
            continue

        history_data.append({
            'beer_id': beer['id'],
            'name': beer['name'],
            'brewery': beer.get('brewery', ''),
            'style': style_name,
            'abv': beer.get('abv', ''),
            'image': beer.get('image') or '',
            'image_url': data_access.resolve_media_url('beers', beer.get('image')),
            'preference': p['preference'],
            'notify_nearby': bool(p.get('notify_nearby')),
            'updated_at': p.get('updated_at') or p.get('created_at') or '',
        })

    return jsonify(history_data)


@beermatch_bp.route('/api/recommendations', methods=['GET'])
@auth.login_required
def get_test_recommendations():
    user_id = session.get('user_id')
    beers = data_access.list_beers(only_active=True)
    limit = min(20, max(1, int(request.args.get('limit', 5))))

    recommendations = RecommendationEngine.get_recommendations(user_id, beers, limit)
    styles = {s['id']: s['name'] for s in data_access.list_beer_styles()}
    beers_dict = {b['id']: b for b in beers}

    enriched = []
    for r in recommendations:
        b = beers_dict.get(r['beer_id'])
        if b:
            enriched.append({
                'beer_id': b['id'],
                'name': b['name'],
                'style': styles.get(b.get('style_id'), b.get('style') or 'Artesana'),
                'image_url': data_access.resolve_media_url('beers', b.get('image')),
                'score': r['score'],
                'reason': r['reason'],
            })
    return jsonify(enriched)

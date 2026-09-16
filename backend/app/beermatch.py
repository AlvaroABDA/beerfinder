from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash
from datetime import datetime, timezone
from app import data_access
from app import auth
from app.services.recommendation import RecommendationEngine

beermatch_bp = Blueprint('beermatch', __name__, url_prefix='/beermatch')

@beermatch_bp.route('/')
@auth.login_required
def swipe_view():
    return render_template('beermatch/swipe.html', title="BeerMatch")

@beermatch_bp.route('/history')
@auth.login_required
def history_view():
    return render_template('beermatch/history.html', title="Historial BeerMatch")

# --- API Endpoints ---

PROXIMITY_MAX_KM = 20  # a partir de esta distancia el score de proximidad es 0
WEIGHT_TASTE = 0.6
WEIGHT_PROXIMITY = 0.4


def _format_distance(distance_km):
    """Formatea una distancia en km a texto legible.
    Devuelve metros si < 1 km, km con 1 decimal si >= 1 km, None si no hay dato.
    """
    if distance_km is None:
        return None
    if distance_km < 1.0:
        return f"{int(round(distance_km * 1000))} m"
    return f"{round(distance_km, 1)} km"



def _min_distance_to_beer(beer_id, availabilities, venues_by_id, user_lat, user_lon):
    """Distancia (km) y nombre del local activo más cercano donde la cerveza está disponible.
    Retorna (distance_km, venue_name) o (None, None) si no hay datos.
    """
    min_dist = None
    nearest_venue_name = None
    for a in availabilities:
        if a['beer_id'] != beer_id or a.get('status') != 'AVAILABLE':
            continue
        v = venues_by_id.get(a['venue_id'])
        if not v or not v.get('latitude') or not v.get('longitude'):
            continue
        d = data_access.haversine(user_lat, user_lon, v['latitude'], v['longitude'])
        if min_dist is None or d < min_dist:
            min_dist = d
            nearest_venue_name = v.get('name')
    return min_dist, nearest_venue_name


@beermatch_bp.route('/api/beers', methods=['GET'])
@auth.login_required
def get_unrated_beers():
    user_id = session.get('user_id')
    beers = data_access.load_beers()
    prefs = data_access.load_user_beer_preferences()
    styles = {s['id']: s['name'] for s in data_access.load_beer_styles()}

    # Get IDs of beers the user has already rated
    rated_beer_ids = {p['beer_id'] for p in prefs if p['user_id'] == user_id}

    # Filter out rated beers
    unrated_beers = [b for b in beers if b['id'] not in rated_beer_ids]

    # Search filter
    q = request.args.get('q', '').strip().lower()
    if q:
        unrated_beers = [
            b for b in unrated_beers
            if q in b.get('name', '').lower()
            or q in b.get('brewery', '').lower()
            or q in styles.get(b.get('style_id'), '').lower()
        ]

    sample_size = min(10, len(unrated_beers))

    lat_str = request.args.get('lat')
    lon_str = request.args.get('lon')
    user_lat = float(lat_str) if lat_str else None
    user_lon = float(lon_str) if lon_str else None

    # Afinidad de gustos: obtenemos un ranking amplio para poder mezclarlo con proximidad
    taste_ranked = RecommendationEngine.get_recommendations(user_id, unrated_beers, limit=len(unrated_beers))
    taste_scores = {r['beer_id']: r['score'] for r in taste_ranked}

    if user_lat is not None and user_lon is not None:
        availabilities = data_access.load_availability()
        venues_by_id = {v['id']: v for v in data_access.load_venues() if data_access.is_active(v)}
    else:
        availabilities, venues_by_id = [], {}

    scored_beers = []
    
    user_max_distance = PROXIMITY_MAX_KM
    if user_id:
        users = data_access.load_users()
        user = next((u for u in users if u['id'] == user_id), {})
        user_max_distance = user.get('max_distance', PROXIMITY_MAX_KM)
        
    for b in unrated_beers:
        taste_score = taste_scores.get(b['id'], 50)  # neutral si el motor no la puntuó

        if user_lat is not None and user_lon is not None:
            dist, _ = _min_distance_to_beer(b['id'], availabilities, venues_by_id, user_lat, user_lon)
            if dist is not None:
                if dist > user_max_distance:
                    continue # Excede el radio de búsqueda del usuario, la descartamos
                proximity_score = max(0, 100 - (min(dist, user_max_distance) / user_max_distance) * 100)
                combined = WEIGHT_TASTE * taste_score + WEIGHT_PROXIMITY * proximity_score
            else:
                # No sabemos dónde encontrarla: solo cuenta el gusto
                combined = taste_score
        else:
            combined = taste_score

        scored_beers.append((combined, b))

    scored_beers.sort(key=lambda x: x[0], reverse=True)
    selected_beers = [b for _, b in scored_beers[:sample_size]]

    # Enrich with some extra info for the UI card (descriptores y distancia)
    tags_by_id = {t['id']: t['name'] for t in data_access.load_tags()}
    beer_tags = data_access.load_beer_tags()

    response_data = []
    for b in selected_beers:
        b_tag_names = [tags_by_id[bt['tag_id']] for bt in beer_tags if bt['beer_id'] == b['id'] and bt['tag_id'] in tags_by_id]

        distance_km = None
        nearest_venue_name = None
        if user_lat is not None and user_lon is not None:
            distance_km, nearest_venue_name = _min_distance_to_beer(b['id'], availabilities, venues_by_id, user_lat, user_lon)

        response_data.append({
            'id': b['id'],
            'name': b['name'],
            'brewery': b.get('brewery', ''),
            'style': styles.get(b.get('style_id'), 'Desconocido'),
            'abv': b.get('abv', ''),
            'image': b.get('image', 'default_beer.png'),
            'tags': b_tag_names[:4],
            'distance_km': round(distance_km, 1) if distance_km is not None else None,
            'distance_str': _format_distance(distance_km),
            'nearest_venue_name': nearest_venue_name,
        })

    return jsonify(response_data)


@beermatch_bp.route('/api/preferences', methods=['POST'])
@auth.login_required
def save_preference():
    user_id = session.get('user_id')
    data = request.get_json()
    
    if not data or 'beer_id' not in data or 'preference' not in data:
        return jsonify({'error': 'Bad Request'}), 400
        
    beer_id = int(data['beer_id'])
    preference = data['preference']
    
    if preference not in ['LIKE', 'DISLIKE']:
        return jsonify({'error': 'Invalid preference value'}), 400
        
    prefs = data_access.load_user_beer_preferences()
    now_iso = datetime.now(timezone.utc).isoformat()
    
    # UPSERT Logic
    existing_pref = next((p for p in prefs if p['user_id'] == user_id and p['beer_id'] == beer_id), None)
    
    if existing_pref:
        existing_pref['preference'] = preference
        existing_pref['updated_at'] = now_iso
    else:
        # Determine new ID
        new_id = max([p.get('id', 0) for p in prefs] + [0]) + 1
        prefs.append({
            'id': new_id,
            'user_id': user_id,
            'beer_id': beer_id,
            'preference': preference,
            'created_at': now_iso,
            'updated_at': now_iso
        })
        
    data_access.save_user_beer_preferences(prefs)
    return jsonify({'status': 'success', 'preference': preference})


@beermatch_bp.route('/api/history', methods=['GET'])
@auth.login_required
def get_history():
    user_id = session.get('user_id')
    prefs = data_access.load_user_beer_preferences()
    beers = {b['id']: b for b in data_access.load_beers()}
    styles = {s['id']: s['name'] for s in data_access.load_beer_styles()}
    
    user_prefs = [p for p in prefs if p['user_id'] == user_id]
    
    # Search filter
    q = request.args.get('q', '').strip().lower()
    if q:
        user_prefs = [
            p for p in user_prefs
            if q in beers.get(p['beer_id'], {}).get('name', '').lower()
            or q in styles.get(beers.get(p['beer_id'], {}).get('style_id'), '').lower()
        ]
    
    # Sort by updated_at descending (most recent first)
    user_prefs.sort(key=lambda x: x.get('updated_at', x.get('created_at', '')), reverse=True)
    
    history_data = []
    for p in user_prefs:
        beer = beers.get(p['beer_id'])
        if beer:
            history_data.append({
                'beer_id': beer['id'],
                'name': beer['name'],
                'style': styles.get(beer.get('style_id'), 'Desconocido'),
                'abv': beer.get('abv', ''),
                'image': beer.get('image', 'default_beer.png'),
                'preference': p['preference'],
                'updated_at': p.get('updated_at', p.get('created_at', ''))
            })
            
    return jsonify(history_data)

@beermatch_bp.route('/api/recommendations', methods=['GET'])
@auth.login_required
def get_test_recommendations():
    user_id = session.get('user_id')
    beers = data_access.load_beers()
    
    # We pass all active beers as candidates. The engine filters out already rated ones.
    # In a real app we might pass a limited set of available beers.
    limit = int(request.args.get('limit', 5))
    
    try:
        recommendations = RecommendationEngine.get_recommendations(user_id, beers, limit)
        
        # Enrich the response with beer names/images for the UI if needed
        styles = {s['id']: s['name'] for s in data_access.load_beer_styles()}
        beers_dict = {b['id']: b for b in beers}
        
        enriched = []
        for r in recommendations:
            b = beers_dict.get(r['beer_id'])
            if b:
                enriched.append({
                    'beer_id': b['id'],
                    'name': b['name'],
                    'style': styles.get(b.get('style_id'), 'Desconocido'),
                    'image': b.get('image', 'default_beer.png'),
                    'score': r['score'],
                    'reason': r['reason']
                })
        
        return jsonify(enriched)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

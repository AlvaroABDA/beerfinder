from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, flash
from datetime import datetime, timezone
from app import data_access
from app import auth
import random
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

@beermatch_bp.route('/api/beers', methods=['GET'])
@auth.login_required
def get_unrated_beers():
    user_id = session.get('user_id')
    beers = data_access.load_beers()
    prefs = data_access.load_user_beer_preferences()
    
    # Get IDs of beers the user has already rated
    rated_beer_ids = {p['beer_id'] for p in prefs if p['user_id'] == user_id}
    
    # Filter out rated beers
    unrated_beers = [b for b in beers if b['id'] not in rated_beer_ids]
    
    # Return a random sample of up to 10 beers
    sample_size = min(10, len(unrated_beers))
    selected_beers = random.sample(unrated_beers, sample_size)
    
    # Enrich with some extra info if needed for the UI card
    styles = {s['id']: s['name'] for s in data_access.load_beer_styles()}
    
    response_data = []
    for b in selected_beers:
        response_data.append({
            'id': b['id'],
            'name': b['name'],
            'brewery': b.get('brewery', ''),
            'style': styles.get(b.get('style_id'), 'Desconocido'),
            'abv': b.get('abv', ''),
            'image': b.get('image', 'default_beer.png'),
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

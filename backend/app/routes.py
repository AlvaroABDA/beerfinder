import math
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from . import data_access
from . import auth

bp = Blueprint('routes', __name__)

@bp.route('/')
def index():
    beers = data_access.load_beers()[:3] # Show max 3 for "Descubre"
    venues = [v for v in data_access.load_venues() if v.get('active', True)][:2] # Show max 2 for "Cerca de ti"
    return render_template('index.html', title="BeerMap MVP", beers=beers, venues=venues)

@bp.route('/search')
def search():
    query = request.args.get('q', '').lower()
    beers = data_access.load_beers()
    results = []
    if query:
        results = [b for b in beers if query in b['name'].lower() or query in b['style'].lower() or query in b['brewery'].lower()]
    return render_template('search_results.html', query=query, results=results)

@bp.route('/beers')
def beers_list():
    tags = data_access.load_tags()
    styles = data_access.load_beer_styles()
    beers = data_access.load_beers()
    return render_template('beers_list.html', tags=tags, styles=styles, beers=beers)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        users = data_access.load_users()
        user = next((u for u in users if u['username'] == username and u['password'] == password), None)
        if user:
            if user['status'] != 'ACTIVE':
                flash('Account pending approval.', 'warning')
            else:
                auth.login_user(user)
                return redirect(url_for('routes.index'))
        else:
            flash('Invalid credentials.', 'danger')
    return render_template('login.html')

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')
        role = request.form.get('role')
        
        users = data_access.load_users()
        if any(u['username'] == username for u in users):
            flash('Username already taken.', 'danger')
            return redirect(url_for('routes.register'))
        
        new_id = max([u['id'] for u in users] + [0]) + 1
        status = 'ACTIVE' if role == 'USER' else 'PENDING'
        
        new_user = {
            'id': new_id,
            'username': username,
            'password': password,
            'email': email,
            'role': role,
            'status': status
        }
        users.append(new_user)
        data_access.save_users(users)
        flash('Registration successful!', 'success')
        return redirect(url_for('routes.login'))
    return render_template('register.html')

@bp.route('/logout')
def logout():
    auth.logout_user()
    return redirect(url_for('routes.index'))

@bp.route('/admin')
@auth.admin_required
def admin():
    users = data_access.load_users()
    venues = data_access.load_venues()
    beers = data_access.load_beers()
    fabricantes = data_access.load_fabricantes()
    pending_users = [u for u in users if u['status'] == 'PENDING']
    
    # Simple server‑side search scoped to specific tab
    search_type = request.args.get('type')
    q = request.args.get('q', '').lower()
    
    if q and search_type:
        if search_type == 'users':
            users = [u for u in users if q in u.get('username','').lower() or q in u.get('email','').lower()]
        elif search_type == 'venues':
            venues = [v for v in venues if q in v.get('name','').lower() or q in v.get('city','').lower()]
        elif search_type == 'beers':
            beers = [b for b in beers if q in b.get('name','').lower() or q in b.get('style','').lower() or q in b.get('brewery','').lower()]
        elif search_type == 'fabricantes':
            fabricantes = [f for f in fabricantes if f.get('name','').lower() or q in f.get('country','').lower()]
    
    families = data_access.load_beer_families()
    styles = data_access.load_beer_styles()
    tags = data_access.load_tags()
    
    return render_template('admin.html', users=users, venues=venues, beers=beers, fabricantes=fabricantes, families=families, styles=styles, tags=tags, pending_users=pending_users, search_type=search_type)

@bp.route('/admin/approve/<int:user_id>', methods=['POST'])
@auth.admin_required
def approve_user(user_id):
    users = data_access.load_users()
    for user in users:
        if user['id'] == user_id:
            user['status'] = 'ACTIVE'
            break
    data_access.save_users(users)
    return redirect(url_for('routes.admin', type='users'))

@bp.route('/venue/new', methods=['POST'])
@auth.admin_required
def venue_new():
    venues = data_access.load_venues()
    new_id = max([v.get('id', 0) for v in venues] + [0]) + 1
    
    address = request.form.get('address')
    lat = request.form.get('latitude')
    lon = request.form.get('longitude')
    
    if (not lat or not lon) and address:
        geocoded_lat, geocoded_lon = data_access.geocode_address(address)
        if geocoded_lat is not None and geocoded_lon is not None:
            lat = geocoded_lat
            lon = geocoded_lon
    
    new_venue = {
        'id': new_id,
        'name': request.form.get('name'),
        'address': address,
        'city': request.form.get('city'),
        'description': request.form.get('description'),
        'latitude': float(lat) if lat else None,
        'longitude': float(lon) if lon else None
    }
    venues.append(new_venue)
    data_access.save_venues(venues)
    flash(f"Establecimiento '{new_venue['name']}' añadido.", "success")
    return redirect(url_for('routes.admin', type='venues'))

@bp.route('/fabricante/new', methods=['POST'])
@auth.admin_required
def fabricante_new():
    fabricantes = data_access.load_fabricantes()
    new_id = max([f.get('id', 0) for f in fabricantes] + [0]) + 1
    
    logo_filename = ""
    if 'logo' in request.files:
        file = request.files['logo']
        if file.filename != '':
            filename = secure_filename(file.filename)
            upload_folder = os.path.join(os.path.dirname(__file__), 'static', 'images', 'fabricantes')
            os.makedirs(upload_folder, exist_ok=True)
            file.save(os.path.join(upload_folder, filename))
            logo_filename = filename
            
    new_fabricante = {
        'id': new_id,
        'name': request.form.get('name'),
        'country': request.form.get('country'),
        'description': request.form.get('description'),
        'website': request.form.get('website'),
        'logo': logo_filename
    }
    
    fabricantes.append(new_fabricante)
    data_access.save_fabricantes(fabricantes)
    flash(f"Fabricante '{new_fabricante['name']}' añadido.", "success")
    return redirect(url_for('routes.admin', type='fabricantes'))

import os
from werkzeug.utils import secure_filename

@bp.route('/beer/new', methods=['GET', 'POST'])
@auth.login_required
def beer_new():
    fabricantes = data_access.load_fabricantes()
    families = data_access.load_beer_families()
    styles = data_access.load_beer_styles()
    tags = data_access.load_tags()
    
    if request.method == 'POST':
        beers = data_access.load_beers()
        new_id = max([b.get('id', 0) for b in beers] + [0]) + 1
        
        image_filename = ""
        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '':
                filename = secure_filename(file.filename)
                upload_folder = os.path.join(os.path.dirname(__file__), 'static', 'images', 'beers')
                os.makedirs(upload_folder, exist_ok=True)
                file.save(os.path.join(upload_folder, filename))
                image_filename = filename
                
        family_id = request.form.get('family_id')
        style_id = request.form.get('style_id')
        
        new_beer = {
            'id': new_id,
            'name': request.form.get('name'),
            'family_id': int(family_id) if family_id else None,
            'style_id': int(style_id) if style_id else None,
            'brewery': request.form.get('brewery'),
            'abv': request.form.get('abv'),
            'description': request.form.get('description'),
            'image': image_filename
        }
        beers.append(new_beer)
        data_access.save_beers(beers)
        
        selected_tags = request.form.getlist('tags')
        if selected_tags:
            beer_tags = data_access.load_beer_tags()
            for t_id in selected_tags:
                beer_tags.append({'beer_id': new_id, 'tag_id': int(t_id)})
            data_access.save_beer_tags(beer_tags)
            
        flash("Cerveza añadida correctamente.", "success")
        return redirect(url_for('routes.admin', type='beers'))
        
    return render_template('beer_form.html', fabricantes=fabricantes, families=families, styles=styles, tags=tags)

@bp.route('/beer/<int:id>')
def beer_view(id):
    beers = data_access.load_beers()
    beer = next((b for b in beers if b['id'] == id), None)
    if not beer:
        flash("Cerveza no encontrada.", "error")
        return redirect(url_for('routes.index'))
        
    if beer.get('family_id'):
        fams = data_access.load_beer_families()
        beer['family_name'] = next((f['name'] for f in fams if f['id'] == beer['family_id']), '')
    if beer.get('style_id'):
        styles = data_access.load_beer_styles()
        beer['style_name'] = next((s['name'] for s in styles if s['id'] == beer['style_id']), '')
        
    b_tags = [bt['tag_id'] for bt in data_access.load_beer_tags() if bt['beer_id'] == id]
    if b_tags:
        all_tags = data_access.load_tags()
        beer['tags_list'] = [t for t in all_tags if t['id'] in b_tags]
    else:
        beer['tags_list'] = []
        
    fabricantes = data_access.load_fabricantes()
    
    # User's BeerMatch preference
    user_preference = None
    if session.get('user_id'):
        user_id = session.get('user_id')
        prefs = data_access.load_user_beer_preferences()
        pref_entry = next((p for p in prefs if p['user_id'] == user_id and p['beer_id'] == id), None)
        if pref_entry:
            user_preference = pref_entry['preference']
            
    return render_template('beer_view.html', beer=beer, fabricantes=fabricantes, user_preference=user_preference)

@bp.route('/fabricante/<int:id>')
def fabricante_view(id):
    fabricantes = data_access.load_fabricantes()
    fabricante = next((f for f in fabricantes if f['id'] == id), None)
    if not fabricante:
        return "Fabricante no encontrado", 404
        
    beers = data_access.load_beers()
    # Retroactive association: find all beers whose brewery string matches this fabricante's name
    fabricante_beers = [b for b in beers if b.get('brewery', '').lower() == fabricante['name'].lower()]
    
    return render_template('fabricante_view.html', fabricante=fabricante, beers=fabricante_beers)

from datetime import datetime, timezone

@bp.route('/venue/<int:id>')
def venue_view(id):
    venues = data_access.load_venues()
    venue = next((v for v in venues if v['id'] == id), None)
    if not venue:
        return "Venue not found", 404
        
    availabilities = data_access.load_availability()
    venue_availabilities = [a for a in availabilities if a['venue_id'] == id]
    
    # Sort logs newest first
    venue_availabilities.sort(key=lambda x: x.get('last_updated', ''), reverse=True)
    
    beers = data_access.load_beers()
    available_beers = []
    seen_beers = set()
    
    for a in venue_availabilities:
        if a['beer_id'] not in seen_beers:
            seen_beers.add(a['beer_id'])
            beer = next((b for b in beers if b['id'] == a['beer_id']), None)
            if beer:
                beer_with_status = beer.copy()
                beer_with_status['status'] = a['status']
                # Gather recent history for this beer at this venue
                history = [log for log in venue_availabilities if log['beer_id'] == beer['id']][:5]
                beer_with_status['history'] = history
                available_beers.append(beer_with_status)
            
    return render_template('venue_view.html', venue=venue, available_beers=available_beers, all_beers=beers)

@bp.route('/venue/<int:venue_id>/beer/<int:beer_id>/status', methods=['POST'])
@auth.login_required
def update_status(venue_id, beer_id):
    user_id = session.get('user_id')
    role = session.get('role')
    status = request.form.get('status')
    
    availabilities = data_access.load_availability()
    now = datetime.now(timezone.utc)
    now_str = now.isoformat(timespec='seconds').replace('+00:00', 'Z')
    
    # Rate limit check for normal users
    if role == 'USER':
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        updates_today = 0
        for log in availabilities:
            if log.get('user_id') == user_id and log.get('venue_id') == venue_id and log.get('beer_id') == beer_id:
                try:
                    log_time = datetime.fromisoformat(log.get('last_updated', '').replace('Z', '+00:00'))
                    if log_time >= today_start:
                        updates_today += 1
                except ValueError:
                    pass
        
        if updates_today >= 2:
            flash("Has alcanzado el límite diario (2) de actualizaciones para esta cerveza aquí.", "danger")
            return redirect(url_for('routes.venue_view', id=venue_id))

    new_id = max([a.get('id', 0) for a in availabilities] + [0]) + 1
    new_log = {
        'id': new_id,
        'venue_id': venue_id,
        'beer_id': beer_id,
        'user_id': user_id,
        'status': status,
        'last_updated': now_str
    }
    availabilities.append(new_log)
    data_access.save_availability(availabilities)
    flash("Estado actualizado.", "success")
    return redirect(url_for('routes.venue_view', id=venue_id))

@bp.route('/venue/<int:venue_id>/add_beer', methods=['POST'])
@auth.login_required
def venue_add_beer(venue_id):
    beer_id = int(request.form.get('beer_id'))
    user_id = session.get('user_id')
    
    availabilities = data_access.load_availability()
    now_str = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
    
    new_id = max([a.get('id', 0) for a in availabilities] + [0]) + 1
    new_log = {
        'id': new_id,
        'venue_id': venue_id,
        'beer_id': beer_id,
        'user_id': user_id,
        'status': 'AVAILABLE',
        'last_updated': now_str
    }
    availabilities.append(new_log)
    data_access.save_availability(availabilities)
    flash("Cerveza añadida al catálogo del bar.", "success")
    return redirect(url_for('routes.venue_view', id=venue_id))

def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0 # Radio de la Tierra en km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

@bp.route('/api/beer/<int:id>/venues')
def api_beer_venues(id):
    lat_str = request.args.get('lat')
    lon_str = request.args.get('lon')
    
    user_lat = float(lat_str) if lat_str else None
    user_lon = float(lon_str) if lon_str else None
    
    availabilities = data_access.load_availability()
    venues = data_access.load_venues()
    
    # Get active venues with this beer available
    active_venues = {v['id']: v for v in venues if v.get('active', True)}
    
    results = []
    seen_venues = set()
    
    # Process newest logs first
    availabilities.sort(key=lambda x: x.get('last_updated', ''), reverse=True)
    
    for log in availabilities:
        if log['beer_id'] == id and log['status'] == 'AVAILABLE':
            vid = log['venue_id']
            if vid in active_venues and vid not in seen_venues:
                seen_venues.add(vid)
                v = active_venues[vid]
                
                distance = None
                if user_lat is not None and user_lon is not None and v.get('latitude') and v.get('longitude'):
                    distance = haversine(user_lat, user_lon, v['latitude'], v['longitude'])
                    
                results.append({
                    'venue_id': v['id'],
                    'name': v['name'],
                    'address': v['address'],
                    'city': v['city'],
                    'distance_km': distance,
                    'last_updated': log['last_updated']
                })
                
    if user_lat is not None and user_lon is not None:
        # Sort by distance (venues without coordinates go to the end)
        results.sort(key=lambda x: x['distance_km'] if x['distance_km'] is not None else 999999)
    else:
        # Sort by last_updated desc
        results.sort(key=lambda x: x['last_updated'], reverse=True)
        
    return jsonify(results)

@bp.route('/api/explore')
def api_explore():
    q = request.args.get('q', '').lower()
    tag_name = request.args.get('tag', '').lower()
    style_name = request.args.get('style', '').lower()
    lat_str = request.args.get('lat')
    lon_str = request.args.get('lon')
    
    user_lat = float(lat_str) if lat_str else None
    user_lon = float(lon_str) if lon_str else None
    
    beers = data_access.load_beers()
    beer_tags = data_access.load_beer_tags()
    availabilities = data_access.load_availability()
    venues = {v['id']: v for v in data_access.load_venues() if v.get('active', True)}
    
    # Pre-resolve tags and styles dictionaries for string lookup
    all_styles = {s['id']: s['name'].lower() for s in data_access.load_beer_styles()}
    all_tags = {t['id']: t['name'].lower() for t in data_access.load_tags()}
    
    # 1. Filtrar
    filtered = []
    for b in beers:
        if not b.get('active', True): continue
        if q and q not in b.get('name','').lower() and q not in b.get('brewery','').lower(): continue
        
        b_style_name = all_styles.get(b.get('style_id'), '')
        if style_name and style_name not in b_style_name: continue
        
        b_tag_names = [all_tags.get(bt['tag_id'], '') for bt in beer_tags if bt['beer_id'] == b['id']]
        if tag_name and not any(tag_name in t for t in b_tag_names): continue
        
        filtered.append(b)
        
    # 2. Calcular distancias
    results = []
    for b in filtered:
        b_avail = [a for a in availabilities if a['beer_id'] == b['id'] and a['status'] == 'AVAILABLE']
        min_dist = 9999
        for a in b_avail:
            v = venues.get(a['venue_id'])
            if v and v.get('latitude') and v.get('longitude') and user_lat and user_lon:
                d = haversine(user_lat, user_lon, v['latitude'], v['longitude'])
                if d < min_dist:
                    min_dist = d
                    
        b_copy = dict(b)
        if min_dist != 9999:
            b_copy['distance'] = min_dist
            b_copy['distance_str'] = f"{round(min_dist, 1)} km"
        else:
            b_copy['distance'] = 9999
            b_copy['distance_str'] = ""
            
        b_copy['image_url'] = url_for('static', filename='images/beers/' + b.get('image', 'default.png')) if b.get('image') else None
        b_copy['view_url'] = url_for('routes.beer_view', id=b['id'])
        
        results.append(b_copy)
        
    results.sort(key=lambda x: (x['distance'], x['name']))
    
    return jsonify(results)


@bp.route('/map')
def map_view():
    venues = [v for v in data_access.load_venues() if v.get('active', True)]
    return render_template('map.html', venues=venues)

# --- Admin Actions: Toggle & Delete ---

@bp.route('/admin/user/<int:id>/toggle', methods=['POST'])
@auth.admin_required
def toggle_user(id):
    users = data_access.load_users()
    for u in users:
        if u['id'] == id:
            u['status'] = 'INACTIVE' if u['status'] == 'ACTIVE' else 'ACTIVE'
            break
    data_access.save_users(users)
    return redirect(url_for('routes.admin', type='users'))

@bp.route('/admin/user/<int:id>/delete', methods=['POST'])
@auth.admin_required
def delete_user(id):
    users = [u for u in data_access.load_users() if u['id'] != id]
    data_access.save_users(users)
    return redirect(url_for('routes.admin', type='users'))

@bp.route('/admin/venue/<int:id>/toggle', methods=['POST'])
@auth.admin_required
def toggle_venue(id):
    venues = data_access.load_venues()
    for v in venues:
        if v.get('id') == id:
            v['active'] = not v.get('active', True)
            break
    data_access.save_venues(venues)
    return redirect(url_for('routes.admin', type='venues'))

@bp.route('/admin/venue/<int:id>/delete', methods=['POST'])
@auth.admin_required
def delete_venue(id):
    venues = [v for v in data_access.load_venues() if v.get('id') != id]
    data_access.save_venues(venues)
    return redirect(url_for('routes.admin', type='venues'))

@bp.route('/admin/beer/<int:id>/toggle', methods=['POST'])
@auth.admin_required
def toggle_beer(id):
    beers = data_access.load_beers()
    for b in beers:
        if b.get('id') == id:
            b['active'] = not b.get('active', True)
            break
    data_access.save_beers(beers)
    return redirect(url_for('routes.admin', type='beers'))

@bp.route('/admin/beer/<int:id>/delete', methods=['POST'])
@auth.admin_required
def delete_beer(id):
    beers = [b for b in data_access.load_beers() if b.get('id') != id]
    data_access.save_beers(beers)
    return redirect(url_for('routes.admin', type='beers'))

@bp.route('/admin/fabricante/<int:id>/toggle', methods=['POST'])
@auth.admin_required
def toggle_fabricante(id):
    fabricantes = data_access.load_fabricantes()
    for f in fabricantes:
        if f.get('id') == id:
            f['active'] = not f.get('active', True)
            break
    data_access.save_fabricantes(fabricantes)
    return redirect(url_for('routes.admin', type='fabricantes'))

@bp.route('/admin/fabricante/<int:id>/delete', methods=['POST'])
@auth.admin_required
def delete_fabricante(id):
    fabricantes = [f for f in data_access.load_fabricantes() if f.get('id') != id]
    data_access.save_fabricantes(fabricantes)
    return redirect(url_for('routes.admin', type='fabricantes'))

@bp.route('/admin/family/new', methods=['POST'])
@auth.admin_required
def add_family():
    name = request.form.get('name')
    if name:
        families = data_access.load_beer_families()
        new_id = max([f.get('id', 0) for f in families] + [0]) + 1
        families.append({'id': new_id, 'name': name, 'description': ''})
        data_access.save_beer_families(families)
        flash("Familia añadida", "success")
    return redirect(url_for('routes.admin', type='taxonomy'))

@bp.route('/admin/style/new', methods=['POST'])
@auth.admin_required
def add_style():
    name = request.form.get('name')
    family_id = request.form.get('family_id')
    if name and family_id:
        styles = data_access.load_beer_styles()
        new_id = max([s.get('id', 0) for s in styles] + [0]) + 1
        styles.append({'id': new_id, 'family_id': int(family_id), 'name': name, 'description': ''})
        data_access.save_beer_styles(styles)
        flash("Estilo añadido", "success")
    return redirect(url_for('routes.admin', type='taxonomy'))

@bp.route('/admin/tag/new', methods=['POST'])
@auth.admin_required
def add_tag():
    name = request.form.get('name')
    if name:
        tags = data_access.load_tags()
        new_id = max([t.get('id', 0) for t in tags] + [0]) + 1
        tags.append({'id': new_id, 'name': name, 'description': ''})
        data_access.save_tags(tags)
        flash("Tag añadido", "success")
    return redirect(url_for('routes.admin', type='taxonomy'))


@bp.route('/profile')
@auth.login_required
def profile():
    user_id = session.get('user_id')
    
    families = data_access.load_beer_families()
    styles = data_access.load_beer_styles()
    tags = data_access.load_tags()
    
    prefs = data_access.load_user_preferences()
    user_prefs_raw = [p for p in prefs if p.get('user_id') == user_id]
    
    user_prefs = {
        'FAMILY': {},
        'STYLE': {},
        'TAG': {}
    }
    for p in user_prefs_raw:
        ttype = p.get('target_type')
        if ttype in user_prefs:
            user_prefs[ttype][p['target_id']] = p['preference']
            
    # Group styles by family for easy rendering
    styles_by_family = {}
    for s in styles:
        f_id = s['family_id']
        if f_id not in styles_by_family:
            styles_by_family[f_id] = []
        styles_by_family[f_id].append(s)
            
    return render_template('profile.html', 
                           families=families, 
                           styles_by_family=styles_by_family, 
                           tags=tags, 
                           user_prefs=user_prefs)

@bp.route('/api/user/preferences', methods=['POST'])
@auth.login_required
def update_preference():
    user_id = session.get('user_id')
    data = request.get_json()
    
    if not data or 'target_type' not in data or 'target_id' not in data or 'preference' not in data:
        return jsonify({'error': 'Bad Request'}), 400
        
    target_type = data['target_type']
    target_id = int(data['target_id'])
    preference = data['preference']
    
    if target_type not in ['FAMILY', 'STYLE', 'TAG']:
        return jsonify({'error': 'Invalid target_type'}), 400
        
    if preference not in ['LIKE', 'DISLIKE', 'NEUTRAL']:
        return jsonify({'error': 'Invalid preference'}), 400
        
    prefs = data_access.load_user_preferences()
    
    # Remove existing if any
    prefs = [p for p in prefs if not (p.get('user_id') == user_id and p.get('target_type') == target_type and p.get('target_id') == target_id)]
    
    # If not NEUTRAL, add new preference
    if preference != 'NEUTRAL':
        prefs.append({
            'user_id': user_id,
            'target_type': target_type,
            'target_id': target_id,
            'preference': preference
        })
        
    data_access.save_user_preferences(prefs)
    return jsonify({'status': 'success'})

@bp.route('/admin/user/<int:id>/edit', methods=['GET', 'POST'])
@auth.admin_required
def edit_user(id):
    users = data_access.load_users()
    user = next((u for u in users if u['id'] == id), None)
    if not user:
        flash("Usuario no encontrado.", "danger")
        return redirect(url_for('routes.admin', type='users'))
        
    if request.method == 'POST':
        user['username'] = request.form.get('username')
        user['email'] = request.form.get('email')
        user['role'] = request.form.get('role')
        user['status'] = request.form.get('status')
        data_access.save_users(users)
        flash("Usuario actualizado.", "success")
        return redirect(url_for('routes.admin', type='users'))
        
    return render_template('edit_user.html', user=user)

@bp.route('/admin/venue/<int:id>/edit', methods=['GET', 'POST'])
@auth.admin_required
def edit_venue(id):
    venues = data_access.load_venues()
    venue = next((v for v in venues if v['id'] == id), None)
    if not venue:
        flash("Local no encontrado.", "danger")
        return redirect(url_for('routes.admin', type='venues'))
        
    if request.method == 'POST':
        venue['name'] = request.form.get('name')
        venue['city'] = request.form.get('city')
        venue['address'] = request.form.get('address')
        venue['description'] = request.form.get('description')
        
        lat = request.form.get('latitude')
        lon = request.form.get('longitude')
        venue['latitude'] = float(lat) if lat else None
        venue['longitude'] = float(lon) if lon else None
        
        data_access.save_venues(venues)
        flash("Local actualizado.", "success")
        return redirect(url_for('routes.admin', type='venues'))
        
    return render_template('edit_venue.html', venue=venue)

@bp.route('/admin/fabricante/<int:id>/edit', methods=['GET', 'POST'])
@auth.admin_required
def edit_fabricante(id):
    fabricantes = data_access.load_fabricantes()
    fabricante = next((f for f in fabricantes if f['id'] == id), None)
    if not fabricante:
        flash("Fabricante no encontrado.", "danger")
        return redirect(url_for('routes.admin', type='fabricantes'))
        
    if request.method == 'POST':
        fabricante['name'] = request.form.get('name')
        fabricante['country'] = request.form.get('country')
        fabricante['website'] = request.form.get('website')
        fabricante['description'] = request.form.get('description')
        
        if 'logo' in request.files:
            file = request.files['logo']
            if file.filename != '':
                filename = secure_filename(file.filename)
                upload_folder = os.path.join(os.path.dirname(__file__), 'static', 'images', 'fabricantes')
                os.makedirs(upload_folder, exist_ok=True)
                file.save(os.path.join(upload_folder, filename))
                fabricante['logo'] = filename
                
        data_access.save_fabricantes(fabricantes)
        flash("Fabricante actualizado.", "success")
        return redirect(url_for('routes.admin', type='fabricantes'))
        
    return render_template('edit_fabricante.html', fabricante=fabricante)

@bp.route('/beer/<int:id>/edit', methods=['GET', 'POST'])
@auth.admin_required
def edit_beer(id):
    beers = data_access.load_beers()
    beer = next((b for b in beers if b['id'] == id), None)
    if not beer:
        flash("Cerveza no encontrada.", "danger")
        return redirect(url_for('routes.admin', type='beers'))
        
    fabricantes = data_access.load_fabricantes()
    families = data_access.load_beer_families()
    styles = data_access.load_beer_styles()
    tags = data_access.load_tags()
    
    if request.method == 'POST':
        beer['name'] = request.form.get('name')
        beer['brewery'] = request.form.get('brewery')
        
        family_id = request.form.get('family_id')
        style_id = request.form.get('style_id')
        beer['family_id'] = int(family_id) if family_id else None
        beer['style_id'] = int(style_id) if style_id else None
        
        beer['abv'] = request.form.get('abv')
        beer['description'] = request.form.get('description')
        
        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '':
                filename = secure_filename(file.filename)
                upload_folder = os.path.join(os.path.dirname(__file__), 'static', 'images', 'beers')
                os.makedirs(upload_folder, exist_ok=True)
                file.save(os.path.join(upload_folder, filename))
                beer['image'] = filename
                
        data_access.save_beers(beers)
        
        selected_tags = request.form.getlist('tags')
        beer_tags = data_access.load_beer_tags()
        beer_tags = [bt for bt in beer_tags if bt['beer_id'] != id] # clear old tags
        for t_id in selected_tags:
            beer_tags.append({'beer_id': id, 'tag_id': int(t_id)})
        data_access.save_beer_tags(beer_tags)
        
        flash("Cerveza actualizada correctamente.", "success")
        return redirect(url_for('routes.admin', type='beers'))
        
    beer_tag_ids = [bt['tag_id'] for bt in data_access.load_beer_tags() if bt['beer_id'] == id]
    return render_template('beer_form.html', beer=beer, fabricantes=fabricantes, families=families, styles=styles, tags=tags, beer_tag_ids=beer_tag_ids)


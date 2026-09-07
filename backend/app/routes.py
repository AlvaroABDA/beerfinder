from flask import Blueprint, render_template, request, redirect, url_for, flash
from . import data_access
from . import auth

bp = Blueprint('routes', __name__)

@bp.route('/')
def index():
    beers = data_access.load_beers()[:3] # Show max 3 for "Descubre"
    venues = data_access.load_venues()[:2] # Show max 2 for "Cerca de ti"
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
    beers = data_access.load_beers()
    return render_template('beers_list.html', beers=beers)

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
    pending_users = [u for u in users if u['status'] == 'PENDING']
    
    # Simple server‑side search
    search_type = request.args.get('type')
    q = request.args.get('q', '').lower()
    if q and search_type:
        if search_type == 'users':
            users = [u for u in users if q in u.get('username','').lower() or q in u.get('email','').lower()]
        elif search_type == 'venues':
            venues = [v for v in venues if q in v.get('name','').lower() or q in v.get('city','').lower()]
        elif search_type == 'beers':
            beers = [b for b in beers if q in b.get('name','').lower() or q in b.get('style','').lower() or q in b.get('brewery','').lower()]
    
    return render_template('admin.html', users=users, venues=venues, beers=beers, pending_users=pending_users)


@bp.route('/admin/approve/<int:user_id>', methods=['POST'])
@auth.admin_required
def approve_user(user_id):
    users = data_access.load_users()
    for user in users:
        if user['id'] == user_id:
            user['status'] = 'ACTIVE'
            break
    data_access.save_users(users)
    return redirect(url_for('routes.admin'))

@bp.route('/venue/new', methods=['POST'])
@auth.admin_required
def venue_new():
    venues = data_access.load_venues()
    new_id = max([v.get('id', 0) for v in venues] + [0]) + 1
    
    address = request.form.get('address')
    lat = request.form.get('latitude')
    lon = request.form.get('longitude')
    
    # If latitude/longitude not provided, try geocoding the address using Nominatim
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
    return redirect(url_for('routes.admin'))

import os
from werkzeug.utils import secure_filename

@bp.route('/beer/new', methods=['GET', 'POST'])
@auth.login_required
def beer_new():
    if request.method == 'POST':
        beers = data_access.load_beers()
        new_id = max([b.get('id', 0) for b in beers] + [0]) + 1
        
        image_filename = ""
        if 'image' in request.files:
            file = request.files['image']
            if file.filename != '':
                filename = secure_filename(file.filename)
                # Save to static/images/beers
                upload_folder = os.path.join(os.path.dirname(__file__), 'static', 'images', 'beers')
                os.makedirs(upload_folder, exist_ok=True)
                file.save(os.path.join(upload_folder, filename))
                image_filename = filename
                
        new_beer = {
            'id': new_id,
            'name': request.form.get('name'),
            'brewery': request.form.get('brewery'),
            'style': request.form.get('style'),
            'abv': request.form.get('abv'),
            'description': request.form.get('description'),
            'image': image_filename
        }
        beers.append(new_beer)
        data_access.save_beers(beers)
        flash('Beer added!', 'success')
        return redirect(url_for('routes.beer_view', id=new_id))
    return render_template('beer_form.html')

@bp.route('/beer/<int:id>')
def beer_view(id):
    beers = data_access.load_beers()
    beer = next((b for b in beers if b['id'] == id), None)
    if not beer:
        return "Beer not found", 404
    return render_template('beer_view.html', beer=beer)

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

@bp.route('/map')
def map_view():
    venues = data_access.load_venues()
    return render_template('map.html', venues=venues)


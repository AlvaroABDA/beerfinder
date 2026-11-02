import unittest
import json
from app import create_app, data_access
from app.bootstrap import bootstrap_database
from app.models import db, Event, PushSubscription, User, Venue, BeerStyle


class TestEventsAndPush(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            'TESTING': True,
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
            'DISABLE_EXTERNAL_GEOCODING': True,
            'WTF_CSRF_ENABLED': False,
        })
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            v = Venue(name="Test Brewpub", address="Calle Mayor 1", city="Vitoria-Gasteiz", latitude=42.85, longitude=-2.67, active=True)
            db.session.add(v)
            db.session.commit()
            bootstrap_database(self.app)



    def test_events_seeded_and_listed(self):
        with self.app.app_context():
            events = data_access.list_upcoming_events()
            self.assertGreaterEqual(len(events), 1)
            first = events[0]
            self.assertIn('title', first)
            self.assertIn('event_type_label', first)

    def test_events_http_routes(self):
        # 1. Index shows upcoming events compact ribbon
        r = self.client.get('/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('event-ribbon-pill', r.data.decode('utf-8'))

        # 2. Events catalog list
        r = self.client.get('/events')
        self.assertEqual(r.status_code, 200)
        self.assertIn('Catas y Eventos Cerveceros', r.data.decode('utf-8'))

        # 3. Single event view
        with self.app.app_context():
            ev = Event.query.first()
            ev_id = ev.id

        r = self.client.get(f'/event/{ev_id}')
        self.assertEqual(r.status_code, 200)
        self.assertIn('Google Calendar', r.data.decode('utf-8'))

        # 4. Map JSON contains upcoming events
        r = self.client.get('/map')
        self.assertEqual(r.status_code, 200)
        self.assertIn('has_events', r.data.decode('utf-8'))

    def test_push_api_endpoints(self):
        # 1. VAPID public key
        r = self.client.get('/api/push/vapid_public_key')
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn('publicKey', data)
        self.assertGreater(len(data['publicKey']), 20)

        # 2. Subscribe endpoint
        payload = {
            'endpoint': 'https://push.example.com/sub/unique-456',
            'keys': {'p256dh': 'testp256dhkey', 'auth': 'testauthkey'},
            'lat': 42.85,
            'lon': -2.67,
            'max_distance': 30.0,
        }
        r = self.client.post('/api/push/subscribe', json=payload)
        self.assertEqual(r.status_code, 200)

        with self.app.app_context():
            sub = PushSubscription.query.filter_by(endpoint=payload['endpoint']).first()
            self.assertIsNotNone(sub)
            self.assertEqual(sub.auth, 'testauthkey')

        # 3. Unsubscribe endpoint
        r = self.client.post('/api/push/unsubscribe', json={'endpoint': payload['endpoint']})
        self.assertEqual(r.status_code, 200)

        with self.app.app_context():
            sub = PushSubscription.query.filter_by(endpoint=payload['endpoint']).first()
            self.assertIsNone(sub)

    def test_targeted_affinity_push_eligibility(self):
        with self.app.app_context():
            v = Venue.query.first()
            s = BeerStyle.query.first()
            ev = data_access.create_event({
                'venue_id': v.id,
                'title': 'Cata Especial de Prueba',
                'event_type': 'CATA',
                'event_date': '2026-11-25T19:00',
                'style_id': s.id,
            })

            # Sub 1: muy cerca (mismas coordenadas del venue)
            sub1 = data_access.save_push_subscription(
                endpoint='https://push.example.com/sub/near',
                p256dh='k1', auth='a1',
                lat=v.latitude, lon=v.longitude, max_distance=10.0
            )

            # Sub 2: muy lejos (Madrid a 350 km con max_distance de 20 km)
            sub2 = data_access.save_push_subscription(
                endpoint='https://push.example.com/sub/far',
                p256dh='k2', auth='a2',
                lat=40.4168, lon=-3.7038, max_distance=20.0
            )

            eligible = data_access.get_eligible_push_subscriptions_for_event(ev.id)
            eligible_endpoints = [e['subscription'].endpoint for e in eligible]

            self.assertIn(sub1.endpoint, eligible_endpoints)
            self.assertNotIn(sub2.endpoint, eligible_endpoints)


if __name__ == '__main__':
    unittest.main()

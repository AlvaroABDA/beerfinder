import unittest
from app import create_app
from app.bootstrap import bootstrap_database
from app.models import Beer, Fabricante, Venue, db

class MapAndClaimsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            'TESTING': True,
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
            'WTF_CSRF_ENABLED': False,
            'SECRET_KEY': 'test-secret',
            'DISABLE_EXTERNAL_GEOCODING': True,
        })
        with self.app.app_context():
            bootstrap_database(self.app)
            # Crear cerveza y fabricante de prueba
            fab = Fabricante(name='Cervecera Central', country='España', active=True)
            db.session.add(fab)
            db.session.flush()
            beer = Beer(name='Cerveza Artesana Test', brewery='Cervecera Central', fabricante_id=fab.id, style='IPA', active=True)
            db.session.add(beer)
            db.session.commit()
            self.test_beer_id = beer.id
            self.test_fab_id = fab.id

        self.client = self.app.test_client()

    def test_map_page_script_order(self):
        res = self.client.get('/map')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')

        # Verificamos que escapeHtml se declara ANTES de que cualquier script lo llame
        decl_idx = html.find('function escapeHtml')
        call_idx = html.find('escapeHtml(')
        self.assertNotEqual(decl_idx, -1, "escapeHtml debe estar declarado")
        self.assertNotEqual(call_idx, -1, "escapeHtml debe ser llamado")
        self.assertLess(decl_idx, call_idx, "function escapeHtml debe declararse antes de la primera llamada")
        self.assertIn('venue-claim-box', html)
        self.assertIn('venue-claim-sheet-link', html)

    def test_claim_hub_and_search(self):
        # 1. Acceso a /claim sin sesión (invitado)
        res = self.client.get('/claim')
        self.assertEqual(res.status_code, 200)
        html = res.data.decode('utf-8')
        self.assertIn('Verificación y Reclamación Oficial', html)

        # 2. Alias /claims
        res_alias = self.client.get('/claims')
        self.assertEqual(res_alias.status_code, 200)

        # 3. Búsqueda de entidad para reclamar
        res_search = self.client.get('/claim?q=Tape')
        self.assertEqual(res_search.status_code, 200)
        html_search = res_search.data.decode('utf-8')
        self.assertIn('La Tape', html_search)
        self.assertIn('Reclamar ahora', html_search)

        # 4. Búsqueda de marca
        res_fab = self.client.get('/claim?q=Central&type=brand')
        self.assertEqual(res_fab.status_code, 200)
        html_fab = res_fab.data.decode('utf-8')
        self.assertIn('Cervecera Central', html_fab)

    def test_quick_add_has_claim_option(self):
        # Comprobar tanto /add como /quick_add
        for url in ['/add', '/quick_add']:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 200)
            html = res.data.decode('utf-8')
            self.assertIn('Reclamar Local o Marca', html)
            self.assertIn('/claim', html)

    def test_entity_views_have_claim_anchor(self):
        # Venue view (La Tape se crea en bootstrap)
        res_v = self.client.get('/venue/1')
        self.assertEqual(res_v.status_code, 200)
        html_v = res_v.data.decode('utf-8')
        self.assertIn('id="claim"', html_v)

        # Beer view
        res_b = self.client.get(f'/beer/{self.test_beer_id}')
        self.assertEqual(res_b.status_code, 200)
        html_b = res_b.data.decode('utf-8')
        self.assertIn('id="claim"', html_b)

        # Fabricante view
        res_f = self.client.get(f'/fabricante/{self.test_fab_id}')
        self.assertEqual(res_f.status_code, 200)
        html_f = res_f.data.decode('utf-8')
        self.assertIn('id="claim"', html_f)

if __name__ == '__main__':
    unittest.main()

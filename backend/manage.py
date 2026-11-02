import os
import sys

# Asegurar que 'backend' está en el sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app import create_app, auth
from app.models import db, User
from app.bootstrap import bootstrap_database

app = create_app()

def list_users():
    with app.app_context():
        users = User.query.order_by(User.id).all()
        print("\n=== USUARIOS EN LA BASE DE DATOS ===")
        print(f"{'ID':<4} | {'Usuario':<20} | {'Email':<30} | {'Rol':<8} | {'Estado':<10}")
        print("-" * 80)
        for u in users:
            print(f"{u.id:<4} | {u.username:<20} | {u.email:<30} | {u.role:<8} | {u.status:<10}")
        print(f"Total: {len(users)} usuarios.\n")

def make_admin(identifier):
    with app.app_context():
        ident = identifier.strip().lower()
        user = User.query.filter(
            (db.func.lower(User.username) == ident) | (db.func.lower(User.email) == ident)
        ).first()
        if not user:
            print(f"[ERROR] Usuario '{identifier}' no encontrado.")
            return False
        user.role = 'ADMIN'
        user.status = 'ACTIVE'
        user.email_verified = True
        db.session.commit()
        print(f"[OK] \u00a1Usuario '{user.username}' ({user.email}) ahora es ADMIN activo!")
        return True

def reset_password(identifier, new_password):
    with app.app_context():
        ident = identifier.strip().lower()
        user = User.query.filter(
            (db.func.lower(User.username) == ident) | (db.func.lower(User.email) == ident)
        ).first()
        if not user:
            print(f"[ERROR] Usuario '{identifier}' no encontrado.")
            return False
        user.password = auth.hash_password(new_password)
        db.session.commit()
        print(f"[OK] Contrase\u00f1a de '{user.username}' actualizada exitosamente.")
        return True

def create_admin(username, email, password):
    with app.app_context():
        existing = User.query.filter(
            (db.func.lower(User.username) == username.strip().lower()) |
            (db.func.lower(User.email) == email.strip().lower())
        ).first()
        if existing:
            print(f"[AVISO] El usuario o email ya existe. Actualizando a ADMIN...")
            existing.role = 'ADMIN'
            existing.status = 'ACTIVE'
            existing.email_verified = True
            existing.password = auth.hash_password(password)
            db.session.commit()
            print(f"[OK] Usuario '{existing.username}' actualizado como ADMIN.")
            return True
        user = User(
            username=username.strip(),
            email=email.strip().lower(),
            password=auth.hash_password(password),
            role='ADMIN',
            status='ACTIVE',
            email_verified=True
        )
        db.session.add(user)
        db.session.commit()
        print(f"[OK] Usuario administrador '{username}' creado exitosamente.")
        return True

def run_bootstrap():
    with app.app_context():
        bootstrap_database()
        print("[OK] Bootstrap ejecutado correctamente.")

def print_help():
    print("""
Uso de manage.py:
  python manage.py list-users
  python manage.py make-admin <username_o_email>
  python manage.py reset-password <username_o_email> <nueva_contraseña>
  python manage.py create-admin <username> <email> <contraseña>
  python manage.py bootstrap
    """)

if __name__ == '__main__':
    args = sys.argv[1:]
    if not args:
        print_help()
        sys.exit(0)

    cmd = args[0].lower()
    if cmd == 'list-users':
        list_users()
    elif cmd == 'make-admin' and len(args) >= 2:
        make_admin(args[1])
    elif cmd == 'reset-password' and len(args) >= 3:
        reset_password(args[1], args[2])
    elif cmd == 'create-admin' and len(args) >= 4:
        create_admin(args[1], args[2], args[3])
    elif cmd == 'bootstrap':
        run_bootstrap()
    else:
        print_help()


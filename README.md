# BeerMap / BeerFinder

Aplicación web progresiva (**PWA**) y plataforma SaaS para descubrir cervezas artesanales según tu paladar y encontrarlas cerca en tiempo real, conectando consumidores, cerveceras (marcas) y establecimientos verificados.

---

## Pilares Funcionales

1. **Definición de Paladar y Recomendación Inteligente:**
   - Selector unificado de 3 estados en todo el catálogo y modo *Swipe* (`BeerMatch`): **Me gusta** (`LIKE`), **No es para mí** (`DISLIKE`) y **Quiero probarla** (`WISHLIST`).
   - Motor de afinidad híbrido sobre familias BJCP (8 familias, 46 estilos) y descriptores sensoriales (24 tags).
2. **Disponibilidad Cercana y Radar Silencioso (Variante B):**
   - Mapa interactivo con geolocalización y filtro de radio (`bounding box` + distancia Haversine).
   - Las cervezas marcadas como **Quiero probarla** (`WISHLIST`) iluminan automáticamente marcadores ámbar en el mapa y avisos contextuales en portada cuando algún establecimiento cercano actualiza su pizarra.
3. **Propiedad Jerárquica y Verificación Multi-vía Anti-Fraude:**
   - Cualquier usuario verificado puede dar de alta cervezas, marcas o locales en modo colaborativo (`COMMUNITY`).
   - Sistema de reclamación de **Marcas (`FABRICANTE`)** y **Establecimientos (`VENUE`)** con 4 vías de verificación y protección **Anti-Self-Attestation** (congela dominios/redes editados por comunidad en las últimas 72h):
     - **Nivel 1 (Automático):** `DOMAIN_EMAIL_OTP` (código OTP al dominio corporativo oficial) y `DNS_OR_META_TAG` (meta-etiqueta HTML con protección anti-SSRF).
     - **Nivel 2 (Semi-automático):** `SOCIAL_BIO_TOKEN` (código único en biografía oficial).
     - **Nivel 3 (Revisión privada):** `DOCUMENT_UPLOAD` (licencia, CIF/NIF o recibo almacenado en bucket privado estricto, accesible únicamente por administradores).
4. **Herramientas B2B para Locales Verificados:**
   - Gestión de pizarra en tiempo real (barril / botella-lata), pantalla **TV Digital de Grifos** (`/venues/<id>/tv`) y **Póster QR Imprimible** (`/venues/<id>/qr-poster`).

---

## Estructura del Proyecto

```text
beerfinder/
├── backend/
│   ├── app/
│   │   ├── routes/                 # Blueprint modularizado por dominios
│   │   │   ├── __init__.py         # Permisos de gobernanza, Service Worker, /health y assetlinks.json
│   │   │   ├── admin_routes.py     # Moderación de reclamaciones, auditoría y documentos privados
│   │   │   ├── api_routes.py       # Endpoints JSON (estilos, preferencias, radar, disponibilidad)
│   │   │   ├── auth_routes.py      # Registro, login, verificación OTP de email y perfil
│   │   │   ├── catalog_routes.py   # Portada, mapa, cervezas, marcas, locales, TV Mode y póster QR B2B
│   │   │   └── claims_routes.py    # Flujo multi-vía de reclamación y verificación de entidades
│   │   ├── services/
│   │   │   ├── mailer.py           # Envío transaccional (Resend HTTP API / SMTP / consola dev)
│   │   │   ├── recommendation.py   # Motor de afinidad sensorial + familias BJCP
│   │   │   ├── storage.py          # Almacenamiento público/privado (GCS ADC / S3-R2 / Local)
│   │   │   └── verification.py     # Validador OTP, Meta-Tag anti-SSRF y Anti-Self-Attestation
│   │   ├── static/                 # Iconos PWA, manifest.json, Service Worker (sw.js) e imágenes
│   │   ├── templates/              # Vistas Jinja2 accesibles mobile-first y herramientas B2B
│   │   ├── __init__.py             # Application Factory (SQLAlchemy, ProxyFix, cabeceras seguras)
│   │   ├── auth.py                 # Decoradores de sesión, email verificado y roles de acceso
│   │   ├── beermatch.py            # Blueprint de descubrimiento rápido (BeerMatch Swipe)
│   │   ├── bootstrap.py            # Inicialización idempotente de esquema SQL y semilla BJCP
│   │   ├── csrf.py                 # Protección CSRF en formularios y peticiones AJAX/Fetch
│   │   ├── data_access.py          # Capa relacional de acceso a datos y auditoría
│   │   ├── models.py               # Modelos ORM SQLAlchemy (PostgreSQL / SQLite)
│   │   └── security.py             # Rate limiting en memoria/proceso y validadores de red
│   ├── data/                       # Directorio local para SQLite en desarrollo (ignorado en Git)
│   ├── requirements.txt            # Dependencias de producción (Flask, SQLAlchemy, Gunicorn, GCS)
│   ├── run.py                      # Punto de entrada para desarrollo local
│   └── wsgi.py                     # Punto de entrada WSGI para Gunicorn / Cloud Run
├── .dockerignore
├── .env.example                    # Plantilla de variables de entorno (Local / GCP / TWA)
├── .gitignore
├── DEPLOY_GCP.md                   # Guía completa de arquitectura y despliegue en GCP + Android TWA
├── Dockerfile                      # Imagen multi-entorno lista para Google Cloud Run (puerto 8080)
└── docker-compose.yml              # Entorno local completo con PostgreSQL 16 + Gunicorn
```

---

## Inicio Rápido en Desarrollo Local

### Opción A: Entorno virtual Python (SQLite automático)

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

Al arrancar por primera vez, `bootstrap_database` crea automáticamente las tablas en `backend/data/beerfinder.db` y carga la taxonomía oficial (8 familias BJCP, 46 estilos y 24 descriptores sensoriales). La aplicación queda disponible en `http://localhost:5000`.

### Opción B: Docker Compose (PostgreSQL 16 + Gunicorn)

```bash
docker compose up --build
```

Levanta PostgreSQL 16 y el contenedor de producción en `http://localhost:8080`.

---

## Despliegue en Producción (Google Cloud Platform + Android PWA/TWA)

Consulta la guía detallada paso a paso en **[DEPLOY_GCP.md](./DEPLOY_GCP.md)** para configurar:
- **Cloud Run** + **Cloud SQL (PostgreSQL 16)** + **Google Cloud Storage** + **Secret Manager**.
- Empaquetado nativo para **Google Play Store** mediante **Trusted Web Activity (TWA / Bubblewrap)** y `/.well-known/assetlinks.json`.

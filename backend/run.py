from app import create_app
from app.bootstrap import bootstrap_database

app = create_app()

if __name__ == '__main__':
    bootstrap_database(app)
    app.run(debug=True, port=5008)

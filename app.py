import os
from flask import Flask, jsonify, render_template, request
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Configuración de la Base de Datos
# Utiliza la variable de entorno DATABASE_URL (provista por Render u otro hosting con PostgreSQL).
# Si no existe (entorno local), utiliza SQLite como respaldo local.
db_url = os.environ.get("DATABASE_URL", "sqlite:///agenda.db")

# Render genera URLs que empiezan por "postgres://", SQLAlchemy requiere "postgresql://"
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# Modelo de la tabla Contactos con todos los campos del HTML
class Contacto(db.Model):
    __tablename__ = "contactos"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    telefono = db.Column(db.String(20), nullable=False)
    fenaci = db.Column(db.String(20), nullable=True)
    sexo = db.Column(db.String(20), nullable=True)
    peso = db.Column(db.String(20), nullable=True)
    talla = db.Column(db.String(20), nullable=True)
    tipo_triaje = db.Column(db.String(50), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "nombre": self.nombre,
            "telefono": self.telefono,
            "fenaci": self.fenaci,
            "sexo": self.sexo,
            "peso": self.peso,
            "talla": self.talla,
            "tipoTriaje": self.tipo_triaje,
        }


# Inicializar las tablas en la base de datos
with app.app_context():
    db.create_all()


@app.route("/")
def index():
    return render_template("prueba.html")


# 1. Endpoint para listar todos los registros (GET)
@app.route("/api/contactos", methods=["GET"])
def obtener_contactos():
    contactos = Contacto.query.all()
    return jsonify([c.to_dict() for c in contactos])


# 2. Endpoint para crear un registro nuevo (POST)
@app.route("/api/contactos", methods=["POST"])
def crear_contacto():
    datos = request.get_json() or {}

    nombre = datos.get("nombre")
    telefono = datos.get("telefono")

    if not nombre or not telefono:
        return jsonify({"error": "Faltan datos obligatorios (nombre y teléfono)"}), 400

    nuevo_contacto = Contacto(
        nombre=nombre,
        telefono=telefono,
        fenaci=datos.get("fenaci"),
        sexo=datos.get("sexo"),
        peso=datos.get("peso"),
        talla=datos.get("talla"),
        tipo_triaje=datos.get("tipoTriaje"),
    )

    db.session.add(nuevo_contacto)
    db.session.commit()

    return jsonify({"mensaje": "Contacto guardado con éxito", "contacto": nuevo_contacto.to_dict()}), 201


if __name__ == "__main__":
    app.run(debug=True, port=5000)

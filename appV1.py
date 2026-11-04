import os
import psycopg2
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)


@app.route("/")
def index():
    return render_template("index.html")


# CONFIGURACIÓN AUTOMÁTICA DE LA BASE DE DATOS
DB_HOST_LOCAL = "localhost"
DB_PORT_LOCAL = "5432"
DB_NAME_LOCAL = "agenda_db"
DB_USER_LOCAL = "postgres"
DB_PASS_LOCAL = "1234"  # Tu contraseña local

DATABASE_URL = os.environ.get("DATABASE_URL")


def get_db_connection():
    if DATABASE_URL:
        # Entorno Render / Producción (Neon)
        conn = psycopg2.connect(DATABASE_URL)
    else:
        # Entorno Local automático
        conn = psycopg2.connect(
            host=DB_HOST_LOCAL,
            port=DB_PORT_LOCAL,
            dbname=DB_NAME_LOCAL,
            user=DB_USER_LOCAL,
            password=DB_PASS_LOCAL,
        )
    return conn


# Inicializar la base de datos PostgreSQL de forma segura
def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contactos (
                id SERIAL PRIMARY KEY,
                nombre TEXT NOT NULL,
                telefono TEXT NOT NULL,
                fenaci TEXT,
                sexo TEXT,
                peso REAL,
                talla REAL,
                tipo_triaje TEXT,
                fecha_registro TEXT NOT NULL
            )
        """)
        conn.commit()
        cursor.close()
        conn.close()
        print("Base de datos conectada e inicializada correctamente.")
    except Exception as e:
        print("Error al inicializar la base de datos:", e)


# EJECUTAR LA CREACIÓN DE LA TABLA AL ARRANCAR EL ARCHIVO
# Esto asegura que tanto Flask local como Gunicorn en Render la ejecuten
init_db()


# 1. Endpoint para listar todos los registros (GET)
@app.route("/api/contactos", methods=["GET"])
def obtener_contactos():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, nombre, telefono, fenaci, sexo, peso, talla, tipo_triaje, fecha_registro 
            FROM contactos ORDER BY id DESC
        """)
        filas = cursor.fetchall()
        cursor.close()
        conn.close()

        contactos = [
            {
                "id": f[0],
                "nombre": f[1],
                "telefono": f[2],
                "fenaci": f[3],
                "sexo": f[4],
                "peso": f[5],
                "talla": f[6],
                "tipo_triaje": f[7],
                "fecha_registro": f[8],
            }
            for f in filas
        ]
        return jsonify(contactos), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# 2. Endpoint para crear un registro nuevo (POST)
@app.route("/api/contactos", methods=["POST"])
def crear_contacto():
    datos = request.json
    nombre = datos.get("nombre")
    telefono = datos.get("telefono")
    fenaci = datos.get("fenaci")
    sexo = datos.get("sexo")
    peso = datos.get("peso")
    talla = datos.get("talla")
    tipo_triaje = datos.get("tipoTriaje")
    fecha_registro = datos.get("fecha_registro")

    if not nombre or not telefono or not fecha_registro:
        return jsonify({"error": "Faltan datos obligatorios"}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO contactos (nombre, telefono, fenaci, sexo, peso, talla, tipo_triaje, fecha_registro) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
            (
                nombre,
                telefono,
                fenaci,
                sexo,
                peso,
                talla,
                tipo_triaje,
                fecha_registro,
            ),
        )
        conn.commit()
        cursor.close()
        conn.close()

        return (
            jsonify({"mensaje": "Registro guardado con éxito en PostgreSQL"}),
            201,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
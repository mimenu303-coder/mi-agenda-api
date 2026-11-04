import os
from datetime import datetime
import psycopg2
from dateutil.relativedelta import relativedelta
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


# Función auxiliar para calcular Años, Meses y Días exactos
def calcular_edad_exacta(fenaci_str, fecha_registro_str=None):
    try:
        f_nace = datetime.strptime(fenaci_str, "%Y-%m-%d").date()
        if fecha_registro_str:
            f_ref = datetime.strptime(fecha_registro_str, "%Y-%m-%d").date()
        else:
            f_ref = datetime.now().date()

        diferencia = relativedelta(f_ref, f_nace)
        return f"{diferencia.years} años, {diferencia.months} meses, {diferencia.days} días"
    except Exception:
        return ""


# Inicializar la base de datos PostgreSQL de forma segura
def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pacientes_triaje (
                id SERIAL PRIMARY KEY,
                fecha_registro DATE NOT NULL,
                nombre TEXT NOT NULL,
                telefono TEXT NOT NULL,
                sexo VARCHAR(1) NOT NULL CHECK (sexo IN ('M', 'F')),
                talla NUMERIC(4,2),
                peso NUMERIC(5,2),
                fenaci DATE NOT NULL,
                edad_texto VARCHAR(50),
                lactante VARCHAR(20),
                tipo_triaje VARCHAR(50) NOT NULL,
                observacion VARCHAR(100)
            );
        """)
        conn.commit()
        cursor.close()
        conn.close()
        print("Base de datos conectada e inicializada correctamente.")
    except Exception as e:
        print("Error al inicializar la base de datos:", e)


# Inicializar la tabla al arrancar el archivo
init_db()


# 1. Endpoint para listar todos los registros (GET)
@app.route("/api/contactos", methods=["GET"])
def obtener_contactos():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, fecha_registro, nombre, telefono, sexo, talla, peso, fenaci, edad_texto, lactante, tipo_triaje, observacion 
            FROM pacientes_triaje ORDER BY id DESC
        """)
        filas = cursor.fetchall()
        cursor.close()
        conn.close()

        contactos = [
            {
                "id": f[0],
                "fecha_registro": f[1].strftime("%Y-%m-%d") if f[1] else "",
                "nombre": f[2],
                "telefono": f[3],
                "sexo": f[4],
                "talla": float(f[5]) if f[5] is not None else None,
                "peso": float(f[6]) if f[6] is not None else None,
                "fenaci": f[7].strftime("%Y-%m-%d") if f[7] else "",
                "edad_texto": f[8],
                "lactante": f[9],
                "tipo_triaje": f[10],
                "observacion": f[11],
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
    sexo = datos.get("sexo")
    talla = datos.get("talla")
    peso = datos.get("peso")
    fenaci = datos.get("fenaci")
    edad_texto = datos.get("edad_texto")
    lactante = datos.get("lactante")
    tipo_triaje = datos.get("tipoTriaje") or datos.get("tipo_triaje")
    observacion = datos.get("observacion", "")
    fecha_registro = datos.get("fecha_registro")

    if not nombre or not telefono or not fecha_registro or not fenaci or not sexo:
        return jsonify({"error": "Faltan datos obligatorios"}), 400

    # Si la edad no viene calculada desde el cliente, la calculamos automáticamente
    if not edad_texto:
        edad_texto = calcular_edad_exacta(fenaci, fecha_registro)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO pacientes_triaje (fecha_registro, nombre, telefono, sexo, talla, peso, fenaci, edad_texto, lactante, tipo_triaje, observacion) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
            (
                fecha_registro,
                nombre,
                telefono,
                sexo,
                talla if talla != "" else None,
                peso if peso != "" else None,
                fenaci,
                edad_texto,
                lactante,
                tipo_triaje,
                observacion,
            ),
        )
        conn.commit()
        cursor.close()
        conn.close()

        return (
            jsonify({"mensaje": "Registro guardado con éxito en PostgreSQL", "edad_calculada": edad_texto}),
            201,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
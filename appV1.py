import sqlite3
from flask import Flask, jsonify, request

app = Flask(__name__)

# Inicializar la base de datos SQLite con la columna fecha_registro
def init_db():
    conn = sqlite3.connect("agenda.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contactos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    conn.close()

# 1. Endpoint para listar todos los registros (GET)
@app.route("/api/contactos", methods=["GET"])
def obtener_contactos():
    conn = sqlite3.connect("agenda.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, nombre, telefono, fenaci, sexo, peso, talla, tipo_triaje, fecha_registro 
        FROM contactos
    """)
    filas = cursor.fetchall()
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
            "fecha_registro": f[8]
        }
        for f in filas
    ]
    return jsonify(contactos)

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

    conn = sqlite3.connect("agenda.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO contactos (nombre, telefono, fenaci, sexo, peso, talla, tipo_triaje, fecha_registro) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (nombre, telefono, fenaci, sexo, peso, talla, tipo_triaje, fecha_registro))
    conn.commit()
    conn.close()

    return jsonify({"mensaje": "Contacto guardado con éxito"}), 201

if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)

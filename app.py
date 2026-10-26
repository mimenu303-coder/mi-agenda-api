import sqlite3
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('prueba.html')

# Inicializar la base de datos SQLite simple
def init_db():
  conn = sqlite3.connect("agenda.db")
  cursor = conn.cursor()
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS contactos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            telefono TEXT NOT NULL
        )
    """)
  conn.commit()
  conn.close()


# 1. Endpoint para listar todos los registros (GET)
@app.route("/api/contactos", methods=["GET"])
def obtener_contactos():
  conn = sqlite3.connect("agenda.db")
  cursor = conn.cursor()
  cursor.execute("SELECT id, nombre, telefono FROM contactos")
  filas = cursor.fetchall()
  conn.close()

  # Convertir a formato JSON amigable
  contactos = [{"id": f[0], "nombre": f[1], "telefono": f[2]} for f in filas]
  return jsonify(contactos)


# 2. Endpoint para crear un registro nuevo (POST)
@app.route("/api/contactos", methods=["POST"])
def crear_contacto():
  datos = request.json
  nombre = datos.get("nombre")
  telefono = datos.get("telefono")

  if not nombre or not telefono:
    return jsonify({"error": "Faltan datos"}), 400

  conn = sqlite3.connect("agenda.db")
  cursor = conn.cursor()
  cursor.execute(
      "INSERT INTO contactos (nombre, telefono) VALUES (?, ?)", (nombre, telefono)
  )
  conn.commit()
  conn.close()

  return jsonify({"mensaje": "Contacto guardado con éxito"}), 201


if __name__ == "__main__":
  init_db()
  app.run(debug=True, port=5000)
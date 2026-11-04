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
        conn = psycopg2.connect(DATABASE_URL)
    else:
        conn = psycopg2.connect(
            host=DB_HOST_LOCAL,
            port=DB_PORT_LOCAL,
            dbname=DB_NAME_LOCAL,
            user=DB_USER_LOCAL,
            password=DB_PASS_LOCAL,
        )
    return conn


def calcular_edad_exacta(fenaci_str, fecha_registro_str=None):
    try:
        f_nace = datetime.strptime(fenaci_str, "%Y-%m-%d").date()
        if fecha_registro_str:
            f_ref = datetime.strptime(fecha_registro_str, "%Y-%m-%d").date()
        else:
            f_ref = datetime.now().date()

        diferencia = relativedelta(f_ref, f_nace)
        return f"{diferencia.years} años, {diferencia.months} meses, {diferencia.days} días", diferencia.years
    except Exception:
        return "", 0


def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pacientes_triaje (
                id SERIAL PRIMARY KEY,
                fecha_registro DATE NOT NULL,
                turno VARCHAR(50),
                nombre TEXT NOT NULL,
                telefono TEXT NOT NULL,
                sexo VARCHAR(1) NOT NULL CHECK (sexo IN ('M', 'F')),
                talla NUMERIC(4,2),
                peso NUMERIC(5,2),
                fenaci DATE NOT NULL,
                edad_texto VARCHAR(50),
                lactante VARCHAR(20),
                tipo_triaje VARCHAR(50) NOT NULL,
                observacion TEXT
            );
        """)
        conn.commit()
        cursor.close()
        conn.close()
        print("Base de datos conectada e inicializada correctamente.")
    except Exception as e:
        print("Error al inicializar la base de datos:", e)


init_db()


@app.route("/api/contactos", methods=["GET"])
def obtener_contactos():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, fecha_registro, turno, nombre, telefono, sexo, talla, peso, fenaci, edad_texto, lactante, tipo_triaje, observacion 
            FROM pacientes_triaje ORDER BY id DESC
        """)
        filas = cursor.fetchall()
        cursor.close()
        conn.close()

        contactos = [
            {
                "id": f[0],
                "fecha_registro": f[1].strftime("%Y-%m-%d") if f[1] else "",
                "turno": f[2],
                "nombre": f[3],
                "telefono": f[4],
                "sexo": f[5],
                "talla": float(f[6]) if f[6] is not None else None,
                "peso": float(f[7]) if f[7] is not None else None,
                "fenaci": f[8].strftime("%Y-%m-%d") if f[8] else "",
                "edad_texto": f[9],
                "lactante": f[10],
                "tipo_triaje": f[11],
                "observacion": f[12],
            }
            for f in filas
        ]
        return jsonify(contactos), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/contactos", methods=["POST"])
def crear_contacto():
    datos = request.json
    nombre = datos.get("nombre")
    telefono = datos.get("telefono")
    turno = datos.get("turno", "")
    sexo = datos.get("sexo")
    talla = datos.get("talla")
    peso = datos.get("peso")
    fenaci = datos.get("fenaci")
    lactante = datos.get("lactante", "")
    tipo_triaje = datos.get("tipoTriaje") or datos.get("tipo_triaje")
    observacion = datos.get("observacion", "")
    fecha_registro = datos.get("fecha_registro")

    if not nombre or not telefono or not fecha_registro or not fenaci or not sexo:
        return jsonify({"error": "Faltan datos obligatorios"}), 400

    edad_texto, _ = calcular_edad_exacta(fenaci, fecha_registro)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO pacientes_triaje (fecha_registro, turno, nombre, telefono, sexo, talla, peso, fenaci, edad_texto, lactante, tipo_triaje, observacion) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
            (
                fecha_registro,
                turno,
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
            jsonify({"mensaje": "Registro guardado con éxito", "edad_calculada": edad_texto}),
            201,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/informe-diario", methods=["GET"])
def informe_diario():
    f_inicio = request.args.get("inicio")
    f_fin = request.args.get("fin")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT sexo, tipo_triaje, edad_texto, lactante, fenaci, fecha_registro 
            FROM pacientes_triaje 
            WHERE fecha_registro BETWEEN %s AND %s
        """, (f_inicio, f_fin))
        filas = cursor.fetchall()
        cursor.close()
        conn.close()

        total_registros = len(filas)
        conteo_sexo = {"M": 0, "F": 0}
        conteo_triaje = {}
        conteo_edades = {
            "Menores de 1 año": {"M": 0, "F": 0, "Total": 0},
            "Entre 1 y 3 años": {"M": 0, "F": 0, "Total": 0},
            "Entre 4 y 6 años": {"M": 0, "F": 0, "Total": 0},
            "Entre 7 y 9 años": {"M": 0, "F": 0, "Total": 0},
            "Entre 10 y 12 años": {"M": 0, "F": 0, "Total": 0},
            "Entre 13 y 17 años": {"M": 0, "F": 0, "Total": 0}
        }

        for f in filas:
            sexo = f[0]
            triaje = f[1]
            fenaci = f[4]
            f_reg = f[5]
            lactante = f[3]

            if sexo in conteo_sexo:
                conteo_sexo[sexo] += 1

            _, anos = calcular_edad_exacta(str(fenaci), str(f_reg))

            if anos < 1:
                grupo = "Menores de 1 año"
                triaje_etiqueta = "Lactancia Exclusiva" if lactante == "Exclusivo" else "Lactancia Mixta"
            elif 1 <= anos <= 3:
                grupo = "Entre 1 y 3 años"
                triaje_etiqueta = triaje
            elif 4 <= anos <= 6:
                grupo = "Entre 4 y 6 años"
                triaje_etiqueta = triaje
            elif 7 <= anos <= 9:
                grupo = "Entre 7 y 9 años"
                triaje_etiqueta = triaje
            elif 10 <= anos <= 12:
                grupo = "Entre 10 y 12 años"
                triaje_etiqueta = triaje
            else:
                grupo = "Entre 13 y 17 años"
                triaje_etiqueta = triaje

            conteo_edades[grupo]["Total"] += 1
            if sexo in conteo_edades[grupo]:
                conteo_edades[grupo][sexo] += 1

            if triaje_etiqueta not in conteo_triaje:
                conteo_triaje[triaje_etiqueta] = {"M": 0, "F": 0}
            if sexo in conteo_triaje[triaje_etiqueta]:
                conteo_triaje[triaje_etiqueta][sexo] += 1

        return jsonify({
            "total_registros": total_registros,
            "conteo_sexo": conteo_sexo,
            "conteo_triaje": conteo_triaje,
            "conteo_edades": conteo_edades
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/informe-semanal", methods=["GET"])
def informe_semanal():
    f_inicio = request.args.get("inicio")
    f_fin = request.args.get("fin")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT sexo, tipo_triaje, lactante, fenaci, fecha_registro 
            FROM pacientes_triaje 
            WHERE fecha_registro BETWEEN %s AND %s
        """, (f_inicio, f_fin))
        filas = cursor.fetchall()
        cursor.close()
        conn.close()

        total_registros = len(filas)
        conteo_sexo = {"M": 0, "F": 0}

        tratamientos = ["IM", "EV", "Nebulizacion", "Tratamiento", "Sin Tratamiento", "Suturas", "Lavado Nasal", "Lavado Oido", "Curas Realizadas", "Lact. Exclusivo", "Lact. Mixto", "Totales"]
        edades = ["Totales", "<1", "1-3", "4-6", "7-9", "10-12", "13-17"]

        matriz = {t: {e: {"M": 0, "F": 0} for e in edades} for t in tratamientos}

        for f in filas:
            sexo = f[0]
            trata = f[1]
            lactante = f[2]
            fenaci = f[3]
            f_reg = f[4]

            if sexo in conteo_sexo:
                conteo_sexo[sexo] += 1

            _, anos = calcular_edad_exacta(str(fenaci), str(f_reg))

            if anos < 1:
                edad_grupo = "<1"
                if lactante == "Exclusivo":
                    matriz["Lact. Exclusivo"][edad_grupo][sexo] += 1
                    matriz["Lact. Exclusivo"]["Totales"][sexo] += 1
                else:
                    matriz["Lact. Mixto"][edad_grupo][sexo] += 1
                    matriz["Lact. Mixto"]["Totales"][sexo] += 1
            elif 1 <= anos <= 3:
                edad_grupo = "1-3"
            elif 4 <= anos <= 6:
                edad_grupo = "4-6"
            elif 7 <= anos <= 9:
                edad_grupo = "7-9"
            elif 10 <= anos <= 12:
                edad_grupo = "10-12"
            else:
                edad_grupo = "13-17"

            if anos >= 1 and trata in matriz:
                matriz[trata][edad_grupo][sexo] += 1
                matriz[trata]["Totales"][sexo] += 1

            matriz["Totales"][edad_grupo][sexo] += 1
            matriz["Totales"]["Totales"][sexo] += 1

        return jsonify({
            "total_registros": total_registros,
            "conteo_sexo": conteo_sexo,
            "matriz": matriz,
            "tratamientos": tratamientos,
            "edades": edades
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
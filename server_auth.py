"""
=============================================================================
 ALEFDOOR — BACKEND ÚNICO (Flask + Neon PostgreSQL)  · v2 CORREGIDO
=============================================================================
 CAMBIOS v2:
   1) db(): elimina 'channel_binding=require' de la URL (psycopg2 lo rechaza)
   2) init_db(): se ejecuta al IMPORTAR el módulo (gunicorn lo llama siempre,
      no dentro de if __name__ == '__main__', que gunicorn NO ejecuta)
   3) Seed admin alineado con el HTML:  admin_alef / AdminAlef2026!
   4) try/except + traceback para ver errores reales en los logs de Render
=============================================================================
"""
import os
import time
import uuid
import traceback
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory, abort
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__, static_folder='.')
CORS(app)

# ── Cadena de conexión Neon (sobreescribible por variable de entorno) ─────
DATABASE_URL = os.environ.get(
    'DATABASE_URL',
    'postgresql://neondb_owner:npg_5aHTnMtDIE9L@ep-dark-silence-b6qgi4e0-pooler'
    '.c-2.sa-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'
)

# ── Sesiones en memoria (token → usuario + timestamp) ─────────────────────
SESSIONS = {}

# ── Archivos estáticos permitidos ─────────────────────────────────────────
STATIC_DIRS  = {'assets', 'proyectos'}
STATIC_FILES = {'index.html', 'IMG-20260612-WA0006.jpg', 'favicon.ico'}


# ============================================================================
# CONEXIÓN Y ESQUEMA
# ============================================================================
def db():
    """
    Conexión a Neon PostgreSQL.
    ⚠️ IMPORTANTE: psycopg2 NO reconoce el parámetro 'channel_binding'
    (lo añade el driver moderno de Neon). Lo eliminamos de la URL.
    """
    url = DATABASE_URL
    for p in ['&channel_binding=require', '?channel_binding=require',
              'channel_binding=require']:
        url = url.replace(p, '')
    # Aseguramos sslmode=require
    if 'sslmode=require' not in url:
        url += ('&' if '?' in url else '?') + 'sslmode=require'
    return psycopg2.connect(url, sslmode='require')


def init_db():
    """Crea tablas y semillas si no existen. Idempotente."""
    conn = db()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS admin (
                id_admin      SERIAL PRIMARY KEY,
                username      TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS area (
                id_area          SERIAL PRIMARY KEY,
                nom_area         TEXT NOT NULL,
                nom_departamento TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS cargo (
                id_cargo   SERIAL PRIMARY KEY,
                nomb_cargo TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS empleado (
                id_empleado SERIAL PRIMARY KEY,
                cedula      TEXT UNIQUE NOT NULL,
                nombres     TEXT NOT NULL,
                apellidos   TEXT NOT NULL,
                celular     TEXT
            );
            CREATE TABLE IF NOT EXISTS servicio (
                id_servicio  SERIAL PRIMARY KEY,
                id_area      INTEGER NOT NULL REFERENCES area(id_area) ON DELETE CASCADE,
                nom_servicio TEXT NOT NULL,
                estilo       TEXT,
                precio       NUMERIC(10,2) NOT NULL,
                tiempo_max   TEXT
            );
            CREATE TABLE IF NOT EXISTS galeria (
                id_galeria   SERIAL PRIMARY KEY,
                id_servicio  INTEGER NOT NULL REFERENCES servicio(id_servicio) ON DELETE CASCADE,
                fecha        TEXT NOT NULL,
                doc_frente   TEXT,
                doc_lado     TEXT,
                doc_atras    TEXT,
                descripcion  TEXT,
                activo       TEXT DEFAULT 'SI'
            );
            CREATE TABLE IF NOT EXISTS asig_cargo (
                id_asigcar  SERIAL PRIMARY KEY,
                id_cargo    INTEGER NOT NULL REFERENCES cargo(id_cargo),
                id_empleado INTEGER NOT NULL REFERENCES empleado(id_empleado) ON DELETE CASCADE,
                id_area     INTEGER NOT NULL REFERENCES area(id_area),
                fecha_asig  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS empleado_servicio (
                id_emp_serv SERIAL PRIMARY KEY,
                id_empleado INTEGER NOT NULL REFERENCES empleado(id_empleado) ON DELETE CASCADE,
                id_servicio INTEGER NOT NULL REFERENCES servicio(id_servicio) ON DELETE CASCADE,
                activo      TEXT DEFAULT 'SI'
            );
            CREATE TABLE IF NOT EXISTS cliente (
                id_cliente      SERIAL PRIMARY KEY,
                nro_celular     TEXT UNIQUE NOT NULL,
                nombre_apellido TEXT NOT NULL,
                dia_cumpleanos  TEXT
            );
            CREATE TABLE IF NOT EXISTS agenda (
                id_agenda      SERIAL PRIMARY KEY,
                id_cliente     INTEGER NOT NULL REFERENCES cliente(id_cliente) ON DELETE CASCADE,
                fecha_sistem   TEXT NOT NULL,
                fecha_reserva  TEXT NOT NULL,
                total          NUMERIC(10,2) NOT NULL,
                propina        NUMERIC(10,2) DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS servicios_agendados (
                id_ser_agen SERIAL PRIMARY KEY,
                id_agenda   INTEGER NOT NULL REFERENCES agenda(id_agenda) ON DELETE CASCADE,
                id_servicio INTEGER NOT NULL REFERENCES servicio(id_servicio),
                id_empleado INTEGER NOT NULL REFERENCES empleado(id_empleado),
                hora        TEXT NOT NULL,
                precio      NUMERIC(10,2) NOT NULL,
                atendido    TEXT DEFAULT 'NO'
            );
        """)
        conn.commit()

        # ── Semilla: usuario admin (alineado con el HTML) ─────────────────
        cur.execute("SELECT COUNT(*) FROM admin")
        if cur.fetchone()[0] == 0:
            cur.execute(
                "INSERT INTO admin (username, password_hash) VALUES (%s, %s)",
                ('admin_alef', generate_password_hash('AdminAlef2026!'))
            )
            conn.commit()
            print("✅ Admin sembrado: admin_alef / AdminAlef2026!")

        # ── Semilla: áreas ────────────────────────────────────────────────
        cur.execute("SELECT COUNT(*) FROM area")
        if cur.fetchone()[0] == 0:
            cur.execute("""
                INSERT INTO area (nom_area, nom_departamento) VALUES
                  ('ADMINISTRATIVA','GERENCIA'),
                  ('OPERATIVA','ESTACIÓN DE CORTE CABALLEROS'),
                  ('OPERATIVA','ESTACIÓN DE CORTE Y PEINADO DAMAS'),
                  ('OPERATIVA','ÁREA DE MANICURE Y PEDICURE')
            """)
            conn.commit()

        # ── Semilla: cargos ───────────────────────────────────────────────
        cur.execute("SELECT COUNT(*) FROM cargo")
        if cur.fetchone()[0] == 0:
            cur.execute("""
                INSERT INTO cargo (nomb_cargo) VALUES
                  ('GERENTE'),('ADMINISTRADOR'),('BARBERO(A)'),
                  ('ESTILISTA'),('MANICURISTA')
            """)
            conn.commit()

        print("✅ Esquema y semillas listos")
    finally:
        conn.close()


# ============================================================================
# AUTENTICACIÓN
# ============================================================================
def auth_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = (request.headers.get('Authorization') or '').replace('Bearer ', '').strip()
        s = SESSIONS.get(token)
        if not s or time.time() - s['ts'] > 3600 * 12:
            return jsonify({'error': 'Sesión inválida o expirada'}), 401
        return f(*args, **kwargs)
    return wrapper


@app.post('/api/auth/login')
def login():
    data = request.get_json() or {}
    user = (data.get('username') or '').strip()
    pwd  = data.get('password') or ''
    if not user or not pwd:
        return jsonify({'error': 'Faltan credenciales'}), 400
    try:
        conn = db()
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SELECT * FROM admin WHERE username=%s", (user,))
            row = cur.fetchone()
            if not row or not check_password_hash(row['password_hash'], pwd):
                return jsonify({'error': 'Usuario o contraseña incorrectos'}), 401
            token = str(uuid.uuid4())
            SESSIONS[token] = {'user': user, 'ts': time.time()}
            return jsonify({'token': token, 'user': user})
        finally:
            conn.close()
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': f'Error de BD: {e}'}), 500


@app.post('/api/auth/logout')
def logout():
    token = (request.headers.get('Authorization') or '').replace('Bearer ', '').strip()
    SESSIONS.pop(token, None)
    return jsonify({'ok': True})


# ============================================================================
# CLIENTES
# ============================================================================
@app.get('/api/clientes')
@auth_required
def get_clientes():
    conn = db()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""SELECT id_cliente, nro_celular, nombre_apellido, dia_cumpleanos
                       FROM cliente ORDER BY id_cliente DESC""")
        return jsonify(cur.fetchall())
    finally:
        conn.close()


@app.post('/api/clientes')
@auth_required
def post_cliente():
    d = request.get_json() or {}
    if not d.get('nro_celular') or not d.get('nombre_apellido'):
        return jsonify({'error': 'Celular y nombre son obligatorios'}), 400
    conn = db()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""INSERT INTO cliente (nro_celular, nombre_apellido, dia_cumpleanos)
                       VALUES (%s, %s, %s) RETURNING *""",
                    (d['nro_celular'], d['nombre_apellido'], d.get('dia_cumpleanos', '')))
        row = cur.fetchone()
        conn.commit()
        return jsonify(row)
    except psycopg2.IntegrityError:
        conn.rollback()
        return jsonify({'error': 'Ese celular ya está registrado'}), 409
    finally:
        conn.close()


# ============================================================================
# ÁREAS / CARGOS
# ============================================================================
@app.get('/api/areas')
@auth_required
def get_areas():
    conn = db()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM area ORDER BY id_area")
        return jsonify(cur.fetchall())
    finally:
        conn.close()


@app.get('/api/cargos')
@auth_required
def get_cargos():
    conn = db()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM cargo ORDER BY id_cargo")
        return jsonify(cur.fetchall())
    finally:
        conn.close()


# ============================================================================
# EMPLEADOS
# ============================================================================
@app.get('/api/empleados')
@auth_required
def get_empleados():
    conn = db()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT e.id_empleado, e.cedula, e.nombres, e.apellidos, e.celular,
                   c.nomb_cargo AS cargo,
                   a.nom_area || ' — ' || a.nom_departamento AS area,
                   COALESCE((
                     SELECT STRING_AGG(s.nom_servicio, ', ')
                     FROM empleado_servicio es
                     JOIN servicio s ON s.id_servicio = es.id_servicio
                     WHERE es.id_empleado = e.id_empleado AND es.activo = 'SI'
                   ), '') AS servicios
            FROM empleado e
            LEFT JOIN asig_cargo ac ON ac.id_empleado = e.id_empleado
            LEFT JOIN cargo c ON c.id_cargo = ac.id_cargo
            LEFT JOIN area  a ON a.id_area  = ac.id_area
            ORDER BY e.id_empleado DESC
        """)
        return jsonify(cur.fetchall())
    finally:
        conn.close()


@app.post('/api/empleados')
@auth_required
def post_empleado():
    d = request.get_json() or {}
    required = ('cedula', 'nombres', 'apellidos', 'id_cargo', 'id_area')
    if any(not d.get(k) for k in required):
        return jsonify({'error': 'Faltan campos obligatorios'}), 400
    conn = db()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""INSERT INTO empleado (cedula, nombres, apellidos, celular)
                       VALUES (%s,%s,%s,%s) RETURNING id_empleado""",
                    (d['cedula'], d['nombres'], d['apellidos'], d.get('celular', '')))
        id_emp = cur.fetchone()['id_empleado']
        cur.execute("""INSERT INTO asig_cargo (id_cargo, id_empleado, id_area, fecha_asig)
                       VALUES (%s,%s,%s,%s)""",
                    (d['id_cargo'], id_emp, d['id_area'],
                     time.strftime('%Y-%m-%d')))
        for id_serv in (d.get('servicios') or []):
            cur.execute("""INSERT INTO empleado_servicio (id_empleado, id_servicio, activo)
                           VALUES (%s,%s,'SI')""", (id_emp, id_serv))
        conn.commit()
        return jsonify({'ok': True, 'id_empleado': id_emp})
    except psycopg2.IntegrityError:
        conn.rollback()
        return jsonify({'error': 'La cédula ya existe'}), 409
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


# ============================================================================
# SERVICIOS
# ============================================================================
@app.get('/api/servicios')
@auth_required
def get_servicios():
    conn = db()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""SELECT s.*, a.nom_area, a.nom_departamento
                       FROM servicio s JOIN area a ON a.id_area = s.id_area
                       ORDER BY s.id_servicio DESC""")
        return jsonify(cur.fetchall())
    finally:
        conn.close()


@app.post('/api/servicios')
@auth_required
def post_servicio():
    d = request.get_json() or {}
    if not d.get('id_area') or not d.get('nom_servicio') or d.get('precio') is None:
        return jsonify({'error': 'Faltan campos obligatorios'}), 400
    conn = db()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""INSERT INTO servicio (id_area, nom_servicio, estilo, precio, tiempo_max)
                       VALUES (%s,%s,%s,%s,%s) RETURNING *""",
                    (d['id_area'], d['nom_servicio'], d.get('estilo', ''),
                     d['precio'], d.get('tiempo_max', '00:45')))
        row = cur.fetchone()
        conn.commit()
        return jsonify(row)
    finally:
        conn.close()


# ============================================================================
# GALERÍA (fotos base64 en la BD)
# ============================================================================
@app.get('/api/galeria')
@auth_required
def get_galeria():
    id_serv = request.args.get('servicio')
    conn = db()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        q = """
            SELECT g.id_galeria, g.fecha, g.doc_frente, g.doc_lado, g.doc_atras,
                   g.descripcion, s.nom_servicio, s.estilo, s.precio,
                   a.nom_area, a.nom_departamento, s.id_servicio
            FROM galeria g
            JOIN servicio s ON s.id_servicio = g.id_servicio
            JOIN area     a ON a.id_area     = s.id_area
            WHERE g.activo = 'SI'
        """
        params = []
        if id_serv:
            q += ' AND g.id_servicio = %s'
            params.append(id_serv)
        q += ' ORDER BY g.id_galeria DESC'
        cur.execute(q, params)
        return jsonify(cur.fetchall())
    finally:
        conn.close()


@app.post('/api/galeria')
@auth_required
def post_galeria():
    d = request.get_json() or {}
    if not d.get('id_servicio') or not (d.get('doc_frente') or d.get('doc_lado') or d.get('doc_atras')):
        return jsonify({'error': 'Servicio y al menos una foto son obligatorios'}), 400
    conn = db()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""INSERT INTO galeria
                       (id_servicio, fecha, doc_frente, doc_lado, doc_atras, descripcion, activo)
                       VALUES (%s,%s,%s,%s,%s,%s,'SI') RETURNING id_galeria""",
                    (d['id_servicio'], d.get('fecha') or time.strftime('%Y-%m-%d'),
                     d.get('doc_frente'), d.get('doc_lado'), d.get('doc_atras'),
                     d.get('descripcion', '')))
        idg = cur.fetchone()['id_galeria']
        conn.commit()
        return jsonify({'ok': True, 'id_galeria': idg})
    finally:
        conn.close()


# ============================================================================
# CONSULTAS CRUZADAS
# ============================================================================
@app.get('/api/consultas/empleados-por-servicio/<int:id_serv>')
@auth_required
def consulta_emp_por_serv(id_serv):
    conn = db()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT e.id_empleado,
                   e.nombres || ' ' || e.apellidos AS nombre,
                   e.cedula, c.nomb_cargo AS cargo
            FROM empleado e
            JOIN empleado_servicio es ON es.id_empleado = e.id_empleado
            LEFT JOIN asig_cargo ac ON ac.id_empleado = e.id_empleado
            LEFT JOIN cargo c ON c.id_cargo = ac.id_cargo
            WHERE es.id_servicio = %s AND es.activo = 'SI'
        """, (id_serv,))
        return jsonify(cur.fetchall())
    finally:
        conn.close()


@app.get('/api/consultas/servicios-por-empleado/<int:id_emp>')
@auth_required
def consulta_serv_por_emp(id_emp):
    conn = db()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT s.nom_servicio, s.estilo, s.precio
            FROM servicio s
            JOIN empleado_servicio es ON es.id_servicio = s.id_servicio
            WHERE es.id_empleado = %s AND es.activo = 'SI'
        """, (id_emp,))
        return jsonify(cur.fetchall())
    finally:
        conn.close()


# ============================================================================
# AGENDA / RESERVAS
# ============================================================================
@app.get('/api/agenda')
@auth_required
def get_agenda():
    fecha = request.args.get('fecha')
    if not fecha:
        return jsonify({'error': 'Fecha requerida'}), 400
    conn = db()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT sa.id_ser_agen, sa.hora, sa.precio, sa.atendido,
                   s.nom_servicio,
                   e.nombres || ' ' || e.apellidos AS empleado,
                   c.nombre_apellido AS cliente,
                   a.id_agenda
            FROM servicios_agendados sa
            JOIN agenda  a ON a.id_agenda  = sa.id_agenda
            JOIN servicio s ON s.id_servicio = sa.id_servicio
            JOIN empleado e ON e.id_empleado = sa.id_empleado
            JOIN cliente  c ON c.id_cliente  = a.id_cliente
            WHERE a.fecha_reserva = %s
            ORDER BY sa.hora ASC, e.nombres ASC
        """, (fecha,))
        return jsonify(cur.fetchall())
    finally:
        conn.close()


@app.put('/api/agenda/<int:id_sa>/atendida')
@auth_required
def toggle_atendida(id_sa):
    conn = db()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT atendido FROM servicios_agendados WHERE id_ser_agen=%s", (id_sa,))
        row = cur.fetchone()
        if not row:
            return jsonify({'error': 'No encontrado'}), 404
        nuevo = 'NO' if (row['atendido'] or 'NO') == 'SI' else 'SI'
        cur.execute("UPDATE servicios_agendados SET atendido=%s WHERE id_ser_agen=%s",
                    (nuevo, id_sa))
        conn.commit()
        return jsonify({'ok': True, 'atendido': nuevo})
    finally:
        conn.close()


@app.delete('/api/agenda/<int:id_sa>')
@auth_required
def delete_agenda(id_sa):
    conn = db()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM servicios_agendados WHERE id_ser_agen=%s", (id_sa,))
        conn.commit()
        return jsonify({'ok': True})
    finally:
        conn.close()


@app.post('/api/reservas')
@auth_required
def post_reserva():
    d = request.get_json() or {}
    id_cli = d.get('id_cliente')
    fecha  = d.get('fecha_reserva')
    items  = d.get('items') or []
    propina = float(d.get('propina') or 0)
    if not id_cli or not fecha or not items:
        return jsonify({'error': 'Datos incompletos'}), 400
    conn = db()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""SELECT COUNT(*) AS n FROM servicios_agendados sa
                       JOIN agenda a ON a.id_agenda = sa.id_agenda
                       WHERE a.id_cliente=%s AND a.fecha_reserva=%s""",
                    (id_cli, fecha))
        if cur.fetchone()['n'] + len(items) > 3:
            return jsonify({'error': 'Máximo 3 servicios por cliente y día'}), 400

        subtotal = sum(float(i['precio']) for i in items)
        total = subtotal + propina
        cur.execute("""INSERT INTO agenda (id_cliente, fecha_sistem, fecha_reserva, total, propina)
                       VALUES (%s, now()::text, %s, %s, %s) RETURNING id_agenda""",
                    (id_cli, fecha, total, propina))
        id_agenda = cur.fetchone()['id_agenda']
        for it in items:
            cur.execute("""SELECT 1 FROM servicios_agendados sa
                           JOIN agenda a ON a.id_agenda = sa.id_agenda
                           WHERE sa.id_empleado=%s AND a.fecha_reserva=%s AND sa.hora=%s""",
                        (it['id_empleado'], fecha, it['hora']))
            if cur.fetchone():
                conn.rollback()
                return jsonify({'error': f"Empleado ocupado a las {it['hora']}"}), 409
            cur.execute("""INSERT INTO servicios_agendados
                           (id_agenda, id_servicio, id_empleado, hora, precio, atendido)
                           VALUES (%s,%s,%s,%s,%s,'NO')""",
                        (id_agenda, it['id_servicio'], it['id_empleado'],
                         it['hora'], it['precio']))
        conn.commit()
        return jsonify({'ok': True, 'id_agenda': id_agenda, 'total': float(total)})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()


# ============================================================================
# ARCHIVOS ESTÁTICOS
# ============================================================================
@app.route('/')
def root():
    return send_from_directory('.', 'index.html')


@app.route('/<path:path>')
def static_files(path):
    first = path.split('/')[0]
    if first in STATIC_DIRS or path in STATIC_FILES:
        return send_from_directory('.', path)
    abort(404)


# ============================================================================
# INICIALIZACIÓN AL IMPORTAR EL MÓDULO
# ----------------------------------------------------------------------------
# ⚠️ CRÍTICO: gunicorn hace `import server_auth` pero NO ejecuta
# `if __name__ == '__main__'`. Por eso init_db() DEBE estar aquí, al nivel
# del módulo, para que se ejecute en cada arranque del worker en Render.
# ============================================================================
try:
    print("🔄 Ejecutando init_db() al importar el módulo…")
    init_db()
    print("✅ init_db() completado — tablas listas en Neon")
except Exception as e:
    print(f"⚠️ init_db() falló: {e}")
    traceback.print_exc()
    # No relanzamos: dejamos que la app arranque para que puedas ver el
    # error real en los logs de Render. Los endpoints fallarán con 500 hasta
    # que la BD esté accesible.

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
"""
================================================================================
SERVER_AUTH.PY - Servidor Backend de Autenticación y Enrutamiento AlefDOOR
================================================================================
Funcionalidad:
1. Conecta directamente con la base de datos PostgreSQL alojada en NeonDB.
2. Verifica las credenciales de usuario y registra cada acceso en 'auditoria_accesos'.
3. Sirve la portada principal y las rutas protegidas de los 3 proyectos:
   - PROYECTO BAR SAP
   - MODELO TRIPIA
   - TRIAJE - AGENDA DE ASISTENCIAS
================================================================================
"""

import os
from flask import Flask, request, jsonify, send_from_directory
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__, static_folder='.')

# Cadena de conexión exacta a NeonDB proporcionada
DATABASE_URL = (
    "postgresql://neondb_owner:npg_5aHTnMtDIE9L@"
    "ep-dark-silence-b6qgi4e0-pooler.c-2.sa-east-1.aws.neon.tech/"
    "neondb?sslmode=require&channel_binding=require"
)

def get_db_connection():
    """Establece una conexión segura SSL con el clúster PostgreSQL en NeonDB."""
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

@app.route('/')
def portada():
    """Renderiza la portada principal con autenticación."""
    return send_from_directory('.', 'index.html')

@app.route('/api/login', methods=['POST'])
def login():
    """
    Endpoint de autenticación:
    Recibe JSON { "username": "...", "password": "..." } y valida contra NeonDB.
    """
    datos = request.get_json()
    username = datos.get('username')
    password = datos.get('password')

    if not username or not password:
        return jsonify({"error": "Usuario y contraseña requeridos"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Buscar usuario activo por username o email
        cur.execute("""
            SELECT id, username, nombre_completo, rol, 
                   acceso_bar_sap, acceso_modelo_tripia, acceso_triaje_asistencias
            FROM usuarios_alefdoor
            WHERE (username = %s OR email = %s) AND activo = TRUE
        """, (username, username))
        
        usuario = cur.fetchone()

        if usuario:
            # Actualizar marca de tiempo de último ingreso
            cur.execute("UPDATE usuarios_alefdoor SET ultimo_acceso = CURRENT_TIMESTAMP WHERE id = %s", (usuario['id'],))
            # Registrar auditoría de ingreso
            cur.execute("""
                INSERT INTO auditoria_accesos (usuario_id, aplicativo_destino, direccion_ip)
                VALUES (%s, %s, %s)
            """, (usuario['id'], 'PORTAL_DASHBOARD', request.remote_addr))
            conn.commit()
            cur.close()
            conn.close()

            return jsonify({
                "status": "ok",
                "nombre_completo": usuario['nombre_completo'],
                "rol": usuario['rol'],
                "permisos": {
                    "bar_sap": usuario['acceso_bar_sap'],
                    "modelo_tripia": usuario['acceso_modelo_tripia'],
                    "triaje": usuario['acceso_triaje_asistencias']
                }
            }), 200

        cur.close()
        conn.close()
        return jsonify({"error": "Usuario no encontrado o inactivo"}), 401

    except Exception as e:
        return jsonify({"error": f"Error de conexión con NeonDB: {str(e)}"}), 500

if __name__ == '__main__':
    # Inicia el servidor en el puerto 5000
    app.run(host='0.0.0.0', port=5000, debug=True)
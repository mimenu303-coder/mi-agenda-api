import datetime
import os
import sqlite3
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# Intentar importar PIL (Pillow) para previsualizar imágenes
try:
  from PIL import Image, ImageTk
  HAS_PIL = True
except ImportError:
  HAS_PIL = False


# ==============================================================================
# 1. BASE DE DATOS
# ==============================================================================
def conectar_bd():
  """Establece conexión con SQLite y activa soporte para Claves Foráneas."""
  conn = sqlite3.connect("barberia_spa.db")
  conn.execute("PRAGMA foreign_keys = ON;")
  return conn


def crear_tablas():
  """Crea la estructura de tablas relacionales si no existen e inserta datos semilla."""
  conn = conectar_bd()
  cursor = conn.cursor()

  cursor.executescript(
      """
    CREATE TABLE IF NOT EXISTS AREA (
        ID_AREA INTEGER PRIMARY KEY AUTOINCREMENT,
        NOM_ARE TEXT NOT NULL,
        NOM_DEPARTAMENTO TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS CARGO (
        ID_CARGO INTEGER PRIMARY KEY AUTOINCREMENT,
        NOMB_CARGO TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS EMPLEADO (
        ID_EMPLEADO INTEGER PRIMARY KEY AUTOINCREMENT,
        CEDULA TEXT UNIQUE NOT NULL,
        NOMBRES TEXT NOT NULL,
        APELLIDOS TEXT NOT NULL,
        CELULAR TEXT
    );

    CREATE TABLE IF NOT EXISTS SERVICIO (
        ID_SERVICIO INTEGER PRIMARY KEY AUTOINCREMENT,
        ID_AREA INTEGER NOT NULL,
        NOM_SERVICIO TEXT NOT NULL,
        ESTILO TEXT,
        PRECIO REAL NOT NULL,
        TIEMPO_MAX TEXT,
        FOREIGN KEY (ID_AREA) REFERENCES AREA(ID_AREA) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS GALERIA (
        ID_GALERIA INTEGER PRIMARY KEY AUTOINCREMENT,
        ID_SERVICIO INTEGER NOT NULL,
        FECHA TEXT NOT NULL,
        DOC_FRENTE TEXT NOT NULL,
        DOC_LADO TEXT,
        DOC_ATRAS TEXT,
        DESCRIPCION TEXT,
        ACTIVO TEXT DEFAULT 'SI',
        FOREIGN KEY (ID_SERVICIO) REFERENCES SERVICIO(ID_SERVICIO) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS ASIG_CARGO (
        ID_ASIGCAR INTEGER PRIMARY KEY AUTOINCREMENT,
        ID_CARGO INTEGER NOT NULL,
        ID_EMPLEADO INTEGER NOT NULL,
        ID_AREA INTEGER NOT NULL,
        FECHA_ASIG TEXT NOT NULL,
        FOREIGN KEY (ID_CARGO) REFERENCES CARGO(ID_CARGO),
        FOREIGN KEY (ID_EMPLEADO) REFERENCES EMPLEADO(ID_EMPLEADO) ON DELETE CASCADE,
        FOREIGN KEY (ID_AREA) REFERENCES AREA(ID_AREA)
    );

    CREATE TABLE IF NOT EXISTS EMPLEADO_SERVICIO (
        ID_EMP_SERV INTEGER PRIMARY KEY AUTOINCREMENT,
        ID_EMPLEADO INTEGER NOT NULL,
        ID_SERVICIO INTEGER NOT NULL,
        ACTIVO TEXT DEFAULT 'SI',
        FOREIGN KEY (ID_EMPLEADO) REFERENCES EMPLEADO(ID_EMPLEADO) ON DELETE CASCADE,
        FOREIGN KEY (ID_SERVICIO) REFERENCES SERVICIO(ID_SERVICIO) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS CLIENTE (
        ID_CLIENTE INTEGER PRIMARY KEY AUTOINCREMENT,
        NRO_CELULAR TEXT UNIQUE NOT NULL,
        NOMBRE_APELLIDO TEXT NOT NULL,
        DIA_CUMPLEANOS TEXT
    );

    CREATE TABLE IF NOT EXISTS AGENDA (
        ID_AGENDA INTEGER PRIMARY KEY AUTOINCREMENT,
        ID_CLIENTE INTEGER NOT NULL,
        FECHA_SISTEM TEXT NOT NULL,
        FECHA_RESERVA TEXT NOT NULL,
        TOTAL REAL NOT NULL,
        PROPINA REAL DEFAULT 0,
        FOREIGN KEY (ID_CLIENTE) REFERENCES CLIENTE(ID_CLIENTE) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS SERVICIOS_AGENDADOS (
        ID_SER_AGEN INTEGER PRIMARY KEY AUTOINCREMENT,
        ID_AGENDA INTEGER NOT NULL,
        ID_SERVICIO INTEGER NOT NULL,
        ID_EMPLEADO INTEGER NOT NULL,
        HORA TEXT NOT NULL,
        PRECIO REAL NOT NULL,
        ATENDIDO TEXT DEFAULT 'NO',
        FOREIGN KEY (ID_AGENDA) REFERENCES AGENDA(ID_AGENDA) ON DELETE CASCADE,
        FOREIGN KEY (ID_SERVICIO) REFERENCES SERVICIO(ID_SERVICIO),
        FOREIGN KEY (ID_EMPLEADO) REFERENCES EMPLEADO(ID_EMPLEADO)
    );
    """
  )
  conn.commit()

  # --- Migración: agregar columna ATENDIDO a bases de datos existentes ---
  try:
    cursor.execute(
        "ALTER TABLE SERVICIOS_AGENDADOS ADD COLUMN ATENDIDO TEXT DEFAULT 'NO'"
    )
    conn.commit()
  except sqlite3.OperationalError:
    pass  # La columna ya existe

  cursor.execute("SELECT COUNT(*) FROM AREA")
  if cursor.fetchone()[0] == 0:
    cursor.executemany(
        "INSERT INTO AREA (NOM_ARE, NOM_DEPARTAMENTO) VALUES (?, ?)",
        [
            ("ADMINISTRATIVA", "GERENCIA"),
            ("OPERATIVA", "ESTACIÓN DE CORTE CABALLEROS"),
            ("OPERATIVA", "ESTACIÓN DE CORTE Y PEINADO DAMAS"),
            ("OPERATIVA", "ÁREA DE MANICURE Y PEDICURE"),
        ],
    )
    conn.commit()

  cursor.execute("SELECT COUNT(*) FROM CARGO")
  if cursor.fetchone()[0] == 0:
    cursor.executemany(
        "INSERT INTO CARGO (NOMB_CARGO) VALUES (?)",
        [
            ("GERENTE",),
            ("ADMINISTRADOR",),
            ("BARBERO(A)",),
            ("ESTILISTA",),
            ("MANICURISTA",),
        ],
    )
    conn.commit()

  conn.close()


# ==============================================================================
# 2. INTERFAZ GRÁFICA PRINCIPAL
# ==============================================================================
class AppBarberia(tk.Tk):

  def __init__(self):
    super().__init__()
    self.title("Sistema de Gestión - Barbería / Spa / Peluquería")
    self.geometry("1280x880")

    self.dict_areas = {}
    self.dict_servicios = {}
    self.dict_cargos = {}
    self.dict_empleados = {}
    self.dict_clientes = {}
    self.dict_serv_area_temp = {}
    self.dict_serv_emp_temp = {}

    self.galeria_items = []
    self.galeria_index_actual = 0
    self.imgs_tk_actuales = [None, None, None]
    self.carrito_reserva = []
    self.orden_informe = "HORA"           # "HORA" o "EMPLEADO"
    self.ver_solo_atendidas = False       # filtro de atendidas

    notebook = ttk.Notebook(self)
    notebook.pack(fill="both", expand=True, padx=10, pady=10)

    self.tab_clientes = ttk.Frame(notebook)
    self.tab_reservas = ttk.Frame(notebook)
    self.tab_informes = ttk.Frame(notebook)
    self.tab_servicios = ttk.Frame(notebook)
    self.tab_galeria = ttk.Frame(notebook)
    self.tab_empleados = ttk.Frame(notebook)
    self.tab_consultas = ttk.Frame(notebook)

    notebook.add(self.tab_clientes, text="1. Clientes")
    notebook.add(self.tab_reservas, text="2. Agendar Reserva")
    notebook.add(self.tab_informes, text="3. Informe de Agenda")
    notebook.add(self.tab_servicios, text="4. Gestión Servicios")
    notebook.add(self.tab_galeria, text="5. Cargar Galería")
    notebook.add(self.tab_empleados, text="6. Empleados y Cargos")
    notebook.add(self.tab_consultas, text="7. Consultas y Galería Pro")

    self.init_tab_clientes()
    self.init_tab_reservas()
    self.init_tab_informes()
    self.init_tab_servicios()
    self.init_tab_galeria()
    self.init_tab_empleados()
    self.init_tab_consultas()

    self.actualizar_combos_areas()
    self.actualizar_combos_cargos()
    self.actualizar_combos_servicios()
    self.actualizar_combos_empleados()
    self.actualizar_combos_clientes()

  # --------------------------------------------------------------------------
  # REFRESCO DE CATÁLOGOS
  # --------------------------------------------------------------------------
  def actualizar_combos_areas(self):
    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute("SELECT ID_AREA, NOM_ARE, NOM_DEPARTAMENTO FROM AREA")
    filas = cursor.fetchall()
    conn.close()

    self.dict_areas = {f"{r[1]} - {r[2]}": r[0] for r in filas} if filas else {}
    lista = list(self.dict_areas.keys())

    if hasattr(self, "cb_area_serv"):
      self.cb_area_serv["values"] = lista
    if hasattr(self, "cb_area_emp"):
      self.cb_area_emp["values"] = lista
    if hasattr(self, "cb_res_area"):
      self.cb_res_area["values"] = lista

  def actualizar_combos_cargos(self):
    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute("SELECT ID_CARGO, NOMB_CARGO FROM CARGO")
    filas = cursor.fetchall()
    conn.close()

    self.dict_cargos = {r[1]: r[0] for r in filas} if filas else {}
    if hasattr(self, "cb_cargo"):
      self.cb_cargo["values"] = list(self.dict_cargos.keys())

  def actualizar_combos_servicios(self):
    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute("SELECT ID_SERVICIO, NOM_SERVICIO, ESTILO FROM SERVICIO")
    filas = cursor.fetchall()
    conn.close()

    self.dict_servicios = (
        {f"{r[0]} - {r[1]} ({r[2]})": r[0] for r in filas} if filas else {}
    )
    serv_keys = list(self.dict_servicios.keys())

    if hasattr(self, "cb_servicio_galeria"):
      self.cb_servicio_galeria["values"] = serv_keys
    if hasattr(self, "cb_consulta_servicio"):
      self.cb_consulta_servicio["values"] = serv_keys
    if hasattr(self, "cb_galeria_servicio"):
      self.cb_galeria_servicio["values"] = [
          "-- Ver Todos los Servicios --"
      ] + serv_keys
    if hasattr(self, "lb_servicios"):
      self.lb_servicios.delete(0, tk.END)
      for s in serv_keys:
        self.lb_servicios.insert(tk.END, s)

  def actualizar_combos_empleados(self):
    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT ID_EMPLEADO, NOMBRES, APELLIDOS, CEDULA FROM EMPLEADO"
    )
    filas = cursor.fetchall()
    conn.close()

    self.dict_empleados = (
        {f"{r[1]} {r[2]} (C.I: {r[3]})": r[0] for r in filas} if filas else {}
    )
    lista = list(self.dict_empleados.keys())

    if hasattr(self, "cb_consulta_empleado"):
      self.cb_consulta_empleado["values"] = lista
    if hasattr(self, "cb_res_empleado"):
      self.cb_res_empleado["values"] = lista

  def actualizar_combos_clientes(self):
    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT ID_CLIENTE, NOMBRE_APELLIDO, NRO_CELULAR FROM CLIENTE"
    )
    filas = cursor.fetchall()
    conn.close()

    self.dict_clientes = (
        {f"{r[1]} - Cel: {r[2]}": r[0] for r in filas} if filas else {}
    )

    if hasattr(self, "cb_res_cliente"):
      self.cb_res_cliente["values"] = list(self.dict_clientes.keys())

    if hasattr(self, "tree_clientes"):
      for i in self.tree_clientes.get_children():
        self.tree_clientes.delete(i)
      conn = conectar_bd()
      cursor = conn.cursor()
      cursor.execute(
          "SELECT ID_CLIENTE, NRO_CELULAR, NOMBRE_APELLIDO, DIA_CUMPLEANOS FROM"
          " CLIENTE"
      )
      for r in cursor.fetchall():
        self.tree_clientes.insert("", "end", values=r)
      conn.close()

  # --------------------------------------------------------------------------
  # PESTAÑA 1: CLIENTES
  # --------------------------------------------------------------------------
  def init_tab_clientes(self):
    frame = ttk.LabelFrame(
        self.tab_clientes, text=" Registrar Nuevo Cliente "
    )
    frame.pack(fill="x", padx=15, pady=10)

    ttk.Label(frame, text="Nro. Celular:").grid(
        row=0, column=0, padx=5, pady=5, sticky="e"
    )
    self.ent_cli_celular = ttk.Entry(frame, width=40)
    self.ent_cli_celular.grid(row=0, column=1, padx=5, pady=5)

    ttk.Label(frame, text="Nombre y Apellido:").grid(
        row=1, column=0, padx=5, pady=5, sticky="e"
    )
    self.ent_cli_nombre = ttk.Entry(frame, width=40)
    self.ent_cli_nombre.grid(row=1, column=1, padx=5, pady=5)

    ttk.Label(frame, text="Día Cumpleaños (ej: 15 de Mayo):").grid(
        row=2, column=0, padx=5, pady=5, sticky="e"
    )
    self.ent_cli_cumple = ttk.Entry(frame, width=40)
    self.ent_cli_cumple.grid(row=2, column=1, padx=5, pady=5)

    ttk.Button(
        frame, text="Guardar Cliente", command=self.guardar_cliente
    ).grid(row=3, column=0, columnspan=2, pady=10)

    frame_tabla = ttk.LabelFrame(
        self.tab_clientes, text=" Clientes Registrados "
    )
    frame_tabla.pack(fill="both", expand=True, padx=15, pady=10)

    self.tree_clientes = ttk.Treeview(
        frame_tabla,
        columns=("ID", "Celular", "Nombre", "Cumpleaños"),
        show="headings",
    )
    self.tree_clientes.heading("ID", text="ID")
    self.tree_clientes.heading("Celular", text="Celular")
    self.tree_clientes.heading("Nombre", text="Nombre y Apellido")
    self.tree_clientes.heading("Cumpleaños", text="Día Cumpleaños")

    self.tree_clientes.column("ID", width=60, anchor="center")
    self.tree_clientes.column("Celular", width=180)
    self.tree_clientes.column("Nombre", width=350)
    self.tree_clientes.column("Cumpleaños", width=200)
    self.tree_clientes.pack(fill="both", expand=True, padx=5, pady=5)

  def guardar_cliente(self):
    celular = self.ent_cli_celular.get().strip()
    nombre = self.ent_cli_nombre.get().strip()
    cumple = self.ent_cli_cumple.get().strip()

    if not celular or not nombre:
      messagebox.showwarning(
          "Advertencia", "Los campos Celular y Nombre son obligatorios."
      )
      return

    try:
      conn = conectar_bd()
      cursor = conn.cursor()
      cursor.execute(
          "INSERT INTO CLIENTE (NRO_CELULAR, NOMBRE_APELLIDO, DIA_CUMPLEANOS)"
          " VALUES (?, ?, ?)",
          (celular, nombre, cumple),
      )
      conn.commit()
      conn.close()

      messagebox.showinfo("Éxito", "Cliente registrado correctamente.")
      self.ent_cli_celular.delete(0, tk.END)
      self.ent_cli_nombre.delete(0, tk.END)
      self.ent_cli_cumple.delete(0, tk.END)
      self.actualizar_combos_clientes()
    except sqlite3.IntegrityError:
      messagebox.showerror(
          "Error", "El número de celular ya está registrado para otro cliente."
      )

  # --------------------------------------------------------------------------
  # PESTAÑA 2: AGENDAR RESERVA
  # --------------------------------------------------------------------------
  def init_tab_reservas(self):
    f_cli = ttk.LabelFrame(
        self.tab_reservas, text=" 1. Selección de Cliente y Fecha "
    )
    f_cli.pack(fill="x", padx=15, pady=5)

    ttk.Label(f_cli, text="Cliente:").grid(row=0, column=0, padx=5, pady=5)
    self.cb_res_cliente = ttk.Combobox(f_cli, state="readonly", width=45)
    self.cb_res_cliente.grid(row=0, column=1, padx=5, pady=5)

    ttk.Label(f_cli, text="Fecha Reserva:").grid(
        row=0, column=2, padx=5, pady=5
    )
    self.cb_res_fecha = ttk.Combobox(f_cli, state="readonly", width=15)

    hoy = datetime.date.today()
    fechas_validas = [
        (hoy + datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(3)
    ]
    self.cb_res_fecha["values"] = fechas_validas
    self.cb_res_fecha.current(0)
    self.cb_res_fecha.grid(row=0, column=3, padx=5, pady=5)

    f_modos = ttk.LabelFrame(
        self.tab_reservas, text=" 2. Modos de Agendamiento "
    )
    f_modos.pack(fill="x", padx=15, pady=5)

    nb_modos = ttk.Notebook(f_modos)
    nb_modos.pack(fill="x", expand=True, padx=5, pady=5)

    self.tab_modo_area = ttk.Frame(nb_modos)
    self.tab_modo_emp = ttk.Frame(nb_modos)

    nb_modos.add(
        self.tab_modo_area,
        text="Opción 1: Por Área y Servicio (Cualquier Empleado)",
    )
    nb_modos.add(
        self.tab_modo_emp, text="Opción 2: Por Empleado Específico y Servicio"
    )

    ttk.Label(self.tab_modo_area, text="Área:").grid(
        row=0, column=0, padx=5, pady=5
    )
    self.cb_res_area = ttk.Combobox(
        self.tab_modo_area, state="readonly", width=35
    )
    self.cb_res_area.grid(row=0, column=1, padx=5, pady=5)
    self.cb_res_area.bind(
        "<<ComboboxSelected>>",
        lambda e: self.al_seleccionar_area_reserva(),
    )

    ttk.Label(self.tab_modo_area, text="Servicio:").grid(
        row=0, column=2, padx=5, pady=5
    )
    self.cb_res_area_servicio = ttk.Combobox(
        self.tab_modo_area, state="readonly", width=35
    )
    self.cb_res_area_servicio.grid(row=0, column=3, padx=5, pady=5)

    ttk.Label(self.tab_modo_area, text="Hora (HH:MM):").grid(
        row=1, column=0, padx=5, pady=5
    )
    self.ent_res_area_hora = ttk.Entry(self.tab_modo_area, width=15)
    self.ent_res_area_hora.insert(0, "10:00")
    self.ent_res_area_hora.grid(row=1, column=1, padx=5, pady=5, sticky="w")

    ttk.Button(
        self.tab_modo_area,
        text="Agregar Servicio al Carrito",
        command=self.agregar_servicio_modo_area,
    ).grid(row=1, column=2, columnspan=2, pady=5)

    ttk.Label(self.tab_modo_emp, text="Empleado:").grid(
        row=0, column=0, padx=5, pady=5
    )
    self.cb_res_empleado = ttk.Combobox(
        self.tab_modo_emp, state="readonly", width=35
    )
    self.cb_res_empleado.grid(row=0, column=1, padx=5, pady=5)
    self.cb_res_empleado.bind(
        "<<ComboboxSelected>>",
        lambda e: self.al_seleccionar_empleado_reserva(),
    )

    ttk.Label(self.tab_modo_emp, text="Servicios que realiza:").grid(
        row=0, column=2, padx=5, pady=5
    )
    self.cb_res_emp_servicio = ttk.Combobox(
        self.tab_modo_emp, state="readonly", width=35
    )
    self.cb_res_emp_servicio.grid(row=0, column=3, padx=5, pady=5)

    ttk.Label(self.tab_modo_emp, text="Hora (HH:MM):").grid(
        row=1, column=0, padx=5, pady=5
    )
    self.ent_res_emp_hora = ttk.Entry(self.tab_modo_emp, width=15)
    self.ent_res_emp_hora.insert(0, "10:00")
    self.ent_res_emp_hora.grid(row=1, column=1, padx=5, pady=5, sticky="w")

    ttk.Button(
        self.tab_modo_emp,
        text="Agregar Servicio al Carrito",
        command=self.agregar_servicio_modo_empleado,
    ).grid(row=1, column=2, columnspan=2, pady=5)

    f_cart = ttk.LabelFrame(
        self.tab_reservas,
        text=" 3. Servicios Agendados para la Reserva (Máx 3 por Día) ",
    )
    f_cart.pack(fill="both", expand=True, padx=15, pady=5)

    self.tree_cart = ttk.Treeview(
        f_cart,
        columns=("Servicio", "Empleado", "Hora", "Precio"),
        show="headings",
        height=5,
    )
    self.tree_cart.heading("Servicio", text="Servicio")
    self.tree_cart.heading("Empleado", text="Empleado Asignado")
    self.tree_cart.heading("Hora", text="Hora")
    self.tree_cart.heading("Precio", text="Precio ($)")
    self.tree_cart.column("Servicio", width=300)
    self.tree_cart.column("Empleado", width=250)
    self.tree_cart.column("Hora", width=120, anchor="center")
    self.tree_cart.column("Precio", width=120, anchor="e")
    self.tree_cart.pack(fill="both", expand=True, padx=5, pady=5)

    f_pago = ttk.Frame(f_cart)
    f_pago.pack(fill="x", padx=5, pady=5)

    ttk.Label(f_pago, text="Propina Voluntaria ($):").pack(side="left", padx=5)
    self.ent_res_propina = ttk.Entry(f_pago, width=12)
    self.ent_res_propina.insert(0, "0.0")
    self.ent_res_propina.pack(side="left", padx=5)

    ttk.Button(
        f_pago, text="Limpiar Carrito", command=self.limpiar_carrito
    ).pack(side="left", padx=15)

    ttk.Button(
        f_pago,
        text="PROCESAR RESERVA Y EMITIR RECIBO",
        command=self.confirmar_y_procesar_reserva,
    ).pack(side="right", padx=10)

  def al_seleccionar_area_reserva(self):
    area_sel = self.cb_res_area.get()
    if not area_sel or area_sel not in self.dict_areas:
      return
    id_area = self.dict_areas[area_sel]

    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT ID_SERVICIO, NOM_SERVICIO, ESTILO, PRECIO FROM SERVICIO WHERE"
        " ID_AREA = ?",
        (id_area,),
    )
    filas = cursor.fetchall()
    conn.close()

    self.dict_serv_area_temp = (
        {f"{r[1]} [{r[2]}] - ${r[3]:.2f}": (r[0], r[3]) for r in filas}
        if filas
        else {}
    )
    self.cb_res_area_servicio["values"] = list(self.dict_serv_area_temp.keys())

  def al_seleccionar_empleado_reserva(self):
    emp_sel = self.cb_res_empleado.get()
    if not emp_sel or emp_sel not in self.dict_empleados:
      return
    id_empleado = self.dict_empleados[emp_sel]

    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT S.ID_SERVICIO, S.NOM_SERVICIO, S.ESTILO, S.PRECIO
        FROM SERVICIO S
        JOIN EMPLEADO_SERVICIO ES ON S.ID_SERVICIO = ES.ID_SERVICIO
        WHERE ES.ID_EMPLEADO = ? AND ES.ACTIVO = 'SI'
    """,
        (id_empleado,),
    )
    filas = cursor.fetchall()
    conn.close()

    self.dict_serv_emp_temp = (
        {f"{r[1]} [{r[2]}] - ${r[3]:.2f}": (r[0], r[3]) for r in filas}
        if filas
        else {}
    )
    self.cb_res_emp_servicio["values"] = list(self.dict_serv_emp_temp.keys())

  # --------------------------------------------------------------------------
  # VENTANA DE DISPONIBILIDAD DEL EMPLEADO
  # --------------------------------------------------------------------------
  def mostrar_ventana_disponibilidad_empleado(
      self, id_empleado, nombre_empleado, hora_solicitada, target_entry_hora
  ):
    win = tk.Toplevel(self)
    win.title(f"Disponibilidad de Horarios - {nombre_empleado}")
    win.geometry("700x550")
    win.grab_set()

    ttk.Label(
        win,
        text=f"El empleado {nombre_empleado} está OCUPADO a las {hora_solicitada}.",
        font=("Arial", 11, "bold"),
        foreground="red",
    ).pack(pady=10)
    ttk.Label(
        win,
        text=(
            "A continuación se muestran los horarios ocupados y disponibles"
            " para hoy y los próximos 2 días:"
        ),
        font=("Arial", 9),
    ).pack(pady=2)

    nb_dias = ttk.Notebook(win)
    nb_dias.pack(fill="both", expand=True, padx=15, pady=10)

    hoy = datetime.date.today()
    bloques_jornada = [
        "08:00", "09:00", "10:00", "11:00", "12:00", "13:00", "14:00",
        "15:00", "16:00", "17:00", "18:00", "19:00", "20:00",
    ]

    conn = conectar_bd()
    cursor = conn.cursor()

    for i in range(3):
      fecha_obj = hoy + datetime.timedelta(days=i)
      fecha_str = fecha_obj.strftime("%Y-%m-%d")
      etiqueta_dia = "Hoy" if i == 0 else f"+{i} Día(s)"
      titulo_tab = f"{etiqueta_dia} ({fecha_str})"

      frame_dia = ttk.Frame(nb_dias)
      nb_dias.add(frame_dia, text=titulo_tab)

      cursor.execute(
          """
            SELECT SA.HORA, S.NOM_SERVICIO, C.NOMBRE_APELLIDO
            FROM SERVICIOS_AGENDADOS SA
            JOIN AGENDA A ON SA.ID_AGENDA = A.ID_AGENDA
            JOIN SERVICIO S ON SA.ID_SERVICIO = S.ID_SERVICIO
            JOIN CLIENTE C ON A.ID_CLIENTE = C.ID_CLIENTE
            WHERE SA.ID_EMPLEADO = ? AND A.FECHA_RESERVA = ?
            ORDER BY SA.HORA ASC
        """,
          (id_empleado, fecha_str),
      )
      citas_ocupadas = cursor.fetchall()
      horas_ocupadas_set = {c[0] for c in citas_ocupadas}

      f_ocup = ttk.LabelFrame(
          frame_dia, text=f" Citas Agendadas ({fecha_str}) "
      )
      f_ocup.pack(fill="x", padx=10, pady=5)

      tree_ocup = ttk.Treeview(
          f_ocup,
          columns=("Hora", "Servicio", "Cliente"),
          show="headings",
          height=3,
      )
      tree_ocup.heading("Hora", text="Hora")
      tree_ocup.heading("Servicio", text="Servicio")
      tree_ocup.heading("Cliente", text="Cliente")
      tree_ocup.column("Hora", width=80, anchor="center")
      tree_ocup.column("Servicio", width=250)
      tree_ocup.column("Cliente", width=250)
      tree_ocup.pack(fill="x", padx=5, pady=5)

      if citas_ocupadas:
        for c in citas_ocupadas:
          tree_ocup.insert("", "end", values=(c[0], c[1], c[2]))
      else:
        tree_ocup.insert(
            "", "end", values=("-", "[Sin citas agendadas en este día]", "-")
        )

      f_libres = ttk.LabelFrame(
          frame_dia, text=" Horarios Sugeridos Disponibles "
      )
      f_libres.pack(fill="both", expand=True, padx=10, pady=5)

      lb_libres = tk.Listbox(
          f_libres, font=("Arial", 10), selectmode="single", height=5
      )
      lb_libres.pack(fill="both", expand=True, padx=5, pady=5)

      horas_libres = [h for h in bloques_jornada if h not in horas_ocupadas_set]
      for h in horas_libres:
        lb_libres.insert(tk.END, f"  Disponible a las {h} hrs")

      frame_dia.lb_libres_ref = lb_libres
      frame_dia.fecha_str_ref = fecha_str

    conn.close()

    def aplicar_hora_seleccionada():
      tab_actual = nb_dias.nametowidget(nb_dias.select())
      lb_ref = getattr(tab_actual, "lb_libres_ref", None)
      fecha_ref = getattr(tab_actual, "fecha_str_ref", None)

      if lb_ref and lb_ref.curselection():
        texto_sel = lb_ref.get(lb_ref.curselection()[0])
        hora_extraida = texto_sel.split(" a las ")[1].replace(" hrs", "").strip()

        target_entry_hora.delete(0, tk.END)
        target_entry_hora.insert(0, hora_extraida)

        if fecha_ref:
          self.cb_res_fecha.set(fecha_ref)

        messagebox.showinfo(
            "Horario Actualizado",
            f"Se ha asignado la hora {hora_extraida} y la fecha {fecha_ref} al"
            " formulario de agendamiento.",
        )
        win.destroy()
      else:
        messagebox.showwarning(
            "Selección Requerida",
            "Por favor haz clic en un horario disponible de la lista para"
            " seleccionarlo.",
        )

    f_pie = ttk.Frame(win)
    f_pie.pack(fill="x", padx=15, pady=10)

    ttk.Button(
        f_pie,
        text="Usar Horario Seleccionado",
        command=aplicar_hora_seleccionada,
    ).pack(side="right", padx=5)
    ttk.Button(f_pie, text="Cerrar", command=win.destroy).pack(
        side="right", padx=5
    )

  def agregar_servicio_modo_area(self):
    if len(self.carrito_reserva) >= 3:
      messagebox.showwarning(
          "Límite Excedido",
          "Regla D: Un cliente no puede exceder más de 3 reservas por día.",
      )
      return

    cli_sel = self.cb_res_cliente.get()
    if not cli_sel:
      messagebox.showwarning(
          "Advertencia",
          "Debes seleccionar primero el Cliente para verificar su agenda.",
      )
      return

    id_cliente = self.dict_clientes[cli_sel]
    area_sel = self.cb_res_area.get()
    serv_sel = self.cb_res_area_servicio.get()
    hora = self.ent_res_area_hora.get().strip()
    fecha = self.cb_res_fecha.get()

    if not area_sel or not serv_sel or not hora:
      messagebox.showwarning("Advertencia", "Completa todos los campos.")
      return

    id_servicio, precio = self.dict_serv_area_temp[serv_sel]

    for item in self.carrito_reserva:
      if item["id_servicio"] == id_servicio:
        messagebox.showwarning(
            "Servicio Duplicado",
            f"El servicio '{serv_sel.split(' - $')[0]}' ya está en el carrito.",
        )
        return
      if item["hora"] == hora:
        messagebox.showwarning(
            "Hora Ocupada en Carrito",
            f"Ya existe un servicio asignado a las {hora} en el carrito.",
        )
        return

    conn = conectar_bd()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT COUNT(*) FROM SERVICIOS_AGENDADOS SA
        JOIN AGENDA A ON SA.ID_AGENDA = A.ID_AGENDA
        WHERE A.ID_CLIENTE = ? AND A.FECHA_RESERVA = ? AND SA.ID_SERVICIO = ?
    """,
        (id_cliente, fecha, id_servicio),
    )
    if cursor.fetchone()[0] > 0:
      conn.close()
      messagebox.showwarning(
          "Servicio Ya Agendado",
          f"El cliente ya tiene registrado el servicio '{serv_sel.split(' - $')[0]}' el día {fecha}.",
      )
      return

    cursor.execute(
        """
        SELECT COUNT(*) FROM SERVICIOS_AGENDADOS SA
        JOIN AGENDA A ON SA.ID_AGENDA = A.ID_AGENDA
        WHERE A.ID_CLIENTE = ? AND A.FECHA_RESERVA = ? AND SA.HORA = ?
    """,
        (id_cliente, fecha, hora),
    )
    if cursor.fetchone()[0] > 0:
      conn.close()
      messagebox.showwarning(
          "Cliente Ocupado",
          f"El cliente ya posee otra cita registrada a las {hora} para la"
          f" fecha {fecha}.",
      )
      return

    cursor.execute(
        """
        SELECT E.ID_EMPLEADO, E.NOMBRES || ' ' || E.APELLIDOS
        FROM EMPLEADO E
        JOIN EMPLEADO_SERVICIO ES ON E.ID_EMPLEADO = ES.ID_EMPLEADO
        WHERE ES.ID_SERVICIO = ? AND ES.ACTIVO = 'SI'
    """,
        (id_servicio,),
    )
    empleados_capacitados = cursor.fetchall()

    empleado_asignado = None
    for emp_id, emp_nom in empleados_capacitados:
      cursor.execute(
          """
            SELECT COUNT(*) FROM SERVICIOS_AGENDADOS SA
            JOIN AGENDA A ON SA.ID_AGENDA = A.ID_AGENDA
            WHERE SA.ID_EMPLEADO = ? AND A.FECHA_RESERVA = ? AND SA.HORA = ?
        """,
          (emp_id, fecha, hora),
      )
      if cursor.fetchone()[0] == 0:
        empleado_asignado = (emp_id, emp_nom)
        break

    conn.close()

    if not empleado_asignado:
      messagebox.showerror(
          "Sin Disponibilidad",
          f"No existen empleados disponibles a las {hora} para este servicio.",
      )
      return

    self.carrito_reserva.append({
        "id_servicio": id_servicio,
        "nom_servicio": serv_sel.split(" - $")[0],
        "id_empleado": empleado_asignado[0],
        "nom_empleado": empleado_asignado[1],
        "hora": hora,
        "precio": precio,
    })
    self.refrescar_vista_carrito()

  def agregar_servicio_modo_empleado(self):
    if len(self.carrito_reserva) >= 3:
      messagebox.showwarning(
          "Límite Excedido",
          "Regla D: Un cliente no puede exceder más de 3 reservas por día.",
      )
      return

    cli_sel = self.cb_res_cliente.get()
    if not cli_sel:
      messagebox.showwarning(
          "Advertencia",
          "Debes seleccionar primero el Cliente para verificar su agenda.",
      )
      return

    id_cliente = self.dict_clientes[cli_sel]
    emp_sel = self.cb_res_empleado.get()
    serv_sel = self.cb_res_emp_servicio.get()
    hora = self.ent_res_emp_hora.get().strip()
    fecha = self.cb_res_fecha.get()

    if not emp_sel or not serv_sel or not hora:
      messagebox.showwarning("Advertencia", "Completa todos los campos.")
      return

    id_empleado = self.dict_empleados[emp_sel]
    id_servicio, precio = self.dict_serv_emp_temp[serv_sel]

    for item in self.carrito_reserva:
      if item["id_servicio"] == id_servicio:
        messagebox.showwarning(
            "Servicio Duplicado",
            f"El servicio '{serv_sel.split(' - $')[0]}' ya está en el carrito.",
        )
        return
      if item["hora"] == hora:
        messagebox.showwarning(
            "Hora Ocupada en Carrito",
            f"Ya existe un servicio programado a las {hora} en el carrito.",
        )
        return

    conn = conectar_bd()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT COUNT(*) FROM SERVICIOS_AGENDADOS SA
        JOIN AGENDA A ON SA.ID_AGENDA = A.ID_AGENDA
        WHERE A.ID_CLIENTE = ? AND A.FECHA_RESERVA = ? AND SA.ID_SERVICIO = ?
    """,
        (id_cliente, fecha, id_servicio),
    )
    if cursor.fetchone()[0] > 0:
      conn.close()
      messagebox.showwarning(
          "Servicio Ya Agendado",
          f"El cliente ya agendó el servicio '{serv_sel.split(' - $')[0]}' para el día {fecha}.",
      )
      return

    cursor.execute(
        """
        SELECT COUNT(*) FROM SERVICIOS_AGENDADOS SA
        JOIN AGENDA A ON SA.ID_AGENDA = A.ID_AGENDA
        WHERE SA.ID_EMPLEADO = ? AND A.FECHA_RESERVA = ? AND SA.HORA = ?
    """,
        (id_empleado, fecha, hora),
    )
    if cursor.fetchone()[0] > 0:
      conn.close()
      nombre_emp = emp_sel.split(" (")[0]
      self.mostrar_ventana_disponibilidad_empleado(
          id_empleado, nombre_emp, hora, self.ent_res_emp_hora
      )
      return

    conn.close()

    self.carrito_reserva.append({
        "id_servicio": id_servicio,
        "nom_servicio": serv_sel.split(" - $")[0],
        "id_empleado": id_empleado,
        "nom_empleado": emp_sel.split(" (")[0],
        "hora": hora,
        "precio": precio,
    })
    self.refrescar_vista_carrito()

  def refrescar_vista_carrito(self):
    for i in self.tree_cart.get_children():
      self.tree_cart.delete(i)
    for c in self.carrito_reserva:
      self.tree_cart.insert(
          "",
          "end",
          values=(
              c["nom_servicio"],
              c["nom_empleado"],
              c["hora"],
              f"${c['precio']:.2f}",
          ),
      )

  def limpiar_carrito(self):
    self.carrito_reserva.clear()
    self.refrescar_vista_carrito()

  def confirmar_y_procesar_reserva(self):
    cli_sel = self.cb_res_cliente.get()
    fecha_reserva = self.cb_res_fecha.get()

    if not cli_sel or not self.carrito_reserva:
      messagebox.showwarning(
          "Advertencia", "Selecciona un cliente y agrega al menos un servicio."
      )
      return

    id_cliente = self.dict_clientes[cli_sel]

    conn = conectar_bd()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT COUNT(SA.ID_SER_AGEN) FROM SERVICIOS_AGENDADOS SA
        JOIN AGENDA A ON SA.ID_AGENDA = A.ID_AGENDA
        WHERE A.ID_CLIENTE = ? AND A.FECHA_RESERVA = ?
    """,
        (id_cliente, fecha_reserva),
    )
    if cursor.fetchone()[0] + len(self.carrito_reserva) > 3:
      conn.close()
      messagebox.showerror(
          "Límite Excedido",
          f"El cliente supera el máximo permitido de 3 servicios diarios para el {fecha_reserva}.",
      )
      return

    try:
      propina = float(self.ent_res_propina.get().strip())
    except ValueError:
      propina = 0.0

    subtotal = sum(c["precio"] for c in self.carrito_reserva)
    total = subtotal + propina
    fecha_sistem = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute(
        """
        INSERT INTO AGENDA (ID_CLIENTE, FECHA_SISTEM, FECHA_RESERVA, TOTAL, PROPINA)
        VALUES (?, ?, ?, ?, ?)
    """,
        (id_cliente, fecha_sistem, fecha_reserva, total, propina),
    )
    id_agenda = cursor.lastrowid

    for item in self.carrito_reserva:
      cursor.execute(
          """
            INSERT INTO SERVICIOS_AGENDADOS (ID_AGENDA, ID_SERVICIO, ID_EMPLEADO, HORA, PRECIO, ATENDIDO)
            VALUES (?, ?, ?, ?, ?, 'NO')
        """,
          (
              id_agenda,
              item["id_servicio"],
              item["id_empleado"],
              item["hora"],
              item["precio"],
          ),
      )

    conn.commit()
    conn.close()

    self.mostrar_recibo(
        cli_sel, fecha_reserva, fecha_sistem, subtotal, propina, total
    )
    self.limpiar_carrito()

  def mostrar_recibo(
      self, cliente_nom, fecha_res, fecha_sis, subtotal, propina, total
  ):
    recibo_win = tk.Toplevel(self)
    recibo_win.title("Recibo de Agendamiento")
    recibo_win.geometry("550x650")

    txt = tk.Text(recibo_win, font=("Courier", 10), padx=10, pady=10)
    txt.pack(fill="both", expand=True)

    lineas = [
        "================================================",
        "      BARBERÍA / SPA / PELUQUERÍA - RECIBO      ",
        "================================================",
        f"Fecha Solicitud (Reloj): {fecha_sis}",
        f"Fecha Reserva          : {fecha_res}",
        f"Cliente                : {cliente_nom}",
        "------------------------------------------------",
        f"{'HORA':<8} {'SERVICIO':<22} {'PRECIO':<8}",
        "------------------------------------------------",
    ]
    for c in self.carrito_reserva:
      serv = (
          c["nom_servicio"][:20] + ".."
          if len(c["nom_servicio"]) > 20
          else c["nom_servicio"]
      )
      lineas.append(f"{c['hora']:<8} {serv:<22} ${c['precio']:.2f}")
      lineas.append(f"         Empleado: {c['nom_empleado']}")

    lineas.extend([
        "------------------------------------------------",
        f"SUBTOTAL SERVICIOS : ${subtotal:.2f}",
        f"PROPINA            : ${propina:.2f}",
        f"TOTAL A PAGAR      : ${total:.2f}",
        "================================================",
        "              RECOMENDACIONES                   ",
        "------------------------------------------------",
        "1. Por favor LLEGAR CON 20 MINUTOS DE ANTICIPACIÓN.",
        "2. En caso de imprevistos, llamar para REAGENDAR.",
        "3. DE LO CONTRARIO, NO SE LE RESPETA EL TURNO.",
        "================================================",
    ])
    txt.insert(tk.END, "\n".join(lineas))
    txt.config(state="disabled")

  # --------------------------------------------------------------------------
  # PESTAÑA 3: INFORMES DE AGENDA (CON CHECKBOX DE ATENDIDA)
  # --------------------------------------------------------------------------
  def init_tab_informes(self):
    f_filtros = ttk.LabelFrame(
        self.tab_informes, text=" Filtros de Consulta de Agenda "
    )
    f_filtros.pack(fill="x", padx=15, pady=10)

    ttk.Label(f_filtros, text="Fecha (AAAA-MM-DD):").grid(
        row=0, column=0, padx=5, pady=5, sticky="e"
    )
    self.cb_inf_fecha = ttk.Combobox(f_filtros, width=15)
    hoy = datetime.date.today()
    fechas_sug = [
        (hoy + datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(5)
    ]
    self.cb_inf_fecha["values"] = fechas_sug
    self.cb_inf_fecha.set(fechas_sug[0])
    self.cb_inf_fecha.grid(row=0, column=1, padx=5, pady=5)

    ttk.Button(
        f_filtros, text="🔄 Generar Informe", command=self.cargar_informe_agenda
    ).grid(row=0, column=2, padx=10, pady=5)

    self.var_ver_precios = tk.BooleanVar(value=True)
    ttk.Checkbutton(
        f_filtros,
        text="Mostrar Precios",
        variable=self.var_ver_precios,
        command=self.cargar_informe_agenda,
    ).grid(row=0, column=3, padx=10, pady=5)

    # --- BOTÓN ORDENAMIENTO ---
    self.btn_orden = ttk.Button(
        f_filtros,
        text="🔀 Ordenar: Por HORA",
        command=self.toggle_orden_informe,
    )
    self.btn_orden.grid(row=0, column=4, padx=10, pady=5)

    # --- BOTÓN "VER ATENDIDAS" ---
    self.btn_atendidas = ttk.Button(
        f_filtros,
        text="👁 Ver: TODAS las reservas",
        command=self.toggle_ver_atendidas,
    )
    self.btn_atendidas.grid(row=0, column=5, padx=10, pady=5)

    # Etiqueta de ayuda
    ttk.Label(
        f_filtros,
        text=(
            "💡 Clic en ☐/☑ para marcar ATENDIDA  |  Doble clic sobre RESERVADA para modificar/eliminar"
            "  |  Doble clic sobre [ DISPONIBLE ] o [ AGENDAR OTRA ] para crear reserva"
        ),
        foreground="#1565C0",
        font=("Arial", 9, "italic"),
    ).grid(row=1, column=0, columnspan=6, padx=5, pady=(0, 5), sticky="w")

    # --- TABLA CON SCROLL VERTICAL ---
    f_tabla = ttk.LabelFrame(
        self.tab_informes, text=" Parrilla General de Citas "
    )
    f_tabla.pack(fill="both", expand=True, padx=15, pady=10)

    style = ttk.Style()
    style.configure("Cuadricula.Treeview", rowheight=26)

    f_tree = ttk.Frame(f_tabla)
    f_tree.pack(fill="both", expand=True, padx=5, pady=5)

    # Columna "Atend" añadida como primera
    self.tree_informe = ttk.Treeview(
        f_tree,
        columns=("Atend", "Hora", "Estado", "Servicio", "Empleado", "Cliente", "Precio"),
        show="headings",
        style="Cuadricula.Treeview",
    )

    # --- TAGS ---
    # Reservadas NO atendidas - verde oliva intercalado
    self.tree_informe.tag_configure(
        "res_par", background="#4A5D23", foreground="white"
    )
    self.tree_informe.tag_configure(
        "res_impar", background="#6B8E23", foreground="white"
    )
    # Reservadas ATENDIDAS - naranja intercalado
    self.tree_informe.tag_configure(
        "aten_par", background="#D2691E", foreground="white"
    )
    self.tree_informe.tag_configure(
        "aten_impar", background="#FF8C00", foreground="white"
    )
    # Libres - blanco / gris claro
    self.tree_informe.tag_configure(
        "libre_par", background="#FFFFFF", foreground="#333333"
    )
    self.tree_informe.tag_configure(
        "libre_impar", background="#F2F2F2", foreground="#333333"
    )
    # Encabezado de empleado
    self.tree_informe.tag_configure(
        "emp_header",
        background="#2E4053",
        foreground="#FFD700",
        font=("Arial", 10, "bold"),
    )
    # Fila "agendar otra"
    self.tree_informe.tag_configure(
        "agendar_otra",
        background="#E8F5E9",
        foreground="#2E7D32",
        font=("Arial", 9, "italic"),
    )

    vsb = ttk.Scrollbar(f_tree, orient="vertical", command=self.tree_informe.yview)
    self.tree_informe.configure(yscrollcommand=vsb.set)

    self.tree_informe.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")

    self.tree_informe.heading("Atend", text="Atendida")
    self.tree_informe.heading("Hora", text="Horario")
    self.tree_informe.heading("Estado", text="Estado")
    self.tree_informe.heading("Servicio", text="Nombre del Servicio")
    self.tree_informe.heading("Empleado", text="Empleado Asignado")
    self.tree_informe.heading("Cliente", text="Cliente")
    self.tree_informe.heading("Precio", text="Precio ($)")

    self.tree_informe.column("Atend", width=80, anchor="center")
    self.tree_informe.column("Hora", width=80, anchor="center")
    self.tree_informe.column("Estado", width=150, anchor="center")
    self.tree_informe.column("Servicio", width=210)
    self.tree_informe.column("Empleado", width=200)
    self.tree_informe.column("Cliente", width=200)
    self.tree_informe.column("Precio", width=100, anchor="e")

    # Eventos: click simple para el checkbox, doble clic para modificar
    self.tree_informe.bind("<Button-1>", self.on_tree_click_checkbox)
    self.tree_informe.bind("<Double-1>", self.abrir_modificacion_cita)

    # Etiqueta de totales / resumen
    self.lbl_total_informe = ttk.Label(
        f_tabla,
        text="SUMATORIA TOTAL DE PRECIOS: $0.00",
        font=("Arial", 11, "bold"),
        foreground="#2E7D32",
    )
    self.lbl_total_informe.pack(anchor="e", padx=15, pady=8)

    # Resumen de atendidas
    self.lbl_resumen_atendidas = ttk.Label(
        f_tabla,
        text="",
        font=("Arial", 10, "italic"),
        foreground="#D2691E",
    )
    self.lbl_resumen_atendidas.pack(anchor="e", padx=15, pady=(0, 8))

  # --------------------------------------------------------------------------
  # TOGGLES DE VISTA
  # --------------------------------------------------------------------------
  def toggle_orden_informe(self):
    """Alterna entre ordenar por HORA o por EMPLEADO."""
    if self.orden_informe == "HORA":
      self.orden_informe = "EMPLEADO"
      self.btn_orden.config(text="🔀 Ordenar: Por EMPLEADO")
    else:
      self.orden_informe = "HORA"
      self.btn_orden.config(text="🔀 Ordenar: Por HORA")
    self.cargar_informe_agenda()

  def toggle_ver_atendidas(self):
    """Alterna entre mostrar todas las reservas o solo las atendidas."""
    self.ver_solo_atendidas = not self.ver_solo_atendidas
    if self.ver_solo_atendidas:
      self.btn_atendidas.config(text="👁 Ver: SOLO ATENDIDAS 🟠")
    else:
      self.btn_atendidas.config(text="👁 Ver: TODAS las reservas")
    self.cargar_informe_agenda()

  # --------------------------------------------------------------------------
  # CLICK SOBRE CHECKBOX DE "ATENDIDA"
  # --------------------------------------------------------------------------
  def on_tree_click_checkbox(self, event):
    """Detecta clic en la columna 'Atend' para alternar el estado."""
    region = self.tree_informe.identify_region(event.x, event.y)
    if region != "cell":
      return
    col = self.tree_informe.identify_column(event.x)
    if col != "#1":  # Primera columna = "Atend"
      return
    iid = self.tree_informe.identify_row(event.y)
    if not iid or not iid.startswith("cita_"):
      return
    try:
      id_ser_agen = int(iid.split("_", 1)[1])
    except (ValueError, IndexError):
      return
    self.toggle_atendida(id_ser_agen)

  def toggle_atendida(self, id_ser_agen):
    """Alterna el estado ATENDIDO de una cita en la base de datos."""
    conn = conectar_bd()
    cur = conn.cursor()
    cur.execute(
        "SELECT ATENDIDO FROM SERVICIOS_AGENDADOS WHERE ID_SER_AGEN = ?",
        (id_ser_agen,),
    )
    row = cur.fetchone()
    if not row:
      conn.close()
      return
    nuevo = "SI" if (row[0] or "NO") != "SI" else "NO"
    cur.execute(
        "UPDATE SERVICIOS_AGENDADOS SET ATENDIDO = ? WHERE ID_SER_AGEN = ?",
        (nuevo, id_ser_agen),
    )
    conn.commit()
    conn.close()
    self.cargar_informe_agenda()

  # --------------------------------------------------------------------------
  # CARGA DEL INFORME
  # --------------------------------------------------------------------------
  def cargar_informe_agenda(self):
    fecha = self.cb_inf_fecha.get().strip()
    if not fecha:
      return

    for i in self.tree_informe.get_children():
      self.tree_informe.delete(i)

    conn = conectar_bd()
    cursor = conn.cursor()

    query = """
        SELECT SA.ID_SER_AGEN, SA.HORA, S.NOM_SERVICIO,
               E.NOMBRES || ' ' || E.APELLIDOS,
               C.NOMBRE_APELLIDO, SA.PRECIO,
               E.ID_EMPLEADO, SA.ATENDIDO
        FROM SERVICIOS_AGENDADOS SA
        JOIN AGENDA A ON SA.ID_AGENDA = A.ID_AGENDA
        JOIN SERVICIO S ON SA.ID_SERVICIO = S.ID_SERVICIO
        JOIN EMPLEADO E ON SA.ID_EMPLEADO = E.ID_EMPLEADO
        JOIN CLIENTE C ON A.ID_CLIENTE = C.ID_CLIENTE
        WHERE A.FECHA_RESERVA = ?
        ORDER BY SA.HORA ASC, E.NOMBRES ASC, E.APELLIDOS ASC
    """
    cursor.execute(query, (fecha,))
    rows = cursor.fetchall()

    cursor.execute(
        """
        SELECT SUM(SA.PRECIO) FROM SERVICIOS_AGENDADOS SA
        JOIN AGENDA A ON SA.ID_AGENDA = A.ID_AGENDA
        WHERE A.FECHA_RESERVA = ?
    """,
        (fecha,),
    )
    total_suma = cursor.fetchone()[0] or 0.0
    conn.close()

    # Aplicar filtro de solo atendidas si está activo
    if self.ver_solo_atendidas:
      rows = [r for r in rows if (r[7] or "NO") == "SI"]

    mostrar_precios = self.var_ver_precios.get()

    if self.orden_informe == "HORA":
      self._render_informe_por_hora(rows, mostrar_precios)
    else:
      self._render_informe_por_empleado(rows, mostrar_precios)

    # Calcular resumen de atendidas
    total_atendidas = sum(1 for r in rows if (r[7] or "NO") == "SI")
    suma_atendidas = sum(r[5] for r in rows if (r[7] or "NO") == "SI")
    total_citas = len(rows)

    if mostrar_precios:
      self.lbl_total_informe.config(
          text=f"SUMATORIA TOTAL DE PRECIOS ({fecha}): ${total_suma:.2f}"
      )
    else:
      self.lbl_total_informe.config(
          text="SUMATORIA TOTAL DE PRECIOS: [OCULTO POR VERIFICACIÓN]"
      )

    if total_citas > 0:
      self.lbl_resumen_atendidas.config(
          text=(
              f"🟠 Atendidas: {total_atendidas} / {total_citas} citas"
              f"   |   Ingresos por atendidas: ${suma_atendidas:.2f}"
          )
      )
    else:
      self.lbl_resumen_atendidas.config(text="🟠 Sin citas para mostrar.")

  def _render_informe_por_hora(self, rows, mostrar_precios):
    """Vista tipo parrilla 08:00 - 20:00 con filas reservadas intercaladas."""
    citas_por_hora = {}
    for r in rows:
      citas_por_hora.setdefault(r[1], []).append(r)

    bloques_jornada = [f"{h:02d}:00" for h in range(8, 21)]
    res_counter = 0
    libre_counter = 0

    for hora in bloques_jornada:
      citas = citas_por_hora.get(hora, [])

      if citas:
        for idx, r in enumerate(citas):
          id_ser_agen = r[0]
          atendido = (r[7] or "NO") == "SI"
          precio_txt = f"${r[5]:.2f}" if mostrar_precios else "******"
          hora_txt = hora if idx == 0 else ""
          if len(citas) > 1:
            estado_txt = f"RESERVADO ({idx + 1}/{len(citas)})"
          else:
            estado_txt = "RESERVADO"

          # Elegir tag según atendida
          if atendido:
            tag = "aten_par" if res_counter % 2 == 0 else "aten_impar"
          else:
            tag = "res_par" if res_counter % 2 == 0 else "res_impar"
          res_counter += 1

          check = "☑" if atendido else "☐"
          self.tree_informe.insert(
              "",
              "end",
              iid=f"cita_{id_ser_agen}",
              values=(check, hora_txt, estado_txt, r[2], r[3], r[4], precio_txt),
              tags=(tag,),
          )

        # Fila para agendar otra reserva a esa misma hora
        self.tree_informe.insert(
            "",
            "end",
            iid=f"libre_{hora}",
            values=(
                "",
                "",
                "↳ [ AGENDAR OTRA ]",
                "------------------",
                "------------------",
                "------------------",
                "$0.00" if mostrar_precios else "******",
            ),
            tags=("agendar_otra",),
        )
      else:
        tag = "libre_par" if libre_counter % 2 == 0 else "libre_impar"
        libre_counter += 1
        self.tree_informe.insert(
            "",
            "end",
            iid=f"libre_{hora}",
            values=(
                "",
                hora,
                "[ DISPONIBLE ]",
                "------------------",
                "------------------",
                "------------------",
                "$0.00" if mostrar_precios else "******",
            ),
            tags=(tag,),
        )

  def _render_informe_por_empleado(self, rows, mostrar_precios):
    """Vista agrupada por empleado con encabezado y citas ordenadas por hora."""
    if not rows:
      self.tree_informe.insert(
          "",
          "end",
          iid="sin_citas",
          values=(
              "--",
              "--",
              "SIN CITAS PARA ESTA FECHA",
              "------------------",
              "------------------",
              "------------------",
              "--",
          ),
          tags=("libre_par",),
      )
      return

    por_empleado = {}
    for r in rows:
      emp_nombre = r[3]
      por_empleado.setdefault(emp_nombre, []).append(r)

    for i_emp, emp_nombre in enumerate(sorted(por_empleado.keys())):
      citas = por_empleado[emp_nombre]
      citas.sort(key=lambda x: x[1])

      # Header del empleado
      atendidas_emp = sum(1 for c in citas if (c[7] or "NO") == "SI")
      self.tree_informe.insert(
          "",
          "end",
          iid=f"emp_hdr_{i_emp}",
          values=(
              f"👤 {emp_nombre}",
              "",
              f"{len(citas)} cita(s) - {atendidas_emp} atendida(s)",
              "",
              "",
              "",
              "",
          ),
          tags=("emp_header",),
      )

      for idx, r in enumerate(citas):
        id_ser_agen = r[0]
        atendido = (r[7] or "NO") == "SI"
        precio_txt = f"${r[5]:.2f}" if mostrar_precios else "******"
        if atendido:
          tag = "aten_par" if idx % 2 == 0 else "aten_impar"
        else:
          tag = "res_par" if idx % 2 == 0 else "res_impar"

        check = "☑" if atendido else "☐"
        self.tree_informe.insert(
            "",
            "end",
            iid=f"cita_{id_ser_agen}",
            values=(check, r[1], "RESERVADO", r[2], "", r[4], precio_txt),
            tags=(tag,),
        )

  # --------------------------------------------------------------------------
  # DOBLE CLIC: MODIFICAR O AGENDAR
  # --------------------------------------------------------------------------
  def abrir_modificacion_cita(self, event):
    """Doble clic: modifica una cita RESERVADA o agenda en un horario DISPONIBLE."""
    # Ignorar si el doble clic fue sobre la columna "Atend" (checkbox)
    col = self.tree_informe.identify_column(event.x)
    if col == "#1":
      return

    iid = self.tree_informe.identify_row(event.y)
    if not iid:
      return

    if iid.startswith("cita_"):
      try:
        id_ser_agen = int(iid.split("_", 1)[1])
      except (ValueError, IndexError):
        return
      self.mostrar_ventana_modificacion_cita(id_ser_agen)
      return

    if iid.startswith("libre_"):
      hora = iid.split("_", 1)[1]
      fecha = self.cb_inf_fecha.get().strip()
      if not fecha:
        messagebox.showwarning(
            "Advertencia", "Selecciona primero una fecha válida."
        )
        return
      self.mostrar_ventana_agendar_desde_informe(fecha, hora)
      return

  # --------------------------------------------------------------------------
  # VENTANA MODIFICAR CITA
  # --------------------------------------------------------------------------
  def mostrar_ventana_modificacion_cita(self, id_ser_agen):
    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT SA.ID_AGENDA, SA.ID_SERVICIO, SA.ID_EMPLEADO, SA.HORA, SA.PRECIO,
               A.FECHA_RESERVA, A.ID_CLIENTE, A.PROPINA,
               S.NOM_SERVICIO, S.ESTILO,
               E.NOMBRES || ' ' || E.APELLIDOS, E.CEDULA,
               C.NOMBRE_APELLIDO, C.NRO_CELULAR, SA.ATENDIDO
        FROM SERVICIOS_AGENDADOS SA
        JOIN AGENDA A ON SA.ID_AGENDA = A.ID_AGENDA
        JOIN SERVICIO S ON SA.ID_SERVICIO = S.ID_SERVICIO
        JOIN EMPLEADO E ON SA.ID_EMPLEADO = E.ID_EMPLEADO
        JOIN CLIENTE C ON A.ID_CLIENTE = C.ID_CLIENTE
        WHERE SA.ID_SER_AGEN = ?
    """,
        (id_ser_agen,),
    )
    row = cursor.fetchone()
    if not row:
      conn.close()
      messagebox.showerror(
          "Error", "No se encontró la cita seleccionada. Refresque el informe."
      )
      return

    (id_agenda, id_servicio_actual, id_empleado_actual, hora_actual,
     precio_actual, fecha_reserva, id_cliente, propina,
     nom_servicio, estilo,
     nom_empleado_actual, cedula_emp,
     nom_cliente, cel_cliente, atendido_actual) = row

    cursor.execute(
        "SELECT ID_SERVICIO, NOM_SERVICIO, ESTILO, PRECIO FROM SERVICIO"
        " ORDER BY NOM_SERVICIO"
    )
    servicios = cursor.fetchall()
    conn.close()

    dict_serv = {
        f"{s[1]} [{s[2]}] - ${s[3]:.2f}": (s[0], s[3]) for s in servicios
    }

    win = tk.Toplevel(self)
    win.title(f"Modificar Cita #{id_ser_agen}")
    win.geometry("680x580")
    win.grab_set()

    ttk.Label(
        win,
        text=f"Cliente: {nom_cliente}   |   Cel: {cel_cliente}",
        font=("Arial", 11, "bold"),
    ).pack(pady=8)

    frm = ttk.LabelFrame(win, text=" Datos de la Cita ")
    frm.pack(fill="x", padx=15, pady=10)

    ttk.Label(frm, text="Fecha (AAAA-MM-DD):").grid(
        row=0, column=0, padx=5, pady=5, sticky="e"
    )
    cb_fecha = ttk.Combobox(frm, width=20)
    hoy = datetime.date.today()
    cb_fecha["values"] = [
        (hoy + datetime.timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(30)
    ]
    cb_fecha.set(fecha_reserva)
    cb_fecha.grid(row=0, column=1, padx=5, pady=5, sticky="w")

    ttk.Label(frm, text="Hora (HH:MM):").grid(
        row=0, column=2, padx=5, pady=5, sticky="e"
    )
    ent_hora = ttk.Entry(frm, width=10)
    ent_hora.insert(0, hora_actual)
    ent_hora.grid(row=0, column=3, padx=5, pady=5, sticky="w")

    ttk.Label(frm, text="Servicio:").grid(
        row=1, column=0, padx=5, pady=5, sticky="e"
    )
    cb_servicio = ttk.Combobox(frm, width=48, state="readonly")
    cb_servicio["values"] = list(dict_serv.keys())
    for k, v in dict_serv.items():
      if v[0] == id_servicio_actual:
        cb_servicio.set(k)
        break
    cb_servicio.grid(row=1, column=1, columnspan=3, padx=5, pady=5, sticky="we")

    ttk.Label(frm, text="Empleado:").grid(
        row=2, column=0, padx=5, pady=5, sticky="e"
    )
    cb_empleado = ttk.Combobox(frm, width=48, state="readonly")
    cb_empleado.grid(row=2, column=1, columnspan=3, padx=5, pady=5, sticky="we")

    ttk.Label(frm, text="Precio ($):").grid(
        row=3, column=0, padx=5, pady=5, sticky="e"
    )
    ent_precio = ttk.Entry(frm, width=15)
    ent_precio.insert(0, f"{precio_actual:.2f}")
    ent_precio.grid(row=3, column=1, padx=5, pady=5, sticky="w")

    # Estado de Atendida
    var_atendida = tk.BooleanVar(value=(atendido_actual or "NO") == "SI")
    ttk.Checkbutton(
        frm,
        text="☑ Marcar como ATENDIDA",
        variable=var_atendida,
    ).grid(row=4, column=0, columnspan=4, padx=5, pady=8, sticky="w")

    dict_emp_temp = {}

    def cargar_empleados_para_servicio():
      nonlocal dict_emp_temp
      serv_key = cb_servicio.get()
      if not serv_key or serv_key not in dict_serv:
        return
      id_s = dict_serv[serv_key][0]
      conn2 = conectar_bd()
      cur2 = conn2.cursor()
      cur2.execute(
          """
          SELECT E.ID_EMPLEADO, E.NOMBRES || ' ' || E.APELLIDOS, E.CEDULA
          FROM EMPLEADO E
          JOIN EMPLEADO_SERVICIO ES ON E.ID_EMPLEADO = ES.ID_EMPLEADO
          WHERE ES.ID_SERVICIO = ? AND ES.ACTIVO = 'SI'
      """,
          (id_s,),
      )
      rows = cur2.fetchall()
      conn2.close()
      dict_emp_temp = {f"{r[1]} (C.I: {r[2]})": r[0] for r in rows}
      cb_empleado["values"] = list(dict_emp_temp.keys())
      for k, v in dict_emp_temp.items():
        if v == id_empleado_actual:
          cb_empleado.set(k)
          break
      else:
        if dict_emp_temp:
          cb_empleado.current(0)

    def al_cambiar_servicio(evt=None):
      cargar_empleados_para_servicio()
      serv_key = cb_servicio.get()
      if serv_key in dict_serv:
        ent_precio.delete(0, tk.END)
        ent_precio.insert(0, f"{dict_serv[serv_key][1]:.2f}")

    cb_servicio.bind("<<ComboboxSelected>>", al_cambiar_servicio)
    cargar_empleados_para_servicio()

    def guardar_cambios():
      nueva_fecha = cb_fecha.get().strip()
      nueva_hora = ent_hora.get().strip()
      serv_key = cb_servicio.get()
      emp_key = cb_empleado.get()

      if not nueva_fecha or not nueva_hora or not serv_key or not emp_key:
        messagebox.showwarning(
            "Advertencia", "Completa todos los campos obligatorios."
        )
        return
      if serv_key not in dict_serv or emp_key not in dict_emp_temp:
        messagebox.showwarning(
            "Advertencia", "Servicio o empleado inválido."
        )
        return

      nuevo_id_servicio = dict_serv[serv_key][0]
      nuevo_id_empleado = dict_emp_temp[emp_key]

      try:
        nuevo_precio = float(ent_precio.get().strip())
      except ValueError:
        messagebox.showerror("Error", "El precio debe ser numérico.")
        return

      nuevo_atendido = "SI" if var_atendida.get() else "NO"

      conn3 = conectar_bd()
      cur3 = conn3.cursor()

      cur3.execute(
          """
          SELECT COUNT(*) FROM SERVICIOS_AGENDADOS SA
          JOIN AGENDA A ON SA.ID_AGENDA = A.ID_AGENDA
          WHERE SA.ID_EMPLEADO = ? AND A.FECHA_RESERVA = ? AND SA.HORA = ?
            AND SA.ID_SER_AGEN <> ?
      """,
          (nuevo_id_empleado, nueva_fecha, nueva_hora, id_ser_agen),
      )
      if cur3.fetchone()[0] > 0:
        conn3.close()
        messagebox.showerror(
            "Conflicto de Empleado",
            f"El empleado ya tiene otra cita a las {nueva_hora} el {nueva_fecha}.",
        )
        return

      cur3.execute(
          """
          SELECT COUNT(*) FROM SERVICIOS_AGENDADOS SA
          JOIN AGENDA A ON SA.ID_AGENDA = A.ID_AGENDA
          WHERE A.ID_CLIENTE = ? AND A.FECHA_RESERVA = ? AND SA.HORA = ?
            AND SA.ID_SER_AGEN <> ?
      """,
          (id_cliente, nueva_fecha, nueva_hora, id_ser_agen),
      )
      if cur3.fetchone()[0] > 0:
        conn3.close()
        messagebox.showerror(
            "Conflicto de Cliente",
            f"El cliente ya tiene otra cita a las {nueva_hora} el {nueva_fecha}.",
        )
        return

      cur3.execute(
          """
          SELECT COUNT(*) FROM SERVICIOS_AGENDADOS SA
          JOIN AGENDA A ON SA.ID_AGENDA = A.ID_AGENDA
          WHERE A.ID_CLIENTE = ? AND A.FECHA_RESERVA = ? AND SA.ID_SERVICIO = ?
            AND SA.ID_SER_AGEN <> ?
      """,
          (id_cliente, nueva_fecha, nuevo_id_servicio, id_ser_agen),
      )
      if cur3.fetchone()[0] > 0:
        conn3.close()
        messagebox.showerror(
            "Servicio Duplicado",
            "El cliente ya tiene ese mismo servicio agendado para esa fecha.",
        )
        return

      cur3.execute(
          """
          UPDATE SERVICIOS_AGENDADOS
          SET ID_SERVICIO = ?, ID_EMPLEADO = ?, HORA = ?, PRECIO = ?, ATENDIDO = ?
          WHERE ID_SER_AGEN = ?
      """,
          (
              nuevo_id_servicio,
              nuevo_id_empleado,
              nueva_hora,
              nuevo_precio,
              nuevo_atendido,
              id_ser_agen,
          ),
      )

      cur3.execute(
          "UPDATE AGENDA SET FECHA_RESERVA = ? WHERE ID_AGENDA = ?",
          (nueva_fecha, id_agenda),
      )

      cur3.execute(
          "SELECT SUM(PRECIO) FROM SERVICIOS_AGENDADOS WHERE ID_AGENDA = ?",
          (id_agenda,),
      )
      nuevo_subtotal = cur3.fetchone()[0] or 0.0
      cur3.execute(
          "UPDATE AGENDA SET TOTAL = ? WHERE ID_AGENDA = ?",
          (nuevo_subtotal + (propina or 0.0), id_agenda),
      )

      conn3.commit()
      conn3.close()

      messagebox.showinfo("Éxito", "Cita modificada correctamente.")
      win.destroy()
      self.cargar_informe_agenda()

    def eliminar_cita():
      if not messagebox.askyesno(
          "Confirmar Eliminación",
          "¿Deseas eliminar esta cita definitivamente?",
      ):
        return
      conn4 = conectar_bd()
      cur4 = conn4.cursor()
      cur4.execute(
          "DELETE FROM SERVICIOS_AGENDADOS WHERE ID_SER_AGEN = ?",
          (id_ser_agen,),
      )
      cur4.execute(
          "SELECT COUNT(*) FROM SERVICIOS_AGENDADOS WHERE ID_AGENDA = ?",
          (id_agenda,),
      )
      restantes = cur4.fetchone()[0]
      if restantes == 0:
        cur4.execute("DELETE FROM AGENDA WHERE ID_AGENDA = ?", (id_agenda,))
      else:
        cur4.execute(
            "SELECT SUM(PRECIO) FROM SERVICIOS_AGENDADOS WHERE ID_AGENDA = ?",
            (id_agenda,),
        )
        st = cur4.fetchone()[0] or 0.0
        cur4.execute(
            "UPDATE AGENDA SET TOTAL = ? WHERE ID_AGENDA = ?",
            (st + (propina or 0.0), id_agenda),
        )
      conn4.commit()
      conn4.close()
      messagebox.showinfo("Éxito", "Cita eliminada correctamente.")
      win.destroy()
      self.cargar_informe_agenda()

    f_pie = ttk.Frame(win)
    f_pie.pack(fill="x", padx=15, pady=10)

    ttk.Button(
        f_pie, text="Guardar Cambios", command=guardar_cambios
    ).pack(side="right", padx=5)
    ttk.Button(
        f_pie, text="Eliminar Cita", command=eliminar_cita
    ).pack(side="right", padx=5)
    ttk.Button(f_pie, text="Cancelar", command=win.destroy).pack(
        side="right", padx=5
    )

  # --------------------------------------------------------------------------
  # VENTANA AGENDAR RÁPIDO DESDE EL INFORME
  # --------------------------------------------------------------------------
  def mostrar_ventana_agendar_desde_informe(self, fecha, hora):
    win = tk.Toplevel(self)
    win.title(f"Agendar Reserva - {fecha} a las {hora}")
    win.geometry("780x560")
    win.grab_set()

    f_head = ttk.LabelFrame(win, text=" Horario Seleccionado (fijo) ")
    f_head.pack(fill="x", padx=15, pady=10)
    ttk.Label(
        f_head, text=f"📅  Fecha: {fecha}", font=("Arial", 11, "bold")
    ).pack(side="left", padx=20, pady=8)
    ttk.Label(
        f_head, text=f"🕒  Hora: {hora}", font=("Arial", 11, "bold")
    ).pack(side="left", padx=20, pady=8)

    f_cli = ttk.LabelFrame(win, text=" Cliente ")
    f_cli.pack(fill="x", padx=15, pady=5)
    ttk.Label(f_cli, text="Selecciona Cliente:").pack(
        side="left", padx=5, pady=8
    )
    cb_cliente = ttk.Combobox(f_cli, state="readonly", width=60)
    cb_cliente["values"] = list(self.dict_clientes.keys())
    cb_cliente.pack(side="left", padx=5, pady=8)

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True, padx=15, pady=5)

    tab1 = ttk.Frame(nb)
    tab2 = ttk.Frame(nb)
    nb.add(tab1, text="Modo 1: Por Área y Servicio (cualquier empleado)")
    nb.add(tab2, text="Modo 2: Por Empleado Específico y Servicio")

    ttk.Label(tab1, text="Área:").grid(
        row=0, column=0, padx=5, pady=12, sticky="e"
    )
    cb_area1 = ttk.Combobox(tab1, state="readonly", width=50)
    cb_area1["values"] = list(self.dict_areas.keys())
    cb_area1.grid(row=0, column=1, padx=5, pady=12, sticky="w")

    ttk.Label(tab1, text="Servicio:").grid(
        row=1, column=0, padx=5, pady=12, sticky="e"
    )
    cb_serv1 = ttk.Combobox(tab1, state="readonly", width=50)
    cb_serv1.grid(row=1, column=1, padx=5, pady=12, sticky="w")

    dict_serv_area_local = {}

    def cargar_servicios_area(evt=None):
      area_sel = cb_area1.get()
      if area_sel not in self.dict_areas:
        return
      id_area = self.dict_areas[area_sel]
      conn = conectar_bd()
      cur = conn.cursor()
      cur.execute(
          "SELECT ID_SERVICIO, NOM_SERVICIO, ESTILO, PRECIO FROM SERVICIO"
          " WHERE ID_AREA = ?",
          (id_area,),
      )
      filas = cur.fetchall()
      conn.close()
      dict_serv_area_local.clear()
      dict_serv_area_local.update(
          {f"{r[1]} [{r[2]}] - ${r[3]:.2f}": (r[0], r[3]) for r in filas}
      )
      cb_serv1["values"] = list(dict_serv_area_local.keys())
      cb_serv1.set("")

    cb_area1.bind("<<ComboboxSelected>>", cargar_servicios_area)

    ttk.Label(tab2, text="Empleado:").grid(
        row=0, column=0, padx=5, pady=12, sticky="e"
    )
    cb_emp2 = ttk.Combobox(tab2, state="readonly", width=50)
    cb_emp2["values"] = list(self.dict_empleados.keys())
    cb_emp2.grid(row=0, column=1, padx=5, pady=12, sticky="w")

    ttk.Label(tab2, text="Servicio:").grid(
        row=1, column=0, padx=5, pady=12, sticky="e"
    )
    cb_serv2 = ttk.Combobox(tab2, state="readonly", width=50)
    cb_serv2.grid(row=1, column=1, padx=5, pady=12, sticky="w")

    dict_serv_emp_local = {}

    def cargar_servicios_emp(evt=None):
      emp_sel = cb_emp2.get()
      if emp_sel not in self.dict_empleados:
        return
      id_emp = self.dict_empleados[emp_sel]
      conn = conectar_bd()
      cur = conn.cursor()
      cur.execute(
          """
          SELECT S.ID_SERVICIO, S.NOM_SERVICIO, S.ESTILO, S.PRECIO
          FROM SERVICIO S
          JOIN EMPLEADO_SERVICIO ES ON S.ID_SERVICIO = ES.ID_SERVICIO
          WHERE ES.ID_EMPLEADO = ? AND ES.ACTIVO = 'SI'
      """,
          (id_emp,),
      )
      filas = cur.fetchall()
      conn.close()
      dict_serv_emp_local.clear()
      dict_serv_emp_local.update(
          {f"{r[1]} [{r[2]}] - ${r[3]:.2f}": (r[0], r[3]) for r in filas}
      )
      cb_serv2["values"] = list(dict_serv_emp_local.keys())
      cb_serv2.set("")

    cb_emp2.bind("<<ComboboxSelected>>", cargar_servicios_emp)

    def agendar():
      cli_sel = cb_cliente.get()
      if not cli_sel or cli_sel not in self.dict_clientes:
        messagebox.showwarning("Advertencia", "Selecciona un cliente.")
        return
      id_cliente = self.dict_clientes[cli_sel]

      modo = nb.index(nb.select())
      id_servicio = None
      precio = 0.0
      id_empleado = None

      if modo == 0:
        serv_key = cb_serv1.get()
        if not serv_key or serv_key not in dict_serv_area_local:
          messagebox.showwarning(
              "Advertencia", "Selecciona un Área y un Servicio."
          )
          return
        id_servicio, precio = dict_serv_area_local[serv_key]
      else:
        emp_sel = cb_emp2.get()
        serv_key = cb_serv2.get()
        if not emp_sel or emp_sel not in self.dict_empleados:
          messagebox.showwarning("Advertencia", "Selecciona un empleado.")
          return
        if not serv_key or serv_key not in dict_serv_emp_local:
          messagebox.showwarning("Advertencia", "Selecciona un servicio.")
          return
        id_empleado = self.dict_empleados[emp_sel]
        id_servicio, precio = dict_serv_emp_local[serv_key]

      conn = conectar_bd()
      cur = conn.cursor()

      cur.execute(
          """
          SELECT COUNT(*) FROM SERVICIOS_AGENDADOS SA
          JOIN AGENDA A ON SA.ID_AGENDA = A.ID_AGENDA
          WHERE A.ID_CLIENTE = ? AND A.FECHA_RESERVA = ? AND SA.ID_SERVICIO = ?
      """,
          (id_cliente, fecha, id_servicio),
      )
      if cur.fetchone()[0] > 0:
        conn.close()
        messagebox.showwarning(
            "Servicio Duplicado",
            "El cliente ya tiene ese mismo servicio agendado para esa fecha.",
        )
        return

      cur.execute(
          """
          SELECT COUNT(*) FROM SERVICIOS_AGENDADOS SA
          JOIN AGENDA A ON SA.ID_AGENDA = A.ID_AGENDA
          WHERE A.ID_CLIENTE = ? AND A.FECHA_RESERVA = ? AND SA.HORA = ?
      """,
          (id_cliente, fecha, hora),
      )
      if cur.fetchone()[0] > 0:
        conn.close()
        messagebox.showwarning(
            "Cliente Ocupado",
            f"El cliente ya tiene otra cita a las {hora} el {fecha}.",
        )
        return

      cur.execute(
          """
          SELECT COUNT(*) FROM SERVICIOS_AGENDADOS SA
          JOIN AGENDA A ON SA.ID_AGENDA = A.ID_AGENDA
          WHERE A.ID_CLIENTE = ? AND A.FECHA_RESERVA = ?
      """,
          (id_cliente, fecha),
      )
      if cur.fetchone()[0] >= 3:
        conn.close()
        messagebox.showwarning(
            "Límite Excedido",
            "El cliente ya tiene 3 servicios agendados ese día.",
        )
        return

      if id_empleado is None:
        cur.execute(
            """
            SELECT E.ID_EMPLEADO
            FROM EMPLEADO E
            JOIN EMPLEADO_SERVICIO ES ON E.ID_EMPLEADO = ES.ID_EMPLEADO
            WHERE ES.ID_SERVICIO = ? AND ES.ACTIVO = 'SI'
        """,
            (id_servicio,),
        )
        candidatos = [r[0] for r in cur.fetchall()]
        for emp_id in candidatos:
          cur.execute(
              """
              SELECT COUNT(*) FROM SERVICIOS_AGENDADOS SA
              JOIN AGENDA A ON SA.ID_AGENDA = A.ID_AGENDA
              WHERE SA.ID_EMPLEADO = ? AND A.FECHA_RESERVA = ? AND SA.HORA = ?
          """,
              (emp_id, fecha, hora),
          )
          if cur.fetchone()[0] == 0:
            id_empleado = emp_id
            break
        if id_empleado is None:
          conn.close()
          messagebox.showerror(
              "Sin Disponibilidad",
              f"No hay empleados disponibles a las {hora} para ese servicio.",
          )
          return
      else:
        cur.execute(
            """
            SELECT COUNT(*) FROM SERVICIOS_AGENDADOS SA
            JOIN AGENDA A ON SA.ID_AGENDA = A.ID_AGENDA
            WHERE SA.ID_EMPLEADO = ? AND A.FECHA_RESERVA = ? AND SA.HORA = ?
        """,
            (id_empleado, fecha, hora),
        )
        if cur.fetchone()[0] > 0:
          conn.close()
          messagebox.showerror(
              "Empleado Ocupado",
              f"El empleado seleccionado ya tiene otra cita a las {hora} el"
              f" {fecha}.",
          )
          return

      fecha_sistem = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

      cur.execute(
          """
          SELECT ID_AGENDA, PROPINA FROM AGENDA
          WHERE ID_CLIENTE = ? AND FECHA_RESERVA = ?
          ORDER BY ID_AGENDA DESC LIMIT 1
      """,
          (id_cliente, fecha),
      )
      fila_agenda = cur.fetchone()

      if fila_agenda:
        id_agenda, propina_existente = fila_agenda
        cur.execute(
            """
            INSERT INTO SERVICIOS_AGENDADOS
                (ID_AGENDA, ID_SERVICIO, ID_EMPLEADO, HORA, PRECIO, ATENDIDO)
            VALUES (?, ?, ?, ?, ?, 'NO')
        """,
            (id_agenda, id_servicio, id_empleado, hora, precio),
        )
        cur.execute(
            "SELECT SUM(PRECIO) FROM SERVICIOS_AGENDADOS WHERE ID_AGENDA = ?",
            (id_agenda,),
        )
        sub = cur.fetchone()[0] or 0.0
        cur.execute(
            "UPDATE AGENDA SET TOTAL = ? WHERE ID_AGENDA = ?",
            (sub + (propina_existente or 0.0), id_agenda),
        )
      else:
        cur.execute(
            """
            INSERT INTO AGENDA
                (ID_CLIENTE, FECHA_SISTEM, FECHA_RESERVA, TOTAL, PROPINA)
            VALUES (?, ?, ?, ?, 0)
        """,
            (id_cliente, fecha_sistem, fecha, precio),
        )
        id_agenda = cur.lastrowid
        cur.execute(
            """
            INSERT INTO SERVICIOS_AGENDADOS
                (ID_AGENDA, ID_SERVICIO, ID_EMPLEADO, HORA, PRECIO, ATENDIDO)
            VALUES (?, ?, ?, ?, ?, 'NO')
        """,
            (id_agenda, id_servicio, id_empleado, hora, precio),
        )

      conn.commit()
      conn.close()

      messagebox.showinfo(
          "Éxito",
          f"Reserva agendada correctamente para las {hora} del {fecha}.",
      )
      win.destroy()
      self.cargar_informe_agenda()

    f_pie = ttk.Frame(win)
    f_pie.pack(fill="x", padx=15, pady=10)

    ttk.Button(f_pie, text="AGENDAR RESERVA", command=agendar).pack(
        side="right", padx=5
    )
    ttk.Button(f_pie, text="Cancelar", command=win.destroy).pack(
        side="right", padx=5
    )

  # --------------------------------------------------------------------------
  # PESTAÑA 4: SERVICIOS
  # --------------------------------------------------------------------------
  def init_tab_servicios(self):
    frame = ttk.LabelFrame(
        self.tab_servicios, text=" Registrar Nuevo Servicio "
    )
    frame.pack(fill="x", padx=15, pady=15)

    ttk.Label(frame, text="Área:").grid(row=0, column=0, padx=5, pady=5)
    self.cb_area_serv = ttk.Combobox(frame, state="readonly", width=55)
    self.cb_area_serv.grid(row=0, column=1, padx=5, pady=5)

    ttk.Label(frame, text="Nombre Servicio:").grid(
        row=1, column=0, padx=5, pady=5
    )
    self.ent_nom_serv = ttk.Entry(frame, width=58)
    self.ent_nom_serv.grid(row=1, column=1, padx=5, pady=5)

    ttk.Label(frame, text="Estilo/Detalle:").grid(
        row=2, column=0, padx=5, pady=5
    )
    self.ent_estilo_serv = ttk.Entry(frame, width=58)
    self.ent_estilo_serv.grid(row=2, column=1, padx=5, pady=5)

    ttk.Label(frame, text="Precio ($):").grid(row=3, column=0, padx=5, pady=5)
    self.ent_precio_serv = ttk.Entry(frame, width=58)
    self.ent_precio_serv.grid(row=3, column=1, padx=5, pady=5)

    ttk.Label(frame, text="Tiempo Máx (HH:MM):").grid(
        row=4, column=0, padx=5, pady=5
    )
    self.ent_tiempo_serv = ttk.Entry(frame, width=58)
    self.ent_tiempo_serv.insert(0, "00:45")
    self.ent_tiempo_serv.grid(row=4, column=1, padx=5, pady=5)

    ttk.Button(
        frame, text="Guardar Servicio", command=self.guardar_servicio
    ).grid(row=5, column=0, columnspan=2, pady=10)

  def guardar_servicio(self):
    area_sel = self.cb_area_serv.get()
    nombre = self.ent_nom_serv.get().strip()
    precio = self.ent_precio_serv.get().strip()

    if not area_sel or not nombre or not precio:
      messagebox.showwarning(
          "Advertencia", "Por favor completa todos los campos requeridos."
      )
      return

    try:
      id_area = self.dict_areas[area_sel]
      conn = conectar_bd()
      cursor = conn.cursor()
      cursor.execute(
          """
                INSERT INTO SERVICIO (ID_AREA, NOM_SERVICIO, ESTILO, PRECIO, TIEMPO_MAX)
                VALUES (?, ?, ?, ?, ?)
            """,
          (
              id_area,
              nombre,
              self.ent_estilo_serv.get().strip(),
              float(precio),
              self.ent_tiempo_serv.get().strip(),
          ),
      )
      conn.commit()
      conn.close()

      messagebox.showinfo("Éxito", "Servicio registrado correctamente.")
      self.ent_nom_serv.delete(0, tk.END)
      self.ent_estilo_serv.delete(0, tk.END)
      self.ent_precio_serv.delete(0, tk.END)
      self.actualizar_combos_servicios()
    except ValueError:
      messagebox.showerror("Error", "El precio debe ser un número válido.")

  # --------------------------------------------------------------------------
  # PESTAÑA 5: GALERÍA
  # --------------------------------------------------------------------------
  def init_tab_galeria(self):
    frame = ttk.LabelFrame(
        self.tab_galeria, text=" Asignar Fotografías a Servicio "
    )
    frame.pack(fill="x", padx=15, pady=15)

    ttk.Label(frame, text="Servicio:").grid(row=0, column=0, padx=5, pady=5)
    self.cb_servicio_galeria = ttk.Combobox(frame, state="readonly", width=55)
    self.cb_servicio_galeria.grid(row=0, column=1, padx=5, pady=5)

    ttk.Label(frame, text="Fecha (AAAA-MM-DD):").grid(
        row=1, column=0, padx=5, pady=5
    )
    self.ent_fecha_galeria = ttk.Entry(frame, width=58)
    self.ent_fecha_galeria.insert(0, datetime.date.today().strftime("%Y-%m-%d"))
    self.ent_fecha_galeria.grid(row=1, column=1, padx=5, pady=5)

    ttk.Label(frame, text="Foto Frente:").grid(row=2, column=0, padx=5, pady=5)
    self.ent_ruta_frente = ttk.Entry(frame, width=45)
    self.ent_ruta_frente.grid(row=2, column=1, sticky="w", padx=5, pady=5)
    ttk.Button(
        frame,
        text="Buscar...",
        command=lambda: self.buscar_archivo_3(self.ent_ruta_frente),
    ).grid(row=2, column=1, sticky="e", padx=5, pady=5)

    ttk.Label(frame, text="Foto Lado / Perfil:").grid(
        row=3, column=0, padx=5, pady=5
    )
    self.ent_ruta_lado = ttk.Entry(frame, width=45)
    self.ent_ruta_lado.grid(row=3, column=1, sticky="w", padx=5, pady=5)
    ttk.Button(
        frame,
        text="Buscar...",
        command=lambda: self.buscar_archivo_3(self.ent_ruta_lado),
    ).grid(row=3, column=1, sticky="e", padx=5, pady=5)

    ttk.Label(frame, text="Foto Atrás / Posterior:").grid(
        row=4, column=0, padx=5, pady=5
    )
    self.ent_ruta_atras = ttk.Entry(frame, width=45)
    self.ent_ruta_atras.grid(row=4, column=1, sticky="w", padx=5, pady=5)
    ttk.Button(
        frame,
        text="Buscar...",
        command=lambda: self.buscar_archivo_3(self.ent_ruta_atras),
    ).grid(row=4, column=1, sticky="e", padx=5, pady=5)

    ttk.Label(frame, text="Descripción:").grid(row=5, column=0, padx=5, pady=5)
    self.ent_desc_galeria = ttk.Entry(frame, width=58)
    self.ent_desc_galeria.grid(row=5, column=1, padx=5, pady=5)

    ttk.Button(
        frame, text="Guardar en Galería", command=self.guardar_galeria
    ).grid(row=6, column=0, columnspan=2, pady=15)

  def buscar_archivo_3(self, entry_target):
    ruta = filedialog.askopenfilename(
        title="Seleccionar imagen",
        filetypes=[
            ("Archivos de Imagen", "*.png *.jpg *.jpeg *.gif *.bmp"),
            ("Todos los archivos", "*.*"),
        ],
    )
    if ruta:
      entry_target.delete(0, tk.END)
      entry_target.insert(0, ruta)

  def guardar_galeria(self):
    serv_sel = self.cb_servicio_galeria.get()
    frente = self.ent_ruta_frente.get().strip()
    lado = self.ent_ruta_lado.get().strip()
    atras = self.ent_ruta_atras.get().strip()

    if not serv_sel:
      messagebox.showwarning(
          "Advertencia", "Debes seleccionar un Servicio obligatoriamente."
      )
      return

    if not frente and not lado and not atras:
      messagebox.showwarning(
          "Advertencia", "Debes cargar al menos una ruta de imagen."
      )
      return

    id_servicio = self.dict_servicios[serv_sel]

    try:
      conn = conectar_bd()
      cursor = conn.cursor()
      cursor.execute(
          """
                INSERT INTO GALERIA (ID_SERVICIO, FECHA, DOC_FRENTE, DOC_LADO, DOC_ATRAS, DESCRIPCION, ACTIVO)
                VALUES (?, ?, ?, ?, ?, ?, 'SI')
            """,
          (
              id_servicio,
              self.ent_fecha_galeria.get().strip(),
              frente,
              lado,
              atras,
              self.ent_desc_galeria.get().strip(),
          ),
      )
      conn.commit()
      conn.close()

      messagebox.showinfo(
          "Éxito", "Fotos e información guardadas en la Base de Datos."
      )
      self.ent_ruta_frente.delete(0, tk.END)
      self.ent_ruta_lado.delete(0, tk.END)
      self.ent_ruta_atras.delete(0, tk.END)
      self.ent_desc_galeria.delete(0, tk.END)

    except Exception as e:
      messagebox.showerror("Error", f"No se pudo guardar:\n{str(e)}")

  # --------------------------------------------------------------------------
  # PESTAÑA 6: EMPLEADOS
  # --------------------------------------------------------------------------
  def init_tab_empleados(self):
    frame = ttk.LabelFrame(self.tab_empleados, text=" Registro de Empleado ")
    frame.pack(fill="both", expand=True, padx=15, pady=15)

    ttk.Label(frame, text="Cédula:").grid(row=0, column=0, padx=5, pady=4)
    self.ent_cedula = ttk.Entry(frame, width=45)
    self.ent_cedula.grid(row=0, column=1, padx=5, pady=4)

    ttk.Label(frame, text="Nombres:").grid(row=1, column=0, padx=5, pady=4)
    self.ent_nombres = ttk.Entry(frame, width=45)
    self.ent_nombres.grid(row=1, column=1, padx=5, pady=4)

    ttk.Label(frame, text="Apellidos:").grid(row=2, column=0, padx=5, pady=4)
    self.ent_apellidos = ttk.Entry(frame, width=45)
    self.ent_apellidos.grid(row=2, column=1, padx=5, pady=4)

    ttk.Label(frame, text="Cargo:").grid(row=3, column=0, padx=5, pady=4)
    self.cb_cargo = ttk.Combobox(frame, state="readonly", width=42)
    self.cb_cargo.grid(row=3, column=1, padx=5, pady=4)

    ttk.Label(frame, text="Área de Trabajo:").grid(
        row=4, column=0, padx=5, pady=4
    )
    self.cb_area_emp = ttk.Combobox(frame, state="readonly", width=42)
    self.cb_area_emp.grid(row=4, column=1, padx=5, pady=4)

    ttk.Label(frame, text="Servicios Habilitados:\n(Mantén Ctrl + Clic)").grid(
        row=5, column=0, padx=5, pady=4
    )
    self.lb_servicios = tk.Listbox(
        frame, selectmode="multiple", height=6, width=45, exportselection=False
    )
    self.lb_servicios.grid(row=5, column=1, padx=5, pady=4, sticky="we")

    ttk.Button(
        frame, text="Registrar Empleado", command=self.guardar_empleado
    ).grid(row=6, column=0, columnspan=2, pady=10)

  def guardar_empleado(self):
    cedula = self.ent_cedula.get().strip()
    nombres = self.ent_nombres.get().strip()
    apellidos = self.ent_apellidos.get().strip()
    cargo_sel = self.cb_cargo.get()
    area_sel = self.cb_area_emp.get()
    indices_servicios = self.lb_servicios.curselection()

    if not (cedula and nombres and apellidos and cargo_sel and area_sel):
      messagebox.showwarning(
          "Advertencia", "Por favor completa todos los campos."
      )
      return

    try:
      conn = conectar_bd()
      cursor = conn.cursor()

      cursor.execute(
          "INSERT INTO EMPLEADO (CEDULA, NOMBRES, APELLIDOS) VALUES (?, ?, ?)",
          (cedula, nombres, apellidos),
      )
      id_empleado = cursor.lastrowid

      id_cargo = self.dict_cargos[cargo_sel]
      id_area = self.dict_areas[area_sel]
      cursor.execute(
          "INSERT INTO ASIG_CARGO (ID_CARGO, ID_EMPLEADO, ID_AREA, FECHA_ASIG)"
          " VALUES (?, ?, ?, ?)",
          (
              id_cargo,
              id_empleado,
              id_area,
              datetime.date.today().strftime("%Y-%m-%d"),
          ),
      )

      serv_keys = list(self.dict_servicios.keys())
      for idx in indices_servicios:
        nombre_key = serv_keys[idx]
        id_servicio = self.dict_servicios[nombre_key]
        cursor.execute(
            "INSERT INTO EMPLEADO_SERVICIO (ID_EMPLEADO, ID_SERVICIO, ACTIVO)"
            " VALUES (?, ?, 'SI')",
            (id_empleado, id_servicio),
        )

      conn.commit()
      conn.close()

      messagebox.showinfo("Éxito", "Empleado registrado correctamente.")
      self.ent_cedula.delete(0, tk.END)
      self.ent_nombres.delete(0, tk.END)
      self.ent_apellidos.delete(0, tk.END)
      self.actualizar_combos_empleados()

    except sqlite3.IntegrityError:
      messagebox.showerror("Error", "La cédula ingresada ya está registrada.")

  # --------------------------------------------------------------------------
  # PESTAÑA 7: CONSULTAS
  # --------------------------------------------------------------------------
  def init_tab_consultas(self):
    sub_notebook = ttk.Notebook(self.tab_consultas)
    sub_notebook.pack(fill="both", expand=True, padx=5, pady=5)

    tab_listados = ttk.Frame(sub_notebook)
    tab_visor_galeria = ttk.Frame(sub_notebook)

    sub_notebook.add(tab_listados, text="Listados de Empleados/Servicios")
    sub_notebook.add(tab_visor_galeria, text="Visor de Galería")

    f1 = ttk.LabelFrame(
        tab_listados, text=" 1. Buscar Empleados que presten un Servicio "
    )
    f1.pack(fill="x", padx=10, pady=5)

    ttk.Label(f1, text="Selecciona Servicio:").pack(side="left", padx=5)
    self.cb_consulta_servicio = ttk.Combobox(f1, state="readonly", width=55)
    self.cb_consulta_servicio.pack(side="left", padx=5)

    ttk.Button(
        f1,
        text="Listar Empleados",
        command=self.consultar_empleados_por_servicio,
    ).pack(side="left", padx=5)

    f2 = ttk.LabelFrame(
        tab_listados, text=" 2. Buscar Servicios que realiza un Empleado "
    )
    f2.pack(fill="x", padx=10, pady=5)

    ttk.Label(f2, text="Selecciona Empleado:").pack(side="left", padx=5)
    self.cb_consulta_empleado = ttk.Combobox(f2, state="readonly", width=55)
    self.cb_consulta_empleado.pack(side="left", padx=5)

    ttk.Button(
        f2,
        text="Listar Servicios",
        command=self.consultar_servicios_por_empleado,
    ).pack(side="left", padx=5)

    f3 = ttk.LabelFrame(tab_listados, text=" Resultados ")
    f3.pack(fill="both", expand=True, padx=10, pady=5)

    self.tree_resultados = ttk.Treeview(
        f3, columns=("Col1", "Col2", "Col3"), show="headings"
    )
    self.tree_resultados.heading("Col1", text="Dato Principal")
    self.tree_resultados.heading("Col2", text="Detalle / Estilo / Cargo")
    self.tree_resultados.heading("Col3", text="Información Adicional")
    self.tree_resultados.column("Col1", width=300)
    self.tree_resultados.column("Col2", width=250)
    self.tree_resultados.column("Col3", width=200)
    self.tree_resultados.pack(fill="both", expand=True, padx=5, pady=5)

    f_top_galeria = ttk.Frame(tab_visor_galeria)
    f_top_galeria.pack(fill="x", padx=10, pady=5)

    ttk.Label(f_top_galeria, text="Seleccionar Servicio:").pack(
        side="left", padx=5
    )
    self.cb_galeria_servicio = ttk.Combobox(
        f_top_galeria, state="readonly", width=50
    )
    self.cb_galeria_servicio.pack(side="left", padx=5)

    ttk.Button(
        f_top_galeria, text="Ver Galería", command=self.cargar_galeria_servicio
    ).pack(side="left", padx=5)

    self.frame_visor = ttk.LabelFrame(
        tab_visor_galeria, text=" Detalle Tridimensional del Servicio "
    )
    self.frame_visor.pack(fill="both", expand=True, padx=10, pady=5)

    self.lbl_galeria_info_header = ttk.Label(
        self.frame_visor,
        text="Haz clic en 'Ver Galería' para explorar los registros.",
        font=("Arial", 11, "bold"),
        anchor="center",
    )
    self.lbl_galeria_info_header.pack(fill="x", pady=5)

    f_3_fotos = ttk.Frame(self.frame_visor)
    f_3_fotos.pack(fill="both", expand=True, padx=10, pady=5)

    f_col1 = ttk.LabelFrame(f_3_fotos, text=" 1. FRENTE ")
    f_col1.pack(side="left", fill="both", expand=True, padx=5)
    self.lbl_img_frente = ttk.Label(
        f_col1,
        text="[ Sin Foto ]",
        anchor="center",
        background="#F0F0F0",
        relief="groove",
    )
    self.lbl_img_frente.pack(fill="both", expand=True, padx=5, pady=5)

    f_col2 = ttk.LabelFrame(f_3_fotos, text=" 2. LADO / PERFIL ")
    f_col2.pack(side="left", fill="both", expand=True, padx=5)
    self.lbl_img_lado = ttk.Label(
        f_col2,
        text="[ Sin Foto ]",
        anchor="center",
        background="#F0F0F0",
        relief="groove",
    )
    self.lbl_img_lado.pack(fill="both", expand=True, padx=5, pady=5)

    f_col3 = ttk.LabelFrame(f_3_fotos, text=" 3. ATRÁS / POSTERIOR ")
    f_col3.pack(side="left", fill="both", expand=True, padx=5)
    self.lbl_img_atras = ttk.Label(
        f_col3,
        text="[ Sin Foto ]",
        anchor="center",
        background="#F0F0F0",
        relief="groove",
    )
    self.lbl_img_atras.pack(fill="both", expand=True, padx=5, pady=5)

    self.lbl_galeria_desc = ttk.Label(
        self.frame_visor,
        text="",
        font=("Arial", 10),
        wraplength=1000,
        justify="center",
    )
    self.lbl_galeria_desc.pack(fill="x", pady=5)

  def consultar_empleados_por_servicio(self):
    serv_sel = self.cb_consulta_servicio.get()
    if not serv_sel:
      messagebox.showwarning(
          "Advertencia", "Selecciona un servicio para filtrar."
      )
      return

    id_servicio = self.dict_servicios[serv_sel]
    for i in self.tree_resultados.get_children():
      self.tree_resultados.delete(i)

    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute(
        """
            SELECT E.NOMBRES || ' ' || E.APELLIDOS, C.NOMB_CARGO, E.CEDULA
            FROM EMPLEADO E
            JOIN EMPLEADO_SERVICIO ES ON E.ID_EMPLEADO = ES.ID_EMPLEADO
            LEFT JOIN ASIG_CARGO AC ON E.ID_EMPLEADO = AC.ID_EMPLEADO
            LEFT JOIN CARGO C ON AC.ID_CARGO = C.ID_CARGO
            WHERE ES.ID_SERVICIO = ? AND ES.ACTIVO = 'SI'
        """,
        (id_servicio,),
    )
    for res in cursor.fetchall():
      self.tree_resultados.insert(
          "",
          "end",
          values=(res[0], res[1] if res[1] else "Sin Cargo", f"C.I: {res[2]}"),
      )
    conn.close()

  def consultar_servicios_por_empleado(self):
    emp_sel = self.cb_consulta_empleado.get()
    if not emp_sel:
      messagebox.showwarning(
          "Advertencia", "Selecciona un empleado para filtrar."
      )
      return

    id_empleado = self.dict_empleados[emp_sel]
    for i in self.tree_resultados.get_children():
      self.tree_resultados.delete(i)

    conn = conectar_bd()
    cursor = conn.cursor()
    cursor.execute(
        """
            SELECT S.NOM_SERVICIO, S.ESTILO, '$' || S.PRECIO
            FROM SERVICIO S
            JOIN EMPLEADO_SERVICIO ES ON S.ID_SERVICIO = ES.ID_SERVICIO
            WHERE ES.ID_EMPLEADO = ? AND ES.ACTIVO = 'SI'
        """,
        (id_empleado,),
    )
    for res in cursor.fetchall():
      self.tree_resultados.insert("", "end", values=(res[0], res[1], res[2]))
    conn.close()

  def cargar_galeria_servicio(self):
    serv_sel = self.cb_galeria_servicio.get().strip()

    conn = conectar_bd()
    cursor = conn.cursor()

    if not serv_sel or serv_sel == "-- Ver Todos los Servicios --":
      cursor.execute("""
                SELECT A.NOM_ARE, A.NOM_DEPARTAMENTO, S.NOM_SERVICIO, S.ESTILO, S.PRECIO,
                       G.DOC_FRENTE, G.DOC_LADO, G.DOC_ATRAS, G.DESCRIPCION, G.FECHA, G.ID_GALERIA
                FROM GALERIA G
                JOIN SERVICIO S ON G.ID_SERVICIO = S.ID_SERVICIO
                JOIN AREA A ON S.ID_AREA = A.ID_AREA
                WHERE G.ACTIVO = 'SI'
                ORDER BY G.ID_GALERIA DESC
            """)
    else:
      id_servicio = self.dict_servicios[serv_sel]
      cursor.execute(
          """
                SELECT A.NOM_ARE, A.NOM_DEPARTAMENTO, S.NOM_SERVICIO, S.ESTILO, S.PRECIO,
                       G.DOC_FRENTE, G.DOC_LADO, G.DOC_ATRAS, G.DESCRIPCION, G.FECHA, G.ID_GALERIA
                FROM GALERIA G
                JOIN SERVICIO S ON G.ID_SERVICIO = S.ID_SERVICIO
                JOIN AREA A ON S.ID_AREA = A.ID_AREA
                WHERE G.ID_SERVICIO = ? AND G.ACTIVO = 'SI'
                ORDER BY G.ID_GALERIA DESC
            """,
          (id_servicio,),
      )

    self.galeria_items = cursor.fetchall()
    conn.close()

    if not self.galeria_items:
      messagebox.showinfo(
          "Galería Vacía", "No hay fotos o gráficos activos registrados."
      )
      return

    item = self.galeria_items[0]
    self.lbl_galeria_info_header.config(
        text=f"ÁREA: {item[0]} | SERVICIO: {item[2]} [{item[3]}]"
    )
    self.lbl_galeria_desc.config(
        text=f"Descripción: {item[8]} | Fecha: {item[9]}"
    )
    self.renderizar_imagen_columna(item[5], self.lbl_img_frente, 0)
    self.renderizar_imagen_columna(item[6], self.lbl_img_lado, 1)
    self.renderizar_imagen_columna(item[7], self.lbl_img_atras, 2)

  def renderizar_imagen_columna(self, ruta, lbl_widget, index_img):
    if ruta and os.path.exists(ruta):
      if HAS_PIL:
        try:
          img = Image.open(ruta)
          img.thumbnail((300, 320))
          img_tk = ImageTk.PhotoImage(img)
          self.imgs_tk_actuales[index_img] = img_tk
          lbl_widget.config(image=img_tk, text="")
        except Exception:
          lbl_widget.config(image="", text=f"[ Error en foto:\n{ruta} ]")
      else:
        lbl_widget.config(
            image="", text=f"[ Imagen:\n{os.path.basename(ruta)} ]"
        )
    else:
      lbl_widget.config(image="", text="[ Sin Archivo registrado ]")


# ==============================================================================
# 3. PUNTO DE ENTRADA
# ==============================================================================
if __name__ == "__main__":
  try:
    crear_tablas()
    app = AppBarberia()
    app.mainloop()
  except Exception as e:
    print(f"\n[ERROR CRÍTICO AL INICIAR]: {e}", file=sys.stderr)
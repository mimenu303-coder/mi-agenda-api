"""
App Móvil - BAR SAP (Barbería / Spa / Peluquería)
Cliente: Registrarse | Reservas + Alarmas | Galería | Informe de Agenda
Estilo: Dark-Amber Glass | Base de datos: Neon PostgreSQL (spa-bar)
"""

import datetime
import os
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import psycopg2

try:
    from PIL import Image, ImageEnhance, ImageOps, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False


# ---------- Conexión Neon PostgreSQL (spa-bar) ----------
RAW_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_5aHTnMtDIE9L@ep-dark-silence-b6qgi4e0-pooler.c-2.sa-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require",
)


def _normalizar_url_neon(url: str) -> str:
    limpia = (url or "").strip()
    for param in (
        "&channel_binding=require",
        "?channel_binding=require",
        "channel_binding=require",
    ):
        limpia = limpia.replace(param, "")
    if limpa and "sslmode=require" not in limpia:
        limpia += ("&" if "?" in limpia else "?") + "sslmode=require"
    return limpia


DATABASE_URL = _normalizar_url_neon(RAW_DATABASE_URL)

# ---------- Tema Dark-Amber Glass ----------
BG_MAIN = "#070605"        # Fondo oscuro profundo
BG_CARD = "#16120E"        # Tarjetas / cabeceras vidrio oscuro cálido
BG_INPUT = "#241D16"       # Campos de entrada / listas
FG_PRIMARY = "#F8FAFC"     # Texto principal claro
FG_SECONDARY = "#C7B9A5"   # Texto secundario cálido / arena
ACCENT = "#F59E0B"         # Ámbar principal
ACCENT_BRIGHT = "#FDE68A"  # Dorado / ámbar brillante
ACCENT2 = "#D97706"        # Ámbar intenso / bronce
SUCCESS = "#22C55E"        # Confirmación
WARN = "#FBBF24"           # Advertencia / recordatorio
DANGER = "#DC2626"         # Eliminar / alerta

TONOS_DISPONIBLES = ["Beep Corto", "Beep Doble", "Alarma Larga"]
TIEMPOS_ALARMA = [60, 30, 15]  # minutos antes de la reserva


def conectar_bd():
    return psycopg2.connect(DATABASE_URL, sslmode="require", connect_timeout=10)


# ==============================================================================
# APP MÓVIL - DARK-AMBER GLASS + NEON
# ==============================================================================
class AppMovil(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("BAR SAP — Móvil (Neon)")
        self.geometry("430x830")
        self.configure(bg=BG_MAIN)
        self.resizable(False, False)

        self._configurar_estilos_ttk()

        # --- Estado global ---
        self.cliente_actual = None
        self.carrito = []
        self.galeria_items = []
        self.indice_galeria = 0
        self.sub_indice_vista = 0
        self.timer_carrusel = None
        self.timer_alarmas = None
        self.alarmas = []
        self.vistas = []

        # Ruta de la imagen de fondo elegida por el usuario
        self.bg_image_path = None

        # Bandera de pausa del carrusel
        self.carrusel_pausado = False

        # Estado del informe de agenda
        self.orden_informe = "HORA"
        self.ver_solo_atendidas = False
        self.var_ver_precios = tk.BooleanVar(value=True)

        # --- Contenedor principal ---
        self.container = tk.Frame(self, bg=BG_MAIN)
        self.container.pack(fill="both", expand=True)

        self.mostrar_inicio()
        self._poll_alarmas()

    def _configurar_estilos_ttk(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure(
            "TCombobox",
            fieldbackground=BG_INPUT,
            background=BG_CARD,
            foreground=FG_PRIMARY,
            arrowcolor=ACCENT,
            bordercolor=ACCENT2,
            lightcolor=ACCENT2,
            darkcolor=BG_CARD,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", BG_INPUT)],
            foreground=[("readonly", FG_PRIMARY)],
            selectbackground=[("readonly", ACCENT)],
            selectforeground=[("readonly", "#070605")],
        )

        style.configure("TNotebook", background=BG_MAIN, borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            background=BG_CARD,
            foreground=FG_SECONDARY,
            padding=[12, 6],
            font=("Segoe UI", 9, "bold"),
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", ACCENT)],
            foreground=[("selected", "#070605")],
        )

        style.configure(
            "TCheckbutton",
            background=BG_MAIN,
            foreground=FG_SECONDARY,
            font=("Segoe UI", 9),
        )
        style.map(
            "TCheckbutton",
            background=[("active", BG_MAIN)],
            foreground=[("active", ACCENT_BRIGHT)],
        )

        style.configure(
            "Treeview",
            background=BG_INPUT,
            fieldbackground=BG_INPUT,
            foreground=FG_PRIMARY,
            bordercolor=BG_CARD,
            rowheight=24,
            font=("Segoe UI", 8),
        )
        style.configure(
            "Treeview.Heading",
            background=BG_CARD,
            foreground=ACCENT_BRIGHT,
            relief="flat",
            font=("Segoe UI", 8, "bold"),
        )
        style.map(
            "Treeview",
            background=[("selected", ACCENT2)],
            foreground=[("selected", "#FFFFFF")],
        )

    # ==================================================================
    # UTILIDADES GENERALES
    # ==================================================================
    def _limpiar(self):
        """Destruye todos los widgets del contenedor y cancela timers activos."""
        if self.timer_carrusel:
            try:
                self.after_cancel(self.timer_carrusel)
            except Exception:
                pass
            self.timer_carrusel = None
        for w in self.container.winfo_children():
            w.destroy()

    def _btn(self, parent, text, command, bg=ACCENT, fg="#070605",
             size=13, pady=12, padx=20):
        b = tk.Button(
            parent, text=text, command=command,
            bg=bg, fg=fg, font=("Segoe UI", size, "bold"),
            relief="flat", cursor="hand2",
            activebackground=ACCENT_BRIGHT if bg == ACCENT else bg,
            activeforeground=fg,
            highlightthickness=1,
            highlightbackground=ACCENT2 if bg in (ACCENT, BG_CARD) else bg,
        )
        b.pack(fill="x", padx=padx, pady=pady)
        return b

    def _header(self, parent, titulo):
        f = tk.Frame(parent, bg=BG_CARD, height=70,
                     highlightthickness=1, highlightbackground=ACCENT2)
        f.pack(fill="x")
        f.pack_propagate(False)
        tk.Label(f, text=titulo, bg=BG_CARD, fg=ACCENT_BRIGHT,
                 font=("Segoe UI", 17, "bold")).pack(pady=18)

    # ==================================================================
    # FONDO PERSONALIZADO
    # ==================================================================
    def _elegir_fondo(self):
        """Permite al usuario elegir una imagen como fondo de pantalla."""
        ruta = filedialog.askopenfilename(
            title="Elegir imagen de fondo",
            filetypes=[
                ("Archivos de Imagen", "*.png *.jpg *.jpeg *.gif *.bmp *.webp"),
                ("Todos los archivos", "*.*"),
            ],
        )
        if ruta:
            self.bg_image_path = ruta
            self._limpiar()
            self.mostrar_inicio()

    def _set_screen_background(self, parent):
        """Coloca la imagen de fondo (si existe) detrás de los widgets del parent."""
        if not self.bg_image_path or not os.path.exists(self.bg_image_path):
            return
        if not HAS_PIL:
            return
        try:
            img = Image.open(self.bg_image_path).convert("RGB")
            img = ImageOps.fit(img, (430, 830),
                               method=Image.Resampling.LANCZOS)
            img = ImageEnhance.Brightness(img).enhance(0.28)
            photo = ImageTk.PhotoImage(img)

            lbl = tk.Label(parent, image=photo, bd=0)
            lbl.image = photo
            lbl.place(x=0, y=0, relwidth=1, relheight=1)
            lbl.lower()
        except Exception as e:
            print(f"[Fondo] Error al cargar imagen: {e}")

    # ==================================================================
    # PANTALLA 1: INICIO
    # ==================================================================
    def mostrar_inicio(self):
        self._limpiar()
        root = tk.Frame(self.container, bg=BG_MAIN)
        root.pack(fill="both", expand=True)

        self._set_screen_background(root)

        tk.Frame(root, bg=BG_MAIN, height=1).pack(fill="both", expand=True)

        tk.Label(root, text="✂  BAR SAP", bg=BG_MAIN, fg=ACCENT_BRIGHT,
                 font=("Segoe UI", 23, "bold")).pack(pady=(0, 4))
        tk.Label(root, text="Barbería · Spa · Peluquería", bg=BG_MAIN,
                 fg=ACCENT, font=("Segoe UI", 10, "bold")).pack()
        tk.Label(root, text="Neon PostgreSQL · spa-bar", bg=BG_MAIN,
                 fg=FG_SECONDARY, font=("Segoe UI", 9, "italic")).pack(pady=(2, 0))

        if self.cliente_actual:
            tk.Label(root, text=f"👤  {self.cliente_actual['nombre']}",
                     bg=BG_MAIN, fg=ACCENT_BRIGHT,
                     font=("Segoe UI", 11, "bold")).pack(pady=(20, 0))
            tk.Label(root, text=f"📱  {self.cliente_actual['celular']}",
                     bg=BG_MAIN, fg=FG_SECONDARY,
                     font=("Segoe UI", 10)).pack()

        tk.Frame(root, bg=BG_MAIN, height=1).pack(fill="both", expand=True)

        f_btns = tk.Frame(root, bg=BG_MAIN)
        f_btns.pack(fill="x")

        self._btn(f_btns, "📝  REGISTRARSE", self.mostrar_registro,
                  bg=ACCENT, fg="#070605", size=14)
        self._btn(f_btns, "📅  RESERVAS", self.mostrar_reservas,
                  bg=ACCENT2, fg="#FFFFFF", size=14)
        self._btn(f_btns, "🖼  GALERÍA / REVISTA", self.mostrar_galeria,
                  bg=BG_CARD, fg=ACCENT_BRIGHT, size=14)

        if self.alarmas:
            activas = sum(1 for a in self.alarmas
                          if a["activa"] and not a["disparada"])
            if activas:
                tk.Label(f_btns,
                         text=f"🔔  {activas} alarma(s) activa(s)",
                         bg=BG_MAIN, fg=WARN,
                         font=("Segoe UI", 10, "italic")).pack(pady=(10, 0))

        tk.Frame(root, bg=BG_MAIN, height=1).pack(fill="both", expand=True)

        texto_fondo = ("🖼  Cambiar fondo" if not self.bg_image_path
                       else "🖼  Fondo: " +
                            os.path.basename(self.bg_image_path)[:22])
        tk.Button(root, text=texto_fondo,
                  command=self._elegir_fondo,
                  bg=BG_CARD, fg=FG_SECONDARY,
                  font=("Segoe UI", 9), relief="flat",
                  highlightthickness=1, highlightbackground=ACCENT2,
                  cursor="hand2").pack(fill="x", padx=20, pady=(0, 20))

    # ==================================================================
    # PANTALLA 2: REGISTRO
    # ==================================================================
    def mostrar_registro(self):
        self._limpiar()
        root = tk.Frame(self.container, bg=BG_MAIN)
        root.pack(fill="both", expand=True)

        self._set_screen_background(root)
        self._header(root, "📝  Registrarse")

        canvas = tk.Canvas(root, bg=BG_MAIN, highlightthickness=0)
        sb = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
        body = tk.Frame(canvas, bg=BG_MAIN)
        body.bind("<Configure>",
                  lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=body, anchor="nw", width=420)
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        tk.Frame(body, bg=BG_MAIN, height=20).pack()

        form = tk.Frame(body, bg=BG_MAIN)
        form.pack(fill="x", padx=25)

        def _campo(label_txt, attr_name, focus=False):
            tk.Label(form, text=label_txt, bg=BG_MAIN,
                     fg=FG_SECONDARY, font=("Segoe UI", 10)
                     ).pack(anchor="w", pady=(0, 4))
            ent = tk.Entry(form, bg=BG_INPUT, fg=FG_PRIMARY,
                           insertbackground=ACCENT, relief="flat",
                           highlightthickness=1, highlightbackground=ACCENT2,
                           font=("Segoe UI", 12))
            ent.pack(fill="x", ipady=10, pady=(0, 18))
            if focus:
                ent.focus_set()
            setattr(self, attr_name, ent)

        _campo("Número de celular:", "ent_celular", focus=True)
        _campo("Alias:", "ent_alias")
        _campo("Nombre y Apellido:", "ent_nombre")
        _campo("Día Cumpleaños (ej: 15 de Mayo):", "ent_cumple")

        self._btn(form, "✅  CREAR CUENTA", self._guardar_registro,
                  bg=ACCENT, fg="#070605", size=14)
        self._btn(form, "←  Volver", self.mostrar_inicio,
                  bg=BG_CARD, fg=ACCENT_BRIGHT, size=11, pady=8)

        tk.Frame(body, bg=BG_MAIN, height=30).pack()

    def _guardar_registro(self):
        celular = self.ent_celular.get().strip()
        alias = self.ent_alias.get().strip()
        nombre = self.ent_nombre.get().strip()
        cumple = self.ent_cumple.get().strip()

        if not celular:
            messagebox.showwarning("Falta", "Debes ingresar tu número de celular.")
            return
        if not nombre:
            messagebox.showwarning("Falta", "Debes ingresar tu nombre.")
            return

        nombre_final = f"{nombre} ({alias})" if alias else nombre

        conn = None
        try:
            conn = conectar_bd()
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO cliente (nro_celular, nombre_apellido, dia_cumpleanos)"
                " VALUES (%s, %s, %s) RETURNING id_cliente",
                (celular, nombre_final, cumple),
            )
            id_cliente = cur.fetchone()[0]
            conn.commit()
            conn.close()
            conn = None

            self.cliente_actual = {
                "id": id_cliente,
                "celular": celular,
                "nombre": nombre_final,
            }
            messagebox.showinfo("¡Listo!",
                                f"Cuenta creada:\n{nombre_final}\n{celular}")
            self.mostrar_inicio()
        except psycopg2.IntegrityError:
            if conn:
                conn.rollback()
                conn.close()
            messagebox.showerror(
                "Error", "Ese número de celular ya está registrado.\n"
                         "Prueba con otro.")
        except Exception as e:
            if conn:
                conn.rollback()
                conn.close()
            messagebox.showerror("Error", str(e))

    # ==================================================================
    # PANTALLA 3: RESERVAS
    # ==================================================================
    def mostrar_reservas(self):
        self._limpiar()
        root = tk.Frame(self.container, bg=BG_MAIN)
        root.pack(fill="both", expand=True)

        self._header(root, "📅  Reservas")

        canvas = tk.Canvas(root, bg=BG_MAIN, highlightthickness=0)
        scrollbar = ttk.Scrollbar(root, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=BG_MAIN)
        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw", width=420)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        form = scroll_frame

        tk.Button(form, text="←  Volver", command=self.mostrar_inicio,
                  bg=BG_CARD, fg=ACCENT_BRIGHT, font=("Segoe UI", 11, "bold"),
                  relief="flat", highlightthickness=1, highlightbackground=ACCENT2,
                  cursor="hand2").pack(fill="x", padx=20, pady=(8, 5))

        f_cli = tk.Frame(form, bg=BG_MAIN)
        f_cli.pack(fill="x", padx=20, pady=(10, 5))
        f_cli.grid_columnconfigure(1, weight=1)

        tk.Label(f_cli, text="Cliente:", bg=BG_MAIN, fg=FG_SECONDARY,
                 font=("Segoe UI", 10)).grid(row=0, column=0,
                                             sticky="w", padx=(0, 6))
        self.cb_cliente = ttk.Combobox(f_cli, state="readonly", width=40)
        self.cb_cliente.grid(row=0, column=1, sticky="ew")
        self._cargar_clientes()
        self.cb_cliente.bind("<<ComboboxSelected>>",
                             lambda e: self._cargar_agenda_cliente())

        tk.Label(form, text="Mis próximas reservas:", bg=BG_MAIN,
                 fg=ACCENT, font=("Segoe UI", 10, "bold")
                 ).pack(anchor="w", padx=20, pady=(15, 2))
        self.tree_agenda = ttk.Treeview(
            form, columns=("Fecha", "Hora", "Servicio"),
            show="headings", height=4)
        self.tree_agenda.heading("Fecha", text="Fecha")
        self.tree_agenda.heading("Hora", text="Hora")
        self.tree_agenda.heading("Servicio", text="Servicio")
        self.tree_agenda.column("Fecha", width=90, anchor="center")
        self.tree_agenda.column("Hora", width=60, anchor="center")
        self.tree_agenda.column("Servicio", width=230)
        self.tree_agenda.pack(fill="x", padx=20, pady=(0, 10))

        f_fh = tk.Frame(form, bg=BG_MAIN)
        f_fh.pack(fill="x", padx=20, pady=5)
        tk.Label(f_fh, text="Fecha:", bg=BG_MAIN, fg=FG_SECONDARY,
                 font=("Segoe UI", 10)).pack(side="left")
        self.cb_fecha = ttk.Combobox(f_fh, state="readonly", width=13)
        hoy = datetime.date.today()
        self.cb_fecha["values"] = [
            (hoy + datetime.timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(7)]
        self.cb_fecha.current(0)
        self.cb_fecha.pack(side="left", padx=(5, 15))
        tk.Label(f_fh, text="Hora:", bg=BG_MAIN, fg=FG_SECONDARY,
                 font=("Segoe UI", 10)).pack(side="left")
        self.cb_hora = ttk.Combobox(f_fh, state="readonly", width=8)
        self.cb_hora["values"] = [f"{h:02d}:00" for h in range(8, 21)]
        self.cb_hora.current(2)
        self.cb_hora.pack(side="left", padx=5)

        nb = ttk.Notebook(form)
        nb.pack(fill="x", padx=20, pady=(15, 5))

        tab1 = tk.Frame(nb, bg=BG_CARD)
        tab2 = tk.Frame(nb, bg=BG_CARD)
        nb.add(tab1, text="Por Área")
        nb.add(tab2, text="Por Empleado")

        tk.Label(tab1, text="Área:", bg=BG_CARD, fg=FG_SECONDARY,
                 font=("Segoe UI", 10)).pack(anchor="w", padx=12, pady=(8, 2))
        self.cb_area = ttk.Combobox(tab1, state="readonly", width=38)
        self.cb_area.pack(padx=12)
        self.cb_area.bind("<<ComboboxSelected>>",
                          lambda e: self._cargar_servicios_area())

        tk.Label(tab1, text="Servicio:", bg=BG_CARD, fg=FG_SECONDARY,
                 font=("Segoe UI", 10)).pack(anchor="w", padx=12, pady=(8, 2))
        self.cb_serv_area = ttk.Combobox(tab1, state="readonly", width=38)
        self.cb_serv_area.pack(padx=12, pady=(0, 12))

        tk.Label(tab2, text="Empleado:", bg=BG_CARD, fg=FG_SECONDARY,
                 font=("Segoe UI", 10)).pack(anchor="w", padx=12, pady=(8, 2))
        self.cb_emp = ttk.Combobox(tab2, state="readonly", width=38)
        self.cb_emp.pack(padx=12)
        self.cb_emp.bind("<<ComboboxSelected>>",
                         lambda e: self._cargar_servicios_emp())

        tk.Label(tab2, text="Servicio:", bg=BG_CARD, fg=FG_SECONDARY,
                 font=("Segoe UI", 10)).pack(anchor="w", padx=12, pady=(8, 2))
        self.cb_serv_emp = ttk.Combobox(tab2, state="readonly", width=38)
        self.cb_serv_emp.pack(padx=12, pady=(0, 12))

        f_add = tk.Frame(form, bg=BG_MAIN)
        f_add.pack(fill="x", padx=20, pady=10)
        tk.Button(f_add, text="➕  Agregar al carrito",
                  command=lambda: self._agregar_al_carrito(nb.index(nb.select())),
                  bg=ACCENT, fg="#070605", font=("Segoe UI", 11, "bold"),
                  relief="flat", cursor="hand2").pack(fill="x", ipady=4)

        tk.Label(form, text="Carrito:", bg=BG_MAIN, fg=ACCENT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=20, pady=(10, 2))
        self.lb_carrito = tk.Listbox(form, bg=BG_INPUT, fg=FG_PRIMARY,
                                     relief="flat", highlightthickness=1,
                                     highlightbackground=ACCENT2,
                                     font=("Consolas", 10),
                                     height=4, selectbackground=ACCENT,
                                     selectforeground="#070605")
        self.lb_carrito.pack(fill="x", padx=20, pady=(0, 10))

        tk.Button(form, text="✅  CONFIRMAR RESERVA",
                  command=self._confirmar_reserva,
                  bg=ACCENT, fg="#070605", font=("Segoe UI", 13, "bold"),
                  relief="flat", cursor="hand2").pack(fill="x", padx=20, pady=8, ipady=4)

        tk.Button(form, text="📋  INFORME DE AGENDA",
                  command=self.mostrar_informe_agenda,
                  bg=ACCENT2, fg="#FFFFFF", font=("Segoe UI", 12, "bold"),
                  relief="flat", cursor="hand2").pack(fill="x", padx=20, pady=8, ipady=3)

        tk.Button(form, text="🗑  Vaciar carrito",
                  command=self._vaciar_carrito,
                  bg=BG_CARD, fg=FG_SECONDARY, font=("Segoe UI", 10),
                  relief="flat", highlightthickness=1, highlightbackground=ACCENT2,
                  cursor="hand2").pack(fill="x", padx=20, pady=4)

        self._cargar_areas()
        self._cargar_empleados()
        if self.cliente_actual:
            for k in self.cb_cliente["values"]:
                if self.cliente_actual["celular"] in k:
                    self.cb_cliente.set(k)
                    self._cargar_agenda_cliente()
                    break

    # ------- Cargas (Neon PostgreSQL - spa-bar) -------
    def _cargar_clientes(self):
        conn = conectar_bd()
        cur = conn.cursor()
        cur.execute("SELECT id_cliente, nombre_apellido, nro_celular FROM cliente ORDER BY nombre_apellido ASC")
        filas = cur.fetchall()
        conn.close()
        self.dict_clientes = {f"{r[1]} - {r[2]}": r[0] for r in filas}
        self.cb_cliente["values"] = list(self.dict_clientes.keys())

    def _cargar_areas(self):
        conn = conectar_bd()
        cur = conn.cursor()
        cur.execute(
            "SELECT id_area, nom_area, nom_departamento FROM area "
            "ORDER BY nom_area ASC, nom_departamento ASC"
        )
        filas = cur.fetchall()
        conn.close()
        self.dict_areas = {f"{r[1]} - {r[2] or 'General'}": r[0] for r in filas}
        self.cb_area["values"] = list(self.dict_areas.keys())

    def _cargar_servicios_area(self):
        id_area = self.dict_areas.get(self.cb_area.get())
        if not id_area:
            return
        conn = conectar_bd()
        cur = conn.cursor()
        cur.execute(
            "SELECT id_servicio, nom_servicio, estilo, precio "
            "FROM servicio WHERE id_area = %s ORDER BY nom_servicio ASC",
            (id_area,),
        )
        filas = cur.fetchall()
        conn.close()
        self.dict_serv_area = {
            f"{r[1]} [{r[2] or 'Estándar'}] - ${float(r[3] or 0):.2f}": (r[0], float(r[3] or 0))
            for r in filas
        }
        self.cb_serv_area["values"] = list(self.dict_serv_area.keys())

    def _cargar_empleados(self):
        conn = conectar_bd()
        cur = conn.cursor()
        cur.execute("SELECT id_empleado, nombres, apellidos, cedula FROM empleado ORDER BY nombres ASC, apellidos ASC")
        filas = cur.fetchall()
        conn.close()
        self.dict_empleados = {f"{r[1]} {r[2]}": r[0] for r in filas}
        self.cb_emp["values"] = list(self.dict_empleados.keys())

    def _cargar_servicios_emp(self):
        id_emp = self.dict_empleados.get(self.cb_emp.get())
        if not id_emp:
            return
        conn = conectar_bd()
        cur = conn.cursor()
        cur.execute("""
            SELECT s.id_servicio, s.nom_servicio, s.estilo, s.precio
            FROM servicio s
            JOIN empleado_servicio es ON s.id_servicio = es.id_servicio
            WHERE es.id_empleado = %s AND UPPER(COALESCE(es.activo, 'SI')) = 'SI'
            ORDER BY s.nom_servicio ASC
        """, (id_emp,))
        filas = cur.fetchall()
        conn.close()
        self.dict_serv_emp = {
            f"{r[1]} [{r[2] or 'Estándar'}] - ${float(r[3] or 0):.2f}": (r[0], float(r[3] or 0))
            for r in filas
        }
        self.cb_serv_emp["values"] = list(self.dict_serv_emp.keys())

    def _cargar_agenda_cliente(self):
        for i in self.tree_agenda.get_children():
            self.tree_agenda.delete(i)
        id_cli = self.dict_clientes.get(self.cb_cliente.get())
        if not id_cli:
            return
        hoy = datetime.date.today().strftime("%Y-%m-%d")
        conn = conectar_bd()
        cur = conn.cursor()
        cur.execute("""
            SELECT a.fecha_reserva, sa.hora, s.nom_servicio
            FROM servicios_agendados sa
            JOIN agenda a ON sa.id_agenda = a.id_agenda
            JOIN servicio s ON sa.id_servicio = s.id_servicio
            WHERE a.id_cliente = %s AND a.fecha_reserva >= %s
            ORDER BY a.fecha_reserva, sa.hora
        """, (id_cli, hoy))
        for r in cur.fetchall():
            self.tree_agenda.insert("", "end", values=r)
        conn.close()

    # ------- Carrito -------
    def _agregar_al_carrito(self, modo):
        if not self.cb_cliente.get():
            messagebox.showwarning("Falta", "Selecciona el cliente.")
            return
        if len(self.carrito) >= 3:
            messagebox.showwarning("Límite", "Máximo 3 servicios por reserva.")
            return

        fecha = self.cb_fecha.get()
        hora = self.cb_hora.get()

        if modo == 0:
            if not self.cb_area.get() or not self.cb_serv_area.get():
                messagebox.showwarning("Falta", "Selecciona área y servicio.")
                return
            id_serv, precio = self.dict_serv_area[self.cb_serv_area.get()]
            nombre_serv = self.cb_serv_area.get().split(" [")[0]
            id_emp = self._buscar_empleado_libre(id_serv, fecha, hora)
            if not id_emp:
                messagebox.showerror("Sin disponibilidad",
                                     f"No hay empleado libre a las {hora}.")
                return
            nombre_emp = self._nombre_empleado(id_emp)
        else:
            if not self.cb_emp.get() or not self.cb_serv_emp.get():
                messagebox.showwarning("Falta", "Selecciona empleado y servicio.")
                return
            id_emp = self.dict_empleados[self.cb_emp.get()]
            id_serv, precio = self.dict_serv_emp[self.cb_serv_emp.get()]
            nombre_serv = self.cb_serv_emp.get().split(" [")[0]
            nombre_emp = self.cb_emp.get()
            if self._empleado_ocupado(id_emp, fecha, hora):
                messagebox.showerror("Ocupado",
                                     f"{nombre_emp} ya tiene cita a las {hora}.")
                return

        for it in self.carrito:
            if it["hora"] == hora:
                messagebox.showwarning("Hora ocupada",
                                       f"Ya hay un servicio a las {hora}.")
                return
            if it["id_servicio"] == id_serv:
                messagebox.showwarning("Duplicado",
                                       "Ese servicio ya está en el carrito.")
                return

        self.carrito.append({
            "id_servicio": id_serv,
            "nom_servicio": nombre_serv,
            "id_empleado": id_emp,
            "nom_empleado": nombre_emp,
            "hora": hora,
            "precio": precio,
            "fecha": fecha,
        })
        self._refrescar_carrito()

    def _refrescar_carrito(self):
        self.lb_carrito.delete(0, tk.END)
        for it in self.carrito:
            self.lb_carrito.insert(
                tk.END,
                f"• {it['hora']}  {it['nom_servicio'][:18]:<18} ${it['precio']:.2f}")

    def _vaciar_carrito(self):
        self.carrito.clear()
        self._refrescar_carrito()

    def _buscar_empleado_libre(self, id_servicio, fecha, hora):
        conn = conectar_bd()
        cur = conn.cursor()
        cur.execute("""
            SELECT e.id_empleado FROM empleado e
            JOIN empleado_servicio es ON e.id_empleado = es.id_empleado
            WHERE es.id_servicio = %s AND UPPER(COALESCE(es.activo, 'SI')) = 'SI'
        """, (id_servicio,))
        candidatos = [r[0] for r in cur.fetchall()]
        for emp in candidatos:
            if not self._empleado_ocupado(emp, fecha, hora, cur):
                conn.close()
                return emp
        conn.close()
        return None

    def _empleado_ocupado(self, id_emp, fecha, hora, cursor=None):
        cerrar = False
        if cursor is None:
            conn = conectar_bd()
            cursor = conn.cursor()
            cerrar = True
        cursor.execute("""
            SELECT COUNT(*) FROM servicios_agendados sa
            JOIN agenda a ON sa.id_agenda = a.id_agenda
            WHERE sa.id_empleado = %s AND a.fecha_reserva = %s AND sa.hora = %s
        """, (id_emp, fecha, hora))
        ocupado = cursor.fetchone()[0] > 0
        if cerrar:
            conn.close()
        return ocupado

    def _nombre_empleado(self, id_emp):
        conn = conectar_bd()
        cur = conn.cursor()
        cur.execute("SELECT nombres || ' ' || apellidos FROM empleado"
                    " WHERE id_empleado = %s", (id_emp,))
        r = cur.fetchone()
        conn.close()
        return r[0] if r else "Empleado"

    def _confirmar_reserva(self):
        if not self.carrito:
            messagebox.showwarning("Carrito vacío", "Agrega al menos un servicio.")
            return
        id_cli = self.dict_clientes.get(self.cb_cliente.get())
        if not id_cli:
            return

        fecha = self.carrito[0]["fecha"]
        subtotal = sum(it["precio"] for it in self.carrito)
        fecha_sistem = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = conectar_bd()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO agenda (id_cliente, fecha_sistem, fecha_reserva, total, propina)
            VALUES (%s, %s, %s, %s, 0) RETURNING id_agenda
        """, (id_cli, fecha_sistem, fecha, subtotal))
        id_agenda = cur.fetchone()[0]
        for it in self.carrito:
            cur.execute("""
                INSERT INTO servicios_agendados
                (id_agenda, id_servicio, id_empleado, hora, precio, atendido)
                VALUES (%s, %s, %s, %s, %s, 'NO')
            """, (id_agenda, it["id_servicio"], it["id_empleado"],
                  it["hora"], it["precio"]))
        conn.commit()
        conn.close()

        messagebox.showinfo("Reserva confirmada",
                            f"Total: ${subtotal:.2f}\nFecha: {fecha}\n"
                            f"{len(self.carrito)} servicio(s)")
        if messagebox.askyesno("Alarmas",
                               "¿Quieres configurar recordatorios para esta reserva?"):
            self.mostrar_alarmas(id_agenda, fecha, self.carrito[0]["hora"])
        else:
            self._vaciar_carrito()
            self._cargar_agenda_cliente()

    # ==================================================================
    # PANTALLA 4: ALARMAS
    # ==================================================================
    def mostrar_alarmas(self, id_agenda, fecha, hora_base):
        self._limpiar()
        root = tk.Frame(self.container, bg=BG_MAIN)
        root.pack(fill="both", expand=True)

        self._header(root, "🔔  Alarmas")

        tk.Button(root, text="←  Volver", command=self.mostrar_inicio,
                  bg=BG_CARD, fg=ACCENT_BRIGHT, font=("Segoe UI", 11, "bold"),
                  relief="flat", highlightthickness=1, highlightbackground=ACCENT2,
                  cursor="hand2").pack(fill="x", padx=20, pady=(8, 0))

        tk.Label(root,
                 text=f"Reserva del {fecha} a las {hora_base}",
                 bg=BG_MAIN, fg=ACCENT_BRIGHT,
                 font=("Segoe UI", 12, "bold")).pack(pady=(15, 5))
        tk.Label(root,
                 text="Activa hasta 3 recordatorios. Elige el tiempo y el tono.",
                 bg=BG_MAIN, fg=FG_SECONDARY,
                 font=("Segoe UI", 9, "italic")).pack(pady=(0, 20))

        self._alarmas_form = []
        for minutos in TIEMPOS_ALARMA:
            card = tk.Frame(root, bg=BG_CARD, highlightthickness=1,
                            highlightbackground=ACCENT2)
            card.pack(fill="x", padx=20, pady=6)

            fila_top = tk.Frame(card, bg=BG_CARD)
            fila_top.pack(fill="x", padx=10, pady=(8, 4))
            var_act = tk.BooleanVar(value=False)
            tk.Checkbutton(fila_top, text=f"⏰ {minutos} min antes",
                           variable=var_act, bg=BG_CARD, fg=FG_PRIMARY,
                           selectcolor=BG_INPUT, activebackground=BG_CARD,
                           activeforeground=ACCENT_BRIGHT,
                           font=("Segoe UI", 11, "bold")).pack(side="left")

            fila_mid = tk.Frame(card, bg=BG_CARD)
            fila_mid.pack(fill="x", padx=10, pady=(0, 8))
            tk.Label(fila_mid, text="Tono:", bg=BG_CARD, fg=FG_SECONDARY,
                     font=("Segoe UI", 9)).pack(side="left")
            cb_tono = ttk.Combobox(fila_mid, values=TONOS_DISPONIBLES,
                                   state="readonly", width=14)
            cb_tono.current(0)
            cb_tono.pack(side="left", padx=8)
            tk.Button(fila_mid, text="▶ Probar",
                      command=lambda c=cb_tono: self._reproducir_tono_async(c.get()),
                      bg=BG_INPUT, fg=ACCENT, relief="flat",
                      font=("Segoe UI", 9, "bold")).pack(side="right")

            self._alarmas_form.append({
                "minutos": minutos, "var": var_act, "cb_tono": cb_tono
            })

        def guardar():
            for entry in self._alarmas_form:
                if entry["var"].get():
                    self.alarmas.append({
                        "id_agenda": id_agenda,
                        "fecha_reserva": fecha,
                        "hora_reserva": hora_base,
                        "minutos_antes": entry["minutos"],
                        "tono": entry["cb_tono"].get(),
                        "activa": True,
                        "disparada": False,
                    })
            messagebox.showinfo("Alarmas", "Recordatorios guardados.")
            self._vaciar_carrito()
            self.mostrar_inicio()

        self._btn(root, "💾  GUARDAR ALARMAS", guardar,
                  bg=ACCENT, fg="#070605", size=13)
        self._btn(root, "←  Omitir", self._volver_sin_alarma,
                  bg=BG_CARD, fg=FG_SECONDARY, size=11, pady=8)

    def _volver_sin_alarma(self):
        self._vaciar_carrito()
        self.mostrar_inicio()

    def _reproducir_tono_async(self, tono):
        def _play():
            try:
                if HAS_WINSOUND:
                    if tono == "Beep Corto":
                        winsound.Beep(700, 350)
                    elif tono == "Beep Doble":
                        winsound.Beep(900, 200)
                        time.sleep(0.1)
                        winsound.Beep(900, 200)
                    else:
                        for _ in range(3):
                            winsound.Beep(1100, 350)
                            time.sleep(0.12)
            except Exception:
                pass
        threading.Thread(target=_play, daemon=True).start()
        try:
            self.bell()
        except Exception:
            pass

    def _poll_alarmas(self):
        try:
            ahora = datetime.datetime.now()
            for alarma in self.alarmas:
                if not alarma["activa"] or alarma["disparada"]:
                    continue
                try:
                    fh = datetime.datetime.strptime(
                        f"{alarma['fecha_reserva']} {alarma['hora_reserva']}",
                        "%Y-%m-%d %H:%M")
                except ValueError:
                    continue
                target = fh - datetime.timedelta(minutes=alarma["minutos_antes"])
                if ahora >= target:
                    alarma["disparada"] = True
                    self._disparar_alarma(alarma)
        except Exception:
            pass
        self.timer_alarmas = self.after(20000, self._poll_alarmas)

    def _disparar_alarma(self, alarma):
        self._reproducir_tono_async(alarma["tono"])
        messagebox.showinfo(
            "🔔 Recordatorio",
            f"Tu cita es a las {alarma['hora_reserva']} el "
            f"{alarma['fecha_reserva']}.\n(Faltan {alarma['minutos_antes']} min)")

    # ==================================================================
    # PANTALLA 5: GALERÍA / REVISTA
    # ==================================================================
    def mostrar_galeria(self):
        self._limpiar()
        root = tk.Frame(self.container, bg=BG_MAIN)
        root.pack(fill="both", expand=True)

        f_header = tk.Frame(root, bg=BG_CARD, height=70,
                            highlightthickness=1, highlightbackground=ACCENT2)
        f_header.pack(fill="x")
        f_header.pack_propagate(False)

        tk.Button(f_header, text="←  Volver",
                  command=self.mostrar_inicio,
                  bg=BG_CARD, fg=ACCENT_BRIGHT,
                  font=("Segoe UI", 10, "bold"),
                  relief="flat", cursor="hand2",
                  activebackground=BG_CARD, activeforeground=ACCENT
                  ).pack(side="left", padx=(10, 0), pady=15)

        tk.Label(f_header, text="🖼  Galería / Revista",
                 bg=BG_CARD, fg=ACCENT_BRIGHT,
                 font=("Segoe UI", 15, "bold")
                 ).pack(side="left", expand=True, pady=18)

        f_top = tk.Frame(root, bg=BG_MAIN)
        f_top.pack(fill="x", padx=15, pady=(8, 4))

        tk.Label(f_top, text="Servicio:", bg=BG_MAIN, fg=FG_SECONDARY,
                 font=("Segoe UI", 10)).pack(side="left")

        self.cb_gal_serv = ttk.Combobox(f_top, state="readonly", width=24)
        self.cb_gal_serv.pack(side="left", padx=8)

        tk.Button(f_top, text="🔍", command=self._cargar_galeria,
                  bg=ACCENT, fg="#070605", relief="flat",
                  font=("Segoe UI", 11, "bold"),
                  activebackground=ACCENT_BRIGHT).pack(side="left")

        self._cargar_combo_servicios_galeria()

        self.f_cine = tk.Frame(root, bg=BG_CARD, highlightthickness=1,
                               highlightbackground=ACCENT2)
        self.f_cine.pack(fill="both", expand=True, padx=15, pady=(4, 8))

        self.lbl_foto = tk.Label(self.f_cine, bg=BG_CARD,
                                 text="[ Selecciona un servicio y pulsa 🔍 ]",
                                 fg=FG_SECONDARY, font=("Segoe UI", 11),
                                 anchor="center")
        self.lbl_foto.pack(fill="both", expand=True)

        self.lbl_foto.bind("<Button-1>", lambda e: self._toggle_pausa_carrusel())
        self.f_cine.bind("<Button-1>",   lambda e: self._toggle_pausa_carrusel())

        self.lbl_tag = tk.Label(root, text="", bg=BG_MAIN,
                                fg=ACCENT_BRIGHT, font=("Segoe UI", 11, "bold"))
        self.lbl_tag.pack(fill="x")

        self.lbl_estado_carrusel = tk.Label(root, text="",
                                            bg=BG_MAIN, fg=ACCENT,
                                            font=("Segoe UI", 9, "italic"))
        self.lbl_estado_carrusel.pack(fill="x", pady=(0, 8))

        self.lbl_info_titulo = tk.Label(
            root, text="", bg=BG_MAIN, fg=FG_PRIMARY,
            font=("Segoe UI", 11, "bold"),
            wraplength=400, justify="center")
        self.lbl_info_titulo.pack(fill="x", padx=20, pady=(4, 0))

        self.lbl_info = tk.Label(
            root, text="", bg=BG_MAIN, fg=FG_SECONDARY,
            font=("Segoe UI", 9),
            wraplength=400, justify="center")
        self.lbl_info.pack(fill="x", padx=20, pady=(0, 8))

        f_nav = tk.Frame(root, bg=BG_MAIN)
        f_nav.pack(fill="x", pady=(4, 15))

        self.btn_prev = tk.Button(
            f_nav, text="◀", command=self._gal_prev,
            bg=BG_CARD, fg=ACCENT_BRIGHT,
            font=("Segoe UI", 14, "bold"),
            relief="flat", highlightthickness=1, highlightbackground=ACCENT2,
            width=4, cursor="hand2",
            activebackground=ACCENT, activeforeground="#070605")
        self.btn_prev.pack(side="left", padx=15)

        self.lbl_contador = tk.Label(
            f_nav, text="0/0", bg=BG_MAIN, fg=FG_SECONDARY,
            font=("Segoe UI", 11, "bold"))
        self.lbl_contador.pack(side="left", expand=True)

        self.btn_next = tk.Button(
            f_nav, text="▶", command=self._gal_next,
            bg=BG_CARD, fg=ACCENT_BRIGHT,
            font=("Segoe UI", 14, "bold"),
            relief="flat", highlightthickness=1, highlightbackground=ACCENT2,
            width=4, cursor="hand2",
            activebackground=ACCENT, activeforeground="#070605")
        self.btn_next.pack(side="right", padx=15)

    def _cargar_combo_servicios_galeria(self):
        conn = conectar_bd()
        cur = conn.cursor()
        cur.execute("SELECT id_servicio, nom_servicio, estilo FROM servicio ORDER BY nom_servicio ASC")
        filas = cur.fetchall()
        conn.close()
        self.dict_gal_serv = {f"{r[1]} [{r[2] or 'Estándar'}]": r[0] for r in filas}
        self.cb_gal_serv["values"] = ["-- Ver Todos --"] + list(self.dict_gal_serv.keys())
        self.cb_gal_serv.current(0)

    def _cargar_galeria(self):
        self.carrusel_pausado = False
        self._actualizar_estado_carrusel()

        sel = self.cb_gal_serv.get()
        conn = conectar_bd()
        cur = conn.cursor()
        if sel == "-- Ver Todos --" or not sel:
            cur.execute("""
                SELECT s.nom_servicio, s.estilo, g.doc_frente, g.doc_lado,
                       g.doc_atras, g.descripcion, g.fecha
                FROM galeria g
                JOIN servicio s ON g.id_servicio = s.id_servicio
                WHERE UPPER(COALESCE(g.activo, 'SI')) = 'SI'
                ORDER BY s.nom_servicio, g.id_galeria DESC
            """)
        else:
            id_serv = self.dict_gal_serv.get(sel)
            cur.execute("""
                SELECT s.nom_servicio, s.estilo, g.doc_frente, g.doc_lado,
                       g.doc_atras, g.descripcion, g.fecha
                FROM galeria g
                JOIN servicio s ON g.id_servicio = s.id_servicio
                WHERE g.id_servicio = %s AND UPPER(COALESCE(g.activo, 'SI')) = 'SI'
                ORDER BY g.id_galeria DESC
            """, (id_serv,))
        self.galeria_items = cur.fetchall()
        conn.close()

        if not self.galeria_items:
            self.lbl_foto.config(image="", text="[ Sin registros ]")
            self.lbl_tag.config(text="")
            self.lbl_info_titulo.config(text="")
            self.lbl_info.config(text="")
            self.lbl_contador.config(text="0/0")
            self.lbl_estado_carrusel.config(text="")
            return

        self.indice_galeria = 0
        self._mostrar_gal_item()

    def _mostrar_gal_item(self):
        if not self.galeria_items:
            return
        item = self.galeria_items[self.indice_galeria]

        self.lbl_info_titulo.config(text=item[0])
        estilo = item[1] or "—"
        desc = item[5] or "—"
        fecha = item[6] or "—"
        self.lbl_info.config(
            text=f"Estilo: {estilo}   |   Fecha: {fecha}\n{desc}")

        self.lbl_contador.config(
            text=f"{self.indice_galeria + 1}/{len(self.galeria_items)}")

        self.vistas = [
            (item[2], "1. FRENTE"),
            (item[3], "2. LADO / PERFIL"),
            (item[4], "3. ATRÁS / POSTERIOR"),
        ]
        self.sub_indice_vista = 0

        if self.timer_carrusel:
            try:
                self.after_cancel(self.timer_carrusel)
            except Exception:
                pass
            self.timer_carrusel = None

        self._renderizar_vista_actual()
        self._programar_siguiente_frame()

    def _animar_carrusel(self):
        if self.carrusel_pausado:
            return
        if not getattr(self, "vistas", None):
            return
        self.sub_indice_vista = (self.sub_indice_vista + 1) % len(self.vistas)
        self._renderizar_vista_actual()
        self._programar_siguiente_frame()

    def _renderizar_vista_actual(self):
        if not getattr(self, "vistas", None):
            return
        ruta, tag = self.vistas[self.sub_indice_vista]
        self.lbl_tag.config(text=f"— {tag} —")
        self._render_cine(ruta)

    def _programar_siguiente_frame(self):
        if self.timer_carrusel:
            try:
                self.after_cancel(self.timer_carrusel)
            except Exception:
                pass
            self.timer_carrusel = None

        if self.carrusel_pausado:
            return
        if not getattr(self, "vistas", None):
            return

        self.timer_carrusel = self.after(3000, self._animar_carrusel)

    def _toggle_pausa_carrusel(self):
        if not getattr(self, "galeria_items", None):
            return
        self.carrusel_pausado = not self.carrusel_pausado
        self._actualizar_estado_carrusel()

        if self.carrusel_pausado:
            if self.timer_carrusel:
                try:
                    self.after_cancel(self.timer_carrusel)
                except Exception:
                    pass
                self.timer_carrusel = None
        else:
            self._renderizar_vista_actual()
            self._programar_siguiente_frame()

    def _actualizar_estado_carrusel(self):
        if not hasattr(self, "lbl_estado_carrusel"):
            return
        if self.carrusel_pausado:
            self.lbl_estado_carrusel.config(
                text="⏸  PAUSADO  —  toca la foto para reanudar", fg=WARN)
        else:
            self.lbl_estado_carrusel.config(
                text="▶  REPRODUCIENDO  —  toca la foto para pausar", fg=ACCENT)

    def _resolver_ruta_imagen(self, ruta):
        if not ruta:
            return None
        limpia = str(ruta).strip()
        if not limpia or limpia.lower().startswith("data:image"):
            return None
        if os.path.isabs(limpia) and os.path.exists(limpia):
            return limpia

        base_dir = os.path.dirname(os.path.abspath(__file__))
        candidatas = [
            limpia,
            os.path.join(base_dir, limpia),
            os.path.join(base_dir, "galeria", os.path.basename(limpia)),
            os.path.join(base_dir, "static", "galeria", os.path.basename(limpia)),
            os.path.join(base_dir, "imagenes", os.path.basename(limpia)),
        ]
        for cand in candidatas:
            if os.path.exists(cand):
                return cand
        return None

    def _render_cine(self, ruta):
        ruta_valida = self._resolver_ruta_imagen(ruta)
        if not ruta_valida:
            self.lbl_foto.config(image="", text="[ Sin Toma ]")
            return
        if not HAS_PIL:
            self.lbl_foto.config(image="", text=f"[ {os.path.basename(ruta_valida)} ]")
            return
        try:
            img = Image.open(ruta_valida).convert("RGB")
            img = ImageOps.fit(img, (340, 340),
                               method=Image.Resampling.LANCZOS)
            tkimg = ImageTk.PhotoImage(img)
            self.lbl_foto.image = tkimg
            self.lbl_foto.config(image=tkimg, text="")
        except Exception as e:
            self.lbl_foto.config(image="", text=f"[ Error: {e} ]")

    def _gal_prev(self):
        if not self.galeria_items:
            return
        self.indice_galeria = (self.indice_galeria - 1) % len(self.galeria_items)
        self._mostrar_gal_item()

    def _gal_next(self):
        if not self.galeria_items:
            return
        self.indice_galeria = (self.indice_galeria + 1) % len(self.galeria_items)
        self._mostrar_gal_item()

    # ==================================================================
    # PANTALLA 6: INFORME DE AGENDA
    # ==================================================================
    def mostrar_informe_agenda(self):
        self._limpiar()
        root = tk.Frame(self.container, bg=BG_MAIN)
        root.pack(fill="both", expand=True)

        f_header = tk.Frame(root, bg=BG_CARD, height=70,
                            highlightthickness=1, highlightbackground=ACCENT2)
        f_header.pack(fill="x")
        f_header.pack_propagate(False)

        tk.Button(f_header, text="←  Volver",
                  command=self.mostrar_inicio,
                  bg=BG_CARD, fg=ACCENT_BRIGHT,
                  font=("Segoe UI", 10, "bold"),
                  relief="flat", cursor="hand2",
                  activebackground=BG_CARD, activeforeground=ACCENT
                  ).pack(side="left", padx=(10, 0), pady=15)

        tk.Label(f_header, text="📋  Informe de Agenda",
                 bg=BG_CARD, fg=ACCENT_BRIGHT,
                 font=("Segoe UI", 15, "bold")
                 ).pack(side="left", expand=True, pady=18)

        filtros = tk.Frame(root, bg=BG_MAIN)
        filtros.pack(fill="x", padx=8, pady=6)

        tk.Label(filtros, text="Fecha:", bg=BG_MAIN, fg=FG_SECONDARY,
                 font=("Segoe UI", 9)).grid(row=0, column=0, sticky="e", padx=2)

        self.cb_inf_fecha = ttk.Combobox(filtros, width=11, state="readonly")
        hoy = datetime.date.today()
        self.cb_inf_fecha["values"] = [
            (hoy + datetime.timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(5)]
        self.cb_inf_fecha.current(0)
        self.cb_inf_fecha.grid(row=0, column=1, padx=2)
        self.cb_inf_fecha.bind("<<ComboboxSelected>>",
                               lambda e: self._cargar_informe_agenda())

        ttk.Checkbutton(filtros, text="Precios",
                        variable=self.var_ver_precios,
                        command=self._cargar_informe_agenda
                        ).grid(row=0, column=2, padx=3)

        self.btn_orden_inf = tk.Button(
            filtros,
            text="🔀 HORA" if self.orden_informe == "HORA" else "🔀 EMPLEADO",
            command=self._toggle_orden_informe,
            bg=BG_CARD, fg=ACCENT_BRIGHT, relief="flat",
            highlightthickness=1, highlightbackground=ACCENT2,
            font=("Segoe UI", 9, "bold"))
        self.btn_orden_inf.grid(row=0, column=3, padx=2)

        self.btn_atend_inf = tk.Button(
            filtros,
            text="👁 TODAS" if not self.ver_solo_atendidas else "👁 ATENDIDAS",
            command=self._toggle_ver_atendidas,
            bg=BG_CARD, fg=WARN, relief="flat",
            highlightthickness=1, highlightbackground=ACCENT2,
            font=("Segoe UI", 9, "bold"))
        self.btn_atend_inf.grid(row=0, column=4, padx=2)

        tk.Button(filtros, text="🔄", command=self._cargar_informe_agenda,
                  bg=ACCENT, fg="#070605", relief="flat",
                  font=("Segoe UI", 10, "bold")).grid(row=0, column=5, padx=2)

        f_tree = tk.Frame(root, bg=BG_MAIN)
        f_tree.pack(fill="both", expand=True, padx=6, pady=4)

        self.tree_informe = ttk.Treeview(
            f_tree,
            columns=("Atend", "Hora", "Estado", "Servicio",
                     "Empleado", "Cliente", "Precio"),
            show="headings",
            height=18)

        self.tree_informe.tag_configure("res_par",    background="#3B2808", foreground="#FDE68A")
        self.tree_informe.tag_configure("res_impar",  background="#4D340B", foreground="#FEF3C7")
        self.tree_informe.tag_configure("aten_par",   background="#143622", foreground="#86EFAC")
        self.tree_informe.tag_configure("aten_impar", background="#1B462D", foreground="#BBF7D0")
        self.tree_informe.tag_configure("libre_par",  background="#16120E", foreground="#C7B9A5")
        self.tree_informe.tag_configure("libre_impar",background="#1E1813", foreground="#D6C7B2")
        self.tree_informe.tag_configure("emp_header", background="#2A1F12", foreground=ACCENT_BRIGHT,
                                        font=("Segoe UI", 9, "bold"))
        self.tree_informe.tag_configure("agendar_otra", background="#261D12",
                                        foreground=ACCENT,
                                        font=("Segoe UI", 8, "italic"))

        vsb = ttk.Scrollbar(f_tree, orient="vertical",   command=self.tree_informe.yview)
        hsb = ttk.Scrollbar(f_tree, orient="horizontal", command=self.tree_informe.xview)
        self.tree_informe.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree_informe.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        f_tree.grid_rowconfigure(0, weight=1)
        f_tree.grid_columnconfigure(0, weight=1)

        for col, txt, w in [
            ("Atend", "Atend", 38), ("Hora", "Hora", 45),
            ("Estado", "Estado", 95), ("Servicio", "Servicio", 110),
            ("Empleado", "Empleado", 95), ("Cliente", "Cliente", 95),
            ("Precio", "Precio", 60),
        ]:
            self.tree_informe.heading(col, text=txt)
            self.tree_informe.column(col, width=w, anchor="center")

        self.tree_informe.bind("<Button-1>",        self.on_tree_click_checkbox)
        self.tree_informe.bind("<Double-Button-1>", self.abrir_modificacion_cita)

        self.lbl_total_informe = tk.Label(root, text="", bg=BG_MAIN, fg=ACCENT_BRIGHT,
                                          font=("Segoe UI", 10, "bold"))
        self.lbl_total_informe.pack(fill="x", padx=15, pady=(6, 0))

        self.lbl_resumen_atendidas = tk.Label(root, text="", bg=BG_MAIN, fg=WARN,
                                              font=("Segoe UI", 9, "italic"))
        self.lbl_resumen_atendidas.pack(fill="x", padx=15, pady=(0, 8))

        self._cargar_informe_agenda()

    def _cargar_informe_agenda(self):
        fecha = self.cb_inf_fecha.get().strip()
        if not fecha:
            return
        for i in self.tree_informe.get_children():
            self.tree_informe.delete(i)

        conn = conectar_bd()
        cur = conn.cursor()
        cur.execute("""
            SELECT sa.id_ser_agen, sa.hora, s.nom_servicio,
                   e.nombres || ' ' || e.apellidos,
                   c.nombre_apellido, sa.precio,
                   e.id_empleado, sa.atendido
            FROM servicios_agendados sa
            JOIN agenda a ON sa.id_agenda = a.id_agenda
            JOIN servicio s ON sa.id_servicio = s.id_servicio
            JOIN empleado e ON sa.id_empleado = e.id_empleado
            JOIN cliente c ON a.id_cliente = c.id_cliente
            WHERE a.fecha_reserva = %s
            ORDER BY sa.hora ASC, e.nombres ASC, e.apellidos ASC
        """, (fecha,))
        rows = cur.fetchall()

        cur.execute("""
            SELECT SUM(sa.precio) FROM servicios_agendados sa
            JOIN agenda a ON sa.id_agenda = a.id_agenda
            WHERE a.fecha_reserva = %s
        """, (fecha,))
        total_suma = float(cur.fetchone()[0] or 0.0)
        conn.close()

        if self.ver_solo_atendidas:
            rows = [r for r in rows if (r[7] or "NO").upper() == "SI"]

        ver_precios = self.var_ver_precios.get()

        if self.orden_informe == "HORA":
            self._render_informe_por_hora(rows, ver_precios)
        else:
            self._render_informe_por_empleado(rows, ver_precios)

        atendidas_citas = [r for r in rows if (r[7] or "NO").upper() == "SI"]
        cant_atendidas = len(atendidas_citas)
        suma_atendidas = sum(float(r[5] or 0.0) for r in atendidas_citas)

        if ver_precios:
            self.lbl_total_informe.config(
                text=f"Sumatoria Total de Precios: ${total_suma:.2f}")
            self.lbl_resumen_atendidas.config(
                text=f"Resumen Atendidas: {cant_atendidas} cita(s) | "
                     f"Ingresos por atendidas: ${suma_atendidas:.2f}")
        else:
            self.lbl_total_informe.config(
                text="Sumatoria Total de Precios: [OCULTO POR VERIFICACIÓN]")
            self.lbl_resumen_atendidas.config(
                text=f"Resumen Atendidas: {cant_atendidas} cita(s) | "
                     f"Ingresos por atendidas: [OCULTO]")

    def _render_informe_por_hora(self, rows, ver_precios):
        citas_hora = {}
        for r in rows:
            citas_hora.setdefault(r[1], []).append(r)

        horas = [f"{h:02d}:00" for h in range(8, 21)]
        rc, lc = 0, 0
        for hora in horas:
            citas = citas_hora.get(hora, [])
            if citas:
                for idx, r in enumerate(citas):
                    atendido = (r[7] or "NO").upper() == "SI"
                    tag = ("aten_par" if rc % 2 == 0 else "aten_impar") if atendido \
                          else ("res_par" if rc % 2 == 0 else "res_impar")
                    rc += 1
                    precio_txt = f"${float(r[5] or 0):.2f}" if ver_precios else "******"
                    hora_txt = hora if idx == 0 else ""
                    self.tree_informe.insert(
                        "", "end",
                        iid=f"cita_{r[0]}",
                        values=("☑" if atendido else "☐", hora_txt, "RESERVADO",
                                r[2], r[3], r[4], precio_txt),
                        tags=(tag,))

                self.tree_informe.insert(
                    "", "end", iid=f"libre_{hora}",
                    values=("", "", "↳ [ AGENDAR OTRA ]", "-----", "-----",
                            "-----", "$0.00" if ver_precios else "******"),
                    tags=("agendar_otra",))
            else:
                tag = "libre_par" if lc % 2 == 0 else "libre_impar"
                lc += 1
                self.tree_informe.insert(
                    "", "end", iid=f"libre_{hora}",
                    values=("", hora, "[ DISPONIBLE ]", "-----", "-----",
                            "-----", "$0.00" if ver_precios else "******"),
                    tags=(tag,))

    def _render_informe_por_empleado(self, rows, ver_precios):
        if not rows:
            self.tree_informe.insert(
                "", "end", iid="sin_citas",
                values=("--", "--", "SIN CITAS PARA ESTA FECHA",
                        "--", "--", "--", "--"),
                tags=("libre_par",))
            return

        por_emp = {}
        for r in rows:
            por_emp.setdefault(r[3], []).append(r)

        for i, emp in enumerate(sorted(por_emp.keys())):
            citas = sorted(por_emp[emp], key=lambda x: x[1])
            aten = sum(1 for c in citas if (c[7] or "NO").upper() == "SI")
            self.tree_informe.insert(
                "", "end", iid=f"emp_hdr_{i}",
                values=(f"👤 {emp} - {len(citas)} cita(s) - {aten} atendida(s)",
                        "", "", "", "", "", ""),
                tags=("emp_header",))
            for idx, r in enumerate(citas):
                atendido = (r[7] or "NO").upper() == "SI"
                tag = ("aten_par" if idx % 2 == 0 else "aten_impar") if atendido \
                      else ("res_par" if idx % 2 == 0 else "res_impar")
                precio_txt = f"${float(r[5] or 0):.2f}" if ver_precios else "******"
                self.tree_informe.insert(
                    "", "end", iid=f"cita_{r[0]}",
                    values=("☑" if atendido else "☐", r[1], "RESERVADO",
                            r[2], r[3], r[4], precio_txt),
                    tags=(tag,))

    def _toggle_orden_informe(self):
        self.orden_informe = "EMPLEADO" if self.orden_informe == "HORA" else "HORA"
        self.btn_orden_inf.config(
            text="🔀 HORA" if self.orden_informe == "HORA" else "🔀 EMPLEADO")
        self._cargar_informe_agenda()

    def _toggle_ver_atendidas(self):
        self.ver_solo_atendidas = not self.ver_solo_atendidas
        self.btn_atend_inf.config(
            text="👁 TODAS" if not self.ver_solo_atendidas else "👁 ATENDIDAS")
        self._cargar_informe_agenda()

    def on_tree_click_checkbox(self, event):
        col = self.tree_informe.identify_column(event.x)
        iid = self.tree_informe.identify_row(event.y)
        if not iid:
            return

        if col == "#1" and iid.startswith("cita_"):
            try:
                id_ser = int(iid.split("_", 1)[1])
            except Exception:
                return
            self.toggle_atendida(id_ser)

    def toggle_atendida(self, id_ser_agen):
        conn = conectar_bd()
        cur = conn.cursor()
        cur.execute("SELECT atendido FROM servicios_agendados WHERE id_ser_agen = %s",
                    (id_ser_agen,))
        row = cur.fetchone()
        if not row:
            conn.close()
            return
        nuevo = "SI" if (row[0] or "NO").upper() != "SI" else "NO"
        cur.execute("UPDATE servicios_agendados SET atendido = %s WHERE id_ser_agen = %s",
                    (nuevo, id_ser_agen))
        conn.commit()
        conn.close()
        self._cargar_informe_agenda()

    def abrir_modificacion_cita(self, event):
        iid = self.tree_informe.identify_row(event.y)
        if not iid:
            return

        if iid.startswith("cita_"):
            try:
                id_ser = int(iid.split("_", 1)[1])
            except Exception:
                return
            self._mostrar_ventana_modificar_cita(id_ser)
        elif iid.startswith("libre_"):
            hora = iid.split("_", 1)[1]
            fecha = self.cb_inf_fecha.get().strip()
            if fecha:
                self._mostrar_ventana_agendar_desde_informe(fecha, hora)

    def _mostrar_ventana_modificar_cita(self, id_ser_agen):
        conn = conectar_bd()
        cur = conn.cursor()
        cur.execute("""
            SELECT sa.id_agenda, sa.id_servicio, sa.id_empleado, sa.hora, sa.precio,
                   a.fecha_reserva, a.id_cliente, a.propina,
                   s.nom_servicio, s.estilo,
                   e.nombres || ' ' || e.apellidos, e.cedula,
                   c.nombre_apellido, c.nro_celular, sa.atendido
            FROM servicios_agendados sa
            JOIN agenda a ON sa.id_agenda = a.id_agenda
            JOIN servicio s ON sa.id_servicio = s.id_servicio
            JOIN empleado e ON sa.id_empleado = e.id_empleado
            JOIN cliente c ON a.id_cliente = c.id_cliente
            WHERE sa.id_ser_agen = %s
        """, (id_ser_agen,))
        row = cur.fetchone()
        if not row:
            conn.close()
            messagebox.showerror("Error", "Cita no encontrada.")
            return
        (id_agenda, id_serv_act, id_emp_act, hora_act, precio_act,
         fecha_res, id_cli, propina, nom_serv, estilo,
         nom_emp_act, ced_emp, nom_cli, cel_cli, atendido_act) = row

        cur.execute("SELECT id_servicio, nom_servicio, estilo, precio "
                    "FROM servicio ORDER BY nom_servicio ASC")
        servicios = cur.fetchall()
        conn.close()

        dict_serv = {
            f"{s[1]} [{s[2] or 'Estándar'}] - ${float(s[3] or 0):.2f}": (s[0], float(s[3] or 0))
            for s in servicios
        }

        win = tk.Toplevel(self)
        win.title("Modificar Cita — BAR SAP")
        win.geometry("400x640")
        win.configure(bg=BG_MAIN)
        win.grab_set()

        tk.Label(win, text=f"👤 {nom_cli}", bg=BG_MAIN, fg=ACCENT_BRIGHT,
                 font=("Segoe UI", 12, "bold")).pack(pady=(15, 2))
        tk.Label(win, text=f"📱 {cel_cli}", bg=BG_MAIN, fg=FG_SECONDARY,
                 font=("Segoe UI", 10)).pack()

        frm = tk.Frame(win, bg=BG_MAIN)
        frm.pack(fill="both", expand=True, padx=20, pady=10)

        tk.Label(frm, text="Fecha (AAAA-MM-DD):", bg=BG_MAIN,
                 fg=FG_SECONDARY, font=("Segoe UI", 9)).pack(anchor="w")
        cb_fecha = ttk.Combobox(frm, width=25)
        hoy = datetime.date.today()
        cb_fecha["values"] = [(hoy + datetime.timedelta(days=i)).strftime("%Y-%m-%d")
                              for i in range(30)]
        cb_fecha.set(fecha_res)
        cb_fecha.pack(fill="x", pady=(0, 8))

        tk.Label(frm, text="Hora (HH:MM):", bg=BG_MAIN,
                 fg=FG_SECONDARY, font=("Segoe UI", 9)).pack(anchor="w")
        ent_hora = ttk.Entry(frm, width=25)
        ent_hora.insert(0, hora_act)
        ent_hora.pack(fill="x", pady=(0, 8))

        tk.Label(frm, text="Servicio:", bg=BG_MAIN,
                 fg=FG_SECONDARY, font=("Segoe UI", 9)).pack(anchor="w")
        cb_serv = ttk.Combobox(frm, width=25, state="readonly")
        cb_serv["values"] = list(dict_serv.keys())
        for k, v in dict_serv.items():
            if v[0] == id_serv_act:
                cb_serv.set(k)
                break
        cb_serv.pack(fill="x", pady=(0, 8))

        tk.Label(frm, text="Empleado:", bg=BG_MAIN,
                 fg=FG_SECONDARY, font=("Segoe UI", 9)).pack(anchor="w")
        cb_emp = ttk.Combobox(frm, width=25, state="readonly")
        cb_emp.pack(fill="x", pady=(0, 8))

        tk.Label(frm, text="Precio ($):", bg=BG_MAIN,
                 fg=FG_SECONDARY, font=("Segoe UI", 9)).pack(anchor="w")
        ent_precio = ttk.Entry(frm, width=25)
        ent_precio.insert(0, f"{float(precio_act or 0):.2f}")
        ent_precio.pack(fill="x", pady=(0, 8))

        var_atendida = tk.BooleanVar(value=(atendido_act or "NO").upper() == "SI")
        tk.Checkbutton(frm, text="☑ Marcar como ATENDIDA",
                       variable=var_atendida,
                       bg=BG_MAIN, fg=ACCENT_BRIGHT, selectcolor=BG_INPUT,
                       activebackground=BG_MAIN).pack(anchor="w", pady=8)

        dict_emp_temp = {}

        def cargar_emps(evt=None):
            nonlocal dict_emp_temp
            sk = cb_serv.get()
            if sk not in dict_serv:
                return
            id_s = dict_serv[sk][0]
            c2 = conectar_bd()
            cu2 = c2.cursor()
            cu2.execute("""
                SELECT e.id_empleado, e.nombres || ' ' || e.apellidos
                FROM empleado e
                JOIN empleado_servicio es ON e.id_empleado = es.id_empleado
                WHERE es.id_servicio = %s AND UPPER(COALESCE(es.activo, 'SI')) = 'SI'
            """, (id_s,))
            rr = cu2.fetchall()
            c2.close()
            dict_emp_temp = {r[1]: r[0] for r in rr}
            cb_emp["values"] = list(dict_emp_temp.keys())
            for k, v in dict_emp_temp.items():
                if v == id_emp_act:
                    cb_emp.set(k)
                    break
            else:
                if dict_emp_temp:
                    cb_emp.current(0)

        def al_cambiar_serv(evt=None):
            cargar_emps()
            sk = cb_serv.get()
            if sk in dict_serv:
                ent_precio.delete(0, tk.END)
                ent_precio.insert(0, f"{dict_serv[sk][1]:.2f}")

        cb_serv.bind("<<ComboboxSelected>>", al_cambiar_serv)
        cargar_emps()

        def guardar():
            nf = cb_fecha.get().strip()
            nh = ent_hora.get().strip()
            sk = cb_serv.get()
            ek = cb_emp.get()
            if not nf or not nh or sk not in dict_serv or ek not in dict_emp_temp:
                messagebox.showwarning("Falta", "Completa todos los campos.")
                return
            try:
                np = float(ent_precio.get().strip())
            except ValueError:
                messagebox.showerror("Error", "Precio inválido.")
                return
            ns = dict_serv[sk][0]
            ne = dict_emp_temp[ek]
            na = "SI" if var_atendida.get() else "NO"

            c3 = conectar_bd()
            cu3 = c3.cursor()
            conflictos = [
                ("""SELECT COUNT(*) FROM servicios_agendados sa
                    JOIN agenda a ON sa.id_agenda = a.id_agenda
                    WHERE sa.id_empleado=%s AND a.fecha_reserva=%s AND sa.hora=%s
                    AND sa.id_ser_agen<>%s""",
                 (ne, nf, nh, id_ser_agen),
                 "Empleado ocupado en esa fecha/hora."),
                ("""SELECT COUNT(*) FROM servicios_agendados sa
                    JOIN agenda a ON sa.id_agenda = a.id_agenda
                    WHERE a.id_cliente=%s AND a.fecha_reserva=%s AND sa.hora=%s
                    AND sa.id_ser_agen<>%s""",
                 (id_cli, nf, nh, id_ser_agen),
                 "Cliente ya tiene cita en la misma fecha/hora."),
                ("""SELECT COUNT(*) FROM servicios_agendados sa
                    JOIN agenda a ON sa.id_agenda = a.id_agenda
                    WHERE a.id_cliente=%s AND a.fecha_reserva=%s AND sa.id_servicio=%s
                    AND sa.id_ser_agen<>%s""",
                 (id_cli, nf, ns, id_ser_agen),
                 "Cliente duplica el mismo servicio en la misma fecha."),
            ]
            for q, args, msg in conflictos:
                cu3.execute(q, args)
                if cu3.fetchone()[0] > 0:
                    c3.close()
                    messagebox.showerror("Conflicto", msg)
                    return

            cu3.execute("""UPDATE servicios_agendados
                           SET id_servicio=%s, id_empleado=%s, hora=%s,
                               precio=%s, atendido=%s
                           WHERE id_ser_agen=%s""",
                        (ns, ne, nh, np, na, id_ser_agen))
            cu3.execute("UPDATE agenda SET fecha_reserva=%s WHERE id_agenda=%s",
                        (nf, id_agenda))
            cu3.execute("SELECT SUM(precio) FROM servicios_agendados WHERE id_agenda=%s",
                        (id_agenda,))
            sub = float(cu3.fetchone()[0] or 0.0)
            cu3.execute("UPDATE agenda SET total=%s WHERE id_agenda=%s",
                        (sub + float(propina or 0.0), id_agenda))
            c3.commit()
            c3.close()
            messagebox.showinfo("OK", "Cita modificada.")
            win.destroy()
            self._cargar_informe_agenda()

        def eliminar():
            if not messagebox.askyesno("Eliminar", "¿Borrar esta cita?"):
                return
            c4 = conectar_bd()
            cu4 = c4.cursor()
            cu4.execute("DELETE FROM servicios_agendados WHERE id_ser_agen=%s",
                        (id_ser_agen,))
            cu4.execute("SELECT COUNT(*) FROM servicios_agendados WHERE id_agenda=%s",
                        (id_agenda,))
            rest = cu4.fetchone()[0]
            if rest == 0:
                cu4.execute("DELETE FROM agenda WHERE id_agenda=%s", (id_agenda,))
            else:
                cu4.execute("SELECT SUM(precio) FROM servicios_agendados WHERE id_agenda=%s",
                            (id_agenda,))
                st = float(cu4.fetchone()[0] or 0.0)
                cu4.execute("UPDATE agenda SET total=%s WHERE id_agenda=%s",
                            (st + float(propina or 0.0), id_agenda))
            c4.commit()
            c4.close()
            messagebox.showinfo("OK", "Cita eliminada.")
            win.destroy()
            self._cargar_informe_agenda()

        f_btn = tk.Frame(win, bg=BG_MAIN)
        f_btn.pack(fill="x", padx=20, pady=15)
        tk.Button(f_btn, text="💾 Guardar", command=guardar,
                  bg=ACCENT, fg="#070605", font=("Segoe UI", 11, "bold"),
                  relief="flat").pack(side="left", expand=True, fill="x", padx=3)
        tk.Button(f_btn, text="🗑 Eliminar", command=eliminar,
                  bg=DANGER, fg="#FFF", font=("Segoe UI", 11, "bold"),
                  relief="flat").pack(side="left", expand=True, fill="x", padx=3)
        tk.Button(f_btn, text="✖", command=win.destroy,
                  bg=BG_CARD, fg=FG_PRIMARY, font=("Segoe UI", 11, "bold"),
                  relief="flat", width=3).pack(side="left", padx=3)

    def _mostrar_ventana_agendar_desde_informe(self, fecha, hora):
        win = tk.Toplevel(self)
        win.title(f"Agendar Reserva — BAR SAP ({fecha} {hora})")
        win.geometry("410x660")
        win.configure(bg=BG_MAIN)
        win.grab_set()

        tk.Label(win, text=f"📅 {fecha}   🕒 {hora}",
                 bg=BG_MAIN, fg=ACCENT_BRIGHT,
                 font=("Segoe UI", 13, "bold")).pack(pady=(15, 10))

        tk.Label(win, text="Cliente:", bg=BG_MAIN, fg=FG_SECONDARY,
                 font=("Segoe UI", 10)).pack(anchor="w", padx=20)
        cb_cli = ttk.Combobox(win, state="readonly", width=40)
        cb_cli["values"] = list(self.dict_clientes.keys())
        cb_cli.pack(padx=20, pady=(0, 12))

        nb = ttk.Notebook(win)
        nb.pack(fill="x", padx=20)

        t1 = tk.Frame(nb, bg=BG_CARD)
        t2 = tk.Frame(nb, bg=BG_CARD)
        nb.add(t1, text="Por Área")
        nb.add(t2, text="Por Empleado")

        tk.Label(t1, text="Área:", bg=BG_CARD, fg=FG_SECONDARY).pack(anchor="w", padx=12, pady=(8, 2))
        cb_a1 = ttk.Combobox(t1, state="readonly", width=35)
        cb_a1["values"] = list(self.dict_areas.keys())
        cb_a1.pack(padx=12)
        tk.Label(t1, text="Servicio:", bg=BG_CARD, fg=FG_SECONDARY).pack(anchor="w", padx=12, pady=(8, 2))
        cb_s1 = ttk.Combobox(t1, state="readonly", width=35)
        cb_s1.pack(padx=12, pady=(0, 12))

        d_sa = {}

        def carga_serv_area(evt=None):
            a = cb_a1.get()
            if a not in self.dict_areas:
                return
            c = conectar_bd()
            cu = c.cursor()
            cu.execute("SELECT id_servicio, nom_servicio, estilo, precio "
                       "FROM servicio WHERE id_area=%s ORDER BY nom_servicio ASC",
                       (self.dict_areas[a],))
            filas = cu.fetchall()
            c.close()
            d_sa.clear()
            d_sa.update({
                f"{r[1]} [{r[2] or 'Estándar'}] - ${float(r[3] or 0):.2f}": (r[0], float(r[3] or 0))
                for r in filas
            })
            cb_s1["values"] = list(d_sa.keys())
            cb_s1.set("")

        cb_a1.bind("<<ComboboxSelected>>", carga_serv_area)

        tk.Label(t2, text="Empleado:", bg=BG_CARD, fg=FG_SECONDARY).pack(anchor="w", padx=12, pady=(8, 2))
        cb_e2 = ttk.Combobox(t2, state="readonly", width=35)
        cb_e2["values"] = list(self.dict_empleados.keys())
        cb_e2.pack(padx=12)
        tk.Label(t2, text="Servicio:", bg=BG_CARD, fg=FG_SECONDARY).pack(anchor="w", padx=12, pady=(8, 2))
        cb_s2 = ttk.Combobox(t2, state="readonly", width=35)
        cb_s2.pack(padx=12, pady=(0, 12))

        d_se = {}

        def carga_serv_emp(evt=None):
            e = cb_e2.get()
            if e not in self.dict_empleados:
                return
            c = conectar_bd()
            cu = c.cursor()
            cu.execute("""SELECT s.id_servicio, s.nom_servicio, s.estilo, s.precio
                          FROM servicio s
                          JOIN empleado_servicio es ON s.id_servicio = es.id_servicio
                          WHERE es.id_empleado=%s AND UPPER(COALESCE(es.activo, 'SI'))='SI'
                          ORDER BY s.nom_servicio ASC""",
                       (self.dict_empleados[e],))
            filas = cu.fetchall()
            c.close()
            d_se.clear()
            d_se.update({
                f"{r[1]} [{r[2] or 'Estándar'}] - ${float(r[3] or 0):.2f}": (r[0], float(r[3] or 0))
                for r in filas
            })
            cb_s2["values"] = list(d_se.keys())
            cb_s2.set("")

        cb_e2.bind("<<ComboboxSelected>>", carga_serv_emp)

        def agendar():
            cs = cb_cli.get()
            if cs not in self.dict_clientes:
                messagebox.showwarning("Falta", "Selecciona un cliente.")
                return
            id_cli = self.dict_clientes[cs]
            modo = nb.index(nb.select())
            id_emp = None

            if modo == 0:
                sk = cb_s1.get()
                if sk not in d_sa:
                    messagebox.showwarning("Falta", "Selecciona área y servicio.")
                    return
                id_serv, precio = d_sa[sk]
            else:
                ek = cb_e2.get()
                sk = cb_s2.get()
                if ek not in self.dict_empleados or sk not in d_se:
                    messagebox.showwarning("Falta", "Selecciona empleado y servicio.")
                    return
                id_emp = self.dict_empleados[ek]
                id_serv, precio = d_se[sk]

            c = conectar_bd()
            cu = c.cursor()

            cu.execute("""SELECT COUNT(*) FROM servicios_agendados sa
                          JOIN agenda a ON sa.id_agenda = a.id_agenda
                          WHERE a.id_cliente=%s AND a.fecha_reserva=%s""",
                       (id_cli, fecha))
            if cu.fetchone()[0] >= 3:
                c.close()
                messagebox.showwarning("Límite",
                                       "Límite alcanzado: máximo 3 servicios por día por cliente.")
                return

            cu.execute("""SELECT COUNT(*) FROM servicios_agendados sa
                          JOIN agenda a ON sa.id_agenda = a.id_agenda
                          WHERE a.id_cliente=%s AND a.fecha_reserva=%s AND sa.hora=%s""",
                       (id_cli, fecha, hora))
            if cu.fetchone()[0] > 0:
                c.close()
                messagebox.showwarning("Cliente ocupado",
                                       "El cliente ya tiene una cita agendada en esta hora.")
                return

            if id_emp is None:
                cu.execute("""SELECT e.id_empleado FROM empleado e
                              JOIN empleado_servicio es ON e.id_empleado = es.id_empleado
                              WHERE es.id_servicio=%s AND UPPER(COALESCE(es.activo, 'SI'))='SI'""",
                           (id_serv,))
                for e in [r[0] for r in cu.fetchall()]:
                    if not self._empleado_ocupado(e, fecha, hora, cu):
                        id_emp = e
                        break
                if id_emp is None:
                    c.close()
                    messagebox.showerror("Sin disp.",
                                         "No hay empleado disponible para este servicio.")
                    return
            else:
                if self._empleado_ocupado(id_emp, fecha, hora, cu):
                    c.close()
                    messagebox.showerror("Ocupado",
                                         "El empleado seleccionado ya está ocupado a esa hora.")
                    return

            fs = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cu.execute("SELECT id_agenda FROM agenda WHERE id_cliente=%s AND fecha_reserva=%s"
                       " ORDER BY id_agenda DESC LIMIT 1", (id_cli, fecha))
            r = cu.fetchone()
            if r:
                id_ag = r[0]
                cu.execute("""INSERT INTO servicios_agendados
                              (id_agenda, id_servicio, id_empleado, hora, precio, atendido)
                              VALUES (%s,%s,%s,%s,%s,'NO')""",
                           (id_ag, id_serv, id_emp, hora, precio))
                cu.execute("SELECT SUM(precio) FROM servicios_agendados WHERE id_agenda=%s",
                           (id_ag,))
                sub = float(cu.fetchone()[0] or 0.0)
                cu.execute("UPDATE agenda SET total=%s WHERE id_agenda=%s", (sub, id_ag))
            else:
                cu.execute("""INSERT INTO agenda
                              (id_cliente, fecha_sistem, fecha_reserva, total, propina)
                              VALUES (%s,%s,%s,%s,0) RETURNING id_agenda""",
                           (id_cli, fs, fecha, precio))
                id_ag = cu.fetchone()[0]
                cu.execute("""INSERT INTO servicios_agendados
                              (id_agenda, id_servicio, id_empleado, hora, precio, atendido)
                              VALUES (%s,%s,%s,%s,%s,'NO')""",
                           (id_ag, id_serv, id_emp, hora, precio))
            c.commit()
            c.close()

            messagebox.showinfo("OK", f"Reserva agendada para las {hora}.")
            win.destroy()
            self._cargar_informe_agenda()

        tk.Button(win, text="✅  AGENDAR RESERVA", command=agendar,
                  bg=ACCENT, fg="#070605", font=("Segoe UI", 12, "bold"),
                  relief="flat").pack(fill="x", padx=20, pady=20)
        tk.Button(win, text="←  Cancelar", command=win.destroy,
                  bg=BG_CARD, fg=FG_SECONDARY, font=("Segoe UI", 10),
                  relief="flat").pack(fill="x", padx=20, pady=(0, 15))


# ==============================================================================
# PUNTO DE ENTRADA
# ==============================================================================
if __name__ == "__main__":
    try:
        app = AppMovil()
        app.mainloop()
    except Exception as e:
        print(f"[ERROR]: {e}", file=sys.stderr)
"""ETAPA 6 – Interfaz gráfica (Tkinter + Matplotlib).

Pestañas: Panel · Gráficas · Cálculos paso a paso · Control y eventos · Datos · Parámetros
"""
import math
import tkinter as tk
import tkinter.font as tkfont
from dataclasses import fields
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from . import modelo, verificacion
from .campos import BOOLEANOS, CAMPOS
from .explicador import explicar_paso, texto_ecuaciones
from .graficas import COLORES
from .informe import generar_informe
from .parametros import Parametros, escenarios
from .simulador import Simulador

VERDE, NARANJA, ROJO, AZUL = "#2e9e5b", "#e08a1e", "#d9534f", "#2e86c1"


def _mezclar(c1, c2, f):
    """Interpola dos colores RGB (tuplas) y devuelve '#rrggbb'."""
    f = min(1.0, max(0.0, f))
    return "#%02x%02x%02x" % tuple(int(a + (b - a) * f) for a, b in zip(c1, c2))


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Simulación y control de un invernadero – Ecuaciones diferenciales")
        self.geometry("1280x800")
        self.minsize(1000, 650)
        ttk.Style(self).theme_use("clam")
        self.fuente_mono = tkfont.nametofont("TkFixedFont").copy()
        self.fuente_mono.configure(size=10)

        self.escenarios = escenarios()
        self.corriendo = False
        self.sim = None
        self._ev_mostrados = 0
        self._ultimo_calc = None
        self._sombras = []
        self._ticks = 0
        self.vars = {}

        self._crear_barra()
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self._crear_panel()
        self._crear_graficas()
        self._crear_calculos()
        self._crear_control()
        self._crear_datos()
        self._crear_parametros()

        self.escenario_var.set("Día normal")
        self._cargar_formulario(self.escenarios["Día normal"])
        self.aplicar_parametros()

    # =========================================================== barra superior
    def _crear_barra(self):
        barra = ttk.Frame(self, padding=6)
        barra.pack(fill="x")

        ttk.Label(barra, text="Escenario:").pack(side="left")
        self.escenario_var = tk.StringVar()
        cb = ttk.Combobox(barra, textvariable=self.escenario_var, state="readonly", width=32,
                          values=list(self.escenarios))
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", self._cambiar_escenario)

        self.btn_play = ttk.Button(barra, text="▶ Iniciar", command=self.alternar)
        self.btn_play.pack(side="left", padx=2)
        ttk.Button(barra, text="⏭ Paso", command=self.un_paso).pack(side="left", padx=2)
        ttk.Button(barra, text="⏩ Ejecutar todo", command=self.ejecutar_todo).pack(side="left", padx=2)
        ttk.Button(barra, text="⟲ Reiniciar", command=self.aplicar_parametros).pack(side="left", padx=2)

        ttk.Label(barra, text="  Velocidad (pasos/tick):").pack(side="left")
        self.velocidad = tk.IntVar(value=5)
        tk.Scale(barra, from_=1, to=120, orient="horizontal", variable=self.velocidad,
                 length=130, showvalue=True).pack(side="left")

        ttk.Button(barra, text="Informe (.docx)", command=self.generar_informe).pack(side="right", padx=2)
        ttk.Button(barra, text="Exportar CSV", command=self.exportar_csv).pack(side="right", padx=2)
        ttk.Button(barra, text="Verificar modelo", command=self.verificar).pack(side="right", padx=2)

        self.progreso = ttk.Progressbar(self, mode="determinate")
        self.progreso.pack(fill="x", padx=8)
        self.lbl_tiempo = ttk.Label(self, text="", anchor="w")
        self.lbl_tiempo.pack(fill="x", padx=8)

    # ================================================================== panel
    def _crear_panel(self):
        f = ttk.Frame(self.nb)
        self.nb.add(f, text=" Panel ")
        self.cv = tk.Canvas(f, width=640, height=380, bg="white", highlightthickness=1,
                            highlightbackground="#999")
        self.cv.pack(side="left", padx=10, pady=10, anchor="n")

        der = ttk.LabelFrame(f, text="Estado del invernadero", padding=10)
        der.pack(side="left", fill="y", padx=10, pady=10)
        self.ind = {}
        for clave, texto in [("T", "Temperatura"), ("Tamb", "Temp. exterior"), ("H", "Humedad del suelo"),
                             ("L", "Luminosidad"), ("P", "Tamaño de la planta"),
                             ("riego", "Riego"), ("vent", "Ventilación"), ("luz", "Iluminación")]:
            fila = ttk.Frame(der)
            fila.pack(fill="x", pady=3)
            ttk.Label(fila, text=texto + ":", width=20).pack(side="left")
            lbl = tk.Label(fila, text="–", width=16, fg="white", bg="#888", font=("TkDefaultFont", 10, "bold"))
            lbl.pack(side="left")
            self.ind[clave] = lbl
        ttk.Label(der, text="\nVerde = dentro del rango\nNaranja/Rojo = fuera del rango\n"
                            "Azul = por encima del rango (humedad)", foreground="#555").pack(anchor="w")

    def _dibujar_panel(self):
        cv, p, r = self.cv, self.sim.p, self.sim.actual
        W, Hh = 640, 380
        cv.delete("all")
        hora = modelo.hora_del_dia(r.t, p)

        # cielo según luminosidad
        cielo = _mezclar((18, 22, 58), (135, 206, 235), r.Lnat / max(p.Lmax, 1e-9))
        cv.create_rectangle(0, 0, W, 285, fill=cielo, outline="")
        cv.create_rectangle(0, 285, W, Hh, fill="#6b8e23", outline="")

        # sol o luna
        if 6.0 <= hora <= 18.0:
            x = 50 + (hora - 6.0) / 12.0 * (W - 100)
            y = 150 - 110 * math.sin(math.pi * (hora - 6.0) / 12.0)
            cv.create_oval(x - 22, y - 22, x + 22, y + 22, fill="#ffd33d", outline="#e6a817", width=2)
        else:
            cv.create_oval(W - 90, 30, W - 56, 64, fill="#e8e8e8", outline="#bbb")

        # estructura del invernadero (color según temperatura interior)
        calor = (r.T - 18.0) / (40.0 - 18.0)
        pared = _mezclar((173, 216, 230), (255, 150, 120), calor)
        cv.create_rectangle(150, 160, 490, 310, fill=pared, outline="#555", width=3)
        cv.create_polygon(140, 160, 320, 90, 500, 160, fill=_mezclar((200, 230, 245), (255, 190, 170), calor),
                          outline="#555", width=3)
        cv.create_line(320, 90, 320, 160, fill="#777")

        # suelo según humedad
        suelo = _mezclar((194, 162, 107), (75, 54, 33), r.H / 100.0)
        cv.create_rectangle(160, 270, 480, 305, fill=suelo, outline="#4b3621")
        cv.create_text(320, 288, text=f"Suelo  {r.H:.1f} %", fill="white", font=("TkDefaultFont", 9, "bold"))

        # planta
        alto = 15 + 130 * min(1.0, r.P / max(p.K, 1e-9)) if p.usar_crecimiento else 45
        cv.create_line(320, 270, 320, 270 - alto, fill="#1e7a34", width=5)
        for i in range(1, 4):
            yy = 270 - alto * i / 4
            cv.create_oval(320 - 28, yy - 8, 320 - 4, yy + 4, fill="#3cb44b", outline="#1e7a34")
            cv.create_oval(320 + 4, yy - 14, 320 + 28, yy - 2, fill="#3cb44b", outline="#1e7a34")

        # riego
        if r.riego:
            for x in (200, 320, 440):
                cv.create_oval(x - 5, 180, x + 5, 190, fill="#555", outline="")
                for dx in (-14, 0, 14):
                    cv.create_line(x, 190, x + dx, 262, fill=AZUL, width=2, dash=(3, 3))
        # ventilación
        if r.vent:
            cv.create_text(320, 70, text="⟳ VENTILACIÓN ⟳", fill=AZUL, font=("TkDefaultFont", 12, "bold"))
            cv.create_line(500, 200, 560, 200, arrow="last", fill=AZUL, width=3)
            cv.create_line(80, 220, 140, 220, arrow="last", fill=AZUL, width=3)
        # iluminación artificial
        if r.luz:
            cv.create_oval(300, 165, 340, 205, fill="#fff176", outline="#e6a817", width=2)
            cv.create_text(320, 185, text="💡")

        # rótulos
        cv.create_text(10, 10, anchor="nw", fill="white" if r.Lnat < 30 else "black",
                       text=f"t = {r.t:g} min   hora {int(hora):02d}:{int((hora % 1) * 60):02d}",
                       font=("TkDefaultFont", 10, "bold"))
        cv.create_text(W - 10, Hh - 10, anchor="se", fill="white",
                       text=f"T interior {r.T:.1f} °C  |  T exterior {r.Tamb:.1f} °C",
                       font=("TkDefaultFont", 10, "bold"))

        # indicadores
        def poner(clave, texto, color):
            self.ind[clave].config(text=texto, bg=color)

        if r.T >= p.T_max:
            ct = ROJO
        elif r.T < 15:
            ct = AZUL
        else:
            ct = VERDE
        poner("T", f"{r.T:.2f} °C", ct)
        poner("Tamb", f"{r.Tamb:.2f} °C", "#777")
        ch = NARANJA if r.H <= p.H_min else AZUL if r.H >= p.H_max else VERDE
        poner("H", f"{r.H:.2f} %", ch)
        poner("L", f"{r.L:.1f} %", "#c99a12")
        poner("P", f"{r.P:.2f} cm" if p.usar_crecimiento else "no simulado", "#2e8b57")
        for clave, estado in (("riego", r.riego), ("vent", r.vent), ("luz", r.luz)):
            poner(clave, "ACTIVO" if estado else "inactivo", VERDE if estado else "#888")

    # ================================================================ gráficas
    def _crear_graficas(self):
        f = ttk.Frame(self.nb)
        self.nb.add(f, text=" Gráficas ")
        self.fig = Figure(figsize=(9, 7), dpi=100)
        self.canvas_fig = FigureCanvasTkAgg(self.fig, master=f)
        self.canvas_fig.get_tk_widget().pack(fill="both", expand=True)

    def _configurar_graficas(self):
        p = self.sim.p
        self.fig.clear()
        n = 4 if p.usar_crecimiento else 3
        self.axs = self.fig.subplots(n, 1, sharex=True)
        a = self.axs
        self.ln = {}
        self.ln["T"], = a[0].plot([], [], color=COLORES["T"], label="T interior")
        self.ln["Tamb"], = a[0].plot([], [], color="gray", ls=":", label="T exterior")
        a[0].set_ylabel("Temperatura [°C]")
        self.ln["H"], = a[1].plot([], [], color=COLORES["H"], label="Humedad")
        a[1].set_ylabel("Humedad [%]")
        self.ln["Lnat"], = a[2].plot([], [], color=COLORES["L"], label="luz natural")
        self.ln["L"], = a[2].plot([], [], color="#8e44ad", ls="--", label="luz efectiva")
        a[2].set_ylabel("Luminosidad [%]")
        if p.usar_crecimiento:
            self.ln["P"], = a[3].plot([], [], color=COLORES["P"], label="Planta")
            a[3].set_ylabel("Tamaño [cm]")
        if p.control_activo:
            a[0].axhline(p.T_max, color=COLORES["T"], ls="--", lw=0.8, label="T_max")
            a[1].axhline(p.H_min, color=COLORES["H"], ls="--", lw=0.8, label="H_min")
            a[1].axhline(p.H_max, color=COLORES["H"], ls="--", lw=0.8, label="H_max")
        for ax in a:
            ax.grid(alpha=0.3)
            ax.set_xlim(0, p.duracion / 60.0)
            ax.legend(loc="upper right", fontsize=7, ncol=3)
        a[-1].set_xlabel("Tiempo [h]")
        self.fig.tight_layout()
        self._sombras = []

    def _actualizar_graficas(self):
        rs = self.sim.registros
        t = [r.t / 60.0 for r in rs]
        self.ln["T"].set_data(t, [r.T for r in rs])
        self.ln["Tamb"].set_data(t, [r.Tamb for r in rs])
        self.ln["H"].set_data(t, [r.H for r in rs])
        self.ln["Lnat"].set_data(t, [r.Lnat for r in rs])
        self.ln["L"].set_data(t, [r.L for r in rs])
        if "P" in self.ln:
            self.ln["P"].set_data(t, [r.P for r in rs])
        for s in self._sombras:
            s.remove()
        self._sombras = []
        for ax, attr, color in ((self.axs[0], "vent", "#5bc0de"), (self.axs[1], "riego", "#7fb3d5"),
                                (self.axs[2], "luz", "#f7dc6f")):
            flags = [getattr(r, attr) for r in rs]
            if any(flags):
                self._sombras.append(ax.fill_between(t, 0, 1, where=flags, color=color, alpha=0.2,
                                                     transform=ax.get_xaxis_transform(), linewidth=0))
        for ax in self.axs:
            ax.relim()
            ax.autoscale_view(scalex=False)
        self.canvas_fig.draw_idle()

    # ================================================================ cálculos
    def _crear_calculos(self):
        f = ttk.Frame(self.nb)
        self.nb.add(f, text=" Cálculos paso a paso ")
        panel = ttk.PanedWindow(f, orient="horizontal")
        panel.pack(fill="both", expand=True, padx=6, pady=6)

        izq = ttk.LabelFrame(panel, text="Ecuaciones del modelo", padding=4)
        self.txt_ecu = tk.Text(izq, width=62, font=self.fuente_mono, wrap="none", bg="#fbfbf4")
        self.txt_ecu.pack(fill="both", expand=True)
        panel.add(izq, weight=2)

        der = ttk.LabelFrame(panel, text="Cálculo del paso seleccionado", padding=4)
        nav = ttk.Frame(der)
        nav.pack(fill="x")
        ttk.Button(nav, text="◀", width=3, command=lambda: self._mover_paso(-1)).pack(side="left")
        self.paso_sel = tk.IntVar(value=0)
        self.spin = ttk.Spinbox(nav, from_=0, to=0, textvariable=self.paso_sel, width=8,
                                command=self._mostrar_calculo)
        self.spin.pack(side="left", padx=4)
        self.spin.bind("<Return>", lambda e: self._mostrar_calculo())
        ttk.Button(nav, text="▶", width=3, command=lambda: self._mover_paso(+1)).pack(side="left")
        self.seguir = tk.BooleanVar(value=True)
        ttk.Checkbutton(nav, text="Seguir el último paso calculado", variable=self.seguir,
                        command=self._mostrar_calculo).pack(side="left", padx=10)
        self.txt_calc = tk.Text(der, font=self.fuente_mono, wrap="none", bg="#fbfbf4")
        self.txt_calc.pack(fill="both", expand=True, pady=(4, 0))
        panel.add(der, weight=3)

    def _mover_paso(self, d):
        self.seguir.set(False)
        n = max(0, min(len(self.sim.registros) - 2, int(self.paso_sel.get()) + d))
        self.paso_sel.set(n)
        self._mostrar_calculo()

    def _mostrar_calculo(self):
        rs = self.sim.registros
        if len(rs) < 2:
            texto, clave = "Presione «⏭ Paso» o «▶ Iniciar» para calcular el primer paso.", None
        else:
            maxn = len(rs) - 2
            self.spin.config(to=maxn)
            if self.seguir.get():
                self.paso_sel.set(maxn)
            try:
                n = max(0, min(maxn, int(self.paso_sel.get())))
            except (tk.TclError, ValueError):
                n = maxn
            self.paso_sel.set(n)
            clave = (n, len(rs))
            if clave == self._ultimo_calc:
                return
            texto = explicar_paso(self.sim, n)
        self._ultimo_calc = clave
        self.txt_calc.config(state="normal")
        self.txt_calc.delete("1.0", "end")
        self.txt_calc.insert("1.0", texto)
        self.txt_calc.config(state="disabled")

    # ============================================================== control
    def _crear_control(self):
        f = ttk.Frame(self.nb)
        self.nb.add(f, text=" Control y eventos ")
        top = ttk.LabelFrame(f, text="Mecanismos de control virtual", padding=10)
        top.pack(fill="x", padx=8, pady=8)
        self.lbl_ctrl = {}
        for i, (clave, texto) in enumerate((("riego", "Sistema de riego"), ("vent", "Ventilación"),
                                            ("luz", "Iluminación artificial"))):
            ttk.Label(top, text=texto, font=("TkDefaultFont", 10, "bold")).grid(row=0, column=i, padx=20)
            lbl = tk.Label(top, text="inactivo", width=14, fg="white", bg="#888",
                           font=("TkDefaultFont", 11, "bold"))
            lbl.grid(row=1, column=i, padx=20, pady=4)
            self.lbl_ctrl[clave] = lbl
        self.lbl_cont = ttk.Label(top, text="")
        self.lbl_cont.grid(row=3, column=0, columnspan=3, pady=(8, 0))

        cuadro = ttk.LabelFrame(f, text="Historial de eventos", padding=4)
        cuadro.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.txt_ev = tk.Text(cuadro, font=self.fuente_mono, state="disabled")
        sb = ttk.Scrollbar(cuadro, command=self.txt_ev.yview)
        self.txt_ev.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.txt_ev.pack(fill="both", expand=True)

    def _actualizar_control(self):
        r = self.sim.actual
        for clave in ("riego", "vent", "luz"):
            activo = getattr(r, clave)
            self.lbl_ctrl[clave].config(text="ACTIVO" if activo else "inactivo",
                                        bg=VERDE if activo else "#888")
        res = self.sim.resumen()
        self.lbl_cont.config(text=f"Activaciones – riego: {res['act_riego']} ({res['min_riego']:g} min)   |   "
                                  f"ventilación: {res['act_vent']} ({res['min_vent']:g} min)   |   "
                                  f"iluminación: {res['act_luz']} ({res['min_luz']:g} min)")
        nuevos = self.sim.eventos[self._ev_mostrados:]
        if nuevos:
            self.txt_ev.config(state="normal")
            for t, _, txt in nuevos:
                self.txt_ev.insert("end", f"t = {t:8.1f} min  ({t / 60:5.2f} h)   {txt}\n")
            self.txt_ev.see("end")
            self.txt_ev.config(state="disabled")
            self._ev_mostrados = len(self.sim.eventos)

    # ================================================================== datos
    def _crear_datos(self):
        f = ttk.Frame(self.nb)
        self.nb.add(f, text=" Datos ")
        cols = ("t", "T", "H", "L", "P", "R", "E", "riego", "vent")
        nombres = ("t [min]", "T [°C]", "H [%]", "L [%]", "P [cm]", "R", "E", "riego", "vent.")
        self.tabla = ttk.Treeview(f, columns=cols, show="headings", height=20)
        for c, n in zip(cols, nombres):
            self.tabla.heading(c, text=n)
            self.tabla.column(c, width=90, anchor="center")
        sb = ttk.Scrollbar(f, command=self.tabla.yview)
        self.tabla.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.tabla.pack(fill="both", expand=True, padx=6, pady=6)

    def _actualizar_tabla(self):
        self.tabla.delete(*self.tabla.get_children())
        for r in self.sim.registros[-300:]:
            self.tabla.insert("", "end", values=(f"{r.t:g}", f"{r.T:.3f}", f"{r.H:.3f}", f"{r.L:.2f}",
                                                 f"{r.P:.3f}", f"{r.R:g}", f"{r.E:.4f}",
                                                 "ON" if r.riego else "–", "ON" if r.vent else "–"))
        hijos = self.tabla.get_children()
        if hijos:
            self.tabla.see(hijos[-1])

    # ============================================================== parámetros
    def _crear_parametros(self):
        f = ttk.Frame(self.nb)
        self.nb.add(f, text=" Parámetros ")
        marco = ttk.Frame(f)
        marco.pack(fill="both", expand=True, padx=8, pady=8)
        for i, (grupo, lista) in enumerate(CAMPOS):
            lf = ttk.LabelFrame(marco, text=grupo, padding=6)
            lf.grid(row=i // 3, column=i % 3, sticky="nsew", padx=5, pady=5)
            for r, (campo, etiqueta, unidad) in enumerate(lista):
                ttk.Label(lf, text=etiqueta).grid(row=r, column=0, sticky="w")
                v = tk.StringVar()
                ttk.Entry(lf, textvariable=v, width=10).grid(row=r, column=1, padx=4, pady=1)
                ttk.Label(lf, text=unidad, foreground="#666").grid(row=r, column=2, sticky="w")
                self.vars[campo] = v
        lf = ttk.LabelFrame(marco, text="Opciones", padding=6)
        lf.grid(row=(len(CAMPOS)) // 3, column=len(CAMPOS) % 3, sticky="nsew", padx=5, pady=5)
        for campo, etiqueta in BOOLEANOS:
            v = tk.BooleanVar()
            ttk.Checkbutton(lf, text=etiqueta, variable=v).pack(anchor="w")
            self.vars[campo] = v
        ttk.Button(marco, text="Aplicar parámetros y reiniciar simulación",
                   command=self.aplicar_parametros).grid(row=4, column=0, columnspan=3, pady=12)

    def _cargar_formulario(self, p):
        for f in fields(p):
            v = self.vars[f.name]
            val = getattr(p, f.name)
            v.set(bool(val) if isinstance(val, bool) else f"{val:g}")

    def _leer_formulario(self):
        kw = {}
        for f in fields(Parametros):
            v = self.vars[f.name].get()
            if isinstance(f.default, bool):
                kw[f.name] = bool(v)
            else:
                try:
                    kw[f.name] = float(str(v).replace(",", "."))
                except ValueError:
                    raise ValueError(f"El valor de «{f.name}» no es un número: {v!r}")
        return Parametros(**kw)

    # ============================================================ acciones
    def _cambiar_escenario(self, _evento=None):
        self._cargar_formulario(self.escenarios[self.escenario_var.get()])
        self.aplicar_parametros()

    def aplicar_parametros(self):
        self._detener()
        try:
            sim = Simulador(self._leer_formulario())
        except ValueError as e:
            messagebox.showerror("Parámetros no válidos", str(e))
            return
        self.sim = sim
        self._ev_mostrados = 0
        self._ultimo_calc = None
        self.txt_ev.config(state="normal")
        self.txt_ev.delete("1.0", "end")
        self.txt_ev.config(state="disabled")
        self.txt_ecu.config(state="normal")
        self.txt_ecu.delete("1.0", "end")
        self.txt_ecu.insert("1.0", texto_ecuaciones(sim.p))
        self.txt_ecu.config(state="disabled")
        self.seguir.set(True)
        self.progreso.config(maximum=max(1, sim.n_pasos), value=0)
        self._configurar_graficas()
        self._refrescar(tabla=True)

    def alternar(self):
        if self.corriendo:
            self._detener()
        elif not self.sim.terminado:
            self.corriendo = True
            self.btn_play.config(text="⏸ Pausar")
            self._tick()

    def _detener(self):
        self.corriendo = False
        self.btn_play.config(text="▶ Iniciar")

    def _tick(self):
        if not self.corriendo:
            return
        for _ in range(max(1, int(self.velocidad.get()))):
            if not self.sim.paso():
                break
        self._ticks += 1
        terminado = self.sim.terminado
        self._refrescar(tabla=terminado or self._ticks % 10 == 0)
        if terminado:
            self._detener()
            return
        self.after(40, self._tick)

    def un_paso(self):
        self._detener()
        self.sim.paso()
        self._refrescar(tabla=True)

    def ejecutar_todo(self):
        self._detener()
        self.sim.ejecutar()
        self._refrescar(tabla=True)

    def _refrescar(self, tabla=False):
        r = self.sim.actual
        self.progreso.config(value=len(self.sim.registros) - 1)
        estado = "FINALIZADA" if self.sim.terminado else ("en ejecución" if self.corriendo else "en pausa")
        self.lbl_tiempo.config(text=f"Simulación {estado}  –  t = {r.t:g} min de {self.sim.p.duracion:g} min  "
                                    f"(paso {len(self.sim.registros) - 1} de {self.sim.n_pasos})")
        self._dibujar_panel()
        self._actualizar_graficas()
        self._mostrar_calculo()
        self._actualizar_control()
        if tabla:
            self._actualizar_tabla()

    # ============================================================== salidas
    def exportar_csv(self):
        ruta = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")],
                                            initialfile="simulacion.csv")
        if ruta:
            self.sim.a_csv(ruta)
            messagebox.showinfo("Exportado", f"Datos guardados en:\n{ruta}")

    def generar_informe(self):
        self._detener()
        if not self.sim.terminado and messagebox.askyesno(
                "Simulación incompleta", "La simulación no ha terminado. ¿Ejecutarla completa antes de generar el informe?"):
            self.sim.ejecutar()
            self._refrescar(tabla=True)
        ruta = filedialog.asksaveasfilename(defaultextension=".docx", filetypes=[("Word", "*.docx")],
                                            initialfile="informe_invernadero.docx")
        if not ruta:
            return
        try:
            generar_informe(self.sim, ruta, titulo=f"Informe de simulación – {self.escenario_var.get()}")
            messagebox.showinfo("Informe generado", f"Informe guardado en:\n{ruta}")
        except Exception as e:  # noqa: BLE001 - mostrar cualquier problema al usuario
            messagebox.showerror("No se pudo generar el informe", str(e))

    def verificar(self):
        v = verificacion.ejecutar_todo()
        L = ["VERIFICACIÓN DEL MODELO", "=" * 60, "", "Humedad – cálculo manual vs programa (ejemplo del documento)"]
        for n, m, c, d in v["humedad_manual"]:
            L.append(f"  n={n}   manual={m:8.3f}   programa={c:10.5f}   |dif|={d:.1e}")
        L += ["", "Temperatura – cálculo manual vs programa"]
        for caso, n, m, c, d in v["temperatura_manual"]:
            L.append(f"  {caso:34s} n={n}  manual={m:10.6f}  programa={c:10.6f}")
        L += ["", "Pruebas de coherencia"]
        L += [f"  [{'OK' if ok else 'FALLA'}] {d}" for d, ok in v["comportamientos"]]
        L += ["", "Error de Euler vs solución exacta según Δt"]
        L += [f"  Δt = {dt:5g} min   error máx = {e:.5f} °C" for dt, e in verificacion.error_vs_dt()]
        L += ["", "RESULTADO: " + ("TODO CUMPLE" if v["ok"] else "HAY PRUEBAS QUE FALLAN")]
        win = tk.Toplevel(self)
        win.title("Verificación del modelo")
        win.geometry("760x620")
        t = tk.Text(win, font=self.fuente_mono)
        t.pack(fill="both", expand=True)
        t.insert("1.0", "\n".join(L))
        t.config(state="disabled")


def main():
    App().mainloop()


if __name__ == "__main__":
    main()

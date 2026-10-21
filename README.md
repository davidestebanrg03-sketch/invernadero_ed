# Simulación y control de un invernadero mediante ecuaciones diferenciales

Proyecto de Ecuaciones Diferenciales – Universidad del Tolima (IDEAD), Ingeniería de Sistemas.
Simula temperatura, humedad del suelo, luminosidad y (opcional) crecimiento de un cultivo con **EDO + método de Euler**,
con control virtual de riego, ventilación e iluminación, interfaz gráfica, ventana de cálculos paso a paso e informes .docx.

## 1. Preparar el entorno en VS Code
```bash
# En la carpeta del proyecto (terminal de VS Code)
python -m venv .venv
.venv\Scripts\activate          # Windows      (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
```
Luego `Ctrl+Shift+P → Python: Select Interpreter → .venv`.
> Tkinter viene con Python en Windows/macOS. En Linux: `sudo apt install python3-tk`.

## 2. Ejecutar (una orden por etapa de la hoja de ruta)
| Etapa | Comando | Qué hace |
|---|---|---|
| 4 Prototipo | `python prototipo.py ["Baja humedad"]` | Simulación por consola, CSV y PNG en `resultados/` |
| 5 Control | incluido en el simulador | histéresis: riego, ventilación, iluminación |
| 6 Interfaz | `python main.py` | Panel, gráficas, cálculos paso a paso, eventos, datos, parámetros |
| 7 Validación | `python validacion.py` | Manual vs programa, Δt, escenarios, informes .docx |
| Pruebas | `python -m unittest -v` | 15 pruebas automáticas |

También hay configuraciones de ejecución en `.vscode/launch.json` (pestaña *Run and Debug*).

## 3. Estructura
```
main.py  prototipo.py  validacion.py
invernadero/
  parametros.py   parámetros, condiciones iniciales y 7 escenarios
  modelo.py       las ecuaciones diferenciales y las entradas (Tamb, L)
  control.py      control con histéresis
  simulador.py    método de Euler + registro de resultados
  explicador.py   texto de ecuaciones y cálculo paso a paso
  verificacion.py cálculos manuales, solución analítica, error vs Δt
  graficas.py     gráficas Matplotlib
  informe.py      informe Word
  gui.py campos.py   interfaz gráfica
tests/            pruebas unitarias
docs/             etapas 1-3 (preguntas al profesor, ecuaciones, cálculos manuales)
resultados/       salidas de ejemplo
```

## 4. Cómo usar la interfaz
1. Elija un **escenario** (o edite la pestaña *Parámetros* y pulse «Aplicar»).
2. **▶ Iniciar** (velocidad ajustable), **⏭ Paso** para avanzar de uno en uno, **⏩ Ejecutar todo**.
3. En **Cálculos paso a paso** verá la ecuación con los valores sustituidos y el resultado de Euler;
   desmarque «Seguir el último paso» para revisar cualquier paso anterior.
4. **Verificar modelo** muestra la comparación con los cálculos manuales; **Informe (.docx)** genera el informe.

## 5. Hoja de ruta
- [ ] 1. Revisar con el profesor → `docs/01_preguntas_profesor.md`
- [x] 2. Ecuaciones definitivas → `docs/02_ecuaciones_definitivas.md`  *(pendiente de su aprobación)*
- [x] 3. Cálculos manuales → `docs/03_calculos_manuales.md`
- [x] 4. Prototipo → `prototipo.py`
- [x] 5. Control virtual → `invernadero/control.py`
- [x] 6. Interfaz → `invernadero/gui.py`
- [x] 7. Validación e informe → `validacion.py`

## 6. Cambios respecto a la propuesta (coméntelos con el profesor)
- La ventilación y la luz se concretan en el término Q(t): `Q = a·L` y `k → k + kv` al ventilar.
- E (pérdida de agua) puede depender de la temperatura (opción activable).
- Para simular 24 h se usan tasas más lentas que las del ejemplo didáctico (que sí está como escenario).

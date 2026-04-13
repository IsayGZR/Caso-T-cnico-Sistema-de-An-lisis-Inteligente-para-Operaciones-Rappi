import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from groq import Groq
from dotenv import load_dotenv
import os
import re
from fpdf import FPDF
import io

load_dotenv()

# Realizamos la configuración inicial de la página
st.set_page_config(page_title="Rappi Operations Intelligence", page_icon="🟠", layout="wide")
st.title("Caso Técnico: Sistema de Análisis Inteligente para Operaciones Rappi")

# las columnas de semanas que que vienen en el excel
semanas_metricas = ["L8W_ROLL", "L7W_ROLL", "L6W_ROLL", "L5W_ROLL", "L4W_ROLL", "L3W_ROLL", "L2W_ROLL", "L1W_ROLL", "L0W_ROLL"]
semanas_ordenes = ["L8W", "L7W", "L6W", "L5W", "L4W", "L3W", "L2W", "L1W", "L0W"]


# PARTE 1 - Carga de los datos

def cargar_datos():
    # leemos las dos hojas del excel
    df_metricas = pd.read_excel(r"C:\Users\isay\Desktop\Prueba Tecnica AI Engineer - Rappi\Solucion_Caso2\Rappi Operations Analysis Dummy Data.xlsx", sheet_name="RAW_INPUT_METRICS")
    df_ordenes = pd.read_excel(r"C:\Users\isay\Desktop\Prueba Tecnica AI Engineer - Rappi\Solucion_Caso2\Rappi Operations Analysis Dummy Data.xlsx", sheet_name="RAW_ORDERS")
    return df_metricas, df_ordenes

# Generamos el contexto para que Groq
def hacer_resumen(df_metricas, df_ordenes):
    paises = sorted(df_metricas['COUNTRY'].unique().tolist())
    metricas = sorted(df_metricas['METRIC'].unique().tolist())
    tipos_zona = sorted(df_metricas['ZONE_TYPE'].unique().tolist())
    priorizacion = sorted(df_metricas['ZONE_PRIORITIZATION'].unique().tolist())
    num_ciudades = df_metricas['CITY'].nunique()
    num_zonas = df_metricas['ZONE'].nunique()

    resumen = f"""
DATOS DISPONIBLES:

1) DataFrame 'df_metrics' ({len(df_metricas)} filas):
   - Columnas: {list(df_metricas.columns)}
   - Países: {paises}
   - Ciudades: {num_ciudades} únicas
   - Zonas: {num_zonas} únicas
   - ZONE_TYPE: {tipos_zona}
   - ZONE_PRIORITIZATION: {priorizacion}
   - Métricas: {metricas}
   - Columnas de semanas: {semanas_metricas} (L8W_ROLL=hace 8 semanas, L0W_ROLL=semana actual)

2) DataFrame 'df_orders' ({len(df_ordenes)} filas):
   - Columnas: {list(df_ordenes.columns)}
   - Tiene el volumen de órdenes por zona
   - Columnas de semanas: {semanas_ordenes} (L8W=hace 8 semanas, L0W=semana actual)

DICCIONARIO DE MÉTRICAS:
- % PRO Users Who Breakeven: Usuarios Pro que cubren costo membresía / Total Pro
- % Restaurants Sessions With Optimal Assortment: Sesiones con 40+ restaurantes / Total sesiones
- Gross Profit UE: Margen bruto por orden
- Lead Penetration: Tiendas habilitadas / (Leads + Habilitadas + Salieron)
- MLTV Top Verticals Adoption: Usuarios multi-vertical / Total usuarios
- Non-Pro PTC > OP: Conversión No Pro de Checkout a Orden
- Perfect Orders: Órdenes sin problemas / Total órdenes
- Pro Adoption (Last Week Status): Usuarios Pro / Total usuarios
- Restaurants Markdowns / GMV: Descuentos restaurantes / GMV restaurantes
- Restaurants SS > ATC CVR: Conversión restaurantes Select Store a Add to Cart
- Restaurants SST > SS CVR: Conversión vertical a tienda (restaurantes)
- Retail SST > SS CVR: Conversión vertical a tienda (retail)
- Turbo Adoption: Usuarios Turbo / Total con Turbo disponible
"""
    return resumen

# PARTE 2 - Chatbot (para la prueba ténica se usa Groq)

# Generamos el prompt que se le mandará a Groq junto con la pregunta del usuario
prompt_sistema = """
Eres un analista de datos experto en Rappi. Tu trabajo es responder preguntas sobre
métricas operacionales generando código Python con Pandas.

{data_summary}

INSTRUCCIONES:
1. Genera código Python/Pandas para responder la pregunta del usuario.
2. El código tiene acceso a estas variables: df_metrics, df_orders, pd, px (plotly.express), go (plotly.graph_objects)
3. "El código DEBE terminar asignando el resultado a una variable llamada 'result' (un string con la respuesta). 
Cuando el resultado sea una tabla o lista de datos, usa el método .to_markdown(index=False) para que se vea como tabla. 
Ejemplo: result = df_resultado.to_markdown(index=False)"
4. Si la pregunta requiere un gráfico, crea una figura de Plotly y asígnala a una variable llamada 'fig'.
5. No uses print(). Solo asigna a 'result' y opcionalmente a 'fig'.

CONTEXTO DE NEGOCIO:
- "Zonas problemáticas" = zonas con métricas deterioradas o valores bajos
- Cambio WoW (week over week) = (L0W - L1W) / L1W
- Las métricas son porcentajes o ratios (entre 0 y 1)
- Para casi todas las métricas, más alto es mejor (excepto Restaurants Markdowns / GMV)
- IMPORTANTE: Los nombres de zonas (como Miraflores, Chapinero, Usaquén, etc.) están en la columna ZONE, NO en CITY
- En df_orders la columna METRIC siempre tiene el valor "Orders", no "Total Orders" ni otro nombre
- Cuando pregunten por órdenes de una zona, filtra por la columna ZONE en df_orders
- "Esta semana" = columna L0W o L0W_ROLL (la más reciente)
- "Semana pasada" = columna L1W o L1W_ROLL
- Cuando hagas gráficos de tendencia para una zona, SIEMPRE filtra también por METRIC antes de transponer. Ejemplo: df_metrics[(df_metrics['ZONE'] == 'X') & (df_metrics['METRIC'] == 'Y')]
- Si hay múltiples filas para una zona, usa .iloc[0] para quedarte con la primera

IMPORTANTE:
- Se preciso con los nombres de columnas y métricas (copia exacto como aparecen)
- Si no puedes responder algo, asigna a result un mensaje explicando por qué
- Para tendencias usa gráfico de línea, para comparaciones usa barras
- Al final agrega sugerencias de otros análisis que podría hacer el usuario
"""

# Función principal para manejar la pregunta del usuario, mandarla a Groq, ejecutar el código que nos devuelve y regresar el resultado y el gráfico (si lo hay)
def hacer_pregunta(modelo, pregunta, df_metricas, df_ordenes, resumen_datos, historial=None):

    # Agregamos el historial para que Groq tenga memoria de la conversacion
    texto_historial = ""
    if historial and len(historial) > 0:
        texto_historial = "\nHISTORIAL DE LA CONVERSACIÓN:\n"
        for msg in historial[-6:]: # Solo mandamos los ultimos 6 mensajes para no saturar el prompt
            contenido = msg.get('content', '')
            if contenido and isinstance(contenido, str):
                texto_historial = texto_historial + f"- {msg['role']}: {contenido[:200]}\n"

    # Armamos el prompt completo
    prompt_completo = f"""
{prompt_sistema.format(data_summary=resumen_datos)}
{texto_historial}

PREGUNTA DEL USUARIO: {pregunta}

Genera SOLO el código Python, sin explicaciones antes ni después.
"""

    # Mandamos el prompt a groq
    try:
        cliente = Groq(api_key=api_key)
        respuesta = cliente.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt_completo}],
            temperature=0,
        )
        texto_respuesta = respuesta.choices[0].message.content

        match = re.search(r"```python\s*(.*?)```", texto_respuesta, re.DOTALL)
        if match:
            codigo = match.group(1).strip()
        else:
            codigo = texto_respuesta.strip().replace("```", "")

    except Exception as e:
        return f"Error al conectar con Groq: {str(e)}", None, ""

    # Ejecutamos el codigo que nos dio Groq
    try:
        # Creamos un ambiente con las variables que el codigo necesita
        variables = {
            "df_metrics": df_metricas,
            "df_orders": df_ordenes,
            "pd": pd,
            "px": px,
            "go": go,
        }
        exec(codigo, variables)

        # Obtenemos el resultado y el grafico
        resultado = variables.get("result", "No se generó resultado.")
        grafico = variables.get("fig", None)

        return resultado, grafico, codigo    
    
    # Si el codigo falla, lo atrapamos para no romper la app y le mandamos el error a Groq para que intente corregirlo y generar un nuevo codigo
    except Exception as e:
        # si fallo, le mandamos el error a groq para que corrija el codigo
        try:
            prompt_correccion = f"""
Tu código anterior generó este error: {str(e)}

Código que falló:
{codigo}

Corrige el código para que funcione. Genera SOLO el código Python corregido, sin explicaciones.
"""
            cliente = Groq(api_key=api_key)
            respuesta2 = cliente.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt_correccion}],
                temperature=0,
            )
            texto2 = respuesta2.choices[0].message.content

            match2 = re.search(r"```python\s*(.*?)```", texto2, re.DOTALL)
            if match2:
                codigo2 = match2.group(1).strip()
            else:
                codigo2 = texto2.strip().replace("```", "")

            variables2 = {
                "df_metrics": df_metricas,
                "df_orders": df_ordenes,
                "pd": pd,
                "px": px,
                "go": go,
            }
            exec(codigo2, variables2)

            resultado = variables2.get("result", "No se generó resultado.")
            grafico = variables2.get("fig", None)

            return resultado, grafico, codigo2

        # Si sigue fallando, le mostramos el error al usuario junto con el ultimo codigo que intento ejecutar
        except Exception as e2:
            return f"❌ Error al ejecutar el análisis: {str(e2)}\n\nCódigo generado:\n```python\n{codigo}\n```", None, codigo


def obtener_sugerencias(pregunta):
    #Sugiere preguntas relacionadas segun lo que pregunto el usuario
    pregunta_lower = pregunta.lower()

    if "lead penetration" in pregunta_lower:
        return [
            "¿Cómo se compara Lead Penetration entre zonas Wealthy y Non Wealthy?",
            "¿Qué zonas tienen Lead Penetration en descenso las últimas 3 semanas?",
            "¿Cuál es el promedio de Lead Penetration por país?"
        ]
    elif "perfect order" in pregunta_lower:
        return [
            "¿Cuáles son las zonas con peor Perfect Orders?",
            "¿Hay correlación entre Perfect Orders y Gross Profit UE?",
            "¿Qué países tienen mejor Perfect Orders en promedio?"
        ]
    elif "orden" in pregunta_lower or "order" in pregunta_lower:
        return [
            "¿Qué zonas crecen más en órdenes las últimas 5 semanas?",
            "¿Cuál es el top 10 de zonas por volumen de órdenes?",
            "¿Qué país tiene más órdenes en total?"
        ]
    elif "profit" in pregunta_lower or "ganancia" in pregunta_lower:
        return [
            "¿Qué países tienen mayor Gross Profit UE promedio?",
            "Muestra la evolución de Gross Profit UE en zonas High Priority"
        ]
    else:
        # sugerencias genericas si no encontramos palabras clave
        return [
            "¿Cuáles son las 5 zonas con mayor Lead Penetration?",
            "Compara Perfect Orders entre Wealthy y Non Wealthy en México",
            "¿Qué zonas tienen alto Lead Penetration pero bajo Perfect Orders?"
        ]



# PARTE 3 - Insights automáticos 

# Función para encontrar anomalías: Zonas con cambios drásticos semana a semana (>10% deterioro/mejora)
def encontrar_anomalias(df_metricas):
        
    # Creamos una copia del dataframe para no modificar el original
    df = df_metricas.copy()

    # Calculamos el cambio porcentual entre semana actual y la anterior
    df["cambio_wow"] = (df["L0W_ROLL"] - df["L1W_ROLL"]) / df["L1W_ROLL"].replace(0, np.nan)

    columnas = ["COUNTRY", "CITY", "ZONE", "METRIC", "L1W_ROLL", "L0W_ROLL", "cambio_wow"]

    # Las que empeoraron mas del 10%
    deterioros = df[df["cambio_wow"] < -0.10].copy() # Los que cayeron mas del 10%
    deterioros = deterioros.sort_values("cambio_wow") # Ordenamos de peor a mejor 
    deterioros = deterioros.head(15) # Nos quedamos con las 15 peores caídas
    deterioros = deterioros[columnas] # Nos quedamos solo con las columnas que nos interesan

    # Las que mejoraron mas del 10%
    mejoras = df[df["cambio_wow"] > 0.10].copy() # Los que mejoraron mas del 10%
    mejoras = mejoras.sort_values("cambio_wow", ascending=False) # Ordenamos de mejor a peor mejora
    mejoras = mejoras.head(15) # Nos quedamos con las 15 mejores mejoras
    mejoras = mejoras[columnas]

    return deterioros, mejoras

# Función para encontrar tendencias negativas: Zonas que llevan 3 o más semanas seguidas en descenso
def encontrar_tendencias(df_metricas):

    df = df_metricas.copy()

    # Revisamos si cada semana es menor que la anterior (3 semanas seguidas)
    semana3_baja = df["L2W_ROLL"] < df["L3W_ROLL"]
    semana2_baja = df["L1W_ROLL"] < df["L2W_ROLL"]
    semana1_baja = df["L0W_ROLL"] < df["L1W_ROLL"]

    # Las tres condiciones deben cumplirse, para asegurar que lleva 3 semanas seguidas en descenso y se considera una tendencia 
    en_descenso = semana3_baja & semana2_baja & semana1_baja

    # Nos quedamos solo con las columnas que nos interesan para mostrar la tendencia
    columnas_semanas = ["L3W_ROLL", "L2W_ROLL", "L1W_ROLL", "L0W_ROLL"]
    tendencias = df[en_descenso][["COUNTRY", "CITY", "ZONE", "METRIC"] + columnas_semanas].copy()

    # Calculamos cuanto bajo en total
    tendencias["deterioro_total"] = (tendencias["L0W_ROLL"] - tendencias["L3W_ROLL"]) / tendencias["L3W_ROLL"].replace(0, np.nan)
    tendencias = tendencias.sort_values("deterioro_total")
    tendencias = tendencias.head(15)

    return tendencias

# Función para benchmarking: Zonas que están muy por debajo del promedio de su grupo (mismo país y tipo de zona)
def encontrar_benchmarking(df_metricas):

    resultados = []

    # Realizamos esto para cada metrica
    for metrica in df_metricas["METRIC"].unique():
        df_filtrado = df_metricas[df_metricas["METRIC"] == metrica].copy()

        # Calculamos promedio y desviacion estandar por grupo
        promedio_grupo = df_filtrado.groupby(["COUNTRY", "ZONE_TYPE"])["L0W_ROLL"].transform("mean")
        desv_grupo = df_filtrado.groupby(["COUNTRY", "ZONE_TYPE"])["L0W_ROLL"].transform("std")

        # Vemos cuantas desviaciones esta por debajo
        df_filtrado["vs_grupo"] = (df_filtrado["L0W_ROLL"] - promedio_grupo) / desv_grupo.replace(0, np.nan)

        # Nos quedamos con las que estan mas de 1 desviacion por debajo
        malas = df_filtrado[df_filtrado["vs_grupo"] < -1]

        # Agregamos al resultado las 3 peores de cada metrica
        for i, fila in malas.head(3).iterrows():
            resultados.append({
                "COUNTRY": fila["COUNTRY"],
                "CITY": fila["CITY"],
                "ZONE": fila["ZONE"],
                "ZONE_TYPE": fila["ZONE_TYPE"],
                "METRIC": metrica,
                "value": fila["L0W_ROLL"],
                "group_avg": promedio_grupo.loc[i],
                "desviation": fila["vs_grupo"],
            })

    # Ordenamos el resultado por la que esta mas desviada y nos quedamos con las 15 peores
    df_resultado = pd.DataFrame(resultados)
    if len(df_resultado) > 0:
        df_resultado = df_resultado.sort_values("desviation").head(15)
    return df_resultado

# Función para encontrar correlaciones entre métricas (ej: zonas con bajo Lead Penetration también tienen bajo Conversion)
def encontrar_correlaciones(df_metricas):

    # Reorganizmaos los datos para comparar dos métricas de la misma zona al mismo tiempo
    tabla = df_metricas.pivot_table(
        index=["COUNTRY", "CITY", "ZONE"],
        columns="METRIC",
        values="L0W_ROLL",
        aggfunc="first"
    ).reset_index()

    resultados = []

    # Caso 1: Alto Lead Penetration pero baja conversion
    
    # Revisamos si las columnas que necesitamos existen 
    if "Lead Penetration" in tabla.columns and "Non-Pro PTC > OP" in tabla.columns:
        lead_alto = tabla["Lead Penetration"] > tabla["Lead Penetration"].quantile(0.75) # Zonas con Lead Penetration alto (top 25%)
        conv_baja = tabla["Non-Pro PTC > OP"] < tabla["Non-Pro PTC > OP"].quantile(0.25) # Zonas con Conversion baja (bottom 25%)
        zonas_caso1 = tabla[lead_alto & conv_baja] # Lead Penetration alto y Conversion baja
        zonas_caso1 = zonas_caso1[["COUNTRY", "CITY", "ZONE", "Lead Penetration", "Non-Pro PTC > OP"]] # Nos quedamos solo con las columnas relevantes

        # Si encontramos zonas que cumplen esta condición, las guardamos
        if len(zonas_caso1) > 0:
            resultados.append({
                "tipo": "Alto Lead Penetration + Baja Conversión",
                "descripcion": "Zonas con muchas tiendas habilitadas pero los usuarios no convierten",
                "data": zonas_caso1.head(10)
            })

    # Caso 2: Perfect Orders bajo (problemas operacionales con las ordenes)
    if "Perfect Orders" in tabla.columns:
        
        # Buscamos las zonas con Perfect Orders bajo (bottom 25%)
        perfect_bajo = tabla[tabla["Perfect Orders"] < tabla["Perfect Orders"].quantile(0.25)]
        
        # Si encontro zonas, las guardamos
        if len(perfect_bajo) > 0:
            resultados.append({
                "tipo": "Bajo Perfect Orders",
                "descripcion": "Zonas con muchas cancelaciones, defectos o demoras en las ordenes",
                "data": perfect_bajo[["COUNTRY", "CITY", "ZONE", "Perfect Orders"]].head(10)
            })

    # Caso 3: Pocos usuarios Pro y ademas bajo profit
    
    # Revisamos si las columnas que necesitamos existen
    if "Pro Adoption (Last Week Status)" in tabla.columns and "Gross Profit UE" in tabla.columns:
        pro_bajo = tabla["Pro Adoption (Last Week Status)"] < tabla["Pro Adoption (Last Week Status)"].quantile(0.25) # Zonas con pocos usuarios Pro (bottom 25%)
        profit_bajo = tabla["Gross Profit UE"] < tabla["Gross Profit UE"].quantile(0.25) # Zonas en el peor 25% de margen de ganancia
        zonas_caso3 = tabla[pro_bajo & profit_bajo]
        zonas_caso3 = zonas_caso3[["COUNTRY", "CITY", "ZONE", "Pro Adoption (Last Week Status)", "Gross Profit UE"]]

        if len(zonas_caso3) > 0:
            resultados.append({
                "tipo": "Baja Pro Adoption + Bajo Gross Profit",
                "descripcion": "Zonas con pocos usuarios Pro y tambien bajo margen de ganancia",
                "data": zonas_caso3.head(10)
            })

    return resultados


# Función para encontrar crecimiento o caída en órdenes: Zonas que crecieron o cayeron más en órdenes comparando hace 5 semanas vs ahora
def encontrar_crecimiento_ordenes(df_ordenes):
    
    df = df_ordenes.copy()
    
    # Calculamos el crecimiento comparando la semana actual (L0W) con hace 5 semanas (L5W)
    df["crecimiento"] = (df["L0W"] - df["L5W"]) / df["L5W"].replace(0, np.nan)

    columnas = ["COUNTRY", "CITY", "ZONE", "L5W", "L0W", "crecimiento"]

    # Top 10 que mas crecieron
    top_crecimiento = df.nlargest(10, "crecimiento")[columnas]

    # Top 10 que mas cayeron
    top_caida = df.nsmallest(10, "crecimiento")[columnas]

    return top_crecimiento, top_caida

# Función principal que corre todos los análisis y junta los resultados en un diccionario para luego pasarlo a Groq y que redacte el reporte
def ejecutar_todos_los_analisis(df_metricas, df_ordenes):
    deterioros, mejoras = encontrar_anomalias(df_metricas)
    tendencias = encontrar_tendencias(df_metricas)
    benchmarking = encontrar_benchmarking(df_metricas)
    correlaciones = encontrar_correlaciones(df_metricas)
    crec_ordenes, caida_ordenes = encontrar_crecimiento_ordenes(df_ordenes)

    todos_los_insights = {
        "anomalias_deterioro": deterioros, # Zonas que empeoraron esta semana
        "anomalias_mejora": mejoras, # Zonas que mejoraron esta semana
        "tendencias_negativas": tendencias, # Zonas que llevan 3 semanas seguidas en bajada
        "benchmarking": benchmarking, # Zonas deebajo su grupo (mismo pais y tipo de zona)
        "correlaciones": correlaciones, # Zonas con combinaciones problemáticas entre métricas (ej: alto Lead Penetration pero bajo Conversion)
        "ordenes_crecimiento": crec_ordenes, # Zonas que mas crecieron en ordenes comparando hace 5 semanas vs ahora
        "ordenes_declive": caida_ordenes, # Zonas que mas cayeron en ordenes comparando hace 5 semanas vs ahora
    }
    return todos_los_insights


# Función para convertir los insights que encontramos con pandas a un formato de texto que Groq pueda leer y redactar el reporte ejecutivo
def convertir_insights_a_texto(insights):
    texto = "HALLAZGOS DEL ANÁLISIS AUTOMÁTICO:\n\n"

    texto = texto + "## 1. ANOMALÍAS - Deterioros (>10% caída WoW)\n"
    texto = texto + insights["anomalias_deterioro"].to_string(index=False) + "\n\n"

    texto = texto + "## 2. ANOMALÍAS - Mejoras (>10% mejora WoW)\n"
    texto = texto + insights["anomalias_mejora"].to_string(index=False) + "\n\n"

    texto = texto + "## 3. TENDENCIAS NEGATIVAS (3+ semanas en descenso)\n"
    texto = texto + insights["tendencias_negativas"].to_string(index=False) + "\n\n"

    texto = texto + "## 4. BENCHMARKING (zonas por debajo de su grupo)\n"
    texto = texto + insights["benchmarking"].to_string(index=False) + "\n\n"

    texto = texto + "## 5. CORRELACIONES PROBLEMÁTICAS\n"
    for c in insights["correlaciones"]:
        texto = texto + f"\n### {c['tipo']}\n{c['descripcion']}\n"
        texto = texto + c["data"].to_string(index=False) + "\n"

    texto = texto + "\n## 6. CRECIMIENTO EN ÓRDENES (Top 10)\n"
    texto = texto + insights["ordenes_crecimiento"].to_string(index=False) + "\n\n"

    texto = texto + "## 7. DECLIVE EN ÓRDENES (Top 10)\n"
    texto = texto + insights["ordenes_declive"].to_string(index=False) + "\n"

    return texto


# Prompt para que Groq escriba el reporte ejecutivo
prompt_reporte = """
Eres un analista de Rappi. Con los siguientes hallazgos, genera un reporte
ejecutivo en español y en formato Markdown.

{insights_text}

ESTRUCTURA DEL REPORTE:
# Reporte Ejecutivo - Análisis Operacional Rappi

## Resumen Ejecutivo
(Los 3-5 hallazgos mas importantes, 1-2 oraciones cada uno)

## 1. Anomalías Detectadas
### Deterioros Críticos
### Mejoras Destacadas

## 2. Tendencias Preocupantes

## 3. Benchmarking

## 4. Correlaciones y Oportunidades

## 5. Dinámica de Órdenes

## Recomendaciones Accionables
(Una acción concreta para cada hallazgo importante)

Sé conciso, usa datos específicos (nombres de zonas, porcentajes), y que las
recomendaciones sean prácticas y accionables.
"""

# Parte 4 - Interfaz con Streamlit

# Barra lateral para configurar la API Key de Groq y mostrar un resumen de los datos que tenemos cargados
with st.sidebar:
    st.header("Configuración")
    
    # carga la key del archivo .env
    api_key = os.getenv("GROQ_API_KEY")
    
    if api_key:
        st.success("API Key configurada")
    else:
        st.warning("No se encontró la API Key en el archivo .env")

    st.divider()
    st.markdown("**Datos cargados:**")
    st.markdown("- 12,573 registros de métricas")
    st.markdown("- 1,242 registros de órdenes")
    st.markdown("- 9 países, 964 zonas")

# Cargamos los datos
df_metricas, df_ordenes = cargar_datos()
resumen_datos = hacer_resumen(df_metricas, df_ordenes)

# Creamos dos pestañas: una para el Chatbot y otra para los insights automáticos
tab_bot, tab_insights = st.tabs(["Chatbot Conversacional", "Insights Automáticos"])


# Pestaña 1 - Chatbot 
with tab_bot:
    st.subheader("Pregunta lo que quieras sobre las operaciones de Rappi")

    # Inicializar el historial del chat si no existe
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Mostrar los mensajes anteriores
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("fig") is not None:
                st.plotly_chart(msg["fig"], use_container_width=True)

    # Botones de sugerencia (solo aparecen si no hay mensajes todavia en el chat)
    if len(st.session_state.messages) == 0:
        st.markdown("Hola! Prueba con estas preguntas:")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Top 5 zonas por Lead Penetration", use_container_width=True):
                st.session_state.suggested = "¿Cuáles son las 5 zonas con mayor Lead Penetration esta semana?"
                st.rerun()
            if st.button("Evolución Gross Profit en Chapinero", use_container_width=True):
                st.session_state.suggested = "Muestra la evolución de Gross Profit UE en Chapinero en las últimas 8 semanas"
                st.rerun()
        with col2:
            if st.button("Perfect Order: Wealthy vs Non Wealthy (MX)", use_container_width=True):
                st.session_state.suggested = "Compara el Perfect Order entre zonas Wealthy y Non Wealthy en México"
                st.rerun()
            if st.button("Alto Lead + Bajo Perfect Order", use_container_width=True):
                st.session_state.suggested = "¿Qué zonas tienen alto Lead Penetration pero bajo Perfect Order?"
                st.rerun()

    # Recibir input del usuario (o la sugerencia si clickeo un boton)
    sugerencia = st.session_state.pop("suggested", None)
    pregunta_usuario = st.chat_input("Escribe tu pregunta aquí...")
    if sugerencia:
        pregunta_usuario = sugerencia

    if pregunta_usuario and api_key:
        # Guardar y mostrar la pregunta
        st.session_state.messages.append({"role": "user", "content": pregunta_usuario})
        with st.chat_message("user"):
            st.markdown(pregunta_usuario)

        # Generar respuesta
        with st.chat_message("assistant"):
            with st.spinner("Analizando..."):
                resultado, grafico, codigo = hacer_pregunta(
                    None, pregunta_usuario, df_metricas, df_ordenes,
                    resumen_datos, st.session_state.messages
                )
                   

            # Mostrar resultado
            st.markdown(resultado)
            if grafico is not None:
                st.plotly_chart(grafico, use_container_width=True)

            # Mostrar el codigo que genero Groq (por si quieren verlo)
            with st.expander("Ver código generado"):
                st.code(codigo, language="python")

            # Sugerencias de que mas puede preguntar
            sugerencias = obtener_sugerencias(pregunta_usuario)
            st.markdown("Análisis sugeridos:")
            for s in sugerencias:
                st.markdown(f"- {s}")

        # Guardar la respuesta en el historial
        st.session_state.messages.append({
            "role": "assistant",
            "content": resultado,
            "fig": grafico
        })

    elif pregunta_usuario and not api_key:
        st.warning("Primero configura tu API Key en la barra lateral.")


# Pestaña 2 - Insights automáticos
with tab_insights:
    st.subheader("Reporte ejecutivo con insights automáticos")
    st.markdown("Se analiza automáticamente los datos y se genera un reporte con los hallazgos más importantes.")

    if st.button("Generar Insights", type="primary", use_container_width=True):
        if not api_key:
            st.warning("Primero configura tu API Key en la barra lateral.")
        else:
            # Paso 1: correr los analisis con pandas
            with st.spinner("Analizando datos..."):
                insights = ejecutar_todos_los_analisis(df_metricas, df_ordenes)
                texto_insights = convertir_insights_a_texto(insights)

            st.success("Análisis completado. Generando reporte...")

            # Mostrar los datos crudos del analisis (colapsado para no estorbar)
            with st.expander("Ver datos del análisis (raw)"):
                st.markdown("Anomalías - Deterioros")
                st.dataframe(insights["anomalias_deterioro"], use_container_width=True)

                st.markdown("Anomalías - Mejoras")
                st.dataframe(insights["anomalias_mejora"], use_container_width=True)

                st.markdown("Tendencias Negativas")
                st.dataframe(insights["tendencias_negativas"], use_container_width=True)

                st.markdown("Benchmarking")
                st.dataframe(insights["benchmarking"], use_container_width=True)

                st.markdown("Órdenes - Crecimiento")
                st.dataframe(insights["ordenes_crecimiento"], use_container_width=True)

                st.markdown("Órdenes - Declive")
                st.dataframe(insights["ordenes_declive"], use_container_width=True)

            # Paso 2: Groq redacta el reporte
            with st.spinner("Redactando reporte..."):
                try:
                    cliente = Groq(api_key=api_key)
                    respuesta = cliente.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[{"role": "user", "content": prompt_reporte.format(insights_text=texto_insights)}],
                        temperature=0,
                    )
                    reporte = respuesta.choices[0].message.content
                except Exception as e:
                    reporte = f"Error al generar el reporte: {str(e)}"

            # Mostrar el reporte
            st.divider()
            st.markdown(reporte)

            # Boton para descargar
            st.download_button(
                label="Descargar Reporte (Markdown)",
                data=reporte,
                file_name="rappi_reporte_ejecutivo.md",
                mime="text/markdown"
            
            )
            
            # Botón para descarga el pdf
            try:
                pdf = FPDF()
                pdf.add_page()
                pdf.set_auto_page_break(auto=True, margin=15)
                pdf.set_font("Helvetica", size=10)
                for linea in reporte.split("\n"):
                    linea = linea.encode('latin-1', 'replace').decode('latin-1')
                    if linea.startswith("# "):
                        pdf.set_font("Helvetica", "B", 16)
                        pdf.cell(0, 10, linea.replace("# ", ""), ln=True)
                        pdf.set_font("Helvetica", size=10)
                    elif linea.startswith("## "):
                        pdf.set_font("Helvetica", "B", 13)
                        pdf.cell(0, 8, linea.replace("## ", ""), ln=True)
                        pdf.set_font("Helvetica", size=10)
                    elif linea.startswith("### "):
                        pdf.set_font("Helvetica", "B", 11)
                        pdf.cell(0, 7, linea.replace("### ", ""), ln=True)
                        pdf.set_font("Helvetica", size=10)
                    elif linea.strip() == "":
                        pdf.cell(0, 5, "", ln=True)
                    else:
                        pdf.multi_cell(0, 5, linea)

                pdf_output = pdf.output(dest='S')
                st.download_button(
                    label="Descargar Reporte (PDF)",
                    data=pdf_output if isinstance(pdf_output, bytes) else pdf_output.encode('latin-1'),
                    file_name="rappi_reporte_ejecutivo.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.warning(f"No se pudo generar el PDF: {str(e)}")
# Caso Técnico: Sistema de Análisis Inteligente para Operaciones Rappi

## Arquitectura

```
Usuario (navegador)
       │
       ▼
  Streamlit (localhost:8501)
       │
       ├── Pestaña 1: Bot Conversacional (70%)
       │     │
       │     ├── El usuario escribe pregunta en español
       │     ├── Groq (Llama 3.3 70B) traduce a código Pandas
       │     ├── Pandas ejecuta sobre los datos del Excel
       │     └── Muestra resultado + gráfico Plotly
       │
       └── Pestaña 2: Insights Automáticos (30%)
             │
             ├── Pandas analiza (anomalías, tendencias, correlaciones)
             ├── Groq redacta reporte ejecutivo
             └── Descarga en Markdown o PDF
```

## Stack Tecnológico

| Componente | Tecnología | Justificación |
|---|---|---|
| Interfaz | Streamlit | Rápido de construir, interactivo|
| Datos | Pandas | Estándar para manipulación de datos en Python |
| LLM | Groq (Llama 3.3 70B) | API gratuita y buena para generar código |
| Gráficos | Plotly | Interactivos, se integra nativamente con Streamlit |
| PDF | FPDF | Generación de reportes en PDF |

**Costo estimado:** $0 (Groq API tiene tier gratuito)

## Cómo ejecutar

### 1. Clonar el repositorio
```bash
git clone <repo-url>
cd rappi-bot
```

### 2. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 3. Configurar API Key de Groq (gratis)
1. Ve a https://console.groq.com/keys
2. Crea una cuenta y genera una API Key
3. Crea un archivo `.env` en la carpeta del proyecto:
```
GROQ_API_KEY=tu_api_key_aqui
```

### 4. Ejecutar
```bash
streamlit run app.py
```
Se abrirá en http://localhost:8501

## Estructura del Proyecto

```
rappi-bot/
├── app.py              # Todo el código (datos, bot, insights, interfaz)
├── data.xlsx           # Datos de operaciones Rappi
├── requirements.txt    # Dependencias
├── .env                # API Key (no se sube al repo)
├── .gitignore          # Archivos ignorados por Git
└── README.md           # Este archivo
```

## Funcionalidades

### Bot Conversacional (70%)
- Preguntas de filtrado ("Top 5 zonas por Lead Penetration")
- Comparaciones ("Wealthy vs Non Wealthy en México")
- Tendencias temporales ("Evolución de Gross Profit últimas 8 semanas")
- Agregaciones ("Promedio de Lead Penetration por país")
- Análisis multivariable ("Alto Lead pero bajo Perfect Order")
- Preguntas de inferencia ("Zonas que más crecen en órdenes")
- Contexto de negocio ("Zonas problemáticas")
- Memoria conversacional
- Sugerencias proactivas
- Visualización con gráficos Plotly
- Reintento automático si el código generado falla

### Insights Automáticos (30%)
- Anomalías: cambios mayores al 10% semana a semana
- Tendencias: métricas en descenso 3 o más semanas consecutivas
- Benchmarking: zonas por debajo del promedio de su grupo
- Correlaciones: combinaciones problemáticas entre métricas
- Dinámica de órdenes: zonas creciendo y decreciendo
- Reporte ejecutivo redactado por IA
- Descarga en Markdown y PDF

## Decisiones Técnicas

1. **Groq (Llama 3.3 70B) en lugar de GPT-4**: Costo $0, calidad suficiente para generación de código Pandas.

2. **Generación de código en vez de RAG**: El LLM genera código Pandas que se ejecuta sobre los datos reales. Esto es más preciso para consultas numéricas que intentar buscar respuestas en texto.

3. **Insights con Pandas + LLM para redacción**: Los análisis estadísticos (anomalías, tendencias) se hacen con Pandas (determinista y confiable). Solo se usa el LLM para redactar el reporte final.

4. **Reintento automático**: Si el código generado falla, se envía el error al LLM para que lo corrija automáticamente, mejorando la tasa de éxito.

5. **Streamlit**: Una sola herramienta para interfaz, chat, gráficos y descarga. Sin necesidad de frontend separado.

## Limitaciones

- El bot puede generar código incorrecto si la pregunta es muy ambigua (se soluciona siendo más específico)
- A veces confunde CITY con ZONE (Chapinero es zona, no ciudad)
- El tier gratuito de Groq tiene límite de requests por minuto (30 requests por minuto, aproximadamente 1,000 requests por día)

## Próximos Pasos

- Envío automático de reportes por email (con smtplib o n8n)
- Programar reportes semanales automáticos
- Dashboard en tiempo real con datos actualizados
- Mejorar el diseño visual del Dashboard
- Exportación de resultados a CSV
- Cache de respuestas frecuentes
- Integración con Power BI para visualización de dashboards ejecutivos

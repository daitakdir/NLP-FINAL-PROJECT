from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_file
import requests
import pandas as pd
import os

load_dotenv()

app = Flask(__name__)

# =====================================================
# GROQ API CONFIG
# =====================================================
# Daftar gratis di https://console.groq.com -> buat API Key
# Lalu set sebagai environment variable, JANGAN ditulis langsung di kode.
#
# Cara set di terminal sebelum run (Mac/Linux):
#   export GROQ_API_KEY="isi_api_key_kamu"
# Windows (PowerShell):
#   $env:GROQ_API_KEY="isi_api_key_kamu"
#
# Kalau deploy ke Streamlit Cloud / Render / Railway, set lewat
# halaman "Secrets" / "Environment Variables" di dashboard mereka.

GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
GROQ_MODEL = 'llama-3.3-70b-versatile'  # model gratis di Groq, setara llama3

# =====================================================
# LOAD DATASET
# =====================================================

df = pd.read_csv('FAOLEX_Food.csv')

# =====================================================
# PREPROCESSING
# =====================================================

# convert Date of text -> Year
df['Year'] = pd.to_datetime(
    df['Date of text'],
    errors='coerce'
).dt.year

# =====================================================
# HOME
# =====================================================

@app.route('/')
def home():

    return send_file('faolex_food_dashboard.html')

# =====================================================
# AI QUERY
# =====================================================

@app.route('/trend-chart')
def trend_chart():

    year_counts = df['Year'].value_counts().sort_index()

    return jsonify({

        'labels': year_counts.index.tolist(),

        'values': year_counts.values.tolist()

    })

@app.route('/predict', methods=['POST'])
def predict():

    try:

        data = request.json

        user_prompt = data['text'].lower()

        context = ""
        chart_payload = None

        # =================================================
        # TOP NEGARA
        # =================================================

        if 'negara' in user_prompt \
        or 'country' in user_prompt \
        or 'wilayah' in user_prompt:

            top_country = df[
                'Country/Territory'
            ].value_counts().head(10)

            context = f"""

            Top 10 negara/wilayah dengan regulasi terbanyak:

            {top_country.to_string()}

            """

            chart_payload = {
                'type': 'bar',
                'labels': top_country.index.tolist(),
                'values': top_country.values.tolist(),
                'label': 'Jumlah Dokumen'
            }

        # =================================================
        # TREND TAHUN
        # =================================================

        elif 'tahun' in user_prompt \
        or 'trend' in user_prompt \
        or 'perkembangan' in user_prompt:

            year_counts = df[
                'Year'
            ].value_counts().sort_index()

            growth = year_counts.pct_change().mean()

            context = f"""

            Jumlah dokumen per tahun:

            {year_counts.tail(20).to_string()}

            Rata-rata pertumbuhan dokumen:
            {growth:.2f}

            """

            chart_payload = {
                'type': 'line',
                'labels': year_counts.index.tolist(),
                'values': year_counts.values.tolist(),
                'label': 'Jumlah Dokumen'
            }

        # =================================================
        # TYPE OF TEXT
        # =================================================

        elif 'regulation' in user_prompt \
        or 'legislation' in user_prompt \
        or 'type' in user_prompt:

            type_counts = (
                df['Type of text']
                .dropna()
                .str.split(',')
                .explode()
                .str.strip()
                .value_counts()
            )

            context = f"""

            Distribusi Type of Text:

            {type_counts.to_string()}

            """

            chart_payload = {
                'type': 'doughnut',
                'labels': type_counts.index.tolist(),
                'values': type_counts.values.tolist(),
                'label': 'Distribusi Type of Text'
            }

        # =================================================
        # KEYWORDS ANALYSIS
        # =================================================

        elif 'keyword' in user_prompt \
        or 'topik' in user_prompt:

            keyword_counts = (
                df['Keywords']
                .dropna()
                .str.split(';')
                .explode()
                .str.strip()
                .value_counts()
                .head(10)
            )

            context = f"""

            Top Keywords Dataset:

            {keyword_counts.to_string()}

            """

            chart_payload = {
                'type': 'bar',
                'labels': keyword_counts.index.tolist(),
                'values': keyword_counts.values.tolist(),
                'label': 'Jumlah Dokumen'
            }

        # =================================================
        # DOMAIN ANALYSIS
        # =================================================

        elif 'domain' in user_prompt:

            domain_counts = (
                df['Domain']
                .dropna()
                .str.split(';')
                .explode()
                .str.strip()
                .value_counts()
                .head(10)
            )

            context = f"""

            Distribusi Domain:

            {domain_counts.to_string()}

            """

            chart_payload = {
                'type': 'bar',
                'labels': domain_counts.index.tolist(),
                'values': domain_counts.values.tolist(),
                'label': 'Jumlah Dokumen'
            }

        # =================================================
        # DEFAULT SUMMARY
        # =================================================

        else:

            context = f"""

            Dataset FAOLEX Summary

            Total Dokumen:
            {len(df)}

            Total Kolom:
            {len(df.columns)}

            Nama Kolom:
            {', '.join(df.columns)}

            Top Negara:
            {df['Country/Territory'].value_counts().head(5).to_string()}

            """

        # =================================================
        # FINAL PROMPT
        # =================================================

        final_prompt = f"""

        Kamu adalah AI Analyst profesional
        untuk dataset FAOLEX Food Law.

        Gunakan data berikut
        untuk menjawab pertanyaan user.

        ==========================
        DATASET INFO
        ==========================

        {context}

        ==========================
        PERTANYAAN USER
        ==========================

        {user_prompt}

        ==========================
        INSTRUKSI
        ==========================

        - Jawab dalam bahasa Indonesia
        - Gunakan analisis data
        - Jangan mengarang data
        - Jelaskan dengan rapi
        - Gunakan bullet point jika perlu

        """

        # =================================================
        # REQUEST KE GROQ API (cloud, gratis)
        # =================================================

        if not GROQ_API_KEY:
            return jsonify({
                'error': 'GROQ_API_KEY belum di-set. Set environment variable GROQ_API_KEY terlebih dahulu.'
            })

        response = requests.post(

            'https://api.groq.com/openai/v1/chat/completions',

            headers={
                'Authorization': f'Bearer {GROQ_API_KEY}',
                'Content-Type': 'application/json'
            },

            json={

                'model': GROQ_MODEL,

                'messages': [
                    {'role': 'user', 'content': final_prompt}
                ],

                'temperature': 0.3

            }

        )

        result = response.json()

        if 'error' in result:
            return jsonify({
                'error': result['error'].get('message', 'Terjadi error pada Groq API')
            })

        prediction_text = result['choices'][0]['message']['content']

        return jsonify({

            'prediction': prediction_text,

            'chart': chart_payload

        })

    except Exception as e:

        return jsonify({

            'error': str(e)

        })

# =====================================================

if __name__ == '__main__':

    app.run(debug=True)
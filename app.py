import streamlit as st
import requests
import networkx as nx
from pyvis.network import Network
import pandas as pd
import tempfile
import time

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="MTG Synergy Pro", layout="wide", page_icon="🔮")

# CSS Custom per nascondere menu default e migliorare il look
st.markdown("""
<style>
    .reportview-container { background: #121212; color: #e0e0e0; }
    .sidebar .sidebar-content { background: #1e1e1e; }
</style>
""", unsafe_allow_html=True)

st.title("🔮 MTG Deck Visualizer 2.0 (Pro Edition)")

# --- LOGICA COLORI MTG (WUBRG) ---
def get_mtg_color(colors, type_line):
    """Restituisce il codice HEX basato sull'identità di colore."""
    if "Land" in type_line: return "#8B4513" # Marrone Terra
    if not colors: return "#A9A9A9" # Grigio Artefatto/Eldrazi
    if len(colors) > 1: return "#DAA520" # Oro (Multicolor)
    
    mapping = {
        'W': '#F8E7B9', # Bianco Panna
        'U': '#0E68AB', # Blu Magic
        'B': '#150B00', # Nero (quasi)
        'R': '#D3202A', # Rosso Fuoco
        'G': '#00733E'  # Verde Foresta
    }
    return mapping.get(colors[0], "#ccc")

# --- FETCH DATI SCRYFALL ---
@st.cache_data
def get_card_data_pro(card_name):
    url = f"https://api.scryfall.com/cards/named?exact={card_name}"
    try:
        time.sleep(0.05) 
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            
            # Gestione carte doppia faccia
            if 'card_faces' in data:
                oracle_text = data['card_faces'][0].get('oracle_text', '') + " " + data['card_faces'][1].get('oracle_text', '')
                image = data['card_faces'][0].get('image_uris', {}).get('normal', '')
            else:
                oracle_text = data.get('oracle_text', '')
                image = data.get('image_uris', {}).get('normal', '')

            return {
                'name': data.get('name'),
                'type': data.get('type_line'),
                'cmc': data.get('cmc', 0),
                'colors': data.get('colors', []),
                'oracle_text': oracle_text,
                'image_url': image,
                'price': data.get('prices', {}).get('eur', 'N/A')
            }
        return None
    except:
        return None

# --- SIDEBAR: INPUT & FILTRI ---
with st.sidebar:
    st.header("🛠️ Deck Editor")
    decklist_input = st.text_area("Lista Carte (una per riga)", height=250, 
                                  value="Sol Ring\nArcane Signet\nCommand Tower\nBirds of Paradise\nWrath of God\nLightning Bolt\nBrainstorm\nCounterspell\nShivan Dragon\nLlanowar Elves")
    
    st.divider()
    st.subheader("🔍 Filtri Visuali")
    min_cmc, max_cmc = st.slider("Filtra per Mana Value (CMC)", 0, 15, (0, 15))
    show_lands = st.checkbox("Mostra Terre", value=True)

    analyze_btn = st.button("🚀 Analizza Mazzo", type="primary")

# --- MAIN APP ---
if analyze_btn and decklist_input:
    raw_names = [line.strip() for line in decklist_input.split('\n') if line.strip()]
    
    # 1. Loading Dati
    with st.spinner(f"Consultando l'Oracolo per {len(raw_names)} carte..."):
        cards_data = []
        for name in raw_names:
            c = get_card_data_pro(name)
            if c: cards_data.append(c)
    
    # Creazione DataFrame per gestire i filtri
    df = pd.DataFrame(cards_data)
    
    # 2. Applicazione Filtri
    if not df.empty:
        # Filtro CMC
        df = df[(df['cmc'] >= min_cmc) & (df['cmc'] <= max_cmc)]
        # Filtro Terre
        if not show_lands:
            df = df[~df['type'].str.contains("Land")]

        # Calcolo Statistiche
        total_price = pd.to_numeric(df['price'], errors='coerce').sum()
        avg_cmc = df['cmc'].mean()
        
        # Display KPI in alto
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("Carte Analizzate", len(df))
        kpi2.metric("Prezzo Stimato (CardMarket)", f"€{total_price:.2f}")
        kpi3.metric("Avg. Mana Value", f"{avg_cmc:.2f}")

        # 3. Costruzione Grafo
        G = nx.DiGraph()
        
        for index, row in df.iterrows():
            # Dimensione basata sul CMC (Minimo 10, +5 per ogni mana)
            node_size = 15 + (row['cmc'] * 5)
            
            # Colore
            node_color = get_mtg_color(row['colors'], row['type'])
            
            # HTML per il Tooltip (Immagine al passaggio del mouse)
            tooltip_html = f"""
            <div style='text-align:center;'>
                <img src='{row['image_url']}' width='200'><br>
                <b>{row['name']}</b><br>
                CMC: {row['cmc']} | €{row['price']}
            </div>
            """
            
            G.add_node(row['name'], 
                       size=node_size, 
                       color=node_color,
                       title=tooltip_html, # Questo fa la magia dell'immagine
                       label=row['name'],
                       font={'color': 'white', 'strokeWidth': 2, 'strokeColor': 'black'})

        # 4. Calcolo Sinergie (Versione Semplificata Keywords)
        # Keywords base da cercare
        keywords = ['artifact', 'enchantment', 'human', 'elf', 'goblin', 'zombie', 'dragon', 
                    'graveyard', 'sacrifice', 'counter', 'destroy', 'draw', 'exile']
        
        nodes_list = list(G.nodes())
        for i in range(len(nodes_list)):
            for j in range(len(nodes_list)):
                if i == j: continue
                
                name_a = nodes_list[i]
                name_b = nodes_list[j]
                
                # Recupera i dati dal DF originale
                card_a = df[df['name'] == name_a].iloc[0]
                card_b = df[df['name'] == name_b].iloc[0]
                
                # Logica Sinergia: A menziona una keyword che B possiede nel tipo
                text_a = card_a['oracle_text'].lower()
                type_b = card_b['type'].lower()
                
                for k in keywords:
                    if k in text_a and k in type_b:
                        G.add_edge(name_a, name_b, color="#555555", width=1)

        # 5. Rendering
        net = Network(height="700px", width="100%", bgcolor="#222222", font_color="white")
        net.from_nx(G)
        
        # Fisica migliorata per evitare sovrapposizioni (BarnsHut)
        net.barnes_hut(gravity=-2000, central_gravity=0.3, spring_length=150)
        
        try:
            path = tempfile.gettempdir() + "/mtg_graph_pro.html"
            net.save_graph(path)
            with open(path, 'r', encoding='utf-8') as f:
                source_code = f.read()
            st.components.v1.html(source_code, height=720)
        except Exception as e:
            st.error(f"Errore visualizzazione: {e}")

    else:
        st.warning("Nessuna carta trovata con i filtri attuali.")

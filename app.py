import streamlit as st
import requests
import networkx as nx
from pyvis.network import Network
import pandas as pd
import tempfile
import time

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="MTG Minimal", layout="wide", page_icon="⚪")

st.markdown("""
<style>
    .reportview-container { background: #121212; color: #e0e0e0; }
    .sidebar .sidebar-content { background: #1e1e1e; }
</style>
""", unsafe_allow_html=True)

st.title("⚪ MTG SINERGY")

# --- LOGICA COLORI MTG ---
def get_mtg_color(colors, type_line):
    if "Land" in type_line: return "#8B4513" 
    if not colors: return "#A9A9A9" 
    if len(colors) > 1: return "#DAA520" 
    mapping = {'W': '#F8E7B9', 'U': '#0E68AB', 'B': '#150B00', 'R': '#D3202A', 'G': '#00733E'}
    return mapping.get(colors[0], "#ccc")

# --- FETCH DATI ---
@st.cache_data
def get_card_data_minimal(card_name):
    url = f"https://api.scryfall.com/cards/named?exact={card_name}"
    try:
        time.sleep(0.05) 
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            
            # Recuperiamo il testo SOLO per il calcolo interno delle linee
            if 'card_faces' in data:
                oracle_text = f"{data['card_faces'][0].get('oracle_text', '')}\n{data['card_faces'][1].get('oracle_text', '')}"
                type_line = f"{data['card_faces'][0].get('type_line', '')}"
            else:
                oracle_text = data.get('oracle_text', '')
                type_line = data.get('type_line', '')

            return {
                'name': data.get('name'),
                'type': type_line, 
                'cmc': data.get('cmc', 0),
                'colors': data.get('color_identity', []), 
                'oracle_text': oracle_text.lower() 
            }
        return None
    except:
        return None

# --- CALCOLO SINERGIA ---
def calculate_synergy_weight(card_a, card_b):
    score = 0
    # Keywords
    tribal_keywords = ['goblin', 'elf', 'human', 'zombie', 'dragon', 'angel', 'artifact', 'enchantment']
    mech_keywords = ['destroy', 'exile', 'draw', 'counter', 'sacrifice', 'graveyard', 'token', 'flying']

    text_a = card_a['oracle_text']
    type_b = card_b['type'].lower()
    text_b = card_b['oracle_text']

    # Sinergia Tribale
    for k in tribal_keywords:
        if k in text_a and k in type_b:
            score += 2 

    # Sinergia Meccanica
    for k in mech_keywords:
        if k in text_a and k in text_b:
            score += 1 

    # Sinergia Colore
    if card_a['colors'] == card_b['colors'] and len(card_a['colors']) > 0:
        score += 0.5

    return score

# --- INTERFACCIA ---
with st.sidebar:
    st.header("Lista Carte")
    decklist_input = st.text_area("Inserisci carte", height=300, 
                                  value="Sol Ring\nArcane Signet\nCommand Tower\nBirds of Paradise\nWrath of God\nLightning Bolt")
    analyze_btn = st.button("Genera Grafo", type="primary")

# --- MAIN ---
if analyze_btn and decklist_input:
    raw_names = [line.strip() for line in decklist_input.split('\n') if line.strip()]
    
    with st.spinner("Elaborazione..."):
        cards_data = [d for name in raw_names if (d := get_card_data_minimal(name))]
    
    df = pd.DataFrame(cards_data)
    
    if not df.empty:
        G = nx.DiGraph()
        
        for index, row in df.iterrows():
            # Dimensione Nodo
            node_size = 15 + (row['cmc'] * 4)
            
            # Tooltip MINIMAL
            colors_display = "/".join(row['colors']) if row['colors'] else "C"
            tooltip = f"<b>{row['name']}</b><br>Colore: {colors_display}<br>Costo: {int(row['cmc'])}"
            
            G.add_node(row['name'], 
                       size=node_size, 
                       color=get_mtg_color(row['colors'], row['type']),
                       title=tooltip, 
                       label=row['name'],
                       font={'color': 'white'})

        # Creazione Archi
        nodes_list = list(G.nodes())
        for i in range(len(nodes_list)):
            for j in range(len(nodes_list)):
                if i == j: continue
                
                name_a, name_b = nodes_list[i], nodes_list[j]
                card_a = df[df['name'] == name_a].iloc[0]
                card_b = df[df['name'] == name_b].iloc[0]
                
                weight = calculate_synergy_weight(card_a, card_b)
                
                if weight >= 1:
                    edge_width = min(weight * 1.5, 6) 
                    G.add_edge(name_a, name_b, width=edge_width, color="#555555")

        # Visualizzazione (CORRETTA)
        net = Network(
            height="700px", 
            width="100%", 
            bgcolor="#222222", 
            font_color="white"
        )
        
        net.from_nx(G)
        net.barnes_hut(gravity=-3000, central_gravity=0.3, spring_length=180)
        
        try:
            path = tempfile.gettempdir() + "/mtg_minimal.html"
            net.save_graph(path)
            with open(path, 'r', encoding='utf-8') as f:
                source_code = f.read()
            st.components.v1.html(source_code, height=720)
        except Exception as e:
            st.error(f"Errore: {e}")


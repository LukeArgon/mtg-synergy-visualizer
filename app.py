import streamlit as st
import requests
import networkx as nx
from pyvis.network import Network
import pandas as pd
import tempfile
import time

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="MTG Clean Analyzer", layout="wide", page_icon="🧿")

# CSS per nascondere elementi inutili e dare il look Dark Mode
st.markdown("""
<style>
    .reportview-container { background: #121212; color: #e0e0e0; }
    .sidebar .sidebar-content { background: #1e1e1e; }
</style>
""", unsafe_allow_html=True)

st.title("MTG Sinergy")

# --- LOGICA COLORI MTG ---
def get_mtg_color(colors, type_line):
    if "Land" in type_line: return "#8B4513"  # Marrone Terra
    if not colors: return "#A9A9A9"           # Grigio Artefatto/Eldrazi
    if len(colors) > 1: return "#DAA520"      # Oro (Multicolor)
    
    mapping = {
        'W': '#F8E7B9', # Bianco
        'U': '#0E68AB', # Blu
        'B': '#150B00', # Nero
        'R': '#D3202A', # Rosso
        'G': '#00733E'  # Verde
    }
    return mapping.get(colors[0], "#ccc")

# --- FETCH DATI ---
@st.cache_data
def get_card_data_clean(card_name):
    url = f"https://api.scryfall.com/cards/named?exact={card_name}"
    try:
        time.sleep(0.05) 
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            
            # Recupero testo per calcoli interni (NON mostrato a video)
            if 'card_faces' in data:
                face0 = data['card_faces'][0]
                face1 = data['card_faces'][1]
                oracle_text = f"{face0.get('oracle_text', '')}\n{face1.get('oracle_text', '')}"
                type_line = f"{face0.get('type_line', '')}"
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

# --- CALCOLO PESO SINERGIA ---
def calculate_synergy_weight(card_a, card_b):
    score = 0
    tribal_keywords = ['goblin', 'elf', 'human', 'zombie', 'dragon', 'angel', 'artifact', 'enchantment', 'sliver']
    mech_keywords = ['destroy', 'exile', 'draw', 'counter', 'sacrifice', 'graveyard', 'token', 'flying', 'haste', 'trample']

    text_a = card_a['oracle_text']
    type_b = card_b['type'].lower()
    text_b = card_b['oracle_text']

    # 1. Tribale / Tipo (+2 pt)
    for k in tribal_keywords:
        if k in text_a and k in type_b:
            score += 2 

    # 2. Meccanica (+1 pt)
    for k in mech_keywords:
        if k in text_a and k in text_b:
            score += 1 

    # 3. Colore (+0.5 pt)
    if card_a['colors'] == card_b['colors'] and len(card_a['colors']) > 0:
        score += 0.5

    return score

# --- SIDEBAR (INPUT & FILTRI) ---
with st.sidebar:
    st.header("🛠️ Configurazione Mazzo")
    
    # Input Lista (Corretto per evitare errori di sintassi)
    decklist_input = st.text_area(
        "Lista Carte", 
        height=200, 
        value="Sol Ring\nArcane Signet\nCommand Tower\nBirds of Paradise\nWrath of God\nLightning Bolt"
    )
    
    st.divider()
    st.subheader("🔍 Filtri Visualizzazione")
    
    # FILTRO 1: Range Costo di Mana
    min_cmc, max_cmc = st.slider("Costo di Mana (CMC)", 0, 15, (0, 15))
    
    # FILTRO 2: Mostra/Nascondi Terre
    show_lands = st.checkbox("Mostra Terre", value=True)
    
    analyze_btn = st.button("Genera Grafo", type="primary")

# --- MAIN ---
if analyze_btn and decklist_input:
    raw_names = [line.strip() for line in decklist_input.split('\n') if line.strip()]
    
    with st.spinner(f"Analisi di {len(raw_names)} carte..."):
        all_cards_data = [d for name in raw_names if (d := get_card_data_clean(name))]
    
    # Creazione DataFrame
    df = pd.DataFrame(all_cards_data)
    
    if not df.empty:
        # --- APPLICAZIONE FILTRI ---
        # 1. Filtro CMC
        df_filtered = df[(df['cmc'] >= min_cmc) & (df['cmc'] <= max_cmc)]
        
        # 2. Filtro Terre
        if not show_lands:
            df_filtered = df_filtered[~df_filtered['type'].str.contains("Land")]
        
        # Statistiche post-filtro
        st.caption(f"Visualizzando {len(df_filtered)} carte su {len(df)} totali.")

        # --- COSTRUZIONE GRAFO ---
        G = nx.DiGraph()
        
        for index, row in df_filtered.iterrows():
            # Logica Dimensione (CMC)
            node_size = 15 + (row['cmc'] * 5)
            
            # Aggiunta nodo SENZA 'title' (No Tooltip)
            G.add_node(row['name'], 
                       size=node_size, 
                       color=get_mtg_color(row['colors'], row['type']),
                       label=row['name'],  # Il nome appare sotto il pallino
                       font={'color': 'white', 'size': 14, 'strokeWidth': 2, 'strokeColor': 'black'})

        # Logica Archi (Sinergie)
        nodes_list = list(G.nodes())
        connections = 0
        
        for i in range(len(nodes_list)):
            for j in range(len(nodes_list)):
                if i == j: continue
                
                name_a, name_b = nodes_list[i], nodes_list[j]
                
                # Recuperiamo i dati dal DF filtrato
                card_a = df_filtered[df_filtered['name'] == name_a].iloc[0]
                card_b = df_filtered[df_filtered['name'] == name_b].iloc[0]
                
                weight = calculate_synergy_weight(card_a, card_b)
                
                # Disegna solo se c'è sinergia rilevante (>= 1)
                if weight >= 1:
                    connections += 1
                    # Spessore linea proporzionale
                    edge_width = min(weight * 1.5, 7) 
                    G.add_edge(name_a, name_b, width=edge_width, color="#555555")

        # --- VISUALIZZAZIONE ---
        net = Network(
            height="700px", 
            width="100%", 
            bgcolor="#222222", 
            font_color="white"
        )
        
        net.from_nx(G)
        
        # Fisica ottimizzata per distanziare i nodi con etichette
        net.barnes_hut(gravity=-4000, central_gravity=0.1, spring_length=200)
        
        try:
            path = tempfile.gettempdir() + "/mtg_clean.html"
            net.save_graph(path)
            with open(path, 'r', encoding='utf-8') as f:
                source_code = f.read()
            st.components.v1.html(source_code, height=720)
        except Exception as e:
            st.error(f"Errore: {e}")
            
    else:
        st.warning("Nessuna carta trovata con i filtri attuali.")

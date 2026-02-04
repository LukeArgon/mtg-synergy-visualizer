import streamlit as st
import requests
import networkx as nx
from pyvis.network import Network
import pandas as pd
import tempfile
import time

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(
    page_title="MTG Chromatic Analyzer",
    layout="wide",
    page_icon="🌈"
)

# CSS Dark Mode & Stile
st.markdown("""
<style>
    .reportview-container { background: #121212; color: #e0e0e0; }
    .sidebar .sidebar-content { background: #1e1e1e; }
    .stTextArea textarea { font-family: monospace; }
</style>
""", unsafe_allow_html=True)

st.title("MTG Sinergy")

# --- FUNZIONI UTILI ---
def get_mtg_color(colors, type_line):
    if "Land" in type_line: return "#8B4513"
    if not colors: return "#A9A9A9"
    if len(colors) > 1: return "#DAA520"
    
    mapping = {
        'W': '#F8E7B9',
        'U': '#0E68AB',
        'B': '#150B00',
        'R': '#D3202A',
        'G': '#00733E'
    }
    return mapping.get(colors[0], "#ccc")

@st.cache_data
def get_card_data_chroma(card_name):
    clean_name = card_name.strip()
    url = f"https://api.scryfall.com/cards/named?exact={clean_name}"
    try:
        time.sleep(0.05)
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            
            if 'card_faces' in data:
                face0 = data['card_faces'][0]
                face1 = data['card_faces'][1]
                oracle_text = f"{face0.get('oracle_text', '')}\n{face1.get('oracle_text', '')}"
                type_line = face0.get('type_line', '')
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

def calculate_synergy_weight(card_a, card_b):
    score = 0
    # Liste estese di keyword
    tribal_keywords = ['goblin', 'elf', 'human', 'zombie', 'dragon', 'angel', 'artifact', 'enchantment', 'sliver', 'eldrazi', 'wizard', 'warrior', 'cleric']
    mech_keywords = ['destroy', 'exile', 'draw', 'counter', 'sacrifice', 'graveyard', 'token', 'flying', 'haste', 'trample', 'lifelink', 'deathtouch', 'flash']

    text_a = card_a['oracle_text']
    type_b = card_b['type'].lower()
    text_b = card_b['oracle_text']

    # Punteggio Tribale (+2)
    for k in tribal_keywords:
        if k in text_a and k in type_b:
            score += 2

    # Punteggio Meccanico (+1)
    for k in mech_keywords:
        if k in text_a and k in text_b:
            score += 1

    # Punteggio Colore (+0.5)
    if card_a['colors'] == card_b['colors'] and len(card_a['colors']) > 0:
        score += 0.5

    return score

# --- SIDEBAR ---
with st.sidebar:
    st.header("🛠️ Configurazione")
    
    default_deck = "Krenko, Mob Boss\nGoblin Chieftain\nGoblin Warchief\nSkirk Prospector\nImpact Tremors\nSol Ring\nMountain"
    decklist_input = st.text_area(
        "Lista Carte",
        height=200,
        value=default_deck
    )
    
    st.divider()
    
    # Legenda Visiva
    st.subheader("🎨 Legenda Sinergia")
    st.markdown("🟡 **Oro:** Perfetta (4+ pts)")
    st.markdown("🟢 **Verde:** Forte (3-4 pts)")
    st.markdown("🔵 **Blu:** Media (2-3 pts)")
    st.markdown("🟣 **Viola:** Bassa (1-2 pts)")
    
    st.divider()
    
    # Filtri sicuri
    cmc_range = st.slider(
        "Costo di Mana (CMC)",
        min_value=0,
        max_value=15,
        value=(0, 15)
    )
    min_cmc, max_cmc = cmc_range
    
    show_lands = st.checkbox("Mostra Terre", value=True)
    analyze_btn = st.button("Genera Grafo Cromatico", type="primary")

# --- APP PRINCIPALE ---
if analyze_btn and decklist_input:
    raw_names = [line.strip() for line in decklist_input.split('\n') if line.strip()]
    
    with st.spinner(f"Analisi Spettrale in corso..."):
        all_cards_data = []
        for name in raw_names:
            d = get_card_data_chroma(name)
            if d:
                all_cards_data.append(d)
    
    df = pd.DataFrame(all_cards_data)
    
    if not df.empty:
        # Filtri
        df_filtered = df[
            (df['cmc'] >= min_cmc) & 
            (df['cmc'] <= max_cmc)
        ]
        
        if not show_lands:
            df_filtered = df_filtered[~df_filtered['type'].str.contains("Land")]
            
        st.caption(f"Visualizzando {len(df_filtered)} nodi.")

        # COSTRUZIONE GRAFO
        G = nx.DiGraph()
        
        # Nodi
        for index, row in df_filtered.iterrows():
            size = 20 + (row['cmc'] * 5)
            color = get_mtg_color(row['colors'], row['type'])
            
            G.add_node(
                row['name'],
                size=size,
                color=color,
                label=row['name'],
                font={'color': 'white', 'size': 16, 'strokeWidth': 4, 'strokeColor': 'black'}
            )

        # Archi (Edges) con Logica Colore
        nodes = list(G.nodes())
        connections = 0
        
        for i in range(len(nodes)):
            for j in range(len(nodes)):
                if i == j: continue
                
                name_a = nodes[i]
                name_b = nodes[j]
                
                card_a = df_filtered[df_filtered['name'] == name_a].iloc[0]
                card_b = df_filtered[df_filtered['name'] == name_b].iloc[0]
                
                w = calculate_synergy_weight(card_a, card_b)
                
                if w >= 1:
                    connections += 1
                    
                    # 1. Definizione Spessore (Più spesso!)
                    width = min(w * 3, 15) # Moltiplicatore 3x, Max 15px
                    
                    # 2. Definizione Colore (Gradiente Sinergia)
                    if w >= 4:
                        edge_color = "#FFD700" # Oro (Perfetta)
                        opacity = 1.0
                    elif w >= 3:
                        edge_color = "#32CD32" # Lime Green (Forte)
                        opacity = 0.9
                    elif w >= 2:
                        edge_color = "#1E90FF" # Dodger Blue (Media)
                        opacity = 0.7
                    else:
                        edge_color = "#9370DB" # Medium Purple (Bassa)
                        opacity = 0.5

                    # Aggiunta arco con opacità per leggibilità
                    # Nota: Pyvis gestisce i colori HEX, l'opacità va gestita nel colore o nel settings
                    G.add_edge(name_a, name_b, width=width, color=edge_color)

        # Visualizzazione
        net = Network(
            height="750px",
            width="100%",
            bgcolor="#111111", # Sfondo ancora più scuro per far risaltare i colori neon
            font_color="white"
        )
        
        net.from_nx(G)
        
        # Fisica: Aumentiamo la repulsione perché le linee sono spesse
        net.barnes_hut(gravity=-5000, central_gravity=0.1, spring_length=250)
        
        try:
            path = tempfile.gettempdir() + "/mtg_chroma.html"
            net.save_graph(path)
            with open(path, 'r', encoding='utf-8') as f:
                source = f.read()
            st.components.v1.html(source, height=770)
        except Exception as e:
            st.error(f"Errore visualizzazione: {e}")
            
    else:
        st.warning("Nessuna carta trovata.")

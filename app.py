import streamlit as st
import requests
import networkx as nx
from pyvis.network import Network
import pandas as pd
import tempfile
import time

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="MTG Synergy Weighted", layout="wide", page_icon="⚖️")

st.markdown("""
<style>
    .reportview-container { background: #121212; color: #e0e0e0; }
    .sidebar .sidebar-content { background: #1e1e1e; }
</style>
""", unsafe_allow_html=True)

st.title("⚖️ MTG Synergy: Weighted Edition")
st.caption("Lo spessore della linea indica la potenza della sinergia tra le carte.")

# --- LOGICA COLORI MTG ---
def get_mtg_color(colors, type_line):
    if "Land" in type_line: return "#8B4513" 
    if not colors: return "#A9A9A9" 
    if len(colors) > 1: return "#DAA520" 
    mapping = {'W': '#F8E7B9', 'U': '#0E68AB', 'B': '#150B00', 'R': '#D3202A', 'G': '#00733E'}
    return mapping.get(colors[0], "#ccc")

# --- FETCH DATI ---
@st.cache_data
def get_card_data_weighted(card_name):
    url = f"https://api.scryfall.com/cards/named?exact={card_name}"
    try:
        time.sleep(0.05) 
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            
            if 'card_faces' in data:
                oracle_text = f"{data['card_faces'][0].get('oracle_text', '')}\n{data['card_faces'][1].get('oracle_text', '')}"
                type_line = f"{data['card_faces'][0].get('type_line', '')} {data['card_faces'][1].get('type_line', '')}"
            else:
                oracle_text = data.get('oracle_text', '')
                type_line = data.get('type_line', '')

            return {
                'name': data.get('name'),
                'type': type_line,
                'cmc': data.get('cmc', 0),
                'colors': data.get('colors', []),
                'oracle_text': oracle_text.lower(), # Tutto minuscolo per confronto facile
                'price': data.get('prices', {}).get('eur', 'N/A')
            }
        return None
    except:
        return None

# --- SIDEBAR ---
with st.sidebar:
    st.header("🛠️ Deck Editor")
    decklist_input = st.text_area("Lista Carte", height=300, 
                                  value="Krenko, Mob Boss\nGoblin Chieftain\nGoblin Warchief\nSkirk Prospector\nImpact Tremors\nMountain\nSol Ring")
    
    st.info("💡 Suggerimento: Metti il Comandante come prima carta della lista.")
    analyze_btn = st.button("Calcola Pesi Sinergici", type="primary")

# --- ENGINE DI CALCOLO SINERGIA ---
def calculate_synergy_weight(card_a, card_b):
    score = 0
    reasons = []

    # 1. Lista Keyword Tribali e di Tipo
    tribal_keywords = ['goblin', 'elf', 'human', 'zombie', 'dragon', 'angel', 'sliver', 'wizard', 'merfolk', 'artifact', 'enchantment']
    
    # 2. Lista Keyword Meccaniche (Più pesanti)
    mech_keywords = ['destroy', 'exile', 'draw', 'counter', 'sacrifice', 'graveyard', 'token', 'haste', 'trample', 'flying', 'life', 'damage']

    text_a = card_a['oracle_text']
    type_b = card_b['type'].lower()
    text_b = card_b['oracle_text']

    # Regola A: Carta A menziona il TIPO di Carta B (Es. Lord che buffa)
    for k in tribal_keywords:
        if k in text_a and k in type_b:
            score += 2 # Sinergia forte
            reasons.append(f"Tribal: {k}")

    # Regola B: Condivisione Meccanica (Entrambe parlano di "Sacrifice")
    for k in mech_keywords:
        if k in text_a and k in text_b:
            score += 1 # Sinergia meccanica
            reasons.append(f"Mech: {k}")

    # Regola C: Identità di Colore esatta (Bonus piccolo)
    if card_a['colors'] == card_b['colors'] and len(card_a['colors']) > 0:
        score += 0.5

    return score, list(set(reasons))

# --- MAIN APP ---
if analyze_btn and decklist_input:
    raw_names = [line.strip() for line in decklist_input.split('\n') if line.strip()]
    
    with st.spinner("Calcolo delle interazioni complesse..."):
        cards_data = [d for name in raw_names if (d := get_card_data_weighted(name))]
    
    df = pd.DataFrame(cards_data)
    
    if not df.empty:
        # KPI veloci
        st.metric("Carte Analizzate", len(df))

        G = nx.DiGraph()
        
        # Aggiunta Nodi
        for index, row in df.iterrows():
            node_size = 15 + (row['cmc'] * 4)
            # Evidenzia il comandante (assumiamo sia il primo della lista)
            if row['name'] == raw_names[0]:
                border_width = 5 
                border_color = "#FFD700" # Oro
                label_text = f"👑 {row['name']}"
            else:
                border_width = 1
                border_color = "black"
                label_text = row['name']

            tooltip = f"<b>{row['name']}</b><br>{row['type']}<br>€{row['price']}<hr>{row['oracle_text'][:100]}..."
            
            G.add_node(row['name'], 
                       size=node_size, 
                       color=get_mtg_color(row['colors'], row['type']),
                       title=tooltip,
                       label=label_text,
                       borderWidth=border_width,
                       borderWidthSelected=border_width+2,
                       shapeProperties={'useBorderWithImage':True},
                       font={'color': 'white'})

        # Calcolo Archi Pesati
        nodes_list = list(G.nodes())
        connections_count = 0
        
        for i in range(len(nodes_list)):
            for j in range(len(nodes_list)):
                if i == j: continue
                
                name_a, name_b = nodes_list[i], nodes_list[j]
                card_a = df[df['name'] == name_a].iloc[0]
                card_b = df[df['name'] == name_b].iloc[0]
                
                weight, reasons = calculate_synergy_weight(card_a, card_b)
                
                # Disegniamo la linea solo se il peso è rilevante (> 1)
                # Oppure > 0.5 se vogliamo vedere tutto
                if weight >= 1:
                    connections_count += 1
                    # Scala larghezza: da 1px a 8px max
                    edge_width = min(weight * 1.5, 8) 
                    
                    G.add_edge(name_a, name_b, 
                               width=edge_width, 
                               title=f"Score: {weight} ({', '.join(reasons)})",
                               color="#555555")

        # Visualizzazione
        net = Network(height="750px", width="100%", bgcolor="#222222", font_color="white")
        net.from_nx(G)
        
        # Physics config: Aumentiamo la repulsione per vedere meglio le linee spesse
        net.barnes_hut(gravity=-3000, central_gravity=0.1, spring_length=200, spring_strength=0.05)
        
        try:
            path = tempfile.gettempdir() + "/mtg_weighted.html"
            net.save_graph(path)
            with open(path, 'r', encoding='utf-8') as f:
                source_code = f.read()
            st.components.v1.html(source_code, height=770)
            st.success(f"Trovate {connections_count} sinergie significative.")
        except Exception as e:
            st.error(f"Errore: {e}")

import streamlit as st
import requests
import networkx as nx
from pyvis.network import Network
import tempfile
import time

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="MTG Synergy Visualizer", layout="wide")

st.title("🔮 MTG Deck Synergy Visualizer")
st.markdown("""
Questa app visualizza le connessioni tra le carte del tuo mazzo Commander.
**Logica del Judge:** Collega le carte se il testo di una menziona il tipo o la meccanica dell'altra.
""")

# --- FUNZIONI BACKEND (Scryfall API) ---
@st.cache_data
def get_card_data(card_name):
    """Scarica i dati della carta da Scryfall."""
    url = f"https://api.scryfall.com/cards/named?exact={card_name}"
    try:
        time.sleep(0.05) # Rispetto per l'API (Rate limiting)
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except:
        return None

def analyze_synergy(card_a, card_b):
    """
    Analisi Euristica Semplificata:
    Controlla se la Carta A menziona tipi o sottotipi che la Carta B possiede.
    """
    score = 0
    reason = []
    
    # Dati grezzi
    type_line_b = card_b.get('type_line', '').lower()
    oracle_text_a = card_a.get('oracle_text', '').lower()
    
    # Lista di parole chiave da controllare (Tipi di carta e Sottotipi comuni)
    keywords = ['artifact', 'enchantment', 'instant', 'sorcery', 'land', 
                'goblin', 'elf', 'zombie', 'human', 'dragon', 'graveyard', 'exile']
    
    # 1. Controllo Tipi/Tribal
    # Se A dice "Distruggi artefatto" e B è un Artefatto -> Connessione (Interazione)
    # Se A dice "Gli elfi prendono +1/+1" e B è un Elfo -> Connessione (Sinergia)
    
    for kw in keywords:
        if kw in oracle_text_a and kw in type_line_b:
            score += 1
            reason.append(f"Interazione {kw.capitalize()}")
            
    # 2. Controllo Identità di Colore (Semplice)
    # colors_a = card_a.get('colors', [])
    # colors_b = card_b.get('colors', [])
    # if colors_a == colors_b and len(colors_a) > 0:
    #     score += 0.5 # Leggera affinità
        
    return score, ", ".join(reason)

# --- INTERFACCIA UTENTE ---
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader("📝 Inserisci la Lista")
    decklist_input = st.text_area("Incolla qui le carte (una per riga)", height=300, 
                                  placeholder="Sol Ring\nArcane Signet\nLlanowar Elves\nWrath of God")
    
    analyze_btn = st.button("Analizza Sinergie")

with col2:
    st.subheader("🕸️ Grafo delle Sinergie")
    
    if analyze_btn and decklist_input:
        card_names = [line.strip() for line in decklist_input.split('\n') if line.strip()]
        
        if len(card_names) > 30:
            st.warning("⚠️ Hai inserito molte carte. L'analisi potrebbe richiedere un minuto per scaricare i dati.")
        
        # 1. Fetch Dati
        cards_data = []
        progress_bar = st.progress(0)
        
        for i, name in enumerate(card_names):
            data = get_card_data(name)
            if data:
                cards_data.append(data)
            progress_bar.progress((i + 1) / len(card_names))
            
        st.success(f"Scaricati dati per {len(cards_data)} carte.")
        
        # 2. Costruzione Grafo
        G = nx.DiGraph() # Grafo direzionale
        
        for card in cards_data:
            # Aggiungi nodo (Carta)
            # Colora in base al tipo principale
            color = "#97c2fc" # Default Blue
            if "Land" in card.get('type_line', ''): color = "#bfbfbf" # Grigio terre
            elif "Creature" in card.get('type_line', ''): color = "#90EE90" # Verde creature
            elif "Artifact" in card.get('type_line', ''): color = "#D3D3D3" # Grigio artefatti
            
            G.add_node(card['name'], label=card['name'], title=card.get('type_line'), color=color)
            
        # 3. Calcolo Archi (Edges)
        # Confronta ogni carta con ogni altra carta (O(n^2))
        edge_count = 0
        for i in range(len(cards_data)):
            for j in range(len(cards_data)):
                if i == j: continue
                
                card_a = cards_data[i]
                card_b = cards_data[j]
                
                score, reason = analyze_synergy(card_a, card_b)
                
                if score > 0:
                    # Aggiungi connessione
                    G.add_edge(card_a['name'], card_b['name'], title=reason)
                    edge_count += 1

        # 4. Visualizzazione con Pyvis
        net = Network(height="600px", width="100%", bgcolor="#222222", font_color="white", directed=True)
        net.from_nx(G)
        
        # Fisica del grafo (per farlo muovere in modo organico)
        net.force_atlas_2based()
        
        # Salva e mostra
        try:
            path = tempfile.gettempdir() + "/synergy_graph.html"
            net.save_graph(path)
            with open(path, 'r', encoding='utf-8') as f:
                source_code = f.read()
            st.components.v1.html(source_code, height=610)
            st.caption(f"Trovate {edge_count} connessioni sinergiche basate sul testo.")
        except Exception as e:
            st.error(f"Errore nella visualizzazione: {e}")

    elif not decklist_input:
        st.info("Incolla una lista per iniziare.")
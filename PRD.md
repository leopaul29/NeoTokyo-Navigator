Il est 19h00 à Tokyo, les démos commencent à 20h00 ! Il te reste **exactement 1 heure**. Voici un PRD (Product Requirements Document) ultra-ciblé, conçu pour être implémenté en 45 minutes et bluffer les juges (Neo4j, Qdrant, OpenAI).

---

## 🚀 PRD : NeoTokyo Navigator (GraphRAG Agent)

### 1. Elevator Pitch

Un agent conversationnel intelligent qui aide les touristes ou résidents à naviguer dans Tokyo en combinant la compréhension du contexte (Vector DB) et la logique des transports (Graph DB).

### 2. Le Problème & La Solution

- **Problème :** À Tokyo, trouver un lieu qui correspond à une "ambiance" (ex: un café calme) ET qui se trouve sur une ligne de métro pratique depuis notre position actuelle est un casse-tête. Les LLM classiques inventent de fausses lignes de métro.
- **Solution (La Démo) :** L'utilisateur tape (en FR, EN ou JP) : _"Je suis à Shinjuku, je veux visiter un temple traditionnel sans faire plus d'un changement de métro."_ L'application trouve les temples via similarité (Qdrant) et calcule le chemin exact via le réseau de métro (Neo4j).

### 3. Architecture & Tech Stack (Sponsors focus)

| Composant         | Technologie / Sponsor  | Rôle dans l'App (POC)                                                              |
| ----------------- | ---------------------- | ---------------------------------------------------------------------------------- |
| **Frontend UI**   | **Streamlit** (Python) | Interface de chat minimaliste (mise en place en 2 min).                            |
| **Cerveau (LLM)** | **OpenAI** (API)       | Comprend le prompt, extrait l'intention (Lieu + Station de départ).                |
| **Vector DB**     | **Qdrant**             | Recherche sémantique : _"Trouve les lieux correspondant à 'temple traditionnel'"_. |
| **Graph DB**      | **Neo4j**              | Calcule le trajet réel : `"Shinjuku" -[Ligne]-> (Station) -[Proche]-> "Temple"`.   |
| **Traduction**    | **Shisa.ai**           | (Bonus si le temps le permet) Traduire les requêtes japonaises en anglais.         |

---

### 4. Le Scénario de Démo (Ce que tu montreras à 20h)

1. **Écran d'accueil :** Une barre de chat simple.
2. **Action :** Tu tapes : _"Je suis à Shibuya, trouve-moi un grand parc avec peu de correspondances."_
3. **Magie sous le capot (affiché dans des logs visuels) :**

- _Log 1 :_ Qdrant identifie "Shinjuku Gyoen" et "Yoyogi Park".
- _Log 2 :_ Neo4j calcule que Yoyogi est à 1 station direct, Shinjuku Gyoen nécessite 1 correspondance.

4. **Résultat :** L'agent répond : _"Le Parc Yoyogi est idéal. Prenez la Yamanote Line depuis Shibuya (1 arrêt). Bon trajet !"_

---

### 5. Plan d'Action "Urgence" (Prochaines 45 minutes)

1. **Initialiser le projet et l'UI (10 min):**
   Crée un fichier `app.py` avec Streamlit. Mets en place la barre de chat basique (`st.chat_input`) et prépare les variables d'environnement (`OPENAI_API_KEY`, credentials Neo4j/Qdrant).

2. **Mocker / Peupler les bases de données (15 min):** Ne perds pas de temps avec l'Open Data complet.
   Injecte juste **5 stations de métro** (ex: Shibuya, Shinjuku, Harajuku) et **5 lieux** (ex: Yoyogi Park, Meiji Shrine) en dur dans ton instance Neo4j via une requête Cypher. Fais pareil pour Qdrant avec 5 phrases de description. L'important c'est que la démo marche, pas l'exhaustivité.

3. **Coder la fonction logique principale (15 min):**
   Écris la fonction Python qui prend le texte de l'utilisateur, demande à OpenAI d'extraire la station de départ et la catégorie de lieu, puis fait la requête à Neo4j pour trouver le chemin.

4. **Tests et préparation du pitch (5 min):**
   Teste ton scénario de démo (celui de l'étape 4) 3 ou 4 fois. Prépare ta phrase d'accroche pour les juges.

import re
import textwrap
import html
from collections import Counter
from datetime import datetime, timezone, timedelta
from difflib import SequenceMatcher
from urllib.parse import quote

import feedparser
import requests
import streamlit as st
from dateutil import parser as dateparser


st.set_page_config(
    page_title="Tech Week 5",
    page_icon="⚡",
    layout="wide",
)

# ============================================================
# 1. FUENTES Y RADARES REGIONALES
# ============================================================

def google_news_url(query, lang="en-US", gl="US", ceid="US:en"):
    return (
        "https://news.google.com/rss/search?"
        f"q={quote(query)}&hl={lang}&gl={gl}&ceid={ceid}"
    )


BASE_SOURCES = {
    "Reuters": {
        "url": google_news_url(
            "site:reuters.com technology OR AI OR cloud OR cybersecurity OR chips when:7d"
        ),
        "region_hint": None,
    },
    "Financial Times": {
        "url": google_news_url(
            "site:ft.com technology OR AI OR cloud OR cybersecurity OR semiconductors when:7d"
        ),
        "region_hint": None,
    },
    "TechCrunch": {
        "url": "https://techcrunch.com/feed/",
        "region_hint": None,
    },
    "The Verge": {
        "url": "https://www.theverge.com/rss/index.xml",
        "region_hint": None,
    },
    "Ars Technica": {
        "url": "https://feeds.arstechnica.com/arstechnica/index",
        "region_hint": None,
    },
    "WIRED": {
        "url": "https://www.wired.com/feed/rss",
        "region_hint": None,
    },
    "MIT Technology Review": {
        "url": "https://www.technologyreview.com/feed/",
        "region_hint": None,
    },
    "BBC Technology": {
        "url": "https://feeds.bbci.co.uk/news/technology/rss.xml",
        "region_hint": None,
    },
}

# Estos radares complementan a los grandes medios globales.
# No sustituyen fuentes: ayudan a descubrir noticias regionales
# que podrían no entrar en los feeds globales.
REGIONAL_RADARS = {
    "España Radar": {
        "url": google_news_url(
            '(España OR Spain OR Madrid OR Barcelona) '
            '(tecnología OR technology OR IA OR AI OR cloud OR ciberseguridad OR cybersecurity '
            'OR telecom OR "data center") when:7d',
            lang="es",
            gl="ES",
            ceid="ES:es",
        ),
        "region_hint": ("Europa", "España"),
    },
    "Europa Radar": {
        "url": google_news_url(
            '(Europe OR European OR EU OR Germany OR France OR Italy OR Netherlands OR UK) '
            '(technology OR AI OR cloud OR cybersecurity OR telecom OR "data center") when:7d'
        ),
        "region_hint": ("Europa", "Resto de Europa"),
    },
    "Norteamérica Radar": {
        "url": google_news_url(
            '("United States" OR U.S. OR Canada OR Mexico) '
            '(technology OR AI OR cloud OR cybersecurity OR telecom OR chips OR "data center") when:7d'
        ),
        "region_hint": ("Norteamérica", "Norteamérica"),
    },
    "Pakistán Radar": {
        "url": google_news_url(
            '(Pakistan OR Pakistani OR Islamabad OR Karachi OR Lahore) '
            '(technology OR AI OR cloud OR cybersecurity OR telecom OR digital OR "data center") when:7d'
        ),
        "region_hint": ("Medio Oriente / MEA + Pakistán", "Pakistán"),
    },
    "Dubai & UAE Radar": {
        "url": google_news_url(
            '(Dubai OR UAE OR "United Arab Emirates" OR "Abu Dhabi") '
            '(technology OR AI OR cloud OR cybersecurity OR telecom OR digital OR "data center") when:7d'
        ),
        "region_hint": ("Medio Oriente / MEA + Pakistán", "Dubai / UAE"),
    },
    "Egipto Radar": {
        "url": google_news_url(
            '(Egypt OR Egyptian OR Cairo) '
            '(technology OR AI OR cloud OR cybersecurity OR telecom OR digital OR "data center") when:7d'
        ),
        "region_hint": ("Medio Oriente / MEA + Pakistán", "Egipto"),
    },
    "Middle East Radar": {
        "url": google_news_url(
            '("Middle East" OR Saudi Arabia OR Qatar OR Bahrain OR Oman OR Jordan OR Kuwait) '
            '(technology OR AI OR cloud OR cybersecurity OR telecom OR digital OR "data center") when:7d'
        ),
        "region_hint": ("Medio Oriente / MEA + Pakistán", "Resto de MEA"),
    },
}


# ============================================================
# 2. SEGMENTOS TECNOLÓGICOS ALINEADOS A LA OFERTA DE BEYOND
# ============================================================

SEGMENT_RULES = {
    "IA, Automatización & Observabilidad": [
        "artificial intelligence", " ai ", "machine learning", "generative ai",
        "genai", "llm", "automation", "automated", "observability",
        "predictive", "copilot", "agentic", "ai agent", "agents",
        "openai", "anthropic", "gemini", "chatgpt",
    ],
    "Cloud, Data Center & FinOps": [
        "cloud", "aws", "azure", "google cloud", "gcp", "hybrid cloud",
        "multicloud", "data center", "datacenter", "finops", "container",
        "kubernetes", "serverless", "vmware", "virtualization",
        "cloud migration", "cloud infrastructure",
    ],
    "Networking & Connectivity": [
        "networking", "network", "sd-wan", "sdwan", "sd-lan", "sdlan",
        "wan", "wifi", "wi-fi", "ethernet", "switching", "router",
        "routing", "connectivity", "5g", "6g", "fiber", "fibre",
        "telecom", "carrier", "broadband", "private network",
    ],
    "Cybersecurity & Compliance": [
        "cybersecurity", "cyber security", "security breach", "data breach",
        "ransomware", "malware", "zero trust", "firewall", "ngfw",
        "siem", "soc", "identity", "iam", "ddos", "phishing",
        "vulnerability", "cyberattack", "cyber attack", "compliance",
        "privacy", "cspm", "cwpp", "encryption", "incident response",
    ],
    "Digital Workplace, Apps & DevOps": [
        "digital workplace", "workplace", "collaboration", "remote work",
        "hybrid work", "microsoft 365", "teams", "endpoint", "device management",
        "application modernization", "app modernization", "devops",
        "platform engineering", "developer platform", "containers",
        "software development", "enterprise software", "saas",
    ],
    "Managed Services & IT Operations": [
        "managed services", "managed service", "it operations", "it ops",
        "itsm", "itil", "monitoring", "observability", "incident management",
        "problem management", "rmm", "patch management", "asset management",
        "sla", "service management", "business continuity", "disaster recovery",
        "backup", "capacity planning", "operations",
    ],
    "IT Strategy & Digital Transformation": [
        "digital transformation", "technology strategy", "it strategy",
        "technology roadmap", "it roadmap", "cio", "chief information officer",
        "roi", "technology investment", "enterprise transformation",
        "modernization", "modernisation", "technology consulting",
        "it consulting", "governance", "business case", "ai readiness",
    ],
    "IT Support & Service Delivery": [
        "help desk", "helpdesk", "service desk", "technical support",
        "field services", "field service", "onsite support", "on-site support",
        "customer support", "technical account manager", "tam",
        "project delivery", "implementation", "deployment", "migration project",
        "systems integration", "integration services",
    ],
}

SEGMENT_ORDER = list(SEGMENT_RULES.keys())


# ============================================================
# 3. GEOGRAFÍA
# ============================================================

GEO_RULES = {
    "España": [
        "spain", "spanish", "españa", "español", "española",
        "madrid", "barcelona", "valencia", "sevilla", "bilbao",
    ],
    "Pakistán": [
        "pakistan", "pakistani", "islamabad", "karachi", "lahore",
        "rawalpindi", "peshawar",
    ],
    "Dubai / UAE": [
        "dubai", "uae", "united arab emirates", "emirati", "abu dhabi",
        "sharjah",
    ],
    "Egipto": [
        "egypt", "egyptian", "cairo", "alexandria",
    ],
    "Estados Unidos": [
        "united states", "u.s.", "u.s.a.", "american", "silicon valley",
        "washington", "california", "new york", "texas",
    ],
    "Canadá": [
        "canada", "canadian", "toronto", "vancouver", "montreal", "ottawa",
    ],
    "México": [
        "mexico", "méxico", "mexican", "mexicana", "mexicano",
        "mexico city", "ciudad de méxico", "monterrey", "guadalajara",
    ],
    "Resto de Europa": [
        "europe", "european", "european union", " eu ", "brussels",
        "germany", "german", "france", "french", "italy", "italian",
        "netherlands", "dutch", "belgium", "sweden", "switzerland",
        "poland", "portugal", "ireland", "austria", "denmark", "finland",
        "norway", "united kingdom", "britain", "british", "london",
    ],
    "Resto de MEA": [
        "middle east", "mena", "saudi arabia", "saudi", "riyadh",
        "qatar", "doha", "bahrain", "oman", "muscat", "kuwait",
        "jordan", "amman", "lebanon", "beirut",
    ],
}

SUBREGION_TO_REGION = {
    "España": "Europa",
    "Resto de Europa": "Europa",
    "Estados Unidos": "Norteamérica",
    "Canadá": "Norteamérica",
    "México": "Norteamérica",
    "Norteamérica": "Norteamérica",
    "Pakistán": "Medio Oriente / MEA + Pakistán",
    "Dubai / UAE": "Medio Oriente / MEA + Pakistán",
    "Egipto": "Medio Oriente / MEA + Pakistán",
    "Resto de MEA": "Medio Oriente / MEA + Pakistán",
}

PRIORITY_MARKETS = {"España", "Pakistán", "Dubai / UAE", "Egipto"}


# ============================================================
# 4. RANKING EDITORIAL
# ============================================================

STOPWORDS = {
    "the","a","an","and","or","to","of","in","on","for","with","from","at","by",
    "is","are","be","as","its","it","this","that","these","those","new","says",
    "will","has","have","had","after","before","about","into","over","under",
    "your","you","we","our","their","they","he","she","his","her","more","how",
    "why","what","when","where","which","who","can","could","would","should",
    "tech","technology","latest","report","reports","reportedly"
}

TECH_TERMS = {
    "ai","artificial intelligence","cloud","cybersecurity","chip","chips",
    "semiconductor","networking","5g","6g","data center","datacenter",
    "automation","software","hardware","quantum","robotics","devops",
}

BUSINESS_TERMS = {
    "acquisition","acquires","merger","deal","billion","million",
    "investment","funding","valuation","revenue","earnings","ipo",
    "market","shares","stock","partnership","contract","enterprise",
    "supply chain","manufacturing","jobs","layoffs",
}

POLICY_TERMS = {
    "regulation","regulator","regulatory","antitrust","lawsuit","court",
    "government","ban","law","policy","compliance","sanctions","tariff",
    "export controls","privacy","copyright","commission",
}

BUSINESS_POLICY_SOURCES = {"Reuters", "Financial Times"}


def clean_html(text):
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_date(entry):
    for value in [entry.get("published"), entry.get("updated"), entry.get("created")]:
        if not value:
            continue
        try:
            dt = dateparser.parse(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            pass
    return None


def contains_term(text, term):
    text = text.lower()
    term = term.lower()

    # Para expresiones simples, usamos límites de palabra para reducir falsos positivos.
    stripped = term.strip()
    if re.fullmatch(r"[a-z0-9áéíóúüñ.\-]+", stripped):
        pattern = r"(?<!\w)" + re.escape(stripped) + r"(?!\w)"
        return bool(re.search(pattern, text))

    return term in f" {text} " or stripped in text


def phrase_score(text, terms, cap=5):
    hits = sum(1 for term in terms if contains_term(text, term))
    return min(hits / cap, 1.0)


def classify_segments(text):
    scores = {}
    for segment, terms in SEGMENT_RULES.items():
        score = sum(1 for term in terms if contains_term(text, term))
        if score:
            scores[segment] = score

    if not scores:
        return "IT Strategy & Digital Transformation", []

    ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    primary = ordered[0][0]

    # Hasta dos segmentos relacionados adicionales.
    related = [
        segment for segment, score in ordered[1:3]
        if score >= max(1, ordered[0][1] - 2)
    ]

    return primary, related


def classify_geo(text, region_hint=None):
    matches = {}

    for subregion, terms in GEO_RULES.items():
        hits = sum(1 for term in terms if contains_term(text, term))
        if hits:
            matches[subregion] = hits

    if matches:
        ranked = sorted(matches.items(), key=lambda x: x[1], reverse=True)
        top_subregion, top_score = ranked[0]

        regions_detected = {
            SUBREGION_TO_REGION.get(subregion)
            for subregion, score in ranked
            if score >= max(1, top_score - 1)
        }
        regions_detected.discard(None)

        # Si el artículo claramente toca varias macroregiones, se considera global.
        if len(regions_detected) >= 2:
            return "Global", "Multirregional"

        region = SUBREGION_TO_REGION.get(top_subregion, "Global")
        return region, top_subregion

    # Si el titular no menciona geografía pero fue descubierto por un radar
    # regional, usamos la pista del radar.
    if region_hint:
        return region_hint

    return "Global", "Global"


def tokens(title):
    words = re.findall(r"[a-z0-9áéíóúüñ][a-z0-9áéíóúüñ\-]+", title.lower())
    return {w for w in words if len(w) > 2 and w not in STOPWORDS}


def similarity(a, b):
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    jaccard = len(ta & tb) / len(ta | tb)
    seq = SequenceMatcher(None, a.lower(), b.lower()).ratio()
    return max(jaccard, seq * 0.62)


@st.cache_data(ttl=1800, show_spinner=False)
def load_feed(feed_name, url, region_hint=None):
    headers = {"User-Agent": "Mozilla/5.0 (compatible; TechWeek5/3.0)"}
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    parsed = feedparser.parse(response.content)

    items = []
    for entry in parsed.entries[:80]:
        title = clean_html(entry.get("title", ""))
        link = entry.get("link", "")
        summary = clean_html(entry.get("summary", "") or entry.get("description", ""))
        dt = parse_date(entry)

        if not title or not link or not dt:
            continue

        # Google News suele incluir el publisher real dentro de entry.source.
        publisher = None
        try:
            publisher = clean_html(entry.get("source", {}).get("title", ""))
        except Exception:
            publisher = None

        source = publisher or feed_name

        # En resultados de Google News el título puede terminar en " - Publisher".
        if publisher and title.endswith(f" - {publisher}"):
            title = title[:-(len(publisher) + 3)].strip()

        text_for_classification = f"{title} {summary}"
        segment, related_segments = classify_segments(text_for_classification)
        region, subregion = classify_geo(text_for_classification, region_hint)

        items.append({
            "title": title,
            "link": link,
            "summary": summary,
            "published": dt,
            "source": source,
            "feed_name": feed_name,
            "segment": segment,
            "related_segments": related_segments,
            "region": region,
            "subregion": subregion,
        })

    return items


def collect_articles(selected_sources, use_regional_radars=True):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=7)
    all_items = []
    errors = []

    configs = {
        name: BASE_SOURCES[name]
        for name in selected_sources
        if name in BASE_SOURCES
    }

    if use_regional_radars:
        configs.update(REGIONAL_RADARS)

    for name, cfg in configs.items():
        try:
            all_items.extend(
                load_feed(name, cfg["url"], cfg.get("region_hint"))
            )
        except Exception:
            errors.append(name)

    recent = [
        item for item in all_items
        if cutoff <= item["published"] <= now + timedelta(hours=6)
    ]

    # Dedupe de títulos casi idénticos.
    seen = set()
    deduped = []
    for item in sorted(recent, key=lambda x: x["published"], reverse=True):
        key = re.sub(r"\W+", "", item["title"].lower())[:180]
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    return deduped, errors


def cluster_articles(articles):
    clusters = []

    for article in sorted(articles, key=lambda x: x["published"], reverse=True):
        best_idx = None
        best_sim = 0.0

        for i, cluster in enumerate(clusters):
            sim = max(
                similarity(article["title"], x["title"])
                for x in cluster[:4]
            )
            if sim > best_sim:
                best_sim = sim
                best_idx = i

        if best_idx is not None and best_sim >= 0.30:
            clusters[best_idx].append(article)
        else:
            clusters.append([article])

    return clusters


def score_cluster(cluster):
    now = datetime.now(timezone.utc)
    sources = {a["source"] for a in cluster}
    unique_sources = len(sources)
    newest = max(a["published"] for a in cluster)
    age_days = max(0.0, (now - newest).total_seconds() / 86400)

    text = " ".join(
        a["title"] + " " + a.get("summary", "")[:250]
        for a in cluster
    )

    coverage = min(unique_sources / 5, 1.0)
    business = phrase_score(text, BUSINESS_TERMS, 4)
    tech = phrase_score(text, TECH_TERMS, 4)
    policy = phrase_score(text, POLICY_TERMS, 3)
    recency = max(0.0, 1.0 - age_days / 7.0)
    trend = min(len(cluster) / 5, 1.0)

    if sources & BUSINESS_POLICY_SOURCES:
        business = min(1.0, business + 0.12)

    total = (
        coverage * 0.35
        + business * 0.25
        + tech * 0.15
        + policy * 0.10
        + recency * 0.10
        + trend * 0.05
    )

    breakdown = {
        "Cobertura": round(coverage * 100),
        "Negocio": round(business * 100),
        "Tecnología": round(tech * 100),
        "Regulación": round(policy * 100),
        "Recencia": round(recency * 100),
        "Tendencia": round(trend * 100),
    }

    return round(total * 100), breakdown


def choose_cluster_metadata(cluster):
    # Segmento predominante dentro del cluster.
    segment_counts = Counter(a["segment"] for a in cluster)
    segment = segment_counts.most_common(1)[0][0]

    # Geografía: damos prioridad a clasificación concreta frente a Global.
    concrete = [a for a in cluster if a["region"] != "Global"]
    geo_pool = concrete if concrete else cluster

    region_counts = Counter(a["region"] for a in geo_pool)
    region = region_counts.most_common(1)[0][0]

    subregion_counts = Counter(a["subregion"] for a in geo_pool)
    subregion = subregion_counts.most_common(1)[0][0]

    related = []
    for article in cluster:
        for seg in article["related_segments"]:
            if seg != segment and seg not in related:
                related.append(seg)

    return segment, related[:2], region, subregion


def explain_story(segment, source_count, score):
    explanations = {
        "IA, Automatización & Observabilidad":
            "La historia puede cambiar cómo las empresas automatizan, observan y optimizan sus entornos tecnológicos.",
        "Cloud, Data Center & FinOps":
            "Puede impactar arquitectura cloud, capacidad de centros de datos, costes o decisiones de infraestructura.",
        "Networking & Connectivity":
            "Puede modificar conectividad, redes empresariales, telecomunicaciones o el rendimiento de infraestructuras distribuidas.",
        "Cybersecurity & Compliance":
            "Puede afectar riesgo, cumplimiento, protección de datos y resiliencia de las organizaciones.",
        "Digital Workplace, Apps & DevOps":
            "Puede cambiar la forma de desarrollar aplicaciones, colaborar y operar entornos digitales de trabajo.",
        "Managed Services & IT Operations":
            "Puede influir en monitorización, continuidad, operación proactiva y eficiencia de los equipos de TI.",
        "IT Strategy & Digital Transformation":
            "Puede afectar decisiones de inversión, modernización y estrategia tecnológica empresarial.",
        "IT Support & Service Delivery":
            "Puede cambiar modelos de soporte, implementación, integración o entrega de servicios tecnológicos.",
    }

    coverage = (
        f"La detectamos en {source_count} fuentes distintas."
        if source_count > 1
        else "Por ahora aparece principalmente en una fuente del radar."
    )

    return f"{explanations.get(segment, '')} {coverage}"


def build_ranked_stories(articles):
    clusters = cluster_articles(articles)
    ranked = []

    for cluster in clusters:
        score, breakdown = score_cluster(cluster)
        representative = sorted(
            cluster,
            key=lambda x: x["published"],
            reverse=True
        )[0]

        segment, related, region, subregion = choose_cluster_metadata(cluster)
        sources = sorted({a["source"] for a in cluster})

        ranked.append({
            **representative,
            "segment": segment,
            "related_segments": related,
            "region": region,
            "subregion": subregion,
            "sources": sources,
            "source_count": len(sources),
            "cluster_size": len(cluster),
            "score": score,
            "breakdown": breakdown,
            "why": explain_story(segment, len(sources), score),
        })

    return sorted(ranked, key=lambda x: x["score"], reverse=True)


def filter_stories(stories, segment_filter, region_filter, market_filter):
    filtered = stories

    if segment_filter != "Todos":
        filtered = [
            x for x in filtered
            if x["segment"] == segment_filter
            or segment_filter in x["related_segments"]
        ]

    if region_filter != "Todas":
        filtered = [x for x in filtered if x["region"] == region_filter]

    if market_filter != "Todos":
        filtered = [x for x in filtered if x["subregion"] == market_filter]

    return filtered


def diverse_top_five(stories):
    results = []
    segment_counts = Counter()

    for item in stories:
        if segment_counts[item["segment"]] >= 2:
            continue
        results.append(item)
        segment_counts[item["segment"]] += 1
        if len(results) == 5:
            return results

    # Completar si el límite de diversidad deja huecos.
    used = {x["link"] for x in results}
    for item in stories:
        if item["link"] not in used:
            results.append(item)
            used.add(item["link"])
        if len(results) == 5:
            break

    return results


# ============================================================
# 5. UI
# ============================================================

st.markdown("""
<style>
.block-container {
    max-width: 1180px;
    padding-top: 2.2rem;
    padding-bottom: 4rem;
}
.eyebrow {
    font-size: .76rem;
    letter-spacing: .15em;
    text-transform: uppercase;
    opacity: .58;
    font-weight: 800;
}
.hero-title {
    font-size: 3.8rem;
    line-height: .98;
    font-weight: 900;
    letter-spacing: -.06em;
    margin: .25rem 0 .9rem 0;
}
.hero-copy {
    font-size: 1.08rem;
    line-height: 1.55;
    opacity: .76;
    max-width: 780px;
    margin-bottom: 1.5rem;
}
.news-card {
    border: 1px solid rgba(128,128,128,.22);
    border-radius: 20px;
    padding: 1.3rem 1.35rem 1.15rem 1.35rem;
    margin: 0 0 1rem 0;
}
.rank {
    font-size: .76rem;
    font-weight: 850;
    opacity: .58;
    letter-spacing: .09em;
    text-transform: uppercase;
}
.score {
    float: right;
    font-size: .79rem;
    font-weight: 850;
    opacity: .75;
}
.news-title {
    font-size: 1.42rem;
    line-height: 1.23;
    font-weight: 790;
    letter-spacing: -.018em;
    margin: .42rem 0 .5rem 0;
}
.meta {
    font-size: .84rem;
    opacity: .63;
    margin-bottom: .65rem;
}
.why {
    font-size: .96rem;
    line-height: 1.55;
    opacity: .88;
}
.badge {
    display: inline-block;
    border: 1px solid rgba(128,128,128,.30);
    border-radius: 999px;
    padding: .2rem .58rem;
    font-size: .74rem;
    font-weight: 720;
    margin-right: .34rem;
    margin-bottom: .55rem;
}
.badge-priority {
    display: inline-block;
    border: 1px solid rgba(128,128,128,.55);
    border-radius: 999px;
    padding: .2rem .58rem;
    font-size: .74rem;
    font-weight: 850;
    margin-right: .34rem;
    margin-bottom: .55rem;
}
.method {
    border: 1px solid rgba(128,128,128,.18);
    border-radius: 16px;
    padding: .95rem 1rem;
    margin: .6rem 0 1.4rem 0;
    font-size: .88rem;
    opacity: .74;
}
.section-title {
    font-size: 1.55rem;
    font-weight: 820;
    letter-spacing: -.025em;
    margin: 1.2rem 0 .35rem 0;
}
.section-copy {
    opacity: .68;
    margin-bottom: 1rem;
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="eyebrow">Radar editorial · tecnología empresarial global</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-title">Tech Week 5</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="hero-copy">Cinco historias para entender qué está moviendo la tecnología, '
    'clasificadas por área tecnológica y por mercado.</div>',
    unsafe_allow_html=True
)

with st.sidebar:
    st.header("Configurar radar")

    selected_sources = st.multiselect(
        "Fuentes editoriales base",
        list(BASE_SOURCES.keys()),
        default=list(BASE_SOURCES.keys()),
    )

    use_regional_radars = st.checkbox(
        "Incluir radares regionales",
        value=True,
        help="Añade búsquedas específicas para España, Europa, Norteamérica, Pakistán, Dubai/UAE, Egipto y MEA.",
    )

    st.divider()
    st.subheader("Filtrar noticias")

    segment_filter = st.selectbox(
        "Segmento tecnológico",
        ["Todos"] + SEGMENT_ORDER,
    )

    region_filter = st.selectbox(
        "Región",
        [
            "Todas",
            "Global",
            "Norteamérica",
            "Europa",
            "Medio Oriente / MEA + Pakistán",
        ],
    )

    market_options = ["Todos"]
    if region_filter == "Europa":
        market_options += ["España", "Resto de Europa"]
    elif region_filter == "Norteamérica":
        market_options += ["Estados Unidos", "Canadá", "México", "Norteamérica"]
    elif region_filter == "Medio Oriente / MEA + Pakistán":
        market_options += ["Pakistán", "Dubai / UAE", "Egipto", "Resto de MEA"]
    else:
        market_options += [
            "España", "Estados Unidos", "Canadá", "México",
            "Pakistán", "Dubai / UAE", "Egipto",
            "Resto de Europa", "Resto de MEA",
        ]

    market_filter = st.selectbox(
        "Mercado / subregión",
        market_options,
    )

    if st.button("Actualizar radar", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

if not selected_sources:
    st.warning("Selecciona al menos una fuente editorial.")
    st.stop()

with st.spinner("Analizando medios, mercados y segmentos…"):
    articles, errors = collect_articles(
        selected_sources,
        use_regional_radars=use_regional_radars
    )
    all_stories = build_ranked_stories(articles)
    filtered_stories = filter_stories(
        all_stories,
        segment_filter,
        region_filter,
        market_filter
    )
    picks = diverse_top_five(filtered_stories)

# Resumen del radar
col1, col2, col3, col4 = st.columns(4)
col1.metric("Artículos analizados", len(articles))
col2.metric("Historias detectadas", len(all_stories))
col3.metric("Segmentos", len({x["segment"] for x in all_stories}))
col4.metric(
    "Mercados prioritarios",
    sum(1 for x in all_stories if x["subregion"] in PRIORITY_MARKETS)
)

if errors:
    with st.expander("Fuentes o radares que no respondieron"):
        st.write(", ".join(errors))

filter_description = []
if segment_filter != "Todos":
    filter_description.append(segment_filter)
if region_filter != "Todas":
    filter_description.append(region_filter)
if market_filter != "Todos":
    filter_description.append(market_filter)

active_scope = " · ".join(filter_description) if filter_description else "Radar completo"

st.markdown(
    f'<div class="section-title">Top 5 · {html.escape(active_scope)}</div>',
    unsafe_allow_html=True
)
st.markdown(
    '<div class="section-copy">El ranking se recalcula automáticamente según los filtros seleccionados.</div>',
    unsafe_allow_html=True
)

if not picks:
    st.warning(
        "No encontré noticias que coincidan con estos filtros durante los últimos 7 días. "
        "Prueba ampliando región, mercado o segmento."
    )

for i, item in enumerate(picks, 1):
    local_date = item["published"].astimezone().strftime("%d %b %Y")
    source_line = " · ".join(item["sources"])

    with st.container(border=True):
        st.caption(f"#{i} · {item['segment'].upper()}")
        st.markdown(f"### {item['title']}")
        st.caption(f"{source_line} · {local_date}")

        geo_line = f"📍 {item['region']} · {item['subregion']}"
        if item["subregion"] in PRIORITY_MARKETS:
            geo_line += f" · ★ Mercado prioritario"
        geo_line += f" · {item['source_count']} fuente{'s' if item['source_count'] != 1 else ''}"
        st.caption(geo_line)

        st.markdown(f"**Por qué importa:** {item['why']}")

        if item["related_segments"]:
            st.caption(
                "También relacionada con: " + " · ".join(item["related_segments"])
            )

        if item["summary"]:
            with st.expander("Contexto"):
                st.write(item["summary"][:800])

        st.link_button(
            "Leer noticia original ↗",
            item["link"],
            use_container_width=True
        )

# Panorama por segmentos
st.divider()
st.markdown(
    '<div class="section-title">Panorama del radar</div>',
    unsafe_allow_html=True
)
st.markdown(
    '<div class="section-copy">Cuántas historias detectamos esta semana por segmento tecnológico.</div>',
    unsafe_allow_html=True
)

segment_counts = Counter(x["segment"] for x in all_stories)
for segment in SEGMENT_ORDER:
    count = segment_counts.get(segment, 0)
    st.write(f"**{segment}:** {count}")

st.divider()
st.caption(
    "Clasificación automática basada en lenguaje del titular y contexto RSS. "
    "Las regiones 'MEA + Pakistán' responden a una lógica editorial/comercial del radar, "
    "no a una clasificación geográfica estricta."
)

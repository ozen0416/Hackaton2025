# ======================================================
# DASHBOARD STREAMLIT : ANALYSE DES FERMETURES D’ENTREPRISES
# ======================================================

import streamlit as st
import pandas as pd
import plotly.express as px

# ⚙️ Configuration de la page (doit être la première commande Streamlit)
st.set_page_config(page_title="Fermetures des entreprises", layout="wide")

# ========================
# 1. Chargement des données
# ========================

@st.cache_data
def load_data():
    df = pd.read_csv("data.csv")  # Remplace par ton dataset réel
    df["Survie_24m"] = (df["etatAdministratifUniteLegale"] != "C").astype(int)
    return df

df = load_data()

# ========================
# 2. Barre latérale (filtres)
# ========================

st.sidebar.title("🔍 Filtres")
categories = sorted(df["categorieEntreprise"].dropna().unique())
sectors = sorted(df["activitePrincipaleUniteLegale"].dropna().unique())

selected_categories = st.sidebar.multiselect("Catégorie d’entreprise", categories, default=categories)
selected_sectors = st.sidebar.multiselect("Secteur d’activité (code NAF)", sectors[:10])
min_age, max_age = st.sidebar.slider("Ancienneté (années)", int(df["anciennete"].min()), int(df["anciennete"].max()), (0, 100))

filtered_df = df[
    (df["categorieEntreprise"].isin(selected_categories)) &
    (df["anciennete"].between(min_age, max_age))
]
if selected_sectors:
    filtered_df = filtered_df[filtered_df["activitePrincipaleUniteLegale"].isin(selected_sectors)]

# ========================
# 3. En-tête
# ========================

st.title("📊 Analyse des fermetures d’entreprises (2020–2022)")
st.markdown("Cette section explore la dynamique des **fermetures d’entreprises françaises** pendant la période du **Plan France Relance**.")

st.divider()

# ========================
# 4. KPI globaux
# ========================

col1, col2, col3 = st.columns(3)

nb_total = filtered_df["siren"].nunique()
nb_fermees = filtered_df.loc[filtered_df["etatAdministratifUniteLegale"] == "C", "siren"].nunique()
taux_fermeture = (nb_fermees / nb_total * 100) if nb_total > 0 else 0

col1.metric("🏢 Entreprises analysées", f"{nb_total:,}")
col2.metric("⚰️ Entreprises fermées", f"{nb_fermees:,}")
col3.metric("📉 Taux global de fermeture", f"{taux_fermeture:.2f} %")

st.divider()

# ========================
# 5. Fermetures par catégorie (Camembert)
# ========================

st.subheader("🥧 Répartition des fermetures par catégorie d’entreprise")

fermetures_cat = (
    filtered_df[filtered_df["etatAdministratifUniteLegale"] == "C"]
    .groupby("categorieEntreprise")["siren"]
    .nunique()
    .reset_index(name="nb_fermees")
)
fermetures_cat["part"] = fermetures_cat["nb_fermees"] / fermetures_cat["nb_fermees"].sum() * 100

fig_pie = px.pie(
    fermetures_cat,
    values="nb_fermees",
    names="categorieEntreprise",
    color_discrete_sequence=px.colors.qualitative.Safe,
    hole=0.4,
)
fig_pie.update_traces(textinfo="percent+label")
st.plotly_chart(fig_pie, use_container_width=True)

st.markdown("> 💬 *Ce graphique illustre la contribution de chaque catégorie d’entreprise au total des fermetures observées.*")

st.divider()

# ========================
# 6. Secteurs les plus touchés
# ========================

st.subheader("🏭 Secteurs les plus touchés par les fermetures")

fermetures_secteur = (
    filtered_df.groupby("activitePrincipaleUniteLegale")
    .agg(
        nb_total=("siren", "nunique"),
        nb_fermees=("etatAdministratifUniteLegale", lambda x: (x == "C").sum())
    )
    .reset_index()
)
fermetures_secteur["taux_fermeture"] = fermetures_secteur["nb_fermees"] / fermetures_secteur["nb_total"] * 100
top_secteurs = fermetures_secteur.sort_values("taux_fermeture", ascending=False).head(10)

fig_secteurs = px.bar(
    top_secteurs,
    x="activitePrincipaleUniteLegale",
    y="taux_fermeture",
    text="taux_fermeture",
    labels={"activitePrincipaleUniteLegale": "Secteur (code NAF)", "taux_fermeture": "Taux de fermeture (%)"},
    color="taux_fermeture",
    color_continuous_scale="Reds",
)
fig_secteurs.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
st.plotly_chart(fig_secteurs, use_container_width=True)

st.markdown("> 💡 *Cette analyse permet d’identifier les secteurs économiques les plus fragilisés par la crise.*")

st.divider()

# ========================
# 📉 Taux de fermeture par année (NOUVEAU)
# ========================

st.subheader("📉 Taux de fermeture par année")

if "annee" in filtered_df.columns:
    fermetures = (
        filtered_df.groupby(["annee", "etatAdministratifUniteLegale"])
        .size()
        .reset_index(name="count")
    )
    fermetures_total = fermetures.groupby("annee")["count"].sum().reset_index(name="total")
    fermetures = pd.merge(fermetures, fermetures_total, on="annee")
    fermetures["taux_fermeture"] = fermetures["count"] / fermetures["total"] * 100
    fermetures = fermetures[fermetures["etatAdministratifUniteLegale"] == "C"]

    fig1 = px.bar(
        fermetures,
        x="annee",
        y="taux_fermeture",
        text="taux_fermeture",
        labels={"annee": "Année", "taux_fermeture": "% de fermetures"},
        color_discrete_sequence=["#e74c3c"]
    )
    fig1.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    st.plotly_chart(fig1, use_container_width=True)
    st.markdown("> 📉 *Ce graphique présente le taux de fermeture d’entreprises pour chaque année.*")
    st.divider()
else:
    st.info("La colonne 'annee' n’existe pas dans le jeu de données.")

# ========================
# 7. Impact de l’ancienneté sur la fermeture
# ========================

st.subheader("⏳ Impact de l’ancienneté sur le taux de fermeture")

fermetures_age = (
    filtered_df.groupby(pd.cut(filtered_df["anciennete"], bins=[0, 5, 10, 20, 30, 50, 100]))
    .agg(
        nb_total=("siren", "nunique"),
        nb_fermees=("etatAdministratifUniteLegale", lambda x: (x == "C").sum())
    )
    .reset_index()
)
# Correction : conversion des intervalles en chaînes
fermetures_age["anciennete"] = fermetures_age["anciennete"].astype(str)
fermetures_age["taux_fermeture"] = fermetures_age["nb_fermees"] / fermetures_age["nb_total"] * 100

fig_age = px.bar(
    fermetures_age,
    x="anciennete",
    y="taux_fermeture",
    text="taux_fermeture",
    labels={"anciennete": "Tranche d’ancienneté (années)", "taux_fermeture": "Taux de fermeture (%)"},
    color="taux_fermeture",
    color_continuous_scale="Purples",
)
fig_age.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
st.plotly_chart(fig_age, use_container_width=True)

st.markdown("> 🧠 *Les jeunes entreprises présentent souvent un risque de fermeture plus élevé, tandis que les structures matures démontrent une meilleure résilience.*")

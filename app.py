# ======================================================
# DASHBOARD STREAMLIT : FERMETURES & SURVIE 24M & AIDES ÉTAT
# ======================================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# --------------------------------------------
# 0) CONFIG STREAMLIT (doit être la 1ère commande)
# --------------------------------------------
st.set_page_config(page_title="Analyse des chances de survie d'une entreprise en fonction des mesures prises par l'État à 24 mois post-covid", layout="wide")

# --------------------------------------------
# 1) CHARGEMENT & PRÉPARATION DES DONNÉES
# --------------------------------------------
@st.cache_data
def load_data(path="data.csv") -> pd.DataFrame:
    df = pd.read_csv(path)

    # Normalisations (sans écraser Survie_24m)
    if "etatAdministratifUniteLegale" in df.columns:
        df["etatAdministratifUniteLegale"] = (
            df["etatAdministratifUniteLegale"].astype(str).str.upper().str.strip()
        )
    if "annee" in df.columns:
        df["annee"] = pd.to_numeric(df["annee"], errors="coerce").astype("Int64")
    if "anciennete" in df.columns:
        df["anciennete"] = pd.to_numeric(df["anciennete"], errors="coerce")
    if "categorieEntreprise" in df.columns:
        df["categorieEntreprise"] = df["categorieEntreprise"].astype(str).str.strip()
    if "trancheEffectifsUniteLegale" in df.columns:
        df["trancheEffectifsUniteLegale"] = df["trancheEffectifsUniteLegale"].astype(str).str.strip()
    if "siren" in df.columns:
        df["siren"] = pd.to_numeric(df["siren"], errors="coerce").astype("Int64")

    # Contrôle cible Survie_24m (existe déjà)
    if "Survie_24m" not in df.columns:
        raise ValueError("La colonne 'Survie_24m' doit exister (0/1).")
    df["Survie_24m"] = pd.to_numeric(df["Survie_24m"], errors="coerce").fillna(0).astype(int).clip(0, 1)

    return df

@st.cache_data
def load_aides_etat(path="df_participationEtat.csv") -> pd.DataFrame:
    dfa = pd.read_csv(path)
    # Renommer pour harmoniser
    rename_map = {
        "Somme de MONTANT_PARTICIPATION_ETAT": "montant_participation_etat",
        "MESURE_LIGHT": "mesure_light",
        "MESURE": "mesure",
    }
    dfa = dfa.rename(columns=rename_map)

    # Nettoyage minimal
    if "montant_participation_etat" not in dfa.columns:
        raise ValueError("La colonne 'Somme de MONTANT_PARTICIPATION_ETAT' doit être présente.")
    dfa["montant_participation_etat"] = pd.to_numeric(
        dfa["montant_participation_etat"], errors="coerce"
    ).fillna(0.0)

    for col in ["categorieEntreprise", "mesure", "mesure_light"]:
        if col in dfa.columns:
            dfa[col] = dfa[col].astype(str).str.strip()

    return dfa

def safe_nunique(s: pd.Series) -> int:
    return s.dropna().nunique()

# Charger
df = load_data("data.csv")
try:
    dfa = load_aides_etat("df_participationEtat.csv")
except Exception as e:
    st.error(f"❌ Chargement des aides de l'État impossible : {e}")
    dfa = pd.DataFrame()

# --------------------------------------------
# 2) EN-TÊTE
# --------------------------------------------
st.title("Analyse des chances de survie d'une entreprise en fonction des mesures prises par l'État à 24 mois post-covid")
st.caption("La survie 24 mois est interprétée **à partir de la cohorte 2020** (variable `Survie_24m` fournie).")

st.divider()

# =====================================================
# === PARTIE 1 — FERMETURES (analyse principale)    ===
# =====================================================
st.header("Partie 1 — Analyse des fermetures d'entreprise")

# KPI
col1, col2, col3 = st.columns(3)
nb_total = safe_nunique(df["siren"]) if "siren" in df.columns else len(df)
nb_fermees = (
    safe_nunique(df.loc[df["etatAdministratifUniteLegale"] == "C", "siren"])
    if "siren" in df.columns else int((df["etatAdministratifUniteLegale"] == "C").sum())
)
tx_ferm_glob = (nb_fermees / nb_total * 100) if nb_total else 0.0

col1.metric("Entreprises analysées", f"{nb_total:,}")
col2.metric("Entreprises fermées", f"{nb_fermees:,}")
col3.metric("Taux global de fermeture", f"{tx_ferm_glob:.2f} %")
st.divider()

# Camembert fermetures / catégorie (toutes années)
st.subheader("Répartition des **fermetures** par **catégorie d’entreprise**")
if {"etatAdministratifUniteLegale", "categorieEntreprise", "siren"}.issubset(df.columns):
    ferm_cat = (
        df.loc[df["etatAdministratifUniteLegale"] == "C"]
          .groupby("categorieEntreprise", dropna=False)["siren"]
          .nunique()
          .reset_index(name="nb_fermees")
          .sort_values("nb_fermees", ascending=False)
    )
    if ferm_cat["nb_fermees"].sum() == 0:
        st.info("Aucune entreprise marquée 'C' (cessée).")
    else:
        fig_pie_ferm = px.pie(
            ferm_cat,
            values="nb_fermees", names="categorieEntreprise",
            color_discrete_sequence=px.colors.qualitative.Safe, hole=0.45
        )
        fig_pie_ferm.update_traces(textinfo="percent+label")
        st.plotly_chart(fig_pie_ferm, use_container_width=True)
        st.caption("Contribution de chaque catégorie au total des cessations.")
else:
    st.warning("Colonnes manquantes pour ce graphique.")

st.divider()

# Taux de fermeture par année
st.subheader("Taux de **fermeture** par **année**")
if {"annee", "etatAdministratifUniteLegale"}.issubset(df.columns) and df["annee"].notna().any():
    ferm = df.groupby(["annee", "etatAdministratifUniteLegale"]).size().reset_index(name="count")
    totaux = ferm.groupby("annee")["count"].sum().reset_index(name="total")
    ferm = ferm.merge(totaux, on="annee", how="left")
    ferm["taux_fermeture"] = np.where(ferm["total"] > 0, 100 * ferm["count"] / ferm["total"], np.nan)
    ferm = ferm[ferm["etatAdministratifUniteLegale"] == "C"].sort_values("annee")

    fig_year_ferm = px.bar(
        ferm, x="annee", y="taux_fermeture", text="taux_fermeture",
        labels={"annee": "Année", "taux_fermeture": "% de fermetures"},
        color_discrete_sequence=["#e74c3c"]
    )
    fig_year_ferm.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    st.plotly_chart(fig_year_ferm, use_container_width=True)
else:
    st.info("La colonne 'annee' est absente ou vide — section ignorée.")

st.divider()

# Ancienneté × fermeture
st.subheader("Impact de **l’ancienneté** sur le **taux de fermeture**")
if "anciennete" in df.columns and df["anciennete"].notna().any():
    bins_age = [0, 5, 10, 20, 30, 50, 100, np.inf]
    labels_age = ["0–5", "5–10", "10–20", "20–30", "30–50", "50–100", "100+"]
    age_bin = pd.cut(df["anciennete"], bins=bins_age, labels=labels_age, include_lowest=True, right=False)

    ferm_age = (
        pd.DataFrame({"age_bin": age_bin, "etat": df["etatAdministratifUniteLegale"], "siren": df["siren"]})
          .groupby("age_bin", dropna=False)
          .agg(nb_total=("siren", lambda s: s.dropna().nunique()),
               nb_fermees=("etat", lambda x: (x == "C").sum()))
          .reset_index()
    )
    ferm_age["taux_fermeture"] = np.where(ferm_age["nb_total"] > 0, 100 * ferm_age["nb_fermees"] / ferm_age["nb_total"], np.nan)

    fig_age_ferm = px.bar(
        ferm_age, x="age_bin", y="taux_fermeture", text="taux_fermeture",
        labels={"age_bin": "Tranche d’ancienneté (années)", "taux_fermeture": "Taux de fermeture (%)"},
        color="taux_fermeture", color_continuous_scale="Purples"
    )
    fig_age_ferm.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    st.plotly_chart(fig_age_ferm, use_container_width=True)
else:
    st.info("Ancienneté absente ou vide — section ignorée.")

st.divider()

# Effectifs × fermeture (hors NN & 00)
st.subheader("Taux de **fermeture** par **tranche d’effectif salarié**")
if "trancheEffectifsUniteLegale" in df.columns:
    df_eff = df.loc[~df["trancheEffectifsUniteLegale"].isin(["NN", "00"])].copy()
    tr_map = {
        "01": "1–2", "02": "3–5", "03": "6–9",
        "11": "10–19", "12": "20–49", "21": "50–99", "22": "100–199",
        "31": "200–249", "32": "250–499", "41": "500–999",
        "42": "1 000–1 999", "51": "2 000–4 999", "52": "5 000–9 999", "53": "10 000+",
    }
    order_tr = ["1–2", "3–5", "6–9", "10–19", "20–49", "50–99", "100–199",
                "200–249", "250–499", "500–999", "1 000–1 999", "2 000–4 999", "5 000–9 999", "10 000+"]

    df_eff["trancheEffectifs_label"] = df_eff["trancheEffectifsUniteLegale"].map(tr_map).fillna("Autre/NA")
    ferm_eff = (
        df_eff.groupby("trancheEffectifs_label", dropna=False)
              .agg(nb_total=("siren", lambda s: s.dropna().nunique()),
                   nb_fermees=("etatAdministratifUniteLegale", lambda x: (x == "C").sum()))
              .reset_index()
    )
    ferm_eff["taux_fermeture"] = np.where(ferm_eff["nb_total"] > 0, 100 * ferm_eff["nb_fermees"] / ferm_eff["nb_total"], np.nan)
    ferm_eff["trancheEffectifs_label"] = pd.Categorical(ferm_eff["trancheEffectifs_label"], categories=order_tr + ["Autre/NA"], ordered=True)
    ferm_eff = ferm_eff.sort_values("trancheEffectifs_label")

    fig_eff_ferm = px.bar(
        ferm_eff, x="trancheEffectifs_label", y="taux_fermeture", text="taux_fermeture",
        labels={"trancheEffectifs_label": "Tranche d'effectif", "taux_fermeture": "Taux de fermeture (%)"},
        color="taux_fermeture", color_continuous_scale="Blues"
    )
    fig_eff_ferm.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    fig_eff_ferm.update_layout(xaxis_tickangle=-35)
    st.plotly_chart(fig_eff_ferm, use_container_width=True)
else:
    st.info("La colonne 'trancheEffectifsUniteLegale' est absente — section ignorée.")

st.divider()

# =====================================================
# === PARTIE 2 — SURVIE 24 MOIS (COHORTE 2020)     ===
# =====================================================
st.header("Partie 2 — Analyse des chances de survie à 24 mois des entreprises")

needed_cols = {"siren", "annee", "Survie_24m"}
if not needed_cols.issubset(df.columns):
    st.warning("Colonnes requises manquantes : 'siren', 'annee', 'Survie_24m'.")
else:
    cohort = (
        df.loc[df["annee"] == 2020]
          .sort_values(["siren"])
          .drop_duplicates(subset=["siren"])
          .copy()
    )
    nb_cohorte = cohort["siren"].dropna().nunique()

    if nb_cohorte == 0:
        st.info("Aucune entreprise observée en 2020 — cohorte vide.")
    else:
        cohort["Survie_24m"] = pd.to_numeric(cohort["Survie_24m"], errors="coerce").fillna(0).astype(int).clip(0, 1)

        # KPI
        c1, c2, c3 = st.columns(3)
        taux_survie_global = cohort["Survie_24m"].mean() * 100
        nb_survivantes = int(cohort["Survie_24m"].sum())
        nb_non_survivantes = int((cohort["Survie_24m"] == 0).sum())
        c1.metric("Cohorte 2020 (entreprises)", f"{nb_cohorte:,}")
        c2.metric("Survivantes à 24 mois", f"{nb_survivantes:,}")
        c3.metric("Taux de survie (24m)", f"{taux_survie_global:.2f} %")
        st.caption("Les profils analysés (catégorie, ancienneté, effectifs) sont ceux **observés en 2020**.")
        st.divider()

        # Camembert — survivantes par catégorie (2020)
        st.subheader("Répartition des **survivantes (24m)** par **catégorie d’entreprise**")
        if "categorieEntreprise" in cohort.columns:
            surv_cat_counts = (
                cohort.loc[cohort["Survie_24m"] == 1]
                      .groupby("categorieEntreprise", dropna=False)["siren"]
                      .nunique()
                      .reset_index(name="nb_survivantes")
                      .sort_values("nb_survivantes", ascending=False)
            )
            if surv_cat_counts["nb_survivantes"].sum() == 0:
                st.info("Aucune entreprise survivante dans la cohorte 2020.")
            else:
                fig_pie_surv = px.pie(
                    surv_cat_counts,
                    values="nb_survivantes", names="categorieEntreprise",
                    color_discrete_sequence=px.colors.qualitative.Prism, hole=0.45
                )
                fig_pie_surv.update_traces(textinfo="percent+label")
                st.plotly_chart(fig_pie_surv, use_container_width=True)
        else:
            st.info("Catégorie d’entreprise (2020) indisponible.")

        st.divider()

        # Taux de survie par catégorie (2020)
        st.subheader("Taux de **survie** par **catégorie d’entreprise**")
        if "categorieEntreprise" in cohort.columns:
            survie_par_cat = (
                cohort.groupby("categorieEntreprise")["Survie_24m"]
                      .mean().mul(100).reset_index()
                      .sort_values("Survie_24m", ascending=False)
            )
            fig_surv_cat = px.bar(
                survie_par_cat,
                x="categorieEntreprise", y="Survie_24m", text="Survie_24m",
                labels={"categorieEntreprise": "Catégorie", "Survie_24m": "Taux de survie (%)"},
                color="Survie_24m", color_continuous_scale="Teal"
            )
            fig_surv_cat.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            st.plotly_chart(fig_surv_cat, use_container_width=True)
        else:
            st.info("Catégorie d’entreprise (2020) indisponible.")

        st.divider()

        # Ancienneté × survie (2020)
        st.subheader("**Ancienneté (2020)** × **Survie (24m)**")
        if "anciennete" in cohort.columns and cohort["anciennete"].notna().any():
            bins_age = [0, 5, 10, 20, 30, 50, 100, np.inf]
            labels_age = ["0–5", "5–10", "10–20", "20–30", "30–50", "50–100", "100+"]
            cohort["age_bin"] = pd.cut(cohort["anciennete"], bins=bins_age, labels=labels_age, include_lowest=True, right=False)

            surv_age = (
                cohort.groupby("age_bin")
                      .agg(nb_total=("siren", lambda s: s.dropna().nunique()),
                           taux_survie=("Survie_24m", lambda s: float(s.mean() * 100) if len(s) else np.nan))
                      .reset_index()
            )
            fig_age_surv = px.bar(
                surv_age,
                x="age_bin", y="taux_survie", text="taux_survie",
                labels={"age_bin": "Tranche d’ancienneté (années)", "taux_survie": "Taux de survie (%)"},
                color="taux_survie", color_continuous_scale="Greens"
            )
            fig_age_surv.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            st.plotly_chart(fig_age_surv, use_container_width=True)
        else:
            st.info("Ancienneté (2020) absente ou vide.")

        st.divider()

        # Effectifs × survie (2020) hors NN & 00
        st.subheader("**Survie (24m)** par **tranche d’effectif (2020)**")
        if "trancheEffectifsUniteLegale" in cohort.columns:
            cohort_eff = cohort.loc[~cohort["trancheEffectifsUniteLegale"].isin(["NN", "00"])].copy()
            tr_map = {
                "01": "1–2", "02": "3–5", "03": "6–9",
                "11": "10–19", "12": "20–49", "21": "50–99", "22": "100–199",
                "31": "200–249", "32": "250–499", "41": "500–999",
                "42": "1 000–1 999", "51": "2 000–4 999", "52": "5 000–9 999", "53": "10 000+",
            }
            order_tr = ["1–2", "3–5", "6–9", "10–19", "20–49", "50–99", "100–199",
                        "200–249", "250–499", "500–999", "1 000–1 999", "2 000–4 999", "5 000–9 999", "10 000+"]

            cohort_eff["trancheEffectifs_label"] = cohort_eff["trancheEffectifsUniteLegale"].map(tr_map).fillna("Autre/NA")
            surv_eff = (
                cohort_eff.groupby("trancheEffectifs_label", dropna=False)
                          .agg(nb_total=("siren", lambda s: s.dropna().nunique()),
                               taux_survie=("Survie_24m", lambda s: float(s.mean() * 100) if len(s) else np.nan))
                          .reset_index()
            )
            surv_eff["trancheEffectifs_label"] = pd.Categorical(surv_eff["trancheEffectifs_label"], categories=order_tr + ["Autre/NA"], ordered=True)
            surv_eff = surv_eff.sort_values("trancheEffectifs_label")

            fig_eff_surv = px.bar(
                surv_eff, x="trancheEffectifs_label", y="taux_survie", text="taux_survie",
                labels={"trancheEffectifs_label": "Tranche d'effectif (2020)", "taux_survie": "Taux de survie (%)"},
                color="taux_survie", color_continuous_scale="Tealgrn"
            )
            fig_eff_surv.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig_eff_surv.update_layout(xaxis_tickangle=-35)
            st.plotly_chart(fig_eff_surv, use_container_width=True)
        else:
            st.info("Tranche d’effectif (2020) absente.")

st.divider()

# =====================================================
# === PARTIE 3 — Aides de l'État (focus) & lien survie
# =====================================================
st.header("Partie 3 — Aides de l'État & lien avec la survie des entreprises")

if dfa.empty:
    st.info("Aucune donnée d’aide d’État chargée pour cette section.")
else:
    # KPI : total & concentration (Top-3, Gini) par catégorie
    if "categorieEntreprise" in dfa.columns:
        cat_agg = (
            dfa.groupby("categorieEntreprise", dropna=False)["montant_participation_etat"]
               .sum()
               .reset_index(name="participation_etat")
               .sort_values("participation_etat", ascending=False)
        )
        total_etat = float(cat_agg["participation_etat"].sum())
        top3_share = (100 * cat_agg.head(3)["participation_etat"].sum() / total_etat) if total_etat > 0 else np.nan
        vals = cat_agg["participation_etat"].values.astype(float)
        if vals.sum() > 0 and len(vals) >= 2:
            x = np.sort(vals); n = len(x)
            gini = (2 * np.arange(1, n+1) - n - 1) @ x / (n * x.sum())
        else:
            gini = np.nan

        c1, c2, c3 = st.columns(3)
        c1.metric("Aides de l'État — Total", f"{total_etat:,.0f}".replace(",", " "))
        c2.metric("Part des 3 plus grosses catégories", f"{top3_share:.1f} %" if not np.isnan(top3_share) else "n/d")
        c3.metric("Indice de concentration (Gini)", f"{gini:.2f}" if not np.isnan(gini) else "n/d")
        st.caption("Plus Gini → plus les aides sont concentrées.")
        st.divider()

        # Répartition par catégorie (bar + pie)
        st.subheader("🏢 Répartition des **aides de l'État** par **catégorie d’entreprise**")
        if not cat_agg.empty:
            cat_agg["part_%"] = 100 * cat_agg["participation_etat"] / total_etat if total_etat else 0.0

            fig_cat_bar = px.bar(
                cat_agg, x="categorieEntreprise", y="participation_etat", text="part_%",
                labels={"categorieEntreprise": "Catégorie", "participation_etat": "Participation État (€)"},
                color="participation_etat", color_continuous_scale="Blues"
            )
            fig_cat_bar.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            st.plotly_chart(fig_cat_bar, use_container_width=True)

            fig_cat_pie = px.pie(
                cat_agg, values="participation_etat", names="categorieEntreprise",
                hole=0.45, color_discrete_sequence=px.colors.qualitative.Safe
            )
            fig_cat_pie.update_traces(textinfo="percent+label")
            st.plotly_chart(fig_cat_pie, use_container_width=True)

        else:
            st.info("Aucune agrégation par catégorie.")
    else:
        st.info("'categorieEntreprise' absente dans les aides — KPI par catégorie non calculables.")
    st.divider()

# =====================================================
# === PARTIE 4 — Test simple : Chi² / Fisher
# === Survie 24m vs groupes d'intensité d'aide (catégories)
# =====================================================
st.header("Partie 4 — Test simple : Chi² / Fisher")

# Hypothèses affichées dans le dashboard
st.markdown(
    """
**Hypothèses du test :**  
- **H0 (indépendance)** : le **taux de survie à 24 mois** est **indépendant** du **niveau d’intensité d’aide**.  
  Autrement dit, les proportions de survie sont **identiques** dans tous les groupes d’intensité.  
- **H1 (dépendance)** : le **taux de survie à 24 mois** **diffère** selon le **niveau d’intensité d’aide** (au moins un groupe diffère).
"""
)

# Seuil de décision (α)
alpha = st.selectbox("Seuil de décision (α)", options=[0.01, 0.05, 0.10], index=1)

# Pré-conditions
need_cols = {"siren", "annee", "Survie_24m", "categorieEntreprise"}
if dfa.empty or not need_cols.issubset(df.columns):
    st.info("Données insuffisantes : il faut la table d'aides de l'État et, côté cohorte, 'siren', 'annee', 'Survie_24m', 'categorieEntreprise'.")
else:
    # 5.0 Cohorte 2020 (une ligne par SIREN)
    cohort = (
        df.loc[df["annee"] == 2020, ["siren", "categorieEntreprise", "Survie_24m"]]
          .dropna(subset=["siren"])
          .drop_duplicates(subset=["siren"])
          .copy()
    )
    if cohort.empty:
        st.info("Cohorte 2020 vide — section non calculée.")
    else:
        cohort["categorieEntreprise"] = cohort["categorieEntreprise"].astype(str).str.strip()
        cohort["Survie_24m"] = pd.to_numeric(cohort["Survie_24m"], errors="coerce").fillna(0).astype(int).clip(0, 1)

        # 5.1 Intensité d'aide par entreprise (au niveau catégorie)
        if "categorieEntreprise" not in dfa.columns or "montant_participation_etat" not in dfa.columns:
            st.info("La table d'aides ne contient pas 'categorieEntreprise' et/ou 'montant_participation_etat'.")
        else:
            aides_cat = (
                dfa.groupby("categorieEntreprise", dropna=False)["montant_participation_etat"]
                   .sum()
                   .reset_index(name="participation_etat")
            )
            # Nb d'entreprises par catégorie en 2020
            nb_cat_2020 = cohort.groupby("categorieEntreprise")["siren"].nunique().reset_index(name="nb_2020")

            # Jointure et intensité moyenne par entreprise (catégorie)
            mix = aides_cat.merge(nb_cat_2020, on="categorieEntreprise", how="inner")
            mix["intensite_par_entreprise"] = np.where(
                mix["nb_2020"] > 0, mix["participation_etat"] / mix["nb_2020"], np.nan
            )

            # 🔎 Petite explication de l'intensité (affichée avant le test)
            st.markdown(
                """
**Qu’entend-on par _intensité d’aide_ ?**  
L’**intensité** est le **montant moyen d’aide de l’État par entreprise** dans une **catégorie d’entreprise** (cohorte 2020) :

\\[
\\text{Intensité}_{cat} \= \\frac{\\text{Participation de l’État (€, agrégée) pour la catégorie}}{\\#\\,\\text{d’entreprises observées en 2020 dans cette catégorie}}
\\]

- **Numérateur** : somme des montants de **participation de l’État** pour la *catégorie*.  
- **Dénominateur** : **nombre d’entreprises (SIREN uniques) présentes en 2020** dans cette *catégorie*.  
- **Lecture** : c’est une **moyenne par entreprise** (exprimable en € ou k€ / entreprise).
                """
            )

            # 5.2 Joindre l'intensité à chaque SIREN (via sa catégorie)
            base = cohort.merge(
                mix[["categorieEntreprise", "intensite_par_entreprise"]],
                on="categorieEntreprise", how="left"
            )
            base = base.dropna(subset=["intensite_par_entreprise"]).copy()
            if base.empty:
                st.info("Aucune intensité disponible pour la cohorte 2020 (après jointure).")
            else:
                # 5.3 Création automatique et robuste des groupes d'intensité
                def make_groups_auto(df_base: pd.DataFrame):
                    """
                    Tente un binning par quantiles 4 → 3 → 2.
                    En dernier recours, split binaire par médiane (High vs Low).
                    Retourne df_grouped avec 'groupe_intensite' et une info 'method'.
                    """
                    df = df_base.copy()

                    # Tentatives quantiles
                    for q in [4, 3, 2]:
                        try:
                            df["groupe_intensite"] = pd.qcut(
                                df["intensite_par_entreprise"], q=q, duplicates="drop"
                            )
                            if df["groupe_intensite"].nunique() >= 2:
                                return df, {"method": f"quantiles_{q}"}
                        except Exception:
                            # Fallback sur cut si qcut échoue
                            try:
                                df["groupe_intensite"] = pd.cut(
                                    df["intensite_par_entreprise"], bins=q, include_lowest=True
                                )
                                if df["groupe_intensite"].nunique() >= 2:
                                    return df, {"method": f"cut_{q}"}
                            except Exception:
                                pass

                    # Dernier recours : split médian
                    med = np.nanmedian(df_base["intensite_par_entreprise"])
                    df_base = df_base.copy()
                    df_base["groupe_intensite"] = np.where(
                        df_base["intensite_par_entreprise"] <= med, "Low (≤ médiane)", "High (> médiane)"
                    )
                    if df_base["groupe_intensite"].nunique() >= 2:
                        return df_base, {"method": "median_split"}

                    return df_base, {"method": "failed"}

                grouped, meta = make_groups_auto(base)

                if grouped["groupe_intensite"].nunique() < 2:
                    st.info("Impossible de constituer ≥ 2 groupes d’intensité (valeurs identiques ou trop peu d’observations).")
                else:
                    st.caption(f"Grouping utilisé : **{meta['method']}**.")

                    # 5.4 Table de contingence et taux par groupe
                    tab = pd.crosstab(grouped["groupe_intensite"], grouped["Survie_24m"]).sort_index()
                    surv_by_group = grouped.groupby("groupe_intensite")["Survie_24m"].mean().mul(100).reset_index(name="taux_survie_%")

                    colA, colB = st.columns(2)
                    with colA:
                        st.subheader("Table de contingence (n)")
                        st.dataframe(tab, use_container_width=True)
                    with colB:
                        st.subheader("Taux de survie 24m par groupe")
                        fig_rates = px.bar(
                            surv_by_group, x="groupe_intensite", y="taux_survie_%",
                            text="taux_survie_%",
                            labels={"groupe_intensite": "Groupe d'intensité", "taux_survie_%": "Taux de survie 24m (%)"},
                            color="taux_survie_%", color_continuous_scale="Greens"
                        )
                        fig_rates.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
                        fig_rates.update_layout(xaxis_tickangle=-20)
                        st.plotly_chart(fig_rates, use_container_width=True)

                    # 5.5 Test du Chi² (ou Fisher si 2×2) + décision selon α
                    try:
                        from scipy.stats import chi2_contingency, fisher_exact
                        has_scipy = True
                    except Exception:
                        has_scipy = False

                    st.subheader("Test d’indépendance (Survie × Groupe d’intensité) — Décision")
                    if has_scipy:
                        if tab.shape == (2, 2):
                            # Test exact de Fisher si 2 groupes × 2 issues
                            oddsratio, p_fisher = fisher_exact(tab.values)
                            p_value = float(p_fisher)
                            st.write(f"**Test exact de Fisher** (2×2) — p-value = **{p_value:.4f}** (odds ratio ≈ {oddsratio:.2f})")
                        else:
                            chi2, p, dof, expected = chi2_contingency(tab.values)
                            p_value = float(p)
                            st.write(f"**Chi² = {chi2:.3f}**, **ddl = {dof}**, **p-value = {p_value:.4f}**")
                            with st.expander("Voir les effectifs attendus"):
                                exp_df = pd.DataFrame(expected, index=tab.index, columns=tab.columns)
                                st.dataframe(exp_df.style.format(precision=1), use_container_width=True)

                        # Décision
                        if p_value < float(alpha):
                            st.success(f"**Décision** : p = {p_value:.4f} < α = {alpha} → **Rejet de H0**. "
                                       "Les taux de survie **diffèrent selon le niveau d’intensité d’aide** (dépendance).")
                        else:
                            st.info(f"ℹ**Décision** : p = {p_value:.4f} ≥ α = {alpha} → **Non-rejet de H0**. "
                                    f"Pas d’évidence suffisante que les taux de survie diffèrent selon l’intensité (au seuil {alpha}).")
                    else:
                        st.warning("SciPy n'est pas disponible : installe `scipy` pour exécuter le test du Chi² / Fisher.")

                    st.caption(
                        "⚠️ Rappel : comparaison **agrégée par catégorie** → résultat **descriptif**, non causal. "
                        "Pour inférer un impact, il faut des aides **au niveau SIREN** et un design d’identification (PSM/AIPW, DiD…)."
                    )

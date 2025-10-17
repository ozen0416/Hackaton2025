# ======================================================
# DASHBOARD STREAMLIT : FERMETURES (2020–2024) & SURVIE 24M (COHORTE 2020)
# ======================================================

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# --------------------------------------------
# 0) CONFIG STREAMLIT (doit être la 1ère commande)
# --------------------------------------------
st.set_page_config(page_title="Fermetures & Survie des entreprises", layout="wide")

# --------------------------------------------
# 1) CHARGEMENT & PRÉPARATION DES DONNÉES
# --------------------------------------------
@st.cache_data
def load_data(path="data.csv") -> pd.DataFrame:
    df = pd.read_csv(path)

    # Normalisations douces (ne JAMAIS recréer/écraser 'Survie_24m')
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

    # Contrôle de la cible fournie
    if "Survie_24m" not in df.columns:
        raise ValueError("La colonne 'Survie_24m' doit exister (0/1).")
    df["Survie_24m"] = pd.to_numeric(df["Survie_24m"], errors="coerce").fillna(0).astype(int).clip(0, 1)

    return df

df = load_data()

def safe_nunique(s: pd.Series) -> int:
    return s.dropna().nunique()

# --------------------------------------------
# 2) EN-TÊTE
# --------------------------------------------
st.title("📊 Fermetures d’entreprises (2020–2024) & 💡 Survie à 24 mois (Cohorte 2020)")
st.markdown(
    "Analyse pendant et après le **Plan France Relance**. "
    "Partie 1 : *Fermetures*. Partie 2 : *Survie à 24 mois* calculée **sur la cohorte 2020** "
    "en utilisant la variable `Survie_24m` déjà fournie."
)

st.divider()

# =====================================================
# === PARTIE 1 — FERMETURES (analyse principale)    ===
# =====================================================
st.header("🟥 Partie 1 — Analyse des fermetures")

# 2.1 KPI globaux (fermetures)
col1, col2, col3 = st.columns(3)
nb_total = safe_nunique(df["siren"]) if "siren" in df.columns else len(df)
nb_fermees = (
    safe_nunique(df.loc[df["etatAdministratifUniteLegale"] == "C", "siren"])
    if "siren" in df.columns else int((df["etatAdministratifUniteLegale"] == "C").sum())
)
tx_ferm_glob = (nb_fermees / nb_total * 100) if nb_total else 0.0

col1.metric("🏢 Entreprises analysées", f"{nb_total:,}")
col2.metric("⚰️ Entreprises fermées", f"{nb_fermees:,}")
col3.metric("📉 Taux global de fermeture", f"{tx_ferm_glob:.2f} %")
st.caption("KPI calculés sur l’ensemble du jeu de données chargé.")
st.divider()

# 2.2 Fermetures par catégorie (camembert, toutes années confondues)
st.subheader("🥧 Répartition des **fermetures** par **catégorie d’entreprise**")
if {"etatAdministratifUniteLegale", "categorieEntreprise", "siren"}.issubset(df.columns):
    ferm_cat = (
        df.loc[df["etatAdministratifUniteLegale"] == "C"]
          .groupby("categorieEntreprise", dropna=False)["siren"]
          .nunique()
          .reset_index(name="nb_fermees")
          .sort_values("nb_fermees", ascending=False)
    )
    if ferm_cat["nb_fermees"].sum() == 0:
        st.info("Aucune entreprise marquée 'C' (cessée) — pas de camembert à afficher.")
    else:
        fig_pie_ferm = px.pie(
            ferm_cat,
            values="nb_fermees", names="categorieEntreprise",
            color_discrete_sequence=px.colors.qualitative.Safe,
            hole=0.45
        )
        fig_pie_ferm.update_traces(textinfo="percent+label")
        st.plotly_chart(fig_pie_ferm, use_container_width=True)
        st.caption("Contribution de chaque **catégorie** au total des **cessations**.")
else:
    st.warning("Colonnes manquantes pour le camembert (nécessite : etatAdministratifUniteLegale, categorieEntreprise, siren).")

st.divider()

# 2.3 Taux de fermeture par année (si disponible)
st.subheader("📉 Taux de **fermeture** par **année** (vue globale)")
if {"annee", "etatAdministratifUniteLegale"}.issubset(df.columns) and df["annee"].notna().any():
    ferm = df.groupby(["annee", "etatAdministratifUniteLegale"]).size().reset_index(name="count")
    totaux = ferm.groupby("annee")["count"].sum().reset_index(name="total")
    ferm = ferm.merge(totaux, on="annee", how="left")
    ferm["taux_fermeture"] = np.where(ferm["total"] > 0, 100 * ferm["count"] / ferm["total"], np.nan)
    ferm = ferm[ferm["etatAdministratifUniteLegale"] == "C"].sort_values("annee")

    fig_year_ferm = px.bar(
        ferm,
        x="annee", y="taux_fermeture", text="taux_fermeture",
        labels={"annee": "Année", "taux_fermeture": "% de fermetures"},
        color_discrete_sequence=["#e74c3c"]
    )
    fig_year_ferm.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    st.plotly_chart(fig_year_ferm, use_container_width=True)
else:
    st.info("La colonne 'annee' est absente ou vide — section ignorée.")

st.divider()

# 2.4 Impact de l’ancienneté sur le taux de fermeture
st.subheader("⏳ Impact de **l’ancienneté** sur le **taux de fermeture**")
if "anciennete" in df.columns and df["anciennete"].notna().any():
    bins_age = [0, 5, 10, 20, 30, 50, 100, np.inf]
    labels_age = ["0–5", "5–10", "10–20", "20–30", "30–50", "50–100", "100+"]
    age_bin = pd.cut(df["anciennete"], bins=bins_age, labels=labels_age, include_lowest=True, right=False)

    ferm_age = (
        pd.DataFrame({"age_bin": age_bin, "etat": df["etatAdministratifUniteLegale"], "siren": df["siren"]})
          .groupby("age_bin", dropna=False)
          .agg(
              nb_total=("siren", lambda s: s.dropna().nunique()),
              nb_fermees=("etat", lambda x: (x == "C").sum()),
          )
          .reset_index()
    )
    ferm_age["taux_fermeture"] = np.where(
        ferm_age["nb_total"] > 0, 100 * ferm_age["nb_fermees"] / ferm_age["nb_total"], np.nan
    )

    fig_age_ferm = px.bar(
        ferm_age,
        x="age_bin", y="taux_fermeture", text="taux_fermeture",
        labels={"age_bin": "Tranche d’ancienneté (années)", "taux_fermeture": "Taux de fermeture (%)"},
        color="taux_fermeture", color_continuous_scale="Purples"
    )
    fig_age_ferm.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    st.plotly_chart(fig_age_ferm, use_container_width=True)
else:
    st.info("Ancienneté absente ou vide — section ignorée.")

st.divider()

# 2.5 Taux de fermeture par tranche d’effectif (exclut NN et 00)
st.subheader("👥 Taux de **fermeture** par **tranche d’effectif salarié** (hors 'NN' & '00')")
if "trancheEffectifsUniteLegale" in df.columns:
    df_eff = df.loc[~df["trancheEffectifsUniteLegale"].isin(["NN", "00"])].copy()
    tranches_map = {
        "01": "1–2", "02": "3–5", "03": "6–9",
        "11": "10–19", "12": "20–49", "21": "50–99", "22": "100–199",
        "31": "200–249", "32": "250–499", "41": "500–999",
        "42": "1 000–1 999", "51": "2 000–4 999", "52": "5 000–9 999", "53": "10 000+",
    }
    order_tr = ["1–2", "3–5", "6–9", "10–19", "20–49", "50–99", "100–199",
                "200–249", "250–499", "500–999", "1 000–1 999", "2 000–4 999", "5 000–9 999", "10 000+"]

    df_eff["trancheEffectifs_label"] = df_eff["trancheEffectifsUniteLegale"].map(tranches_map).fillna("Autre/NA")
    ferm_eff = (
        df_eff.groupby("trancheEffectifs_label", dropna=False)
              .agg(
                  nb_total=("siren", lambda s: s.dropna().nunique()),
                  nb_fermees=("etatAdministratifUniteLegale", lambda x: (x == "C").sum()),
              )
              .reset_index()
    )
    ferm_eff["taux_fermeture"] = np.where(
        ferm_eff["nb_total"] > 0, 100 * ferm_eff["nb_fermees"] / ferm_eff["nb_total"], np.nan
    )
    ferm_eff["trancheEffectifs_label"] = pd.Categorical(
        ferm_eff["trancheEffectifs_label"], categories=order_tr + ["Autre/NA"], ordered=True
    )
    ferm_eff = ferm_eff.sort_values("trancheEffectifs_label")

    fig_eff_ferm = px.bar(
        ferm_eff,
        x="trancheEffectifs_label", y="taux_fermeture", text="taux_fermeture",
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
# === PARTIE 2 — SURVIE À 24 MOIS (COHORTE 2020)   ===
# =====================================================
st.header("🟩 Partie 2 — Survie à 24 mois (cohorte 2020, `Survie_24m` fournie)")

needed_cols = {"siren", "annee", "Survie_24m"}
if not needed_cols.issubset(df.columns):
    st.warning("Colonnes requises manquantes pour la cohorte 2020 : 'siren', 'annee', 'Survie_24m'.")
else:
    # 3.1 Cohorte : entreprises observées en 2020 (1 ligne/SIREN)
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

        # 3.2 KPI Survie
        c1, c2, c3 = st.columns(3)
        taux_survie_global = cohort["Survie_24m"].mean() * 100
        nb_survivantes = int(cohort["Survie_24m"].sum())
        nb_non_survivantes = int((cohort["Survie_24m"] == 0).sum())
        c1.metric("🏢 Cohorte 2020 (entreprises)", f"{nb_cohorte:,}")
        c2.metric("📈 Survivantes à 24 mois", f"{nb_survivantes:,}")
        c3.metric("💡 Taux de survie (24m)", f"{taux_survie_global:.2f} %")

        st.caption(
            "Lecture : `Survie_24m` est fournie dans vos données et correspond à l’issue **24 mois après 2020**. "
            "Les profils analysés ci-dessous (catégorie, ancienneté, effectifs) sont ceux **observés en 2020**."
        )
        st.divider()

        # 3.3 Camembert — part des survivantes par catégorie (cohorte 2020)
        st.subheader("🥧 Répartition des **survivantes (24m)** par **catégorie d’entreprise** — cohorte 2020")
        if "categorieEntreprise" in cohort.columns:
            surv_cat_counts = (
                cohort.loc[cohort["Survie_24m"] == 1]
                      .groupby("categorieEntreprise", dropna=False)["siren"]
                      .nunique()
                      .reset_index(name="nb_survivantes")
                      .sort_values("nb_survivantes", ascending=False)
            )
            if surv_cat_counts["nb_survivantes"].sum() == 0:
                st.info("Aucune entreprise survivante (Survie_24m=1) dans la cohorte 2020.")
            else:
                fig_pie_surv = px.pie(
                    surv_cat_counts,
                    values="nb_survivantes", names="categorieEntreprise",
                    color_discrete_sequence=px.colors.qualitative.Prism,
                    hole=0.45
                )
                fig_pie_surv.update_traces(textinfo="percent+label")
                st.plotly_chart(fig_pie_surv, use_container_width=True)
                st.caption("Part des **survivantes** par **catégorie** (profils de 2020).")
        else:
            st.info("Catégorie d’entreprise (2020) indisponible — camembert non affiché.")

        st.divider()

        # 3.4 Taux de survie (24m) par catégorie — cohorte 2020
        st.subheader("🏢 Taux de **survie (24m)** par **catégorie d’entreprise** — cohorte 2020")
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
            st.info("Catégorie d’entreprise (2020) indisponible — graphique non affiché.")

        st.divider()

        # 3.5 Ancienneté (2020) × Survie (24m) — cohorte 2020
        st.subheader("⏳ **Ancienneté (2020)** × **Survie (24m)** — cohorte 2020")
        if "anciennete" in cohort.columns and cohort["anciennete"].notna().any():
            bins_age = [0, 5, 10, 20, 30, 50, 100, np.inf]
            labels_age = ["0–5", "5–10", "10–20", "20–30", "30–50", "50–100", "100+"]
            cohort["age_bin"] = pd.cut(
                cohort["anciennete"], bins=bins_age, labels=labels_age,
                include_lowest=True, right=False
            )

            surv_age = (
                cohort.groupby("age_bin")
                      .agg(
                          nb_total=("siren", lambda s: s.dropna().nunique()),
                          taux_survie=("Survie_24m", lambda s: float(s.mean() * 100) if len(s) else np.nan),
                      )
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
            st.info("Ancienneté (2020) absente ou vide — section ignorée.")

        st.divider()

        # 3.6 Survie par tranche d’effectif (hors NN/00) — cohorte 2020
        st.subheader("👥 **Survie (24m)** par **tranche d’effectif (2020)** — hors 'NN' & '00'")
        if "trancheEffectifsUniteLegale" in cohort.columns:
            cohort_eff = cohort.loc[~cohort["trancheEffectifsUniteLegale"].isin(["NN", "00"])].copy()

            tranches_map = {
                "01": "1–2", "02": "3–5", "03": "6–9",
                "11": "10–19", "12": "20–49", "21": "50–99", "22": "100–199",
                "31": "200–249", "32": "250–499", "41": "500–999",
                "42": "1 000–1 999", "51": "2 000–4 999", "52": "5 000–9 999", "53": "10 000+",
            }
            order_tr = ["1–2", "3–5", "6–9", "10–19", "20–49", "50–99", "100–199",
                        "200–249", "250–499", "500–999", "1 000–1 999", "2 000–4 999", "5 000–9 999", "10 000+"]

            cohort_eff["trancheEffectifs_label"] = cohort_eff["trancheEffectifsUniteLegale"].map(tranches_map).fillna("Autre/NA")

            surv_eff = (
                cohort_eff.groupby("trancheEffectifs_label", dropna=False)
                          .agg(
                              nb_total=("siren", lambda s: s.dropna().nunique()),
                              taux_survie=("Survie_24m", lambda s: float(s.mean() * 100) if len(s) else np.nan),
                          )
                          .reset_index()
            )
            surv_eff["trancheEffectifs_label"] = pd.Categorical(
                surv_eff["trancheEffectifs_label"], categories=order_tr + ["Autre/NA"], ordered=True
            )
            surv_eff = surv_eff.sort_values("trancheEffectifs_label")

            fig_eff_surv = px.bar(
                surv_eff,
                x="trancheEffectifs_label", y="taux_survie", text="taux_survie",
                labels={"trancheEffectifs_label": "Tranche d'effectif (2020)", "taux_survie": "Taux de survie (%)"},
                color="taux_survie", color_continuous_scale="Tealgrn"
            )
            fig_eff_surv.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig_eff_surv.update_layout(xaxis_tickangle=-35)
            st.plotly_chart(fig_eff_surv, use_container_width=True)
        else:
            st.info("Tranche d’effectif (2020) absente — section ignorée.")

        st.divider()

        # 3.7 Tableau récapitulatif — cohorte 2020
        st.subheader("📋 Tableau récap — **cohorte 2020** : profils vs **Survie (24m)**")
        dims = [c for c in ["categorieEntreprise", "trancheEffectifsUniteLegale", "age_bin"] if c in cohort.columns]
        if dims:
            table_surv = (
                cohort.groupby(dims)
                      .agg(
                          nb_total=("siren", lambda s: s.dropna().nunique()),
                          nb_survivantes=("Survie_24m", "sum"),
                          nb_non_survivantes=("Survie_24m", lambda s: int((s == 0).sum())),
                          taux_survie=("Survie_24m", lambda s: float(s.mean() * 100)),
                      )
                      .reset_index()
            )
            st.dataframe(table_surv, use_container_width=True)
            st.download_button(
                "📥 Télécharger la table (CSV) — cohorte 2020",
                data=table_surv.to_csv(index=False).encode("utf-8"),
                file_name="cohorte_2020_survie24m_par_profils.csv"
            )
        else:
            st.info("Colonnes de profil insuffisantes en 2020 pour produire le tableau multi-dimensions.")

st.divider()
st.info("🔜 Étape suivante : relier ces indicateurs aux **montants/types d’aides** pour estimer l’**impact causal** (ex. DID, uplift).")

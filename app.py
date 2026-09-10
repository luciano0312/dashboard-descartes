import os
import pandas as pd
import streamlit as st

# Configuração da página do Dashboard
st.set_page_config(
    page_title="Dashboard de Descarte e Vendas por Produto", layout="wide"
)

st.title("📊 Painel Consolidado: Descarte vs. Vendas por Produto")
st.markdown(
    "Este painel exibe **apenas os produtos que registraram descartes**, cruzando"
    " com as respectivas vendas."
)


# Função para limpar e converter quantidades de forma segura
def limpar_qtd(val):
  if pd.isna(val):
    return 0.0
  if isinstance(val, (int, float)):
    return float(val)
  val_str = str(val).strip().replace(",", ".")
  try:
    return float(val_str)
  except:
    return 0.0


@st.cache_data(ttl=1)
def carregar_e_cruzar_dados():
  if not os.path.exists("descartes.xlsx") or not os.path.exists("Vendas.csv"):
    return None

  # Carregando Descartes
  xls = pd.ExcelFile("descartes.xlsx")
  df_descarte = pd.read_excel(xls, xls.sheet_names[0])

  # Carregando Vendas
  df_vendas = pd.read_csv("Vendas.csv", sep=";", encoding="latin1")

  # Padronizar código como texto limpo
  df_descarte["Cod_Str"] = df_descarte["Código"].astype(str).str.strip()
  df_vendas["Cod_Str"] = df_vendas["Codigo"].astype(str).str.strip()

  df_descarte["Qtd_Descarte"] = df_descarte["Quantidade"].apply(limpar_qtd)
  df_vendas["Qtd_Venda"] = df_vendas["Quantidade"].apply(limpar_qtd)

  # Agrupar descartes e vendas por código
  descartes_grp = (
      df_descarte.groupby("Cod_Str")["Qtd_Descarte"].sum().reset_index()
  )
  vendas_grp = df_vendas.groupby("Cod_Str")["Qtd_Venda"].sum().reset_index()

  # Mapear a descrição de cada produto
  desc_map_vendas = (
      df_vendas.drop_duplicates("Cod_Str")
      .set_index("Cod_Str")["Descrição"]
      .to_dict()
  )
  desc_map_descartes = (
      df_descarte.drop_duplicates("Cod_Str")
      .set_index("Cod_Str")["Descrição"]
      .to_dict()
  )

  # Mesclar as duas bases estritamente pelo Código
  df_cons = pd.merge(descartes_grp, vendas_grp, on="Cod_Str", how="outer")
  df_cons["Qtd_Descarte"] = df_cons["Qtd_Descarte"].fillna(0)
  df_cons["Qtd_Venda"] = df_cons["Qtd_Venda"].fillna(0)

  # Definir a descrição do produto
  df_cons["Descrição do Produto"] = (
      df_cons["Cod_Str"].map(desc_map_vendas).fillna(
          df_cons["Cod_Str"].map(desc_map_descartes)
      )
  )

  # 🚀 FILTRO PRINCIPAL: Manter APENAS os itens que possuem Qtd_Descarte > 0
  df_cons = df_cons[df_cons["Qtd_Descarte"] > 0].copy()

  # Calcular a porcentagem de descarte sobre a venda de forma inteligente:
  def calcular_perc(row):
    v = row["Qtd_Venda"]
    d = row["Qtd_Descarte"]
    if v > 0:
      return (d / v) * 100
    elif d > 0:
      return 999.0  # Indicador especial para descarte sem venda registrada
    return 0.0

  df_cons["% Descarte / Venda"] = df_cons.apply(calcular_perc, axis=1)

  return df_cons


df_resultado = carregar_e_cruzar_dados()

if df_resultado is None:
  st.error(
      "⚠️ Arquivos `descartes.xlsx` ou `Vendas.csv` não encontrados na pasta."
  )
else:
  # --- FILTROS NA BARRA LATERAL ---
  st.sidebar.header("🔍 Filtros de Visualização")
  filtro_status = st.sidebar.selectbox(
      "Filtrar por Status de Descarte:",
      [
          "Todos com Descarte",
          "🔴 Crítico (> 35% ou Sem Venda)",
          "🟡 Atenção (16% a 35%)",
          "🟢 Normal (0% a 15%)",
      ],
  )

  # Aplicar filtro lateral
  if "Crítico" in filtro_status:
    df_exib = df_resultado[df_resultado["% Descarte / Venda"] > 35].copy()
  elif "Atenção" in filtro_status:
    df_exib = df_resultado[
        (df_resultado["% Descarte / Venda"] > 15)
        & (df_resultado["% Descarte / Venda"] <= 35)
    ].copy()
  elif "Normal" in filtro_status:
    df_exib = df_resultado[
        (df_resultado["% Descarte / Venda"] >= 0)
        & (df_resultado["% Descarte / Venda"] <= 15)
    ].copy()
  else:
    df_exib = df_resultado.copy()

  # Totais gerais para os cards do topo (considerando apenas os descartados)
  total_geral_descarte = df_resultado["Qtd_Descarte"].sum()
  total_vendas_dos_descartados = df_resultado["Qtd_Venda"].sum()

  col1, col2, col3 = st.columns(3)
  col1.metric(
      "📦 Total de Itens Descartados", f"{len(df_resultado)} produtos"
  )
  col2.metric("🗑️ Volume Total Descartado", f"{total_geral_descarte:,.2f}")
  col3.metric("📊 Volume Vendido (destes itens)", f"{total_vendas_dos_descartados:,.2f}")

  st.markdown("---")
  st.subheader("📋 Produtos com Descarte Registrado")
  st.markdown(
      "Abaixo estão listados **somente** os itens que tiveram perdas registradas"
      " na planilha de descartes."
  )


  # Função de estilização das cores nas linhas da tabela
  def colorir_faixas(val):
    if val >= 999:
      return "background-color: #f8d7da; color: #721c24; font-weight: bold;"  # Vermelho Crítico (Sem venda)
    elif val <= 15:
      return "background-color: #d4edda; color: #155724; font-weight: bold;"  # Verde
    elif val <= 35:
      return "background-color: #fff3cd; color: #856404; font-weight: bold;"  # Amarelo
    else:
      return "background-color: #f8d7da; color: #721c24; font-weight: bold;"  # Vermelho


  # Formatando a exibição da tabela com cores condicionais
  tabela_exibicao = df_exib[
      [
          "Cod_Str",
          "Descrição do Produto",
          "Qtd_Venda",
          "Qtd_Descarte",
          "% Descarte / Venda",
      ]
  ].copy()
  tabela_exibicao.columns = [
      "Código",
      "Descrição do Produto",
      "Qtd Vendida",
      "Qtd Descartada",
      "% Descarte / Venda",
  ]

  # Ordenar por maior percentual ou maior quantidade de descarte
  tabela_exibicao = tabela_exibicao.sort_values(
      by=["% Descarte / Venda", "Qtd Descartada"], ascending=False
  )


  # Formatação personalizada para exibir texto quando não houver venda
  def formatar_linha(val):
    if val >= 999:
      return "⚠️ Sem Venda Registrada"
    return f"{val:.2f}%"


  tabela_formatada = (
      tabela_exibicao.style.map(
          colorir_faixas, subset=["% Descarte / Venda"]
      )
      .format(
          {
              "Qtd Vendida": "{:,.2f}",
              "Qtd Descartada": "{:,.2f}",
              "% Descarte / Venda": formatar_linha,
          }
      )
  )

  st.dataframe(tabela_formatada, use_container_width=True)

  # Legenda explicativa das cores
  st.markdown("### 🎨 Legenda de Cores e Alertas:")
  st.markdown(
      "🔴 **Sem Venda Registrada (>35%):** Produto descartado sem nenhuma"
      " unidade vendida correspondente (Alerta Crítico)"
  )
  st.markdown("🟡 **16% a 35%:** Descarte em nível de atenção (Amarelo)")
  st.markdown("🟢 **0% a 15%:** Descarte dentro do esperado (Verde)")
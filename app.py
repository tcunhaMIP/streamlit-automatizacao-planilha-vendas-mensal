import io
import requests
import pandas as pd
import streamlit as st

API_URL = "https://mip.cvcrm.com.br/api/v1/comercial/reservas"

EMPREENDEDIMENTOS = [
    {"id": 26, "nome": "ONE VIEW LUXEMBURGO"},
    {"id": 25, "nome": "CARBON"},
    {"id": 24, "nome": "AURA"},
    {"id": 23, "nome": "Terras de Minas"},
    {"id": 22, "nome": "JADE"},
    {"id": 21, "nome": "SION"},
    {"id": 20, "nome": "Campo das Aroeiras"},
    {"id": 19, "nome": "JARDINS 156"},
    {"id": 18, "nome": "Empreendimentos Antigos"},
    {"id": 17, "nome": "MARTIM 440"},
    {"id": 16, "nome": "Terras Altas"},
    {"id": 11, "nome": "Valle da Serra"},
    {"id": 10, "nome": "Três Rios"},
    {"id": 9,  "nome": "Savassi 1022"},
    {"id": 8,  "nome": "Santo Agostinho"},
    {"id": 7,  "nome": "Reserva Piedade"},
    {"id": 6,  "nome": "EDIFÍCIO LOURDES 1580"},
    {"id": 5,  "nome": "Gran Royalle Casa Branca"},
    {"id": 4,  "nome": "Funcionários Lifestyle"},
    {"id": 3,  "nome": "Eco Casa Branca"},
    {"id": 2,  "nome": "ALVARENGA, 594"},
]


def get_data_month(id_empreendimento: int, mes: int, ano: int):
    params = {
        "situacao": 3,
        "idempreendimento": id_empreendimento,
        "a_partir_de": f"01/{mes:02d}/{ano}",
    }

    headers = {
        "email": st.secrets["EMAIL"],
        "token": st.secrets["TOKEN"],
    }

    resp = requests.get(API_URL, params=params, headers=headers)
    resp.raise_for_status()

    if resp.status_code == 204 or not resp.text.strip():
        return {}

    return resp.json()


def get_dataframe_from_month(id_empreendimento: int, mes: int, ano: int):
    data = get_data_month(id_empreendimento=id_empreendimento, mes=mes, ano=ano)

    if not data:
        return pd.DataFrame(columns=[
            "unidade",
            "empreendimento",
            "cliente",
            "data_contrato",
            "valor_contrato",
            "comissao",
            "porcentagem",
            "imobiliaria",
            "data_pag_sinal",
            "forma_pagamento",
            "valor_tabela",
            "valor_sinal",
        ])

    if isinstance(data, list):
        iter_values = data
    else:
        iter_values = data.values()

    rows = []
    for proposta in iter_values:
        unidade_info = proposta.get("unidade", {})
        titular_info = proposta.get("titular", {})
        condicoes_info = proposta.get("condicoes", {})
        comissoes_info = proposta.get("comissoes", {})

        series = condicoes_info.get("series", [])

        # Valor do sinal
        valor_sinal = None
        data_pag_sinal = None
        for parcela in series:
            if parcela.get("serie") == "Sinal":
                try:
                    valor_sinal = float(parcela.get("valor", "0") or 0)
                except ValueError:
                    valor_sinal = None
                data_pag_sinal = parcela.get("vencimento")
                break

        # Forma de pagamento (quantidade de parcelas)
        forma_pagamento_qtd = -1  # mesma lógica do seu script
        for parcela in series:
            try:
                forma_pagamento_qtd += int(parcela.get("quantidade", 0) or 0)
            except ValueError:
                continue

        total_comissao_valor = 0.0
        total_comissao_porcentagem = 0.0
        imobiliarias_envolvidas = []

        for key, valor in comissoes_info.items():
            if isinstance(key, str) and key.isdigit() and isinstance(valor, dict):
                try:
                    valor_comissao = float(valor.get("comissao_valor", "0") or 0)
                except ValueError:
                    valor_comissao = 0.0

                try:
                    perc_comissao = float(valor.get("comissao_porcentagem", "0") or 0)
                except ValueError:
                    perc_comissao = 0.0

                total_comissao_valor += valor_comissao
                total_comissao_porcentagem += perc_comissao

                nome_imobiliaria = valor.get("comissao_quem")
                if nome_imobiliaria and nome_imobiliaria not in imobiliarias_envolvidas:
                    imobiliarias_envolvidas.append(nome_imobiliaria)

        imobiliaria_str = ", ".join(imobiliarias_envolvidas) if imobiliarias_envolvidas else None

        row = {
            "unidade": unidade_info.get("unidade"),
            "empreendimento": unidade_info.get("empreendimento"),
            "cliente": titular_info.get("nome"),
            "data_contrato": proposta.get("data_contrato") or proposta.get("data_venda"),
            "valor_contrato": condicoes_info.get("valor_contrato"),
            "comissao": total_comissao_valor,
            "porcentagem": total_comissao_porcentagem,
            "imobiliaria": imobiliaria_str,
            "data_pag_sinal": data_pag_sinal,
            "forma_pagamento": f"{forma_pagamento_qtd} parcelas",
            "valor_tabela": condicoes_info.get("vpl_reserva"),
            "valor_sinal": valor_sinal,
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    return df


def to_excel_bytes(df: pd.DataFrame) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Reservas")
    output.seek(0)
    return output.read()


# =================== INTERFACE STREAMLIT ===================

st.set_page_config(page_title="Relatório de Reservas", page_icon="📊")

st.title("Relatório de Reservas - CVCRM")

# Seleção de empreendimento
nomes_emp = [e["nome"] for e in EMPREENDEDIMENTOS]
nome_selecionado = st.selectbox("Empreendimento", nomes_emp)

empreendimento = next(e for e in EMPREENDEDIMENTOS if e["nome"] == nome_selecionado)

col1, col2 = st.columns(2)
with col1:
    mes = st.number_input("Mês", min_value=1, max_value=12, value=1, step=1)
with col2:
    ano = st.number_input("Ano", min_value=2000, max_value=2100, value=2025, step=1)

if st.button("Gerar relatório"):
    with st.spinner("Buscando dados..."):
        try:
            df = get_dataframe_from_month(
                id_empreendimento=empreendimento["id"],
                mes=int(mes),
                ano=int(ano),
            )
        except Exception as e:
            st.error(f"Erro ao buscar dados: {e}")
        else:
            if df.empty:
                st.warning("Nenhum dado encontrado para o período selecionado.")
            else:
                st.success("Dados carregados com sucesso!")
                st.dataframe(df, use_container_width=True)

                excel_bytes = to_excel_bytes(df)
                filename = f"reservas_{empreendimento['id']}_{mes:02d}_{ano}.xlsx"

                st.download_button(
                    label="⬇️ Baixar Excel",
                    data=excel_bytes,
                    file_name=filename,
                    mime=(
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                )

# app.py
from flask import Flask, jsonify
import os
import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime, timedelta

app = Flask(__name__)

# ---------- Configurações (ambiente / secrets) ----------
PASTA_ARQUIVOS = os.getenv("PASTA_ARQUIVOS", "/data")
ADMINISTRADORA = os.getenv("ADMINISTRADORA", "GCACARD")
REMETENTE = os.getenv("REMETENTE", "0000")
DESTINATARIO = os.getenv("DESTINATARIO", "000000")
TIPO_PROCESSAMENTO = os.getenv("TIPO_PROCESSAMENTO", "N")
MOEDA = os.getenv("MOEDA", "RE")

def read_secret(name):
    path = f"/run/secrets/{name}"
    if os.path.exists(path):
        return open(path).read().strip()
    return None

def conectar_sqlalchemy():
    """
    Constrói engine SQLAlchemy usando pymssql.
    Preferência: SQLALCHEMY_URL > componentes DB_* > secret db_password
    """
    url = os.getenv("SQLALCHEMY_URL")
    if url:
        return create_engine(url)

    server = os.getenv("DB_SERVER", "138.0.160.201")
    database = os.getenv("DB_NAME", "ErCardGCAD1")
    user = os.getenv("DB_USER", "d1.devee")
    password = os.getenv("DB_PASS") or read_secret("db_password") or "6$ZY325Eo0"

    connection_string = f"mssql+pymssql://{user}:{password}@{server}/{database}"
    return create_engine(connection_string)

# ---------- Funções utilitárias ----------
def gerar_id_movimento():
    if not os.path.exists(PASTA_ARQUIVOS):
        os.makedirs(PASTA_ARQUIVOS)
    arquivos = [f for f in os.listdir(PASTA_ARQUIVOS) if f.endswith(".txt")]
    ids = []
    for f in arquivos:
        if len(f) >= 10 and f[-10:-4].isdigit():
            ids.append(int(f[-10:-4]))
    return max(ids) + 1 if ids else 1

def formatar_valor(valor):
    try:
        return f"{float(valor):011.2f}".replace('.', '')
    except Exception:
        return "00000000000"

def formatar_registro_A0(id_mov, datahora, nseq):
    return (
        "A0"
        + "001.7c"
        + datahora.strftime('%Y%m%d')
        + datahora.strftime('%H%M%S')
        + str(id_mov).zfill(6)
        + ADMINISTRADORA.ljust(30)[:30]
        + REMETENTE.zfill(4)
        + DESTINATARIO.zfill(6)
        + TIPO_PROCESSAMENTO
        + str(nseq).zfill(6)
    )

def formatar_registro_L0(row, nseq):
    # Garantir acesso seguro ao campo data_transacao
    data_tx = row.get('data_transacao') if isinstance(row, dict) else row['data_transacao']
    return f"L0{data_tx}{MOEDA}{str(nseq).zfill(6)}"

def formatar_registro_CV(row, nseq):
    return (
        "CV"
        + str(row.get('cnpj_loja',''))
        + str(row.get('nsu',''))
        + row.get('data_transacao','')
        + str(row.get('hora_transacao',''))
        + str(row.get('tipo_lanc',''))
        + row.get('dataprevisao','')
        + "C"
        + "9"
        + formatar_valor(row.get('valor_bruto',0))
        + "00000000000"
        + formatar_valor(row.get('valor_bruto',0))
        + str(row.get('numero_cartao','')).zfill(19)
        + str(row.get('n_parcela',''))
        + str(row.get('n_prazo',''))
        + str(row.get('nsu',''))
        + formatar_valor(row.get('valor_parcela',0))
        + "00000000000"
        + formatar_valor(row.get('valor_parcela',0))
        + str(row.get('banco_dep',''))
        + str(row.get('agencia_dep',''))
        + str(row.get('conta_dep',''))
        + "000000000000"
        + "000"
        + str(nseq).zfill(6)
    )

def formatar_registro_CC(row, nseq):
    return (
        "CC"
        + str(row.get('cnpj_loja',''))
        + str(row.get('nsu',''))
        + row.get('data_transacao','')
        + str(row.get('n_parcela',''))
        + str(row.get('nsu_cancelamento',''))
        + row.get('data_transacao','')
        + str(row.get('hora_transacao',''))
        + "9"
        + str(nseq).zfill(6)
    )

def formatar_registro_L9(qtd_registros, total_credito, nseq):
    return f"L9{str(qtd_registros).zfill(6)}{formatar_valor(total_credito).rjust(14,'0')}{str(nseq).zfill(6)}"

def formatar_registro_A9(total_registros, nseq):
    return f"A9{str(total_registros).zfill(6)}{str(nseq).zfill(6)}"

# ---------- Query (copiada do Conci_GCA.py que você enviou) ----------
# Nota: a query abaixo vem do seu Conci_GCA.py enviado (mantive exatamente).
query = """
SELECT
CASE WHEN CP.SITUACAO = 'C' THEN 'CC'
     WHEN CP.SITUACAO = 'A' THEN 'CV' 
END                                                 AS tipo_registro,
REPLACE(LJ.CODIGOESTABELECIMENTO, ' ', '')                     AS cnpj_loja,
ISNULL(FORMAT(CP.AUTORIZACAO, '000000000000'), '000000000000')              AS nsu,
ISNULL(FORMAT(CP.AUTORIZACAOCANCELAMENTO, '000000000000'), '000000000000')  AS nsu_cancelamento,
CONVERT(VARCHAR(8), CP.DATACOMPRA, 112)             AS data_transacao,
REPLACE(CP.HORACOMPRA, ':','')                      AS hora_transacao,
CASE
    WHEN PA.REPASSE = 'N' THEN 0
    WHEN PA.REPASSE = 'S' THEN 1
    WHEN PA.REPASSE = 'D' THEN 2
END                                                 AS tipo_lanc,

CASE
        WHEN PA.DATAPREVISAOREPASSE IS NULL 
            THEN  CONVERT(VARCHAR(8), DATEADD(DAY, 30,CP.DATACOMPRA), 112)
        ELSE CONVERT(VARCHAR(8), PA.DATAPREVISAOREPASSE, 112)
END                                                 AS dataprevisao,
CP.VALORCOMPRA                                      AS valor_bruto,
RIGHT('0000000000000000000' + CAST(REPLACE(CP.PLASTICO, ' ', '')AS VARCHAR(19)), 19) AS numero_cartao,
CASE
    WHEN PA.PARCELA = 1 THEN '00'
    ELSE
        RIGHT('00' + CAST(PA.PARCELA AS VARCHAR(2)), 2)
END                                                 AS n_parcela,

CASE
    WHEN CP.PRAZO = 1 THEN '00'
    ELSE
        RIGHT('00' + CAST(CP.PRAZO AS VARCHAR(2)), 2)
END                                                 AS n_prazo,
CASE
    WHEN CP.PRAZO = 1 THEN '00000000000'
    ELSE
         PA.PRESTACAO
END                                                 AS valor_parcela,
CASE WHEN LJ.PARAMETROSPAGAMENTO = 'S' THEN RIGHT(CAST(CAST(LJ.BANCO AS INT) AS VARCHAR(3)), 3)	
     WHEN LJ.PARAMETROSPAGAMENTO = 'N' THEN RIGHT(CAST(CAST(LI.BANCO  AS INT) AS VARCHAR(3)), 3)
END														AS banco_dep,

CASE WHEN LJ.PARAMETROSPAGAMENTO = 'S' THEN RIGHT('000000' + CAST(REPLACE(LJ.BANCOAGENCIA + LJ.BANCOAGENCIADIGITO, ' ', '') AS VARCHAR(6)), 6)
     WHEN LJ.PARAMETROSPAGAMENTO = 'N' THEN RIGHT('000000' + CAST(REPLACE(LI.BANCOAGENCIA + LI.BANCOAGENCIADIGITO, ' ', '') AS VARCHAR(6)), 6)
END														AS agencia_dep,

CASE WHEN LJ.PARAMETROSPAGAMENTO = 'S' THEN RIGHT('00000000000' + CAST(LJ.BANCOCONTACORRENTE + LJ.BANCOCONTADIGITO AS VARCHAR(11)), 11)
     WHEN LJ.PARAMETROSPAGAMENTO = 'N' THEN RIGHT('00000000000' + CAST(LI.BANCOCONTACORRENTE + LI.BANCOCONTADIGITO AS VARCHAR(11)), 11) 
END														AS conta_dep

FROM CRTCOMPRASPARCELAS     AS PA
INNER JOIN CRTCOMPRAS       AS CP ON CP.AUTORIZACAO = PA.AUTORIZACAO
INNER JOIN CRTLOJAS         AS LJ ON LJ.LOJA = CP.LOJA
INNER JOIN CRTLOJISTAS      AS LI ON LI.LOJISTA = CP.LOJISTA
WHERE CP.SITUACAO IN ('A', 'C')
AND PA.DATAREPASSE = CAST(GETDATE() - 1 AS DATE)
ORDER BY tipo_lanc;

UNION

SELECT
CASE WHEN CP.SITUACAO = 'C' THEN 'CC'
     WHEN CP.SITUACAO = 'A' THEN 'CV' 
END                                                 AS tipo_registro,
REPLACE(LJ.CODIGOESTABELECIMENTO, ' ', '')                     AS cnpj_loja,
ISNULL(FORMAT(CP.AUTORIZACAO, '000000000000'), '000000000000')              AS nsu,
ISNULL(FORMAT(CP.AUTORIZACAOCANCELAMENTO, '000000000000'), '000000000000')  AS nsu_cancelamento,
CONVERT(VARCHAR(8), CP.DATACOMPRA, 112)             AS data_transacao,
REPLACE(CP.HORACOMPRA, ':','')                      AS hora_transacao,
CASE
    WHEN PA.REPASSE = 'N' THEN 0
    WHEN PA.REPASSE = 'S' THEN 1
    WHEN PA.REPASSE = 'D' THEN 2
END                                                 AS tipo_lanc,
CONVERT(VARCHAR(8), PA.DATAREPASSE, 112)           AS dataprevisao,
CP.VALORCOMPRA                                      AS valor_bruto,
RIGHT('0000000000000000000' + CAST(REPLACE(CP.PLASTICO, ' ', '')AS VARCHAR(19)), 19) AS numero_cartao,
CASE
    WHEN PA.PARCELA = 1 THEN '00'
    ELSE
        RIGHT('00' + CAST(PA.PARCELA AS VARCHAR(2)), 2)
END                                                 AS n_parcela,

CASE
    WHEN CP.PRAZO = 1 THEN '00'
    ELSE
        RIGHT('00' + CAST(CP.PRAZO AS VARCHAR(2)), 2)
END                                                 AS n_prazo,
CASE
    WHEN CP.PRAZO = 1 THEN '00000000000'
    ELSE
         PA.PRESTACAO
END                                                 AS valor_parcela,
CASE WHEN LJ.PARAMETROSPAGAMENTO = 'S' THEN RIGHT(CAST(CAST(LJ.BANCO AS INT) AS VARCHAR(3)), 3)	
     WHEN LJ.PARAMETROSPAGAMENTO = 'N' THEN RIGHT(CAST(CAST(LI.BANCO  AS INT) AS VARCHAR(3)), 3)
END														AS banco_dep,

CASE WHEN LJ.PARAMETROSPAGAMENTO = 'S' THEN RIGHT('000000' + CAST(REPLACE(LJ.BANCOAGENCIA + LJ.BANCOAGENCIADIGITO, ' ', '') AS VARCHAR(6)), 6)
     WHEN LJ.PARAMETROSPAGAMENTO = 'N' THEN RIGHT('000000' + CAST(REPLACE(LI.BANCOAGENCIA + LI.BANCOAGENCIADIGITO, ' ', '') AS VARCHAR(6)), 6)
END														AS agencia_dep,

CASE WHEN LJ.PARAMETROSPAGAMENTO = 'S' THEN RIGHT('00000000000' + CAST(LJ.BANCOCONTACORRENTE + LJ.BANCOCONTADIGITO AS VARCHAR(11)), 11)
     WHEN LJ.PARAMETROSPAGAMENTO = 'N' THEN RIGHT('00000000000' + CAST(LI.BANCOCONTACORRENTE + LI.BANCOCONTADIGITO AS VARCHAR(11)), 11) 
END														AS conta_dep

FROM CRTCOMPRASPARCELAS     AS PA
INNER JOIN CRTCOMPRAS       AS CP ON CP.AUTORIZACAO = PA.AUTORIZACAO
INNER JOIN CRTLOJAS         AS LJ ON LJ.LOJA = CP.LOJA
INNER JOIN CRTLOJISTAS      AS LI ON LI.LOJISTA = CP.LOJISTA
WHERE CP.SITUACAO IN ('A', 'C')
AND CP.DATACONTABIL = CAST(GETDATE() - 1 AS DATE)
"""
# ---------- Função que busca do DB ----------
def buscar_dados_do_banco():
    engine = conectar_sqlalchemy()
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)
    # garantir que o DataFrame use strings para evitar erros ao formatar
    if not df.empty:
        df = df.fillna('')
        # transformar em lista de dicts para uso seguro
        df = df.to_dict(orient='records')
    return df

# ---------- Gerar arquivo (retorna JSON com caminho) ----------
def gerar_arquivo_conciliacao():
    rows = buscar_dados_do_banco()
    if not rows or len(rows) == 0:
        return {"ok": False, "msg": "Nenhum dado encontrado para gerar o arquivo."}

    id_mov = gerar_id_movimento()
    datahora = datetime.now() - timedelta(days=1)
    nseq = 1
    conteudo = []

    # primeiro registro A0
    conteudo.append(formatar_registro_A0(id_mov, datahora, nseq))
    nseq += 1

    # L0 - usa o primeiro registro apenas para dados de cabeçalho
    conteudo.append(formatar_registro_L0(rows[0], nseq))
    nseq += 1

    qtd_transacoes = 0
    total_credito = 0.0

    for row in rows:
        # row já é dict
        if row.get('tipo_registro') == "CV":
            conteudo.append(formatar_registro_CV(row, nseq))
            try:
                total_credito += float(row.get('valor_bruto') or 0)
            except:
                pass
            qtd_transacoes += 1
            nseq += 1
        elif row.get('tipo_registro') == "CC":
            conteudo.append(formatar_registro_CC(row, nseq))
            qtd_transacoes += 1
            nseq += 1

    conteudo.append(formatar_registro_L9(qtd_transacoes, total_credito, nseq))
    nseq += 1
    conteudo.append(formatar_registro_A9(len(conteudo) + 1, nseq))
    nseq += 1

    nome_arquivo = f"{ADMINISTRADORA}{str(id_mov).zfill(6)}.txt"
    caminho_final = os.path.join(PASTA_ARQUIVOS, nome_arquivo)

    with open(caminho_final, 'w', encoding='utf-8') as f:
        f.write("\n".join(conteudo))

    return {"ok": True, "path": caminho_final, "file": nome_arquivo}

# ---------- Endpoint ----------
@app.route("/generate", methods=["POST"])
def endpoint_generate():
    try:
        result = gerar_arquivo_conciliacao()
        status = 200 if result.get("ok") else 400
        return jsonify(result), status
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

if __name__ == "__main__":
    # somento debug local
    app.run(host="0.0.0.0", port=5000)

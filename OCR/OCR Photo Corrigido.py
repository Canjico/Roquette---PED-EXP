from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException
from selenium import webdriver
from pdf2image import convert_from_path
from PIL import Image, ImageOps
from pathlib import Path
import re, os, time
import shutil
import unicodedata
from thefuzz import fuzz
from thefuzz import process

Image.MAX_IMAGE_PIXELS = None


# ---------------- CONFIG ----------------
BASE_DIR = Path(__file__).resolve().parent
DOWNLOAD_DIR = BASE_DIR / "Downloads"

# Ajuste o caminho do Poppler conforme sua máquina
poppler_path = r"C:\Users\7304078\OneDrive - Roquette\Documentos\OCR\Poppler\Release-24.08.0-0\poppler-24.08.0\Library\bin"

# Pastas
pasta_fotos = Path(r"C:\Users\7304078\OneDrive - Roquette\Documentos\OCR\Fotos para Renomear")
pasta_processando = Path(r"C:\Users\7304078\OneDrive - Roquette\Documentos\OCR\Processando")
pasta_nao_proc = Path(r"C:\Users\7304078\OneDrive - Roquette\Documentos\OCR\Não Processados")
pasta_prontas = Path(r"C:\Users\7304078\OneDrive - Roquette\Documentos\OCR\Fotos Prontas")

DOWNLOAD_DIR.mkdir(exist_ok=True)
pasta_processando.mkdir(exist_ok=True)
pasta_nao_proc.mkdir(exist_ok=True)
pasta_prontas.mkdir(exist_ok=True)

# LISTA PRINCIPAL DE CLIENTES (Usada para Fuzzy Matching)
CLIENTES_CONHECIDOS = [
    "BRAINFARMA", "COSMED", "DSM", "DSV", "TOVANI", "UNIAO QUIMICA", "CARGILL", "EMS", "EUROFARMA", "GLOBALFOOD", "TEUTO",
    "MULTILAB", "NOVAMED", "SANOFI", "TAKEDA", "TATE", "MONDELEZ", "ACHE", "ALIBRA", "ALLPREMIUM", "ANOVIS", "CIMED", "DANISCO",
    "GEOLAB", "HALEON", "HEXUS", "HIPOLABOR", "IHARABRAS", "LABOFARMA", "LALLEMAND", "LIOTECNICA", "PHARLAB", "PRATI",
    "SANDOZ", "BLUMOS", "MARITIME", "BRENNTAG", "DEPOTCHEM", "AZELIS", "ORKILA", "CALTECH", "BIESTERFELD", "GUANGZHOU",
    "REMEDICA", "QUIMIDROGA", "UNI PHARMA", "BARENTZ", "SIGNET", "GIUSTO", "IMCOPHARMA", "LABORATORIO CHILE",
    "NESTLE", "GLAXOSSMITHKLINE", "VICENTE SCAVONE", "IDUN", "INSTITUTO QUIMIOTERAPICO", "QUIMTIA", "TEVA"
]

clientes_exp = [
    "MARITIME", "BRENNTAG", "DEPOTCHEM", "AZELIS", "ORKILA", "CALTECH", "BIESTERFELD",
    "GUANGZHOU", "REMEDICA", "QUIMIDROGA", "UNI-PHARMA", "UNI PHARMA", "UNIPHARMA",
    "BARENTZ", "SIGNET", "GIUSTO", "IMCOPHARMA", "LABORATORIO CHILE", "NESTLE",
    "GLAXOSSMITHKLINE", "VICENTE SCAVONE", "IDUN", "INSTITUTO QUIMIOTERAPICO",
    "QUIMTIA", "TEVA"
]

# Palavras que aparecem no produto/embalagem e NÃO devem ser usadas como cliente.
# ROQUETTE aparece em praticamente toda foto, então não pode decidir EXP/PED.
PALAVRAS_IGNORADAS_CLIENTE = {
    "ROQUETTE", "MICROCEL", "MANGCEL", "NOCEL", "MICROCK", "MICOACHI"
}

# Clientes domésticos conhecidos: qualquer cliente conhecido que não esteja em clientes_exp.
# Exemplo crítico: CIMED é PED, mesmo aparecendo em baú/container e mesmo com texto ROQUETTE na embalagem.

# Se o classificador ficar abaixo disso, o arquivo vai para Não Processados.
# Melhor perder 1 arquivo para revisão do que renomear errado e criar bagunça industrial 4.0 freestyle.
CONFIANCA_MINIMA_CLASSIFICACAO = 45

# SELENIUM
chrome_options = webdriver.ChromeOptions()
prefs = {"download.default_directory": str(DOWNLOAD_DIR)}
chrome_options.add_experimental_option("prefs", prefs)
# Mantém navegador aberto no final
chrome_options.add_experimental_option("detach", True)

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)
wait = WebDriverWait(driver, 60) # Tempo limite geral (e para a extração do OCR)

# URL DO SITE
OCR_URL = "https://roqgpt-frontend.proudcliff-f97e2089.westeurope.azurecontainerapps.io/OCR"

# ---------------- FUNÇÕES DE APOIO ----------------


def normalizar_texto_ocr(texto):
    """
    Normaliza texto vindo do OCR para facilitar regex e comparação.
    """
    if not texto:
        return ""

    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ASCII", "ignore").decode("ASCII")
    texto = texto.upper()

    substituicoes = {
        "E XP": "EXP",
        "EX P": "EXP",
        "E.X.P": "EXP",
        "E X P": "EXP",
        "E-X-P": "EXP",

        "P ED": "PED",
        "PE D": "PED",
        "P.E.D": "PED",
        "P E D": "PED",
        "PEDI DO": "PEDIDO",

        "CIMED S.A.": "CIMED SA",
        "CIMED S A": "CIMED SA",
        "EMS S.A.": "EMS SA",
        "EMS S A": "EMS SA",

        "CONTAINER": "CONTEINER",
        "EXPORTACION": "EXPORTACAO",

        # Correções vistas nos pacotes novos
        "BARRENTZ": "BARENTZ",
        "ROQUETTE FERRES": "ROQUETTE FRERES",
        "ROQUETTE FERRERS": "ROQUETTE FRERES",
        "ROQUETTE FRERES": "ROQUETTE FRERES",
        "BRAIN F": "BRAINF",
        "BRAINF.": "BRAINF",
        "FARMA LOGISTIC": "FARMA LOGIST",
        "FARMA LOGISTICA": "FARMA LOGIST",
        "MARK SAN": "MARKSANS",
        "MARKSAN": "MARKSANS",
    }

    for origem, destino in substituicoes.items():
        texto = texto.replace(origem, destino)

    # Mantém letras, números e separadores úteis.
    texto = re.sub(r"[^A-Z0-9:/\-\s×X]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()

    return texto


def normalizar_chave(texto):
    """
    Normaliza texto para comparação forte:
    remove acentos, espaços, pontuação e símbolos.
    """
    texto = normalizar_texto_ocr(texto)
    return re.sub(r"[^A-Z0-9]", "", texto)


def corrigir_numero_ocr(token):
    """
    Corrige erros comuns do OCR em números de pedido/EXP.
    Exemplo: 24I54 -> 24154, Z4154 -> 24154.
    """
    if not token:
        return None

    token = token.upper().strip()
    mapa = str.maketrans({
        "Z": "2",
        "O": "0",
        "I": "1",
        "L": "1",
        "S": "5",
        "B": "8",
    })
    numero = token.translate(mapa)
    numero = re.sub(r"[^0-9]", "", numero)

    if re.fullmatch(r"2\d{4}", numero):
        return numero

    return None


# ---------------- REGRAS DE CLIENTE / TIPO ----------------
# A regra abaixo foi montada olhando o pacote de fotos enviado:
# - CIMED, TEUTO, UNIAO Q MG, LABOFARMA, PRATI, EMS, OPELLA e IQUINE aparecem como PED.
# - ROQUETTE FR e AZELIS INDIA aparecem com marcador EXP explícito.
# - ROQUETTE sozinho NÃO vale nada, porque aparece como marca/produto na embalagem.

CLIENTES_PED_ALIASES = {
    # Casos vistos no pacote de fotos
    "CIMED",
    "CIMED SA",
    "TEUTO",
    "UNIAO Q MG",
    "UNIAO Q M G",
    "UNIAO Q",
    "UNIAO QUIMICA",
    "LABOFARMA",
    "LABOFARMA PB",
    "LABOFARMA PE",
    "PRATI",
    "EMS",
    "EMS SA",
    "OPELLA",
    "OPELLA H",
    "OPELLA HEALTH",
    "IQUINE",
    "IQUINI",

    # Casos novos vistos nos pacotes 20260428/20260429
    "BARENTZ BR",
    "BARRENTZ BR",
    "BARENTZ BRASIL",
    "BRAINF",
    "BRAINF ITAPE",
    "BRAINFARMA ITAPE",
    "FARMA LOGIST",
    "FARMA LOGISTICA",
    "FARMA LOGISTIC",
    "NEOSOR",
    "GEOLABRA",
    "NOVOMED",
    "NOVIDAM",

    # Clientes domésticos da sua lista principal
    "BRAINFARMA",
    "COSMED",
    "DSM",
    "DSV",
    "TOVANI",
    "CARGILL",
    "EUROFARMA",
    "GLOBALFOOD",
    "MULTILAB",
    "NOVAMED",
    "SANOFI",
    "TAKEDA",
    "TATE",
    "MONDELEZ",
    "ACHE",
    "ALIBRA",
    "ALLPREMIUM",
    "ANOVIS",
    "DANISCO",
    "GEOLAB",
    "HALEON",
    "HEXUS",
    "HIPOLABOR",
    "IHARABRAS",
    "PHARLAB",
    "SANDOZ",
    "BLUMOS",
}

CLIENTES_EXP_ALIASES = {
    # Casos vistos no pacote de fotos
    "ROQUETTE FR",
    "ROQUETTE MEX",
    "ROQUETTE MEXICO",
    "AZELIS INDIA",
    "AZELIS INDA",
    "BESTAR",
    "MARKSANS",
    "MARKSAN",
    "MARK SANS",
    "ROQUETTE FRERES",
    "ROQUETTE FERRES",
    "ROQUETTE FERRERS",
    "ROQUETTE FRERES SA",

    # Clientes de exportação da sua lista
    "MARITIME",
    "BRENNTAG",
    "DEPOTCHEM",
    "AZELIS",
    "ORKILA",
    "CALTECH",
    "BIESTERFELD",
    "GUANGZHOU",
    "REMEDICA",
    "QUIMIDROGA",
    "UNI PHARMA",
    "UNIPHARMA",
    "BARENTZ",
    "SIGNET",
    "GIUSTO",
    "IMCOPHARMA",
    "LABORATORIO CHILE",
    "NESTLE",
    "GLAXOSSMITHKLINE",
    "VICENTE SCAVONE",
    "IDUN",
    "INSTITUTO QUIMIOTERAPICO",
    "QUIMTIA",
    "TEVA",
}

PALAVRAS_PRODUTO_OU_RUIDO = {
    "ROQUETTE",
    "MICROCEL",
    "MANGCEL",
    "MANGEL",
    "NOCEL",
    "MICROCK",
    "MICOACHI",
    "SOLUTAB",
    "TABULOSE",
    "TABULOSE SC",
    "GLYCOLYS",
    "GLYCOLIS",
    "GLYCOLATE",
    "AMIDOGLICOLATO",
    "SODIUM STARCH",
    "LOTE",
    "LOT",
    "QTY",
    "MADE IN BRAZIL",
}


def _alias_em_texto(texto_normalizado, alias):
    """
    Confere alias com segurança.
    Para alias curto, exige palavra inteira.
    Para alias longo, aceita chave compactada para tolerar espaços/traços do OCR.
    """
    alias_norm = normalizar_texto_ocr(alias)
    alias_key = normalizar_chave(alias)
    texto_key = normalizar_chave(texto_normalizado)

    if not alias_key:
        return False

    # Alias curto tipo EMS precisa de borda de palavra para não bater dentro de outra palavra.
    if len(alias_key) <= 3:
        padrao = r"(?<![A-Z0-9])" + re.escape(alias_norm) + r"(?![A-Z0-9])"
        return bool(re.search(padrao, texto_normalizado))

    return alias_key in texto_key


def detectar_cliente_regrado(texto):
    """
    Retorna (cliente, tipo, confianca):
      tipo = "PED", "EXP" ou None.

    Regra importante:
    - Cliente PED visto no pacote vence qualquer ruído de embalagem.
    - ROQUETTE sozinho é ignorado.
    - EXP por cliente só quando o alias de exportação aparece completo.
    """
    t = normalizar_texto_ocr(texto)

    if not t:
        return None, None, 0

    # 1) PED conhecido primeiro. Isso impede CIMED/TEUTO/PRATI virar EXP por causa de ROQUETTE no saco.
    for alias in sorted(CLIENTES_PED_ALIASES, key=lambda a: len(normalizar_chave(a)), reverse=True):
        if _alias_em_texto(t, alias):
            return alias, "PED", 100

    # 2) EXP conhecido. ROQUETTE só entra quando vem com FR/MEX/MEXICO.
    for alias in sorted(CLIENTES_EXP_ALIASES, key=lambda a: len(normalizar_chave(a)), reverse=True):
        if _alias_em_texto(t, alias):
            return alias, "EXP", 100

    return None, None, 0


def cliente_eh_exp(nome_cliente):
    """
    Mantido por compatibilidade, mas agora é conservador.
    """
    if not nome_cliente:
        return False

    cliente_chave = normalizar_chave(nome_cliente)
    exp_chaves = {normalizar_chave(c) for c in CLIENTES_EXP_ALIASES}

    return cliente_chave in exp_chaves


def encontrar_cliente_aproximado(texto, limite_score=95):
    """
    Versão segura.

    As versões anteriores ainda podiam errar porque fuzzy matching em texto grande encontra falso positivo.
    Aqui a regra é:
    1. Primeiro procura aliases exatos/normalizados.
    2. Fuzzy só roda em linhas curtas, com score muito alto.
    3. Palavras de embalagem/produto são ignoradas.
    """
    cliente, tipo, confianca = detectar_cliente_regrado(texto)

    if cliente:
        print(f"✅ Cliente detectado por regra: {cliente} ({tipo})")
        return cliente, confianca

    if not texto:
        return None, None

    t = normalizar_texto_ocr(texto)
    linhas = [l.strip() for l in re.split(r"[\n\r]+", t) if l.strip()]
    escolhas = sorted((CLIENTES_PED_ALIASES | CLIENTES_EXP_ALIASES) - PALAVRAS_PRODUTO_OU_RUIDO)

    melhor = None

    for linha in linhas:
        # Linha gigante é corpo de página/menu; fuzzy nela é fábrica de erro.
        if len(linha) > 80:
            continue

        for cliente_ref in escolhas:
            if len(normalizar_chave(cliente_ref)) < 4:
                continue

            score = fuzz.token_set_ratio(normalizar_texto_ocr(cliente_ref), linha)

            if score >= limite_score:
                if not melhor or score > melhor[1]:
                    melhor = (cliente_ref, score)

    if melhor:
        cliente_ref, score = melhor
        print(f"✅ Cliente detectado por fuzzy seguro: {cliente_ref} (Score: {score})")
        return cliente_ref, score

    print("⚠️ Cliente não identificado com confiança suficiente.")
    return None, None


def preparar_pdf(imagem_origem):
    """
    Converte a imagem em PDF de UMA ÚNICA PÁGINA.

    Importante:
    - Não cria páginas extras. O site deu erro 500 com PDF multipágina.
    - Mantém o comportamento do script antigo.
    """
    img = Image.open(imagem_origem)
    img = ImageOps.exif_transpose(img)

    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    else:
        img = img.convert("RGB")

    pdf_temp = pasta_processando / "Renomear.pdf"
    img.save(pdf_temp, "PDF", resolution=100.0)
    return pdf_temp


def contexto_tem_lot_ou_lote(contexto):
    contexto = normalizar_texto_ocr(contexto)
    return bool(re.search(r"\b(?:LOT|LOTE|LOTE:|LOT:)\b", contexto))


def extrair_linhas_normalizadas(texto):
    """
    Retorna linhas úteis do OCR e também quebra partes de tabelas/figuras.
    """
    if not texto:
        return []

    bruto = texto.replace("<tr>", "\n").replace("</tr>", "\n")
    bruto = bruto.replace("<td>", " ").replace("</td>", " ")
    bruto = bruto.replace("<figure>", "\n").replace("</figure>", "\n")

    linhas = []
    for linha in re.split(r"[\n\r]+", bruto):
        linha = normalizar_texto_ocr(linha)
        if linha:
            linhas.append(linha)

    return linhas


def encontrar_candidatos_numero(texto, cliente_detectado=None):
    """
    Encontra candidatos 2xxxx e pontua qual parece ser pedido/EXP.

    Evita pegar lote, quantidade e ruído.
    """
    t = normalizar_texto_ocr(texto)
    linhas = extrair_linhas_normalizadas(texto)
    padrao_numero = r"([2Z][0-9OILSB]{4})"

    candidatos = {}

    def adicionar(numero, score, motivo, contexto):
        numero = corrigir_numero_ocr(numero)
        if not numero:
            return

        contexto_norm = normalizar_texto_ocr(contexto)

        # Nunca usar número que parece lote.
        # Ex.: LOT: 265000328 pode virar 26500 se o OCR quebrar espaço.
        # Mas não penaliza o pedido só porque a mesma linha também tem LOT depois dele.
        pos_numero = contexto_norm.find(numero)
        janela_antes = contexto_norm[max(0, pos_numero - 30):pos_numero] if pos_numero >= 0 else contexto_norm[:40]

        if re.search(r"\b(?:LOT|LOTE)\s*[:\-]?\s*$", janela_antes) and not re.search(r"\b(?:EXP|PED|PEDIDO)\b", contexto_norm):
            score -= 160
            motivo += " | penalizado: número parece LOT/LOTE"

        if numero not in candidatos:
            candidatos[numero] = {
                "numero": numero,
                "score": 0,
                "motivos": [],
                "contextos": []
            }

        candidatos[numero]["score"] += score
        candidatos[numero]["motivos"].append(motivo)
        candidatos[numero]["contextos"].append(contexto_norm[:180])

    # 1) Padrão mais forte: marcador grudado no número.
    for m in re.finditer(rf"\b(?:EXP|EXPORT|EXPORTACAO)(?:\s*[:\-]\s*|\s+){padrao_numero}\b", t):
        adicionar(m.group(1), 300, "número ligado a EXP/EXPORT", t[max(0, m.start()-50):m.end()+50])

    for m in re.finditer(rf"\b(?:PED|PEDIDO)(?:\s*[:\-]\s*|\s+){padrao_numero}\b", t):
        adicionar(m.group(1), 300, "número ligado a PED/PEDIDO", t[max(0, m.start()-50):m.end()+50])

    # 2) Linha por linha: geralmente o pedido está na mesma linha do cliente.
    cliente_key = normalizar_chave(cliente_detectado or "")

    for linha in linhas:
        for m in re.finditer(rf"\b{padrao_numero}\b", linha):
            numero = m.group(1)
            score = 20
            motivos = ["candidato 2xxxx"]

            linha_key = normalizar_chave(linha)

            if cliente_key and cliente_key in linha_key:
                score += 100
                motivos.append("mesma linha do cliente")

            if re.search(r"\b(?:CIMED|TEUTO|UNIAO|LABOFARMA|PRATI|EMS|OPELLA|IQUINE|AZELIS|ROQUETTE)\b", linha):
                score += 60
                motivos.append("linha com nome de cliente")

            if re.search(r"\b(?:MICROCEL|SOLUTAB|MANGCEL|MC\s*-\s*102|35\s*[X×]\s*15|24\s*[X×]\s*25)\b", linha):
                score += 25
                motivos.append("linha com produto/volume")

            if re.search(r"\b(?:EXP|EXPORT|EXPORTACAO|PED|PEDIDO)\b", linha):
                score += 120
                motivos.append("linha com marcador EXP/PED")

            adicionar(numero, score, " | ".join(motivos), linha)

    # 3) Varredura global.
    for m in re.finditer(rf"\b{padrao_numero}\b", t):
        contexto = t[max(0, m.start()-80):m.end()+80]
        adicionar(m.group(1), 10, "varredura global 2xxxx", contexto)

    if not candidatos:
        return []

    return sorted(candidatos.values(), key=lambda c: c["score"], reverse=True)


def detectar_prefixo_e_pedido(texto, nome_cliente_exato=None):
    """
    Classificador V5 - regras novas dos pacotes 20260428/20260429.

    Prioridade:
    1. Cliente PED forte primeiro.
    2. EXP/PED explícito com separador real perto do número.
    3. Cliente EXP seguro.
    4. Sinais fortes de exportação.
    5. Se não tiver confiança, manda para Não Processados.
    """
    t = normalizar_texto_ocr(texto)

    if not t:
        return None, None, 0, "Texto vazio"

    cliente_detectado, tipo_cliente, confianca_cliente = detectar_cliente_regrado(t)

    # Se o cliente veio da função anterior, usa como apoio, mas sem deixar fuzzy mandar sozinho.
    if not cliente_detectado and nome_cliente_exato:
        cliente_detectado = nome_cliente_exato
        tipo_cliente = "EXP" if cliente_eh_exp(nome_cliente_exato) else "PED"
        confianca_cliente = 80

    candidatos = encontrar_candidatos_numero(t, cliente_detectado)

    if not candidatos:
        return None, None, 0, "Nenhum número 2xxxx encontrado"

    melhor = candidatos[0]
    numero = melhor["numero"]

    padrao_numero = r"([2Z][0-9OILSB]{4})"

    # 1) Cliente PED conhecido ganha primeiro.
    # Isso evita o erro mais perigoso: uma foto PED virar EXP por causa de texto velho da página,
    # nome de arquivo tipo EXP24000.jpg, ou palavra solta fora do rótulo principal.
    if tipo_cliente == "PED":
        return "PED", numero, 98, f"Cliente PED detectado: {cliente_detectado}. Motivos número: {'; '.join(melhor['motivos'][:3])}"

    # 2) EXP explícito: só aceita EXP separado por hífen, dois-pontos ou espaço.
    # Não aceita EXP24000 colado, porque isso costuma vir de nome de arquivo antigo/ruído da página.
    padroes_exp_fortes = [
        rf"\b(?:EXP|EXPORT|EXPORTACAO)(?:\s*[:\-]\s*|\s+){padrao_numero}\b",
        rf"\b(?:ROQUETTE\s+(?:FR|FRERES|FERRES|FERRERS|MEX|MEXICO)|AZELIS\s+INDIA|IDUN|BESTAR|MARKSANS?)\s+(?:EXP(?:\s*[:\-]\s*|\s+))?{padrao_numero}\b",
        rf"\b{padrao_numero}\b\s*[:\-]\s*(?:EXP|EXPORT|EXPORTACAO)\b",
    ]

    for padrao in padroes_exp_fortes:
        m = re.search(padrao, t)
        if m:
            n = corrigir_numero_ocr(m.group(1))
            if n:
                return "EXP", n, 99, "Marcador EXP/exportação explícito perto do número"

    # 3) PED explícito.
    padroes_ped_fortes = [
        rf"\b(?:PED|PEDIDO)(?:\s*[:\-]\s*|\s+){padrao_numero}\b",
        rf"\b{padrao_numero}\b\s*[:\-]\s*(?:PED|PEDIDO)\b",
    ]

    for padrao in padroes_ped_fortes:
        m = re.search(padrao, t)
        if m:
            n = corrigir_numero_ocr(m.group(1))
            if n:
                return "PED", n, 99, "Marcador PED/PEDIDO explícito perto do número"

    # 4) Cliente EXP conhecido.
    if tipo_cliente == "EXP":
        return "EXP", numero, 96, f"Cliente EXP detectado: {cliente_detectado}. Motivos número: {'; '.join(melhor['motivos'][:3])}"

    # 4) Sinais globais fortes de exportação, sem cliente PED.
    tem_export_forte = bool(re.search(
        r"\b(?:COMMERCIAL\s+INVOICE|INVOICE|PACKING\s+LIST|EXPORT|EXPORTACAO|EXP)\b",
        t
    ))

    if tem_export_forte:
        return "EXP", numero, 85, f"Sinal forte de exportação sem cliente PED. Motivos número: {'; '.join(melhor['motivos'][:3])}"

    # 5) Se o número aparece em linha com cliente/produto, mas não achou o cliente no alias,
    # é melhor revisar do que chutar.
    return None, numero, min(70, melhor["score"]), f"Prefixo duvidoso. Melhor candidato: {numero}. Motivos: {'; '.join(melhor['motivos'][:4])}"


def extrair_texto():
    try:
        return driver.find_element(By.TAG_NAME, "body").text
    except:
        return ""


def caminho_sem_sobrescrever(pasta, nome_arquivo):
    """
    Retorna um caminho disponível sem sobrescrever arquivo existente.
    """
    destino = pasta / nome_arquivo

    if not destino.exists():
        return destino

    stem = destino.stem
    suffix = destino.suffix
    contador = 1

    while True:
        novo = pasta / f"{stem}-{contador}{suffix}"
        if not novo.exists():
            return novo
        contador += 1


def mover_nao_processados(imagem):
    destino = caminho_sem_sobrescrever(pasta_nao_proc, imagem.stem + ".jpg")

    try:
        img = Image.open(imagem)
        img = ImageOps.exif_transpose(img).convert("RGB")
        img.save(destino, "JPEG")
        print(f"🚫 Movido para NÃO PROCESSADOS: {destino.name}")
    except Exception as e:
        print(f"⚠️ Erro ao salvar em Não Processados: {e}")

    try:
        os.remove(imagem)
        print("🗑️ Original excluído.")
    except:
        pass


def aguardar_conversao_ocr(timeout=90):
    """
    Aguarda o site concluir o upload/conversão.

    Regra nova:
    - Só considera pronto quando aparecer: "File successfully converted!"
    - Depois disso, o processo principal ainda espera 3 segundos antes de ler o texto.
    - Se aparecer AxiosError/500, falha imediatamente para não tentar classificar lixo.
    """
    print(f"⏳ Aguardando 'File successfully converted!' (máx {timeout}s)...")

    def checar_status(_driver):
        texto_pagina = extrair_texto()
        texto_lower = texto_pagina.lower()

        erros_fortes = [
            "axioserror",
            "request failed with status code",
            "status code 500",
            "status code 400",
            "status code 413",
            "network error",
        ]

        if any(erro in texto_lower for erro in erros_fortes):
            return ("erro", texto_pagina)

        if "file successfully converted" in texto_lower:
            return ("sucesso", texto_pagina)

        return False

    return WebDriverWait(driver, timeout).until(checar_status)


# ---------------- FUNÇÃO PRINCIPAL DE PROCESSAMENTO ----------------

def processar_arquivo(imagem_origem):
    print(f"\n📸 Processando: {imagem_origem.name}")
    pdf_temp = preparar_pdf(imagem_origem)

    # Captura tamanho inicial do texto (menus, rodapés, etc.)
    texto_antes = extrair_texto()
    tamanho_antes = len(texto_antes)

    print("🔎 Localizando campo de upload...")
    try:
        input_file = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']")))

        time.sleep(2)

        input_file.send_keys(str(pdf_temp))
        print("⬆️ Arquivo enviado.")

        time.sleep(5)
    except TimeoutException:
        print("❌ ERRO: Campo de upload não encontrado ou travado.")
        mover_nao_processados(imagem_origem)
        return

    # --- LÓGICA DE ESPERA PELA CONVERSÃO/OCR ---
    try:
        status, texto_status = aguardar_conversao_ocr(timeout=90)

        if status == "erro":
            print("❌ O site retornou erro ao converter o PDF.")
            print("📄 Trecho da página:")
            print(texto_status[-1000:])
            mover_nao_processados(imagem_origem)
            return

        print("✅ File successfully converted! detectado.")
        print("⏳ Esperando 3 segundos para o texto terminar de renderizar...")
        time.sleep(3)

    except TimeoutException:
        print("⚠️ Timeout: a mensagem 'File successfully converted!' não apareceu dentro do limite.")
        mover_nao_processados(imagem_origem)
        return

    texto = extrair_texto()

    # Pequena folga extra: às vezes o site mostra sucesso antes do texto crescer no DOM.
    # Não fica preso: tenta por poucos segundos e segue o fluxo normal.
    prazo_extra = time.time() + 8
    while len(texto) <= tamanho_antes + 10 and time.time() < prazo_extra:
        time.sleep(1)
        texto = extrair_texto()

    # LOG DO TEXTO COMPLETO
    if texto:
        print("\n" + "=" * 40)
        print(f"📄 CONTEÚDO ({len(texto)} chars):")
        print("-" * 40)
        print(texto.strip())
        print("-" * 40)
        print("=" * 40 + "\n")

    if not texto or len(texto) <= tamanho_antes + 10:
        print("❌ Texto inválido/vazio (Não detectou o documento).")
        mover_nao_processados(imagem_origem)
        return

    # --- BUSCA CLIENTE ---
    nome_cliente_exato, score_cliente = encontrar_cliente_aproximado(texto)

    # --- DETECÇÃO INTELIGENTE DE PREFIXO + PEDIDO ---
    prefixo, pedido, confianca, motivo = detectar_prefixo_e_pedido(texto, nome_cliente_exato)

    print("\n" + "=" * 40)
    print("🧠 RESULTADO DA CLASSIFICAÇÃO")
    print(f"Prefixo: {prefixo}")
    print(f"Pedido/EXP: {pedido}")
    print(f"Confiança: {confianca}")
    print(f"Cliente detectado: {nome_cliente_exato} | Score: {score_cliente}")
    print(f"Motivo: {motivo}")
    print("=" * 40 + "\n")

    if not pedido:
        print("❌ Pedido/EXP não encontrado.")
        mover_nao_processados(imagem_origem)
        return

    if not prefixo or confianca < CONFIANCA_MINIMA_CLASSIFICACAO:
        print("⚠️ Prefixo duvidoso. Melhor mandar para NÃO PROCESSADOS do que renomear errado.")
        mover_nao_processados(imagem_origem)
        return

    # --- RENOMEAR ---
    base = f"{prefixo}{pedido}"

    pdf_final = pasta_processando / f"{base}.pdf"
    if pdf_final.exists():
        c = 1
        while (pasta_processando / f"{base}_{c}.pdf").exists():
            c += 1
        pdf_final = pasta_processando / f"{base}_{c}.pdf"

    os.rename(pdf_temp, pdf_final)

    jpg_final = pdf_final.with_suffix(".jpg")
    try:
        imagens = convert_from_path(str(pdf_final), poppler_path=poppler_path)
        imagens[0].save(jpg_final, "JPEG")
        os.remove(pdf_final)
    except Exception as e:
        print(f"❌ Erro conversão JPG: {e}")
        mover_nao_processados(imagem_origem)
        return

    destino = pasta_prontas
    nome_base = jpg_final.stem
    temp_jpg = str(jpg_final)
    contador = 1
    nome_final = f"{nome_base}.jpg"
    caminho_final = destino / nome_final
    while caminho_final.exists():
        nome_final = f"{nome_base}-{contador}.jpg"
        caminho_final = destino / nome_final
        contador += 1

    shutil.move(temp_jpg, caminho_final)
    print(f"✅ Criado e movido: {nome_final}")

    try:
        os.remove(imagem_origem)
        print("🗑️ Original excluído.")
    except Exception as e:
        print(f"⚠️ Erro exclusão: {e}")


# ---------------- LOOP PRINCIPAL ----------------

while True:
    imagens = [p for p in pasta_fotos.glob("*") if p.suffix.lower() in [".jpg", ".jpeg", ".png", ".bmp", ".webp"]]

    if not imagens:
        print("\n🎉 Finalizado! Nenhuma imagem restante.")
        print("🌐 O navegador permanecerá aberto.")
        break

    # 1. SEMPRE RECARREGA A PÁGINA (REFRESH)
    print("🔄 Recarregando página (Refresh)...")
    try:
        driver.get(OCR_URL)
        time.sleep(5)
    except Exception as e:
        print(f"⚠️ Erro ao recarregar: {e}")
        time.sleep(5)
        continue

    # 2. Processa o arquivo
    processar_arquivo(imagens[0])

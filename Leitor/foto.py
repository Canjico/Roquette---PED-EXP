import os
import cv2
import pytesseract
import re
import numpy as np
import time

pytesseract.pytesseract.tesseract_cmd = r"C:\Users\7304078\Downloads\Leitor-20250221T181402Z-001\Leitor\Tesseract\tesseract.exe"

padroes_empresas = {
    "TEUTO": r"\bTEUTO\b",
    "BRAINFARMA": r"\bBRAINFARMA\b",
    "COSMED": r"\bCOSMED\b",
    "NOVAMED": r"\bNOVAMED\b",
    "EMS-HORT e DF": r"EMS[-\s]?HORT\s*E\s*DF",
    "MULTILAB": r"\bMULTILAB\b",
    "GEOLAB": r"\bGEOLAB\b",
    "UNIÃO QUIMICA - DF e MG": r"UNIAO\s+QUIMICA.*DF.*MG",
    "UNIÃO QUIMICA EMBU GUAÇU": r"UNIAO\s+QUIMICA.*EMBU",
    "PRATI DONADUZZI": r"PRATI.*DONADUZZI",
    "ANOVIS": r"\bANOVIS\b",
    "UNIÃO QUIMICA GUARULHOS": r"UNIAO\s+QUIMICA.*GUARULHOS",
    "PHARLAB": r"\bPHARLAB\b",
    "LAB. GLOBO": r"\bGLOBO\b",
    "PF CONSUMER (Haleon)": r"HALEON|PF\s+CONSUMER",
    "BARENTZ BRASIL": r"\bBARENTZ\b",
    "TAKEDA": r"\bTAKEDA\b",
    "ACHE": r"\bACHE\b",
    "LABOFARMA": r"\bLABOFARMA\b",
    "GEMACOM": r"\bGEMACOM\b",
    "GLOBALFOOD": r"\bGLOBALFOOD\b",
    "SANOFI MEDLEY": r"SANOFI|MEDLEY",
    "ALIBRA": r"\bALIBRA\b",
    "BALLAGRO": r"\bBALLAGRO\b",
    "BRAINFARMA - ITAPECERICA DA SERRA": r"BRAINFARMA.*ITAPECERICA",
    "CIMED": r"\bCIMED\b",
    "DANISCO": r"\bDANISCO\b",
    "DSM": r"\bDSM\b",
    "EUROFARMA": r"\bEUROFARMA\b",
    "HEXUS": r"\bHEXUS\b",
    "HIPOLABOR": r"\bHIPOLABOR\b",
    "LALLEMAND": r"\bLALLEMAND\b",
    "LIOTÉCNICA": r"\bLIOTECNICA\b",
    "PÉPSICO": r"PEPSICO",
    "SANDOZ": r"\bSANDOZ\b",
    "ALL PREMIUM": r"ALL\s+PREMIUM",
    "UNIÃO QUIMICA INTERNACIONAL": r"UNIAO\s+QUIMICA.*INTERNACIONAL",
    "CARGIL AGRÍCOLA": r"CARGILL"
}

def identificar_empresa_regex(texto_extraido):
    texto_upper = texto_extraido.upper()
    for empresa, padrao in padroes_empresas.items():
        if re.search(padrao, texto_upper):
            # DEBUG opcional: print(f"DEBUG: Match exato com {empresa}")
            return True
    return False

def ajustar_brilho_contraste(imagem, alpha=1.0, beta=0):
    return cv2.convertScaleAbs(imagem, alpha=alpha, beta=beta)

def aplicar_nitidez(imagem):
    kernel = np.array([[0, -1, 0],
                       [-1, 5, -1],
                       [0, -1, 0]])
    return cv2.filter2D(imagem, -1, kernel)

def morfologia(imagem, tipo='dilate'):
    kernel = np.ones((2, 2), np.uint8)
    if tipo == 'dilate':
        return cv2.dilate(imagem, kernel, iterations=1)
    elif tipo == 'erode':
        return cv2.erode(imagem, kernel, iterations=1)
    return imagem

def imagem_esta_embacada(gray_img, threshold=100):
    lap = cv2.Laplacian(gray_img, cv2.CV_64F)
    variancia = lap.var()
    return variancia < threshold

def tentar_ocr_simples(imagem_bgr):
    gray = cv2.cvtColor(imagem_bgr, cv2.COLOR_BGR2GRAY)
    # Blur pra tirar ruído
    gray = cv2.medianBlur(gray, 3)
    # Threshold simples
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    config = '--oem 3 --psm 6'  # modo padrão, segmentação de bloco de texto
    texto = pytesseract.image_to_string(thresh, config=config)
    # Regex pra número (5 a 8 dígitos pra mais flexibilidade)
    match = re.search(r'\b\d{5,8}\b', texto)
    if match:
        return match.group()
    return None

def ocr_insano_com_timer(imagem_bgr, timeout=12):
    start_time = time.time()
    tentativas = 0
    resultados = []

    escalas = [1.0, 1.5, 2.0, 3.0]
    alphas = [1.0, 1.5, 2.0]
    betas = [0, 30, 60]
    psms = [3, 4, 6, 11, 12, 13]
    morfs = ['none', 'dilate', 'erode']

    gray = cv2.cvtColor(imagem_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.medianBlur(gray, 3)  # Blur leve pra tirar ruído

    # (Opcional) definir ROI (região de interesse) aqui pra cortar imagem e focar no número
    # Exemplo:
    # h, w = gray.shape
    # roi = gray[int(h*0.4):int(h*0.6), int(w*0.3):int(w*0.7)]
    # usar roi em vez de gray pra otimizar

    while time.time() - start_time < timeout:
        for scale in escalas:
            resized = cv2.resize(gray, (0, 0), fx=scale, fy=scale)
            for alpha in alphas:
                for beta in betas:
                    bright_contrast = ajustar_brilho_contraste(resized, alpha, beta)
                    sharpened = aplicar_nitidez(bright_contrast)
                    for morf in morfs:
                        morfed = morfologia(sharpened, morf)
                        _, thresh = cv2.threshold(morfed, 150, 255, cv2.THRESH_BINARY)
                        for psm in psms:
                            tentativas += 1
                            config = f'--oem 3 --psm {psm}'
                            texto = pytesseract.image_to_string(thresh, config=config)
                            match = re.search(r'\b\d{5,8}\b', texto)
                            if match:
                                resultados.append({
                                    'numero': match.group(),
                                    'psm': psm,
                                    'scale': scale,
                                    'alpha': alpha,
                                    'beta': beta,
                                    'morf': morf,
                                    'tentativa': tentativas,
                                    'texto': texto
                                })
                                return resultados
                            if time.time() - start_time >= timeout:
                                break
                        if time.time() - start_time >= timeout:
                            break
                    if time.time() - start_time >= timeout:
                        break
                if time.time() - start_time >= timeout:
                    break
            if time.time() - start_time >= timeout:
                break

    if imagem_esta_embacada(gray):
        print("Imagem muito embaçada, não consegui identificar o número.")
    else:
        print("Imagem ok, mas número não encontrado depois de 1 minuto tentando.")

    return resultados

def renomear_com_sufixo(caminho_antigo, pasta, nome_base, extensao):
    novo_nome = f"{nome_base}{extensao}"
    novo_caminho = os.path.join(pasta, novo_nome)
    contador = 1

    while os.path.exists(novo_caminho):
        novo_nome = f"{nome_base}-{contador}{extensao}"
        novo_caminho = os.path.join(pasta, novo_nome)
        contador += 1

    os.rename(caminho_antigo, novo_caminho)
    return novo_nome

def verificar_prefixo_por_pdf(numero_pedido, pasta_pdf):
    tem_ped = tem_exp = False

    for root, _, arquivos in os.walk(pasta_pdf):
        if f"PED{numero_pedido}.pdf" in arquivos:
            tem_ped = True
        if f"EXP{numero_pedido}.pdf" in arquivos:
            tem_exp = True

    if tem_ped:
        return "PED"
    elif tem_exp:
        return "EXP"
    return None

if __name__ == "__main__":
    pasta = r"C:\Users\7304078\Downloads\Fotos para Renomear"
    pasta_pdf = r"C:\Users\7304078\OneDrive - Roquette\General - Logistic - Brazil\Documentos escaneados"
    extensoes = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']

    for nome_arquivo in os.listdir(pasta):
        if not any(nome_arquivo.lower().endswith(ext) for ext in extensoes):
            continue  # Pula arquivos que não são imagens

        caminho_arquivo = os.path.join(pasta, nome_arquivo)
        imagem = cv2.imread(caminho_arquivo)

        if imagem is None:
            print(f"Não consegui abrir a imagem: {nome_arquivo}")
            continue

        # Pega número pelo OCR
        numero = tentar_ocr_simples(imagem)
        if not numero:
            resultado_insano = ocr_insano_com_timer(imagem)
            if resultado_insano:
                numero = resultado_insano[0]['numero']

        if numero:
            # Verifica se tem PDF para prefixo correto
            prefixo_pdf = verificar_prefixo_por_pdf(numero, pasta_pdf)
            if prefixo_pdf:
                prefixo = prefixo_pdf
            else:
                # Se não achou PDF, decide prefixo pelo conteúdo da imagem
                texto_completo = pytesseract.image_to_string(imagem).upper()
                prefixo = "PED" if identificar_empresa_regex(texto_completo) else "EXP"

            extensao = os.path.splitext(nome_arquivo)[1]
            novo_nome_esperado = f"{prefixo}{numero}{extensao}"

            if nome_arquivo != novo_nome_esperado:
                novo_nome = renomear_com_sufixo(caminho_arquivo, pasta, f"{prefixo}{numero}", extensao)
                print(f"Arquivo {nome_arquivo} renomeado para: {novo_nome}")
            else:
                print(f"Arquivo {nome_arquivo} já está com o nome correto.")

        else:
            print(f"Número inválido ou não encontrado, pulando arquivo {nome_arquivo}")


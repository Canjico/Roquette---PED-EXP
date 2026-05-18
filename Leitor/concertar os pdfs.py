from pdf2image import convert_from_path
import pytesseract
from PIL import Image
import shutil
import re
from pathlib import Path

# Diretório base onde estão as pastas dos anos
DOCUMENTS_DIR = Path("C:/Users/7304078/OneDrive - Roquette/General - Logistic - Brazil/Documentos escaneados")

# Diretório base do próprio script
SCRIPT_DIR = Path(__file__).resolve().parent

# Pasta onde os PDFs problemáticos serão movidos
PASTA_CONCERTAR = DOCUMENTS_DIR / "Concertar"
PASTA_CONCERTAR.mkdir(parents=True, exist_ok=True)

# Lista de meses em português para correspondência
meses_portugues = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]

# Configuração do Tesseract
pytesseract.pytesseract.tesseract_cmd = str(SCRIPT_DIR / "Tesseract" / "tesseract.exe")
poppler_path = str(SCRIPT_DIR / "Poppler" / "Release-24.08.0-0" / "poppler-24.08.0" / "Library" / "bin")

# Expressão regular para capturar datas no formato dd/mm/aaaa ou dd-mm-aaaa
padrao_data = re.compile(r"\b(\d{2})[/-](\d{2})[/-](\d{4})\b")

# Arquivo para registrar PDFs sem data
arquivo_erros = SCRIPT_DIR / "pdfs_sem_data.txt"

def extrair_texto_pdf(pdf_path, dpi=300):
    """Converte o PDF em imagem e extrai texto via OCR."""
    imagens = convert_from_path(pdf_path, poppler_path=poppler_path, first_page=1, last_page=1, dpi=dpi)
    texto_extraido = "\n".join(pytesseract.image_to_string(imagem) for imagem in imagens)
    return texto_extraido

def mes_mais_provavel(mes_str):
    """Tenta identificar o mês mais provável baseado nos caracteres reconhecidos."""
    mes_str = mes_str.zfill(2)  # Garante que tenha dois dígitos (ex: "3" vira "03")

    candidatos = [f"{i:02d}" for i in range(1, 13)]

    def distancia_simples(a, b):
        return sum(1 for x, y in zip(a, b) if x != y)

    mais_proximo = min(candidatos, key=lambda c: distancia_simples(mes_str, c))
    print(f"⚠️ Corrigido mês '{mes_str}' para '{mais_proximo}' por similaridade")
    return int(mais_proximo)


def mover_pdfs():
    print("🚀 Iniciando script...")
    print(f"📁 Verificando a pasta: {PASTA_CONCERTAR}")

    arquivos_pdf = list(PASTA_CONCERTAR.glob("*.pdf"))
    print(f"📄 PDFs encontrados: {len(arquivos_pdf)}")

    if not arquivos_pdf:
        print("⚠️ Nenhum PDF para processar. Verifique se há arquivos na pasta 'Concertar'.")
        return

    with open(arquivo_erros, "a", encoding="utf-8") as erro_log:
        erro_log.write("PDFs que não tiveram data identificada:\n\n")

        for arquivo in arquivos_pdf:
            print(f"\n🔍 Processando: {arquivo.name}")
            try:
                texto_pdf = extrair_texto_pdf(arquivo, dpi=300)
            except Exception as e:
                print(f"❌ Erro ao converter PDF {arquivo.name}: {e}")
                continue

            match = padrao_data.search(texto_pdf)
            if match:
                dia, mes, ano_extraido = match.groups()
                mes_corrigido = mes_mais_provavel(mes)

                if mes_corrigido:
                    mes_nome = meses_portugues[mes_corrigido - 1]
                    print(f"📅 Data detectada: {dia}/{mes_corrigido:02d}/{ano_extraido}")

                    destino = DOCUMENTS_DIR / f"EXP - {mes_nome}"
                    destino.mkdir(parents=True, exist_ok=True)
                    novo_caminho = destino / arquivo.name
                    try:
                        shutil.move(str(arquivo), str(novo_caminho))
                        print(f"✅ Movido para: {novo_caminho}")
                    except Exception as e:
                        print(f"❌ Erro ao mover arquivo: {e}")
                else:
                    print(f"❌ Mês inválido e não corrigível em {arquivo.name}")
            else:
                print(f"⚠️ Nenhuma data reconhecida em {arquivo.name}")
                erro_log.write(f"{arquivo.name}\n")

if __name__ == "__main__":
    mover_pdfs()

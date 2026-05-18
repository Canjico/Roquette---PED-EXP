from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
import ollama
import json
import tkinter as tk
from tkinter import messagebox
import threading
import shutil
import time
import glob
import os
from pathlib import Path
import pytesseract
import os

# Define um arquivo temporário como swap
os.environ["PYTHONMALLOC"] = "debug"
os.environ["PYTHONHASHSEED"] = "0"

ollama.pull("tinyllama")

# Diretório base do projeto
BASE_DIR = Path(__file__).resolve().parent


# Padrão para encontrar datas
padrao_data = r'\b(\d{2}[/-]\d{2}[/-]\d{4})\b'

# Configurações do sistema
DOWNLOAD_DIR = BASE_DIR / "Downloads"
CHROME_DRIVER_PATH = BASE_DIR / "chromedriver.exe"
PDF_PATTERN = "RoquetteBrasil*.*"
PDF_IDENTIFIER = "RoquetteBrasil"  # Parte do título do PDF para buscar
tesseract_path = BASE_DIR / "Tesseract" / "tesseract.exe"
pytesseract.pytesseract.tesseract_cmd = str(tesseract_path)
poppler_path = BASE_DIR / "Poppler" / "Release-24.08.0-0" / "poppler-24.08.0" / "Library" / "bin"

# Lista com as siglas dos estados brasileiros
siglas_estados = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", 
    "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO", "EX"
]

# Lista de meses em português
meses_portugues = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", 
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]

# Inicializar o WebDriver global
service = Service(CHROME_DRIVER_PATH)
chrome_options = webdriver.ChromeOptions()
prefs = {"download.default_directory": str(DOWNLOAD_DIR)}
chrome_options.add_experimental_option("prefs", prefs)
driver = webdriver.Chrome(service=service, options=chrome_options)

def login_to_outlook(email, password):
    """Realiza o login no Outlook usando o WebDriver global."""
    global driver  # Usa o WebDriver global
    driver.get("https://outlook.office.com/mail/")
    wait = WebDriverWait(driver, 20)
    try:
        print("Localizando campo de email...")
        email_input = wait.until(EC.presence_of_element_located((By.NAME, "loginfmt")))
        email_input.send_keys(email)
        email_input.send_keys(Keys.RETURN)
        print("Email inserido com sucesso.")

        print("Localizando campo de senha...")
        password_input = wait.until(EC.presence_of_element_located((By.NAME, "passwd")))
        password_input.send_keys(password)
        password_input.send_keys(Keys.RETURN)
        print("Senha inserida com sucesso.")

        try:
            confirm_button = wait.until(EC.element_to_be_clickable((By.ID, "idSIButton9")))
            confirm_button.click()
            print("Confirmação adicional concluída.")
        except Exception:
            print("Nenhuma confirmação adicional necessária.")
    except Exception as e:
        print(f"Erro durante o login: {e}")
        raise
    return driver

def apply_filter(driver):
    """Aplica o filtro de 'Não lidos' antes de buscar os emails.""" 
    wait = WebDriverWait(driver, 20)
    try:
        print("Aplicando filtro 'Não lidos'...")
        filter_button = wait.until(EC.presence_of_element_located((By.ID, "mailListFilterMenu")))
        filter_button.click()

        unread_filter = wait.until(EC.presence_of_element_located((By.XPATH, "//div[@role='menuitemradio' and @title='Não lidos']")))
        unread_filter.click()
        print("Filtro aplicado com sucesso.")
        time.sleep(8)
        wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(@aria-label, 'Não lidos')]")))
        print("Emails filtrados e prontos para download.")
    except Exception as e:
        print(f"Erro ao aplicar filtro: {e}")
        raise
    
def apply_filter_and_download(driver):
    """Aplica o filtro e faz o download do PDF após filtrar os emails.""" 
    apply_filter(driver)  

    wait = WebDriverWait(driver, 1000)  # O tempo de espera aqui é irrelevante, pois o loop continuará indefinidamente

    while True:
        try:
            print("Buscando email com remetente 'NO REPLY'...")
            email_element = wait.until(
                EC.presence_of_element_located((By.XPATH, "//span[contains(text(), 'NO REPLY')]"))
            )
            email_element.click()
            print("Email com remetente 'NO REPLY' encontrado e aberto.")
            break
        except Exception as e:
            print(f"Erro ao buscar email: {e}. Tentando novamente em 5 segundos...")
            time.sleep(5)

    try:
         #Buscar email com anexo
        print("Buscando email com anexo...")
        pdf_element = wait.until(
            EC.presence_of_element_located((By.XPATH, f"//div[contains(@title, '{PDF_IDENTIFIER}')]"))
        )
        pdf_element.click()
        print("Email com anexo encontrado e aberto.")

        #Baixar o anexo
        print("Baixando anexo...")
        download_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@name='Baixar']")))
        download_button.click()
        print("Download iniciado.")

        #Fechar o modal de download
        print("Fechando o modal clicando no botão 'X'...")
        close_button = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//i[@data-icon-name='Cancel']"))
        )
        close_button.click()
        print("Modal fechado com sucesso.")
    
    except TimeoutException:
        print("Erro: Não foi possível encontrar um dos elementos necessários durante o filtro e download.")
    except Exception as e:
        print(f"Erro durante o processo de filtro e download: {e}")
    
    # Marcar como Lido / Não lido
    try:
        seletores = [
            "//button[@aria-label='Lido / Não lido']",
            "//button[@id='552']",
            "//button[contains(@class, 'ms-Button') and contains(@class, 'root-284')]",
            "//span[contains(text(), 'Lido / Não lido')]/ancestor::button",
            "//button[@aria-describedby='id__502']",
            "//button[@data-unique-id='Ribbon-552']"
        ]

        # Tentativa de clicar em cada seletor
        for seletor in seletores:
            try:
                print(f"Tentando clicar com o seletor: {seletor}")
                # Espera até o botão ser clicável
                botao = wait.until(EC.element_to_be_clickable((By.XPATH, seletor)))

                # Vê se o botão está visível
                if not botao.is_displayed():
                    driver.execute_script("arguments[0].scrollIntoView();", botao)

                # Clica diretamente
                botao.click()
                print("Clique realizado com sucesso!")
                break  # Se o clique foi bem-sucedido, sai do loop
            except Exception as e:
                print(f"Erro ao tentar o seletor {seletor}: {e}")
                continue
        else:
            print("Nenhuma tentativa de clicar no botão foi bem-sucedida.")
    
    except Exception as e:
        print(f"Erro ao tentar marcar como Lido / Não lido: {e}")

def interpretar_texto(texto_extraido):
    """Usa IA do Ollama para extrair e organizar informações do pedido"""
    prompt = f"""
    Extraia as seguintes informações do texto:
    - Número do pedido (ignorar 17703 se aparecer)
    - Data no formato DD/MM/AAAA
    - Tipo do pedido: "PED" ou "EXP"
    - Pasta de destino correta com base no ano e mês da data

    Retorne a resposta no formato JSON:
    {{
        "numero_pedido": "...",
        "data": "...",
        "tipo": "PED/EXP",
        "pasta_destino": "..."
    }}

    Texto extraído do PDF:
    {texto_extraido}
    """

    try:
        resposta = ollama.chat(model="tinyllama", messages=[{"role": "user", "content": prompt}])
    except MemoryError:
        print("⚠️ Memória insuficiente! Reduzindo carga...")
        resposta = {"message": {"content": '{"numero_pedido": "N/A", "data": "N/A", "tipo": "N/A", "pasta_destino": "N/A"}'}}

    try:
        return json.loads(resposta["message"]["content"])  # Converte a resposta da IA para dicionário
    except json.JSONDecodeError:
        print("❌ Erro ao interpretar a resposta da IA.")
        return None


def process_downloaded_pdf():
    """Processa o PDF baixado, extrai o texto e usa IA para interpretar"""
    try:
        print("🔄 Convertendo PDF para texto...")

        # Pegando o arquivo PDF baixado mais recente
        pdf_files = glob.glob(os.path.join(DOWNLOAD_DIR, "RoquetteBrasil*.pdf"))
        if not pdf_files:
            print("❌ Nenhum arquivo PDF encontrado para processamento.")
            return

        pdf_files.sort(key=os.path.getmtime, reverse=True)  # Ordena pelos mais recentes
        downloaded_pdf = pdf_files[0]  # Pega o mais recente
        print(f"📂 Arquivo PDF encontrado: {downloaded_pdf}")

        # Pegando o arquivo de texto extraído
        output_txt_path = BASE_DIR / "texto_extraido.txt"

        if not os.path.exists(output_txt_path):
            print("❌ Arquivo de texto extraído não encontrado.")
            return

        with open(output_txt_path, 'r', encoding='utf-8') as txt_file:
            texto_extraido = txt_file.read()

        # Usando IA para interpretar os dados
        resultado = interpretar_texto(texto_extraido)

        if not resultado:
            print("❌ Erro ao interpretar o pedido. Verifique o texto extraído.")
            return

    except MemoryError:
        print("⚠️ Memória insuficiente ao processar o PDF! Tentando liberar recursos...")
        return

    except Exception as e:
        print(f"❌ Erro inesperado: {e}")


    # Pegando os dados do dicionário retornado pela IA
    pedido = resultado.get("numero_pedido")
    data = resultado.get("data")
    tipo = resultado.get("tipo")
    pasta_destino = resultado.get("pasta_destino")

    # Exibindo os dados obtidos
    print(f"📦 Pedido: {pedido}")
    print(f"📅 Data: {data}")
    print(f"📂 Tipo: {tipo}")
    print(f"📁 Pasta de Destino: {pasta_destino}")

    # Verifica se todos os dados necessários foram extraídos corretamente
    if not pedido or not data or not tipo or not pasta_destino:
        print("❌ Dados incompletos. O arquivo não será movido.")
        return

    # Definir o novo nome do arquivo
    novo_nome = f"{tipo}{pedido}.pdf"
    novo_caminho = os.path.join(DOWNLOAD_DIR, novo_nome)

    try:
        # Renomear o arquivo baixado
        os.rename(downloaded_pdf, novo_caminho)
        print(f"✅ Arquivo renomeado para: {novo_nome}")

        # Criar a pasta de destino, se não existir
        destino_final = os.path.join(DOWNLOAD_DIR, pasta_destino)
        os.makedirs(destino_final, exist_ok=True)

        # Mover o arquivo para a pasta correta
        shutil.move(novo_caminho, os.path.join(destino_final, novo_nome))
        print(f"✅ Arquivo movido para {destino_final}")

    except Exception as e:
        print(f"❌ Erro ao renomear ou mover o arquivo: {e}")


 # Clicando no botão após o processamento
    try:
        # Localizar o botão pelo ID
        botao = driver.find_element(By.ID, "mailListFilterMenu")
        # Realizar a ação de clique no botão
        botao.click()
        print("Botão clicado com sucesso!")
    except Exception as e:
        print(f"Erro ao clicar no botão: {e}")
            
def parar_execucao():
    global executando
    executando = False
    print("Execução parada.")
    messagebox.showinfo("Parado", "O processo foi interrompido.")

# Variável global para controlar o loop
executando = True

def executar_processo():
    """Executa o processo de filtragem e download."""
    global executando
    while executando:
        try:
            apply_filter_and_download(driver)  
            process_downloaded_pdf()  
            print("Processo concluído. Aguardando 10 segundos antes de reiniciar.")
            time.sleep(10) 
        except Exception as e:
            messagebox.showerror("Erro", f"Ocorreu um erro: {e}")
            executando = False  # Para o loop
    print("Execução parada.")

def iniciar_login():
    """Inicia o processo de login e execução contínua."""
    global executando
    email = entry_email.get()
    password = entry_password.get()

    if email and password:  # Verifica se os campos estão preenchidos
        try:
            # Faz login no Outlook e inicializa o WebDriver
            login_to_outlook(email, password)
            executando = True
            # Inicia o processo em uma nova thread
            threading.Thread(target=executar_processo, daemon=True).start()
        except Exception as e:
            messagebox.showerror("Erro", f"Ocorreu um erro durante o login: {e}")
    else:
        messagebox.showwarning("Erro", "Por favor, preencha todos os campos.")

# janela principal
root = tk.Tk()
root.title("LEITOR DE PDF")
root.geometry("480x300")
root.resizable(False, False)

# ícone da janela
root.iconbitmap(BASE_DIR / "icon.ico")

# widgets
label_email = tk.Label(root, text="Email:", font=("Arial", 12))
label_email.grid(row=0, column=0, padx=10, pady=10, sticky="e")  # Alinhado à direita

entry_email = tk.Entry(root, width=30, font=("Arial", 12))
entry_email.grid(row=0, column=1, padx=10, pady=10)

label_password = tk.Label(root, text="Senha:", font=("Arial", 12))
label_password.grid(row=1, column=0, padx=10, pady=10, sticky="e")  # Alinhado à direita

entry_password = tk.Entry(root, show="*", width=30, font=("Arial", 12))
entry_password.grid(row=1, column=1, padx=10, pady=10)

# Botão de login
button_login = tk.Button(root, text="Iniciar", command=iniciar_login, font=("Arial", 12), bg="blue", fg="white")
button_login.grid(row=2, columnspan=2, pady=20)

# Botão de parar
button_stop = tk.Button(root, text="Parar", command=parar_execucao, font=("Arial", 12), bg="red", fg="white")
button_stop.grid(row=3, columnspan=2, pady=20)

# loop da interface
root.mainloop()
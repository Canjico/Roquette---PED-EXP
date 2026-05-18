from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from pdf2image import convert_from_path
import tkinter as tk
from tkinter import messagebox
import threading
import shutil
import time
import glob
import re
import os
from pathlib import Path
import pytesseract

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
chrome_options = webdriver.ChromeOptions()
prefs = {"download.default_directory": str(DOWNLOAD_DIR)}
chrome_options.add_experimental_option("prefs", prefs)
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)


def login_to_outlook(email, password):
    global driver
    driver.get("https://outlook.office.com/mail/")
    
    wait = WebDriverWait(driver, 30)

    try:
        print("Tentando preencher o email...")
        email_input = wait.until(EC.presence_of_element_located((By.NAME, "loginfmt")))
        email_input.send_keys(email)
        email_input.send_keys(Keys.RETURN)
        print("Email enviado.")

        try:
            print("Verificando se o campo de senha será necessário...")
            wait_senha = WebDriverWait(driver, 7)
            password_input = wait_senha.until(EC.presence_of_element_located((By.NAME, "passwd")))
            password_input.send_keys(password)
            password_input.send_keys(Keys.RETURN)
            print("Senha inserida.")
        except TimeoutException:
            print("Campo de senha não apareceu. Provavelmente login automático.")

        try:
            wait_confirm = WebDriverWait(driver, 5)
            confirm_button = wait_confirm.until(EC.element_to_be_clickable((By.ID, "idSIButton9")))
            confirm_button.click()
            print("Clique de confirmação realizado.")
        except TimeoutException:
            print("Confirmação extra não necessária.")
        except Exception as e:
            print(f"Erro ao tentar clicar em confirmação extra: {e}. Mas vamos seguir.")

        try:
            wait.until(EC.presence_of_element_located((By.ID, "O365_MainLink_Mail")))
            print("Login bem-sucedido!")
        except Exception as e:
            print(f"Não localizou a caixa de entrada, mas vamos forçar continuar: {e}")

    except Exception as e:
        print(f"Erro ao fazer login: {e}")
        print("Forçando continuar o processo mesmo com erro.")
        # Aqui NÃO faz raise!

    return driver  # Sempre retorna o driver, com ou sem sucesso "oficial"


def apply_filter(driver):
    """Aplica o filtro de 'Não lidos' antes de buscar os emails.""" 
    wait = WebDriverWait(driver, 10)  # Tempo menor para evitar congelamento
    tentativas = 5  # Tenta clicar até 5 vezes
    sucesso = False

    time.sleep(8)
    for tentativa in range(tentativas):
        try:
            print(f"Tentando encontrar o botão do filtro... (Tentativa {tentativa + 1})")
            
            # Tenta encontrar o botão de filtro
            filter_button = wait.until(EC.element_to_be_clickable((By.ID, "mailListFilterMenu")))
            driver.execute_script("arguments[0].scrollIntoView();", filter_button)  # Rola até o botão
            filter_button.click()
            print("Botão do filtro clicado!")

            # Espera pelo menu abrir
            time.sleep(1)

            # Tenta encontrar e clicar no filtro 'Não lidos'
            unread_filter = wait.until(EC.element_to_be_clickable((
                By.XPATH, "//div[@role='menuitemradio' and @title='Não lidos']"
            )))
            unread_filter.click()
            print("Filtro 'Não lidos' aplicado!")
            
            sucesso = True
            break  # Sai do loop se funcionou
        except Exception as e:
            print(f"Erro ao aplicar filtro na tentativa {tentativa + 1}: {e}")
            time.sleep(2)  # Espera um pouco antes de tentar de novo
    
    if not sucesso:
        print("Não foi possível aplicar o filtro após várias tentativas.")


def apply_filter_and_download(driver):
    """Aplica o filtro e faz o download do PDF após filtrar os emails.""" 
    apply_filter(driver)  

    wait = WebDriverWait(driver, 120)  # O tempo de espera aqui é irrelevante, pois o loop continuará indefinidamente

    while True:
        try:
            print("Buscando email com remetente 'NO REPLY'...")
            email_element = wait.until(
                EC.presence_of_element_located((
                    By.XPATH, 
                    "//span[contains(text(), 'NO REPLY') or contains(text(), 'no-reply@roquette.com')]"
                ))
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
        
        time.sleep(1)
        #Baixar o anexo
        print("Baixando anexo...")
        download_button = wait.until(EC.element_to_be_clickable((
    By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'download') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'baixar')]"
)))

        download_button.click()
        print("Download iniciado.")

        print("Modal detectado. Aguardando botão de fechar...")

        time.sleep(3)
        # Espera o botão de fechar aparecer e ficar clicável
        close_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//i[@data-icon-name='Cancel']"))
        )

        print("Fechando o modal...")
        close_button.click()
        print("Modal fechado com sucesso.")

        # Pequena pausa para evitar cliques muito rápidos
        time.sleep(1)
        
    except Exception as e:
        print(f"Erro ao fechar o modal: {e}")
    
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
        time.sleep(3)
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

def process_downloaded_pdf():
    """Processa o PDF baixado e extrai o texto para um arquivo .txt."""
    print("Aguardando o download do arquivo...")
    time.sleep(20)  # Ajuste o tempo conforme necessário
    arquivos = os.listdir(DOWNLOAD_DIR)
    print("Arquivos no diretório de download:", arquivos)

    tentativas = 10  # número de tentativas
    espera = 5       # segundos entre cada tentativa

    pdf_files = []
    for tentativa in range(tentativas):
        pdf_files = glob.glob(os.path.join(DOWNLOAD_DIR, PDF_PATTERN))
        if pdf_files:
            print(f"Arquivo encontrado na tentativa {tentativa + 1}.")
            break
        else:
            print(f"Nenhum arquivo encontrado ainda. Tentando novamente em {espera} segundos... (Tentativa {tentativa + 1}/{tentativas})")
            time.sleep(espera)

    if not pdf_files:
        raise FileNotFoundError(f"Nenhum arquivo encontrado com o padrão {PDF_PATTERN} em {DOWNLOAD_DIR} após {tentativas} tentativas.")


    pdf_files.sort(key=os.path.getmtime, reverse=True)
    downloaded_pdf = pdf_files[0]
    print(f"Arquivo mais recente: {downloaded_pdf}")

    print("Convertendo PDF para imagens...")
    images = convert_from_path(downloaded_pdf, poppler_path=poppler_path, first_page=1, last_page=1)


    print("Processando texto extraído...")
    ocr_text_list = []
    output_txt_path = BASE_DIR / "texto_extraido.txt"
    
    with open(output_txt_path, 'w', encoding='utf-8') as txt_file:
        for page_num, image in enumerate(images):
            # Realiza OCR na imagem
            ocr_text = pytesseract.image_to_string(image)
            ocr_text_list.append(ocr_text.strip())

            # Exibe o texto extraído no terminal
            print(f"Texto extraído da página {page_num + 1}:\n{ocr_text}\n")

            # Salva o texto extraído no arquivo .txt
            txt_file.write(f"Texto da página {page_num + 1}:\n{ocr_text}\n\n")

    print(f"Processamento concluído. O texto extraído foi salvo como: {output_txt_path}")

    caminho_arquivo = output_txt_path


    # Ler o conteúdo do arquivo
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as arquivo:
            page_text = arquivo.read()  # Lê o conteúdo do arquivo
            print(f"Texto extraído:\n{repr(page_text)}\n")  # Exibe o texto extraído para depuração

        # Lista de padrões para identificar o número do pedido
        padroes = [
        r"\b[Nn][°ºoOeE:]*\s*(?!17703\b)(\d{5,})\b",  # Evita capturar 17703
        r"\b(?!17703\b)[12]\d{4}\b"                   # Evita capturar 17703 na outra regra
        ]

        pedido = None
        for padrao in padroes:
            match = re.search(padrao, page_text)
            if match:
            # Se o regex tiver grupos, capture o correto
                if match.groups():
                    pedido = match.group(1)  # Captura apenas os dígitos numéricos
                else:
                    pedido = match.group()   # Captura o padrão completo
                print(f"Número do pedido encontrado: {pedido}")
                break  

        if not pedido:
            print("Nenhum número de pedido encontrado.")
    except FileNotFoundError:
        print(f"O arquivo {caminho_arquivo} não foi encontrado.")
    except Exception as e:
        print(f"Ocorreu um erro: {e}")


    # identificar datas
    padrao_data = r'\b(\d{2}[/-]\d{2}[/-]\d{4})\b'

    # Lista para armazenar as datas encontradas
    datas_encontradas = []

    # Lendo o arquivo e procurando por datas
    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as arquivo:
            conteudo = arquivo.read()
            datas_encontradas = re.findall(padrao_data, conteudo)

        # Exibindo as datas encontradas
        if datas_encontradas:
            print("Datas encontradas:")
            for data in datas_encontradas:
                print(data)
        else:
            print("Nenhuma data encontrada.")

    except FileNotFoundError:
        print("O arquivo não foi encontrado. Verifique o caminho.")
    except Exception as e:
        print(f"Ocorreu um erro: {e}")

    # Verificar "EX" ou siglas de estados
    ex_encontrado = re.search(r"\bEX\b", page_text) is not None
    estado_encontrado = None
    for sigla in siglas_estados:
        if sigla in page_text:
            estado_encontrado = sigla
            break

    if ex_encontrado:
        novo_nome = f"EXP{pedido}.pdf"
    elif estado_encontrado:
        novo_nome = f"PED{pedido}.pdf"
    else:
        print("Nenhum estado ou 'EX' encontrado no texto.")
        return

    
    novo_caminho = os.path.join(DOWNLOAD_DIR, novo_nome)

    try:
        # Renomear o arquivo
        os.rename(downloaded_pdf, novo_caminho)
        print(f"Arquivo renomeado para: {novo_nome}")

        # Obter o ano e o mês a partir das datas encontradas
        ano = None
        mes = None
        if datas_encontradas:
            try:
                ano = int(datas_encontradas[0].split('/')[-1])  # Considerando o primeiro ano encontrado
                mes = int(datas_encontradas[0].split('/')[1])  # Considerando o primeiro mês encontrado
            except (IndexError, ValueError) as e:
                print(f"Erro ao processar a data: {e}")
                raise

        # Depuração: Exibir os valores encontrados
        print(f"Ano encontrado: {ano}")
        print(f"Mês encontrado: {mes}")

        if ano and mes:
            ano_dir = os.path.join(DOWNLOAD_DIR, str(ano))
            mes_dir = None 

            # Verificar as condições para determinar o diretório
            if ex_encontrado:
                # Para pastas "EXP" (meses de 1 a 12)
                mes_dir = os.path.join(ano_dir, f"EXP - {meses_portugues[mes - 1]}")
                print(f"Definido como EXP: {mes_dir}")
            elif estado_encontrado:
                # Para pastas "MI" (meses de 1 a 12)
                mes_dir = os.path.join(ano_dir, f"MI - {meses_portugues[mes - 1]}")
                print(f"Definido como MI: {mes_dir}")
            else:
                print("Nem estado_encontrado nem ex_encontrado estão True.")

            # Verificar se o diretório existe e mover o arquivo
            if mes_dir:
                if os.path.exists(mes_dir):
                    shutil.move(novo_caminho, os.path.join(mes_dir, novo_nome))
                    print(f"Arquivo movido para: {mes_dir}")
                else:
                    print(f"O diretório {mes_dir} não existe. O arquivo não foi movido.")
            else:
                print("O diretório de destino não foi definido.")
        else:
            print("Ano ou mês não encontrados. O arquivo não foi movido.")
    except Exception as e:
        print(f"Erro ao renomear ou mover o arquivo: {e}")


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

# Variável para contar execuções bem-sucedidas
contador_loops = 0

time.sleep(2)

def executar_processo():
    """Executa o processo de filtragem e download."""
    global executando, contador_loops
    while executando:
        try:
            print(f"Iniciando loop {contador_loops + 1}...")  # Exibir contagem do loop
            
            apply_filter_and_download(driver)

            # Esperar até o download ser detectado
            tentativas = 0
            while True:
                pdf_files = glob.glob(os.path.join(DOWNLOAD_DIR, PDF_PATTERN))
                if pdf_files:
                    print("Arquivo baixado detectado!")
                    break
                else:
                    tentativas += 1
                    print(f"Nenhum arquivo baixado detectado ainda. Tentando novamente... (tentativa {tentativas})")
                    time.sleep(5)  # espera 5 segundos antes de checar de novo

            process_downloaded_pdf()
            
            contador_loops += 1  # Incrementa contador de loops bem-sucedidos
            print(f"Loop {contador_loops} concluído com sucesso!")
            
            print("Aguardando 10 segundos antes de reiniciar.")
            time.sleep(10)
        except Exception as e:
            messagebox.showerror("Erro", f"Ocorreu um erro: {e}")
            executando = False  # Para o loop

    print("Execução finalizada.")


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
import os
import shutil
import keyboard
import time

# Define os caminhos das pastas
PASTA_A = r'C:\Users\7304078\Downloads\Fotos para Renomear'
PASTA_B = r'C:\Users\7304078\OneDrive - Roquette\Área de Trabalho\FAZER AGORA'
PASTA_C = r'C:\Users\7304078\OneDrive - Roquette\Área de Trabalho\Feito'

def mover_arquivos(origem, destino, arquivos):
    for arquivo in arquivos:
        origem_completa = os.path.join(origem, arquivo)
        destino_completo = os.path.join(destino, arquivo)
        if os.path.exists(origem_completa):  # Evita erro se já tiver sido movido
            shutil.move(origem_completa, destino_completo)
            print(f'Movido: {arquivo} -> {destino}')

def trocar_arquivos():
    print("Trocando arquivos...")

    # 1. Salva os 10 arquivos *atuais* da PASTA_B antes de qualquer movimento
    arquivos_b_antigos = sorted([
        f for f in os.listdir(PASTA_B)
        if os.path.isfile(os.path.join(PASTA_B, f))
    ])[:100]

    # 2. Move 10 arquivos de A -> B
    arquivos_a = sorted([
        f for f in os.listdir(PASTA_A)
        if os.path.isfile(os.path.join(PASTA_A, f))
    ])[:100]
    mover_arquivos(PASTA_A, PASTA_B, arquivos_a)

    # 3. Move os arquivos antigos da B -> C
    mover_arquivos(PASTA_B, PASTA_C, arquivos_b_antigos)

    print("Troca concluída.\n")

# Loop escutando o atalho Shift + M
print("Script rodando... Pressione Shift + M para trocar arquivos.\n")
while True:
    try:
        if keyboard.is_pressed('shift') and keyboard.is_pressed('m'):
            trocar_arquivos()
            time.sleep(1)  # Aguarda 1s pra evitar múltiplas execuções
    except:
        break

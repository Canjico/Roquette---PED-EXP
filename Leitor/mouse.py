import pyautogui
import time

while True:
    pyautogui.move(1, 0, duration=0.2)  # Move o mouse ligeiramente para a direita
    pyautogui.move(-1, 0, duration=0.2)  # Move de volta para a esquerda
    print("Mouse movido com sucesso!")  # Mensagem de confirmação
    time.sleep(30)  # Espera 30 segundos antes de repetir
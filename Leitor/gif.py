import subprocess

entrada = "video.mp4"
saida = "video.gif"

subprocess.run([
    "ffmpeg",
    "-i", entrada,
    "-vf", "fps=10,scale=480:-1:flags=lanczos",
    saida
], check=True)

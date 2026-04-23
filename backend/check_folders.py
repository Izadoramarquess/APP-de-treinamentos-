import os
for pasta in ["video", "uploads"]:
    if os.path.exists(pasta):
        arquivos = os.listdir(pasta)
        print(f"{pasta}/: {len(arquivos)} arquivos - {arquivos[:5]}")
    else:
        print(f"{pasta}/: NAO EXISTE")

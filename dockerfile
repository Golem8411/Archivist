# Usa o Python 3.12
FROM python:3.12-slim

# Define a pasta de trabalho dentro do contêiner
WORKDIR /app

# Copia apenas o arquivo de dependências primeir
COPY requirements.txt .

# Instala as bibliotecas
RUN pip install --no-cache-dir -r requirements.txt

# Copia o resto do código para dentro do contêiner
COPY . .

# Comando padrão executado quando o contêiner ligar
CMD ["python", "main.py"]
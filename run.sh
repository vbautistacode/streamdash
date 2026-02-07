#!/usr/bin/env bash
set -euo pipefail

# Configurações
VENV_DIR=".venv"
PYTHON_BIN="${VENV_DIR}/bin/python"
PIP_BIN="${VENV_DIR}/bin/pip"
STREAMLIT_CMD="${VENV_DIR}/bin/streamlit"
APP_ENTRY="app/main.py"

# 1. Criar virtualenv se não existir
if [ ! -d "${VENV_DIR}" ]; then
  echo "Criando virtualenv em ${VENV_DIR}..."
  python3 -m venv "${VENV_DIR}"
fi

# 2. Ativar e garantir pip atualizado
echo "Atualizando pip e instalando dependências..."
"${PIP_BIN}" install --upgrade pip setuptools wheel

# 3. Instalar requirements se houver arquivo
if [ -f "requirements.txt" ]; then
  "${PIP_BIN}" install -r requirements.txt
else
  echo "Atenção: requirements.txt não encontrado. Instale dependências manualmente."
fi

# 4. Rodar Streamlit
echo "Iniciando Streamlit..."
# exportar variáveis de ambiente úteis (opcional)
export STREAMLIT_SERVER_HEADLESS=true
export PYTHONUNBUFFERED=1

# Executa o app
exec "${STREAMLIT_CMD}" run "${APP_ENTRY}" --server.port 8501

# dar permissão e executar
chmod +x run.sh
./run.sh

#python -m streamlit run app/main.py
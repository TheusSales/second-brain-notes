"""Configuração global do pytest.

Adiciona a raiz do projeto ao sys.path para que os imports
`from backend.xxx import yyy` funcionem corretamente nos testes.
"""

import sys
from pathlib import Path

# Garante que a raiz do projeto está no path
sys.path.insert(0, str(Path(__file__).parent))

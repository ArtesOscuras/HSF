# HSF — Hack Station Framework

Herramienta gráfica para análisis de redes, shells remotas y documentación de evidencias en pentest.

## Requisitos

- **Python ≥ 3.11**
- **Tkinter** (interfaz gráfica)
- **Nmap** (escaneo de puertos — opcional pero recomendado)

## Instalación

### 1. Dependencias del sistema

**macOS (Homebrew)**
```bash
brew install python-tk
brew install nmap             # opcional
```

**Debian / Ubuntu**
```bash
sudo apt install python3-tk nmap    # nmap es opcional
```

**Fedora**
```bash
sudo dnf install python3-tkinter nmap
```

**Arch**
```bash
sudo pacman -S tk nmap
```

### 2. Instalar HSF

```bash
pipx install https://github.com/tuusuario/hsf
```

O desde el repositorio clonado:

```bash
git clone <repo>
cd hack_station_framework
pipx install .
```

### 3. Verificar

```bash
hsf
```

### Binarios externos (no incluidos)

El programa funciona sin ellos, pero ciertas funcionalidades los requieren:

| Herramienta | Uso |
|---|---|
| **Nmap** | Escaneo SYN y detección de SO/servicios |
| **Hydra** | Ataques de fuerza bruta |
| **Hashcat** | Crackeo de hashes |

Instálalos con el gestor de paquetes de tu sistema.

## Datos runtime

Los datos de sesión (bases de datos, credenciales, evidencias) se almacenan en:

- `~/.local/share/hsf/` (por defecto)
- `$HSF_HOME/` (si se define la variable de entorno)

## Desarrollo

```bash
pip install -e .
python main.py
python -m src
```

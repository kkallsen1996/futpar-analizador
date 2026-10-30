# futpar-analizador

Sistema para recomendar el 11 de FutPar Fantasy a partir de las notas de SofaScore, las noticias de cada club y el estilo de juego de los equipos. Corre local, en tu computadora.

Propuesta completa: https://claude.ai/artifact/Nd2wffgTn6yrXskS11b5t3

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate        # en Windows: .venv\Scripts\activate
pip install -e ".[dev]"   # comillas dobles: con simples falla en Windows
pytest                            # tienen que pasar todos
```

## Uso (fase 1)

```bash
futpar init                                     # crea data/futpar.db
futpar temporadas                               # lista temporadas del Clausura (torneo 11541)
futpar descargar --torneo 11541 --temporada <ID> --desde 1 --hasta 15
futpar puntos --posicion DEF --minutos 90 --rating 8.2 --goles 1 --recibidos 0 --capitan
```

`descargar` espera 3 segundos entre peticiones y guarda todo en `data/cache/`, así una segunda corrida no vuelve a pedir lo que ya tiene. Los partidos sin terminar no se cachean.

## Si SofaScore responde 403

SofaScore rechaza los pedidos que no vienen de un navegador común, también desde una conexión de casa, así que reintentar no lo arregla. Para ver si los datos se pueden leer, abrí en Chrome https://api.sofascore.com/api/v1/unique-tournament/11541/seasons : si se ve un texto con `"seasons"`, el navegador sí tiene acceso y la carga se puede hacer guardando esas páginas a mano.

## Reglas

Todo el reglamento de Futpar está en `config/reglas_futpar.yaml`. Si los admins cambian una regla, se edita ese archivo, no el código.

## Estructura

| Archivo | Qué hace |
| --- | --- |
| `src/futpar/reglas.py` | Calcula los puntos Futpar de una actuación |
| `src/futpar/sofascore.py` | Lee la API no oficial de SofaScore con caché y validación |
| `src/futpar/ingesta.py` | Guarda partidos y actuaciones en SQLite sin duplicar |
| `src/futpar/db.py` | Esquema de la base (jugadores por ID de SofaScore) |
| `src/futpar/cli.py` | Comandos `futpar ...` |

"""Base SQLite local. Todo jugador se identifica por su ID de SofaScore, nunca por el nombre."""

from __future__ import annotations

import sqlite3
from pathlib import Path

RUTA_DB = Path(__file__).resolve().parents[2] / "data" / "futpar.db"

ESQUEMA = """
CREATE TABLE IF NOT EXISTS equipos (
    sofascore_id INTEGER PRIMARY KEY,
    nombre       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jugadores (
    sofascore_id INTEGER PRIMARY KEY,
    nombre       TEXT NOT NULL,
    posicion     TEXT CHECK (posicion IN ('ARQ', 'DEF', 'MED', 'DEL')),
    equipo_id    INTEGER REFERENCES equipos(sofascore_id)
);

-- Otros nombres con que aparece el jugador en noticias o en Futpar ("D. Rojas", apodos).
CREATE TABLE IF NOT EXISTS alias_jugador (
    alias        TEXT NOT NULL COLLATE NOCASE,
    jugador_id   INTEGER NOT NULL REFERENCES jugadores(sofascore_id),
    PRIMARY KEY (alias, jugador_id)
);

CREATE TABLE IF NOT EXISTS partidos (
    sofascore_id   INTEGER PRIMARY KEY,
    temporada_id   INTEGER NOT NULL,
    ronda          INTEGER,
    inicio_utc     TEXT,            -- ISO 8601 en UTC; se muestra en America/Asuncion
    local_id       INTEGER NOT NULL REFERENCES equipos(sofascore_id),
    visitante_id   INTEGER NOT NULL REFERENCES equipos(sofascore_id),
    goles_local    INTEGER,
    goles_visita   INTEGER,
    estado         TEXT             -- notstarted, inprogress, finished, postponed, canceled
);

CREATE TABLE IF NOT EXISTS actuaciones (
    partido_id     INTEGER NOT NULL REFERENCES partidos(sofascore_id),
    jugador_id     INTEGER NOT NULL REFERENCES jugadores(sofascore_id),
    equipo_id      INTEGER NOT NULL REFERENCES equipos(sofascore_id),
    titular        INTEGER NOT NULL,
    minutos        INTEGER NOT NULL DEFAULT 0,
    rating         REAL,            -- NULL = sin nota, distinto de nota baja
    goles          INTEGER NOT NULL DEFAULT 0,
    asistencias    INTEGER NOT NULL DEFAULT 0,
    amarillas      INTEGER NOT NULL DEFAULT 0,
    roja           INTEGER NOT NULL DEFAULT 0,   -- expulsado (roja directa o doble amarilla)
    doble_amarilla INTEGER NOT NULL DEFAULT 0,
    descargado_utc TEXT NOT NULL,
    PRIMARY KEY (partido_id, jugador_id)
);

-- Cuentas de X / medios. El puntaje de confianza sale de aciertos y fallos, no de seguidores.
CREATE TABLE IF NOT EXISTS fuentes (
    id        INTEGER PRIMARY KEY,
    handle    TEXT NOT NULL UNIQUE COLLATE NOCASE,
    tipo      TEXT NOT NULL CHECK (tipo IN ('oficial', 'medio', 'periodista', 'otro')),
    club_id   INTEGER REFERENCES equipos(sofascore_id),
    aciertos  INTEGER NOT NULL DEFAULT 0,
    fallos    INTEGER NOT NULL DEFAULT 0,
    activa    INTEGER NOT NULL DEFAULT 1
);

-- Noticias cargadas a mano: lesión, suspensión, traspaso, duda, 11 probable.
CREATE TABLE IF NOT EXISTS noticias (
    id             INTEGER PRIMARY KEY,
    jugador_id     INTEGER NOT NULL REFERENCES jugadores(sofascore_id),
    fuente_id      INTEGER REFERENCES fuentes(id),
    tipo           TEXT NOT NULL CHECK (tipo IN ('lesion', 'suspension', 'traspaso', 'duda', 'titular', 'suplente')),
    publicada_utc  TEXT NOT NULL,
    url            TEXT,
    nota           TEXT,
    resultado      TEXT CHECK (resultado IN ('acierto', 'fallo'))  -- se completa al ver la alineación real
);

-- Puntajes reales de Futpar, para verificar que nuestra fórmula coincide.
CREATE TABLE IF NOT EXISTS puntajes_futpar (
    partido_id   INTEGER NOT NULL REFERENCES partidos(sofascore_id),
    jugador_id   INTEGER NOT NULL REFERENCES jugadores(sofascore_id),
    puntos       INTEGER NOT NULL,
    cargado_utc  TEXT NOT NULL,
    PRIMARY KEY (partido_id, jugador_id)
);

-- Lo que recomendó el sistema y lo que eligió el usuario, para medir efectividad.
CREATE TABLE IF NOT EXISTS selecciones (
    temporada_id INTEGER NOT NULL,
    ronda        INTEGER NOT NULL,
    origen       TEXT NOT NULL CHECK (origen IN ('sistema', 'usuario')),
    jugador_id   INTEGER NOT NULL REFERENCES jugadores(sofascore_id),
    capitan      INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (temporada_id, ronda, origen, jugador_id)
);
"""


def conectar(ruta: Path | str = RUTA_DB) -> sqlite3.Connection:
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(ruta)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def inicializar(con: sqlite3.Connection) -> None:
    con.executescript(ESQUEMA)
    con.commit()

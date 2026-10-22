"""Guarda en SQLite lo que se baja de SofaScore. Re-ejecutar una ronda la actualiza, no la duplica."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from futpar.sofascore import ESTADOS_TERMINADOS, ClienteSofaScore, FilaActuacion, Partido


def guardar_partido(con: sqlite3.Connection, temporada_id: int, p: Partido) -> None:
    for equipo_id, nombre in ((p.local_id, p.local_nombre), (p.visitante_id, p.visitante_nombre)):
        con.execute(
            "INSERT INTO equipos (sofascore_id, nombre) VALUES (?, ?) "
            "ON CONFLICT(sofascore_id) DO UPDATE SET nombre = excluded.nombre",
            (equipo_id, nombre),
        )
    con.execute(
        """INSERT INTO partidos (sofascore_id, temporada_id, ronda, inicio_utc, local_id, visitante_id,
                                 goles_local, goles_visita, estado)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(sofascore_id) DO UPDATE SET
               ronda = excluded.ronda, inicio_utc = excluded.inicio_utc,
               goles_local = excluded.goles_local, goles_visita = excluded.goles_visita,
               estado = excluded.estado""",
        (p.sofascore_id, temporada_id, p.ronda, p.inicio_utc, p.local_id, p.visitante_id,
         p.goles_local, p.goles_visita, p.estado),
    )


def guardar_actuaciones(
    con: sqlite3.Connection,
    partido_id: int,
    filas: list[FilaActuacion],
    tarjetas: dict[int, dict[str, int]],
) -> None:
    ahora = datetime.now(timezone.utc).isoformat()
    for f in filas:
        # Un traspaso cambia el equipo actual; el equipo de cada partido queda en `actuaciones`.
        con.execute(
            """INSERT INTO jugadores (sofascore_id, nombre, posicion, equipo_id) VALUES (?, ?, ?, ?)
               ON CONFLICT(sofascore_id) DO UPDATE SET
                   nombre = excluded.nombre,
                   posicion = COALESCE(excluded.posicion, jugadores.posicion),
                   equipo_id = excluded.equipo_id""",
            (f.jugador_id, f.nombre, f.posicion, f.equipo_id),
        )
        t = tarjetas.get(f.jugador_id, {})
        roja = 1 if t.get("roja") or t.get("doble_amarilla") else 0
        con.execute(
            """INSERT INTO actuaciones (partido_id, jugador_id, equipo_id, titular, minutos, rating, goles,
                                        asistencias, amarillas, roja, doble_amarilla, descargado_utc)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(partido_id, jugador_id) DO UPDATE SET
                   equipo_id = excluded.equipo_id, titular = excluded.titular, minutos = excluded.minutos,
                   rating = excluded.rating, goles = excluded.goles, asistencias = excluded.asistencias,
                   amarillas = excluded.amarillas, roja = excluded.roja,
                   doble_amarilla = excluded.doble_amarilla, descargado_utc = excluded.descargado_utc""",
            (partido_id, f.jugador_id, f.equipo_id, int(f.titular), f.minutos, f.rating, f.goles,
             f.asistencias, t.get("amarillas", 0), roja, t.get("doble_amarilla", 0), ahora),
        )


def descargar_ronda(
    con: sqlite3.Connection, cliente: ClienteSofaScore, torneo_id: int, temporada_id: int, ronda: int
) -> dict[str, int]:
    resumen = {"partidos": 0, "con_actuaciones": 0, "pendientes": 0}
    for p in cliente.partidos_de_ronda(torneo_id, temporada_id, ronda):
        guardar_partido(con, temporada_id, p)
        resumen["partidos"] += 1
        if p.estado not in ESTADOS_TERMINADOS:
            resumen["pendientes"] += 1
            continue
        guardar_actuaciones(con, p.sofascore_id, cliente.actuaciones(p), cliente.tarjetas(p))
        resumen["con_actuaciones"] += 1
        con.commit()  # se guarda partido a partido para no perder todo si SofaScore corta a mitad
    con.commit()
    return resumen

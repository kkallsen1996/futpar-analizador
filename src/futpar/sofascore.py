"""Lectura de la API no oficial de SofaScore, con caché en disco y ritmo lento.

La API no es pública: puede cambiar de formato o bloquear la IP. Por eso cada
respuesta se valida antes de usarla y, si algo no cuadra, se corta con un error
claro en vez de guardar datos a medias.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx

BASE = "https://api.sofascore.com/api/v1"
RUTA_CACHE = Path(__file__).resolve().parents[2] / "data" / "cache"
POSICION_SOFASCORE = {"G": "ARQ", "D": "DEF", "M": "MED", "F": "DEL"}
ESTADOS_TERMINADOS = {"finished"}


class ErrorSofaScore(RuntimeError):
    pass


class FormatoInesperado(ErrorSofaScore):
    pass


@dataclass(frozen=True)
class Partido:
    sofascore_id: int
    ronda: int | None
    inicio_utc: str | None
    local_id: int
    local_nombre: str
    visitante_id: int
    visitante_nombre: str
    goles_local: int | None
    goles_visita: int | None
    estado: str


@dataclass(frozen=True)
class FilaActuacion:
    jugador_id: int
    nombre: str
    posicion: str | None
    equipo_id: int
    titular: bool
    minutos: int
    rating: float | None
    goles: int
    asistencias: int


class ClienteSofaScore:
    def __init__(
        self,
        cache: Path = RUTA_CACHE,
        pausa_segundos: float = 3.0,
        cliente: httpx.Client | None = None,
    ):
        self.cache = cache
        self.pausa = pausa_segundos
        self._ultimo = 0.0
        self._http = cliente or httpx.Client(
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0 (futpar-analizador, uso personal)"},
        )

    def get(self, ruta: str, usar_cache: bool = True) -> dict:
        archivo = self.cache / (hashlib.sha1(ruta.encode()).hexdigest() + ".json")
        if usar_cache and archivo.exists():
            return json.loads(archivo.read_text(encoding="utf-8"))

        espera = self.pausa - (time.monotonic() - self._ultimo)
        if espera > 0:
            time.sleep(espera)
        resp = self._http.get(BASE + ruta)
        self._ultimo = time.monotonic()
        if resp.status_code == 403:
            raise ErrorSofaScore(f"SofaScore bloqueó la petición (403) en {ruta}; esperar antes de reintentar")
        if resp.status_code == 404:
            raise ErrorSofaScore(f"No existe en SofaScore: {ruta}")
        resp.raise_for_status()
        datos = resp.json()

        self.cache.mkdir(parents=True, exist_ok=True)
        archivo.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
        return datos

    def partidos_de_ronda(self, torneo_id: int, temporada_id: int, ronda: int) -> list[Partido]:
        # Una ronda no terminada cambia; solo se cachea cuando todos sus partidos terminaron.
        ruta = f"/unique-tournament/{torneo_id}/season/{temporada_id}/events/round/{ronda}"
        partidos = parsear_partidos(self.get(ruta))
        if any(p.estado not in ESTADOS_TERMINADOS for p in partidos):
            partidos = parsear_partidos(self.get(ruta, usar_cache=False))
        return partidos

    # Las notas cambian durante y justo después del partido: solo se usa la caché si ya terminó.
    def actuaciones(self, partido: Partido) -> list[FilaActuacion]:
        terminado = partido.estado in ESTADOS_TERMINADOS
        datos = self.get(f"/event/{partido.sofascore_id}/lineups", usar_cache=terminado)
        return parsear_alineaciones(datos, equipos=(partido.local_id, partido.visitante_id))

    def tarjetas(self, partido: Partido) -> dict[int, dict[str, int]]:
        terminado = partido.estado in ESTADOS_TERMINADOS
        return parsear_tarjetas(self.get(f"/event/{partido.sofascore_id}/incidents", usar_cache=terminado))


def _requerir(d: dict, *claves: str, donde: str) -> None:
    faltan = [c for c in claves if c not in d]
    if faltan:
        raise FormatoInesperado(f"{donde}: faltan claves {faltan}; SofaScore pudo haber cambiado el formato")


def parsear_partidos(datos: dict) -> list[Partido]:
    _requerir(datos, "events", donde="ronda")
    partidos = []
    for ev in datos["events"]:
        _requerir(ev, "id", "homeTeam", "awayTeam", "status", donde=f"partido {ev.get('id')}")
        inicio = ev.get("startTimestamp")
        partidos.append(
            Partido(
                sofascore_id=ev["id"],
                ronda=(ev.get("roundInfo") or {}).get("round"),
                inicio_utc=datetime.fromtimestamp(inicio, tz=timezone.utc).isoformat() if inicio else None,
                local_id=ev["homeTeam"]["id"],
                local_nombre=ev["homeTeam"]["name"],
                visitante_id=ev["awayTeam"]["id"],
                visitante_nombre=ev["awayTeam"]["name"],
                goles_local=(ev.get("homeScore") or {}).get("current"),
                goles_visita=(ev.get("awayScore") or {}).get("current"),
                estado=ev["status"].get("type", "desconocido"),
            )
        )
    return partidos


def parsear_alineaciones(datos: dict, equipos: tuple[int, int] | None = None) -> list[FilaActuacion]:
    _requerir(datos, "home", "away", donde="alineaciones")
    filas = []
    for lado in ("home", "away"):
        bloque = datos[lado]
        _requerir(bloque, "players", donde=f"alineaciones.{lado}")
        for item in bloque["players"]:
            jugador = item.get("player") or {}
            _requerir(jugador, "id", "name", donde=f"alineaciones.{lado}.player")
            # El ID del equipo viene en cada jugador cuando SofaScore lo informa.
            equipo_id = item.get("teamId") or (equipos[0 if lado == "home" else 1] if equipos else None)
            if equipo_id is None:
                raise FormatoInesperado(f"Jugador {jugador['id']} sin equipo; pasar `equipos` al parsear")
            est = item.get("statistics") or {}
            pos = item.get("position") or jugador.get("position")
            filas.append(
                FilaActuacion(
                    jugador_id=jugador["id"],
                    nombre=jugador["name"],
                    posicion=POSICION_SOFASCORE.get(pos),
                    equipo_id=equipo_id,
                    titular=not item.get("substitute", False),
                    minutos=int(est.get("minutesPlayed") or 0),
                    rating=est.get("rating"),
                    goles=int(est.get("goals") or 0),
                    asistencias=int(est.get("goalAssist") or 0),
                )
            )
    return filas


def parsear_tarjetas(datos: dict) -> dict[int, dict[str, int]]:
    """Devuelve {jugador_id: {"amarillas": n, "roja": 0/1, "doble_amarilla": 0/1}}."""
    _requerir(datos, "incidents", donde="incidencias")
    tarjetas: dict[int, dict[str, int]] = {}
    for inc in datos["incidents"]:
        if inc.get("incidentType") != "card" or not inc.get("player"):
            continue
        t = tarjetas.setdefault(inc["player"]["id"], {"amarillas": 0, "roja": 0, "doble_amarilla": 0})
        clase = inc.get("incidentClass")
        if clase == "yellow":
            t["amarillas"] += 1
        elif clase == "yellowRed":
            t["doble_amarilla"] = 1
        elif clase == "red":
            t["roja"] = 1
    return tarjetas

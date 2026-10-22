"""Cálculo de puntos de FutPar a partir de la actuación de un jugador en un partido."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from pathlib import Path

import yaml

RUTA_REGLAS = Path(__file__).resolve().parents[2] / "config" / "reglas_futpar.yaml"
POSICIONES = ("ARQ", "DEF", "MED", "DEL")
BOOSTERS = ("gol", "asistencia", "imbatibilidad")


@dataclass(frozen=True)
class Actuacion:
    """Lo que hizo un jugador en un partido. `rating` es None si SofaScore no le dio nota."""

    posicion: str
    minutos: int
    rating: float | None = None
    goles: int = 0
    asistencias: int = 0
    goles_recibidos_equipo: int | None = None  # None = todavía no se sabe
    doble_amarilla: bool = False
    roja_directa: bool = False


@dataclass(frozen=True)
class Puntaje:
    total: int
    detalle: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class Reglas:
    datos: dict

    @classmethod
    def cargar(cls, ruta: Path | str = RUTA_REGLAS) -> "Reglas":
        with open(ruta, encoding="utf-8") as f:
            datos = yaml.safe_load(f)
        reglas = cls(datos)
        reglas._validar()
        return reglas

    def _validar(self) -> None:
        escala = self.datos["rating"]["escala"]
        minimos = [Decimal(str(m)) for m, _ in escala]
        if minimos != sorted(minimos, reverse=True):
            raise ValueError("La escala de rating debe ir de mayor a menor nota")
        if len(set(minimos)) != len(minimos):
            raise ValueError("La escala de rating tiene notas mínimas repetidas")
        faltan = set(POSICIONES) - set(self.datos["puntos"]["gol"])
        if faltan:
            raise ValueError(f"Faltan puntos por gol para: {sorted(faltan)}")

    def normalizar_rating(self, rating: float) -> Decimal:
        # Decimal evita que 7.2 guardado como 7.19999 caiga en el escalón de abajo.
        modo = self.datos["rating"]["redondeo"]
        redondeo = {"redondear": ROUND_HALF_UP, "truncar": ROUND_DOWN}.get(modo)
        if redondeo is None:
            raise ValueError(f"Modo de redondeo desconocido: {modo!r}")
        return Decimal(str(rating)).quantize(Decimal("0.1"), rounding=redondeo)

    def puntos_por_rating(self, rating: float) -> int:
        nota = self.normalizar_rating(rating)
        for minimo, puntos in self.datos["rating"]["escala"]:
            if nota >= Decimal(str(minimo)):
                return int(puntos)
        return int(self.datos["rating"]["piso"])

    def calcular(
        self,
        act: Actuacion,
        capitan: bool = False,
        boosters: frozenset[str] | set[str] = frozenset(),
    ) -> Puntaje:
        if act.posicion not in POSICIONES:
            raise ValueError(f"Posición desconocida: {act.posicion!r}")
        desconocidos = set(boosters) - set(BOOSTERS)
        if desconocidos:
            raise ValueError(f"Boosters desconocidos: {sorted(desconocidos)}")

        p = self.datos["puntos"]
        if act.minutos < 1:
            return Puntaje(0, {})

        mult = p["booster_multiplicador"]
        detalle: dict[str, int] = {"minutos": p["minutos_jugados"]}
        if act.rating is not None:
            detalle["rating"] = self.puntos_por_rating(act.rating)
        if act.goles:
            detalle["goles"] = act.goles * p["gol"][act.posicion] * (mult if "gol" in boosters else 1)
        if act.asistencias:
            detalle["asistencias"] = act.asistencias * p["asistencia"] * (
                mult if "asistencia" in boosters else 1
            )
        imb = p["imbatibilidad"]
        if (
            act.posicion in imb["posiciones"]
            and act.goles_recibidos_equipo == 0
            and act.minutos >= imb["minutos_minimos"]
        ):
            detalle["imbatibilidad"] = imb["puntos"] * (mult if "imbatibilidad" in boosters else 1)
        if act.roja_directa:
            detalle["tarjetas"] = p["roja_directa"]
        elif act.doble_amarilla:
            detalle["tarjetas"] = p["doble_amarilla"]

        total = sum(detalle.values())
        if capitan:
            total *= p["capitan_multiplicador"]
        return Puntaje(total, detalle)

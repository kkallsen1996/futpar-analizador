"""Línea de comandos: `futpar init`, `futpar descargar`, `futpar puntos`."""

from __future__ import annotations

import argparse
import sys

from futpar import db
from futpar.reglas import Actuacion, Reglas


def _init(args: argparse.Namespace) -> None:
    con = db.conectar(args.db)
    db.inicializar(con)
    print(f"Base lista en {args.db}")


def _descargar(args: argparse.Namespace) -> None:
    from futpar.ingesta import descargar_ronda
    from futpar.sofascore import ClienteSofaScore

    con = db.conectar(args.db)
    db.inicializar(con)
    cliente = ClienteSofaScore(pausa_segundos=args.pausa)
    for ronda in range(args.desde, args.hasta + 1):
        r = descargar_ronda(con, cliente, args.torneo, args.temporada, ronda)
        print(f"Ronda {ronda}: {r['partidos']} partidos, {r['con_actuaciones']} con notas, {r['pendientes']} sin terminar")


def _temporadas(args: argparse.Namespace) -> None:
    from futpar.sofascore import ClienteSofaScore

    datos = ClienteSofaScore().get(f"/unique-tournament/{args.torneo}/seasons", usar_cache=False)
    for t in datos.get("seasons", []):
        print(f"{t.get('id')}\t{t.get('name')}")


def _puntos(args: argparse.Namespace) -> None:
    reglas = Reglas.cargar()
    act = Actuacion(
        posicion=args.posicion,
        minutos=args.minutos,
        rating=args.rating,
        goles=args.goles,
        asistencias=args.asistencias,
        goles_recibidos_equipo=args.recibidos,
        doble_amarilla=args.doble_amarilla,
        roja_directa=args.roja,
    )
    p = reglas.calcular(act, capitan=args.capitan, boosters=set(args.booster or []))
    print(f"Total: {p.total}  {p.detalle}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="futpar")
    ap.add_argument("--db", default=str(db.RUTA_DB))
    sub = ap.add_subparsers(dest="comando", required=True)

    sub.add_parser("init", help="Crea la base SQLite").set_defaults(func=_init)

    d = sub.add_parser("descargar", help="Baja partidos y notas de SofaScore")
    d.add_argument("--torneo", type=int, required=True, help="ID de torneo de SofaScore")
    d.add_argument("--temporada", type=int, required=True, help="ID de temporada de SofaScore")
    d.add_argument("--desde", type=int, required=True)
    d.add_argument("--hasta", type=int, required=True)
    d.add_argument("--pausa", type=float, default=3.0, help="Segundos entre peticiones")
    d.set_defaults(func=_descargar)

    t = sub.add_parser("temporadas", help="Lista las temporadas de un torneo de SofaScore")
    t.add_argument("--torneo", type=int, default=11541, help="11541 = Primera División Clausura")
    t.set_defaults(func=_temporadas)

    p = sub.add_parser("puntos", help="Calcula los puntos Futpar de una actuación")
    p.add_argument("--posicion", choices=["ARQ", "DEF", "MED", "DEL"], required=True)
    p.add_argument("--minutos", type=int, required=True)
    p.add_argument("--rating", type=float)
    p.add_argument("--goles", type=int, default=0)
    p.add_argument("--asistencias", type=int, default=0)
    p.add_argument("--recibidos", type=int, help="Goles que recibió su equipo")
    p.add_argument("--doble-amarilla", action="store_true")
    p.add_argument("--roja", action="store_true")
    p.add_argument("--capitan", action="store_true")
    p.add_argument("--booster", action="append", choices=["gol", "asistencia", "imbatibilidad"])
    p.set_defaults(func=_puntos)

    args = ap.parse_args(argv)
    try:
        args.func(args)
    except Exception as e:  # noqa: BLE001 - mostrar el error en español y salir con código 1
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

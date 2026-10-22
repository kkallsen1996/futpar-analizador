import json
from pathlib import Path

import pytest

from futpar import db
from futpar.ingesta import guardar_actuaciones, guardar_partido
from futpar.sofascore import (
    FormatoInesperado,
    parsear_alineaciones,
    parsear_partidos,
    parsear_tarjetas,
)

FIX = Path(__file__).parent / "fixtures"


def cargar(nombre):
    return json.loads((FIX / nombre).read_text(encoding="utf-8"))


def test_parsear_partidos():
    ps = parsear_partidos(cargar("ronda.json"))
    assert [p.estado for p in ps] == ["finished", "notstarted"]
    assert ps[0].local_nombre == "Olimpia" and ps[0].goles_local == 2
    assert ps[0].inicio_utc.endswith("+00:00")


def test_parsear_alineaciones_sin_nota_es_none():
    filas = parsear_alineaciones(cargar("lineups.json"), equipos=(1, 2))
    suplente = next(f for f in filas if f.jugador_id == 103)
    assert suplente.rating is None and suplente.minutos == 0 and not suplente.titular
    arquero = next(f for f in filas if f.jugador_id == 101)
    assert arquero.posicion == "ARQ" and arquero.equipo_id == 1
    assert next(f for f in filas if f.jugador_id == 201).equipo_id == 2


def test_formato_cambiado_falla_claro():
    with pytest.raises(FormatoInesperado):
        parsear_alineaciones({"home": {}, "away": {"players": []}}, equipos=(1, 2))


def test_tarjetas():
    t = parsear_tarjetas(cargar("incidents.json"))
    assert t[102] == {"amarillas": 1, "roja": 0, "doble_amarilla": 1}
    assert t[201]["roja"] == 1


def test_guardar_dos_veces_no_duplica(tmp_path):
    con = db.conectar(tmp_path / "t.db")
    db.inicializar(con)
    p = parsear_partidos(cargar("ronda.json"))[0]
    filas = parsear_alineaciones(cargar("lineups.json"), equipos=(p.local_id, p.visitante_id))
    tarjetas = parsear_tarjetas(cargar("incidents.json"))
    for _ in range(2):
        guardar_partido(con, 999, p)
        guardar_actuaciones(con, p.sofascore_id, filas, tarjetas)
    assert con.execute("SELECT COUNT(*) FROM actuaciones").fetchone()[0] == len(filas)
    fila = con.execute("SELECT roja, doble_amarilla FROM actuaciones WHERE jugador_id = 102").fetchone()
    assert tuple(fila) == (1, 1)

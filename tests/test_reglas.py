import pytest

from futpar.reglas import Actuacion, Reglas


@pytest.fixture(scope="module")
def reglas():
    return Reglas.cargar()


@pytest.mark.parametrize(
    "rating, puntos",
    [
        (9.3, 12), (10.0, 12), (9.2, 11), (8.6, 11), (8.5, 10), (8.0, 10), (7.9, 9), (7.8, 9),
        (7.7, 8), (7.6, 8), (7.5, 7), (7.4, 7), (7.3, 6), (7.2, 6), (7.1, 5), (7.0, 5),
        (6.9, 4), (6.8, 4), (6.7, 3), (6.6, 3), (6.5, 2), (6.4, 2), (6.3, 1), (6.2, 1),
        (6.1, 0), (6.0, 0), (5.9, -1), (5.8, -1), (5.7, -2), (5.4, -2), (5.3, -3), (5.0, -3),
        (4.9, -4), (3.0, -4),
    ],
)
def test_escala_rating(reglas, rating, puntos):
    assert reglas.puntos_por_rating(rating) == puntos


def test_rating_con_error_de_float_no_baja_de_escalon(reglas):
    assert reglas.puntos_por_rating(7.199999999) == 6


def test_redondeo_configurable(reglas):
    assert reglas.puntos_por_rating(7.95) == 10  # "redondear": 7.95 -> 8.0
    truncar = Reglas({**reglas.datos, "rating": {**reglas.datos["rating"], "redondeo": "truncar"}})
    assert truncar.puntos_por_rating(7.95) == 9


def test_ejemplo_del_reglamento(reglas):
    # Defensa 90', nota 8.2, 1 gol, 1 asistencia, valla invicta, doble amarilla, booster de gol.
    # El reglamento dice +33, pero sus propias cifras suman 27 (cuenta el gol dos veces).
    act = Actuacion("DEF", 90, 8.2, goles=1, asistencias=1, goles_recibidos_equipo=0, doble_amarilla=True)
    p = reglas.calcular(act, boosters={"gol"})
    assert p.detalle == {"minutos": 1, "rating": 10, "goles": 12, "asistencias": 3, "imbatibilidad": 4, "tarjetas": -3}
    assert p.total == 27


def test_no_jugo_suma_cero(reglas):
    assert reglas.calcular(Actuacion("MED", 0, None)).total == 0


def test_sin_nota_solo_suma_minutos(reglas):
    assert reglas.calcular(Actuacion("DEL", 5, None)).total == 1


def test_goles_por_posicion(reglas):
    assert reglas.calcular(Actuacion("ARQ", 90, 6.0, goles=1)).detalle["goles"] == 6
    assert reglas.calcular(Actuacion("MED", 90, 6.0, goles=2)).detalle["goles"] == 10
    assert reglas.calcular(Actuacion("DEL", 90, 6.0, goles=1)).detalle["goles"] == 4


def test_imbatibilidad_arqueros_y_defensas_y_solo_si_se_sabe(reglas):
    assert "imbatibilidad" in reglas.calcular(Actuacion("DEF", 90, 7.0, goles_recibidos_equipo=0)).detalle
    assert "imbatibilidad" not in reglas.calcular(Actuacion("DEF", 90, 7.0, goles_recibidos_equipo=1)).detalle
    assert "imbatibilidad" not in reglas.calcular(Actuacion("DEF", 90, 7.0)).detalle
    assert "imbatibilidad" in reglas.calcular(Actuacion("ARQ", 90, 7.0, goles_recibidos_equipo=0)).detalle
    assert "imbatibilidad" not in reglas.calcular(Actuacion("MED", 90, 7.0, goles_recibidos_equipo=0)).detalle


def test_capitan_duplica_todo(reglas):
    act = Actuacion("DEL", 90, 7.4, goles=1)
    assert reglas.calcular(act, capitan=True).total == 2 * reglas.calcular(act).total


def test_roja_directa_no_suma_doble_amarilla(reglas):
    p = reglas.calcular(Actuacion("MED", 30, 5.5, roja_directa=True, doble_amarilla=True))
    assert p.detalle["tarjetas"] == -6


def test_booster_desconocido_falla(reglas):
    with pytest.raises(ValueError):
        reglas.calcular(Actuacion("MED", 90, 7.0), boosters={"capitan"})


def test_escala_desordenada_falla(reglas):
    mala = {**reglas.datos, "rating": {**reglas.datos["rating"], "escala": [[6.0, 0], [7.0, 5]]}}
    with pytest.raises(ValueError):
        Reglas(mala)._validar()

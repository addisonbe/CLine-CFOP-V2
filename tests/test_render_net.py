"""The unfolded cube net: geometry, colours and text serializers."""

from __future__ import annotations

import json

import pytest

from rubiks_cfop.cube.cube import Cube
from rubiks_cfop.cube.facelets import (
    FACE_COLOR,
    FACE_ORDER,
    Color,
    Face,
    facelet_index,
)
from rubiks_cfop.render.net import (
    DEFAULT_PALETTE,
    EMPTY_CELL,
    NET_COLUMNS,
    NET_ORIGINS,
    NET_ROWS,
    net_layout,
    render_ansi,
    render_emoji,
    render_letters,
    render_plain,
)

SCRAMBLE = "R U R' U' F2 D L2 B'"
SCRAMBLED = Cube.solved().apply_sequence(SCRAMBLE)


def test_net_geometry() -> None:
    layout = net_layout(Cube.solved())
    assert len(layout.colors) == NET_ROWS == 9
    assert all(len(row) == NET_COLUMNS == 12 for row in layout.colors)
    covered = sum(1 for row in layout.colors for cell in row if cell is not None)
    assert covered == 54
    assert sorted(face for face in NET_ORIGINS) == sorted(FACE_ORDER)


def test_each_face_sits_where_expected() -> None:
    expected = {
        Face.U: (0, 3),
        Face.L: (3, 0),
        Face.F: (3, 3),
        Face.R: (3, 6),
        Face.B: (3, 9),
        Face.D: (6, 3),
    }
    assert expected == NET_ORIGINS


def test_cells_map_to_the_right_facelets() -> None:
    layout = net_layout(SCRAMBLED)
    for face in FACE_ORDER:
        row0, column0 = NET_ORIGINS[face]
        for row in range(3):
            for column in range(3):
                expected = facelet_index(face, row * 3 + column + 1)
                assert layout.facelet(row0 + row, column0 + column) == expected


def test_colours_follow_the_facelets() -> None:
    layout = net_layout(SCRAMBLED)
    for row in range(NET_ROWS):
        for column in range(NET_COLUMNS):
            index = layout.facelet(row, column)
            if index == EMPTY_CELL:
                assert layout.cell(row, column) is None
                continue
            letter = SCRAMBLED.facelets[index]
            assert layout.cell(row, column) is FACE_COLOR[Face(letter)]


def test_solved_cube_shows_one_colour_per_face() -> None:
    layout = net_layout(Cube.solved())
    for face in FACE_ORDER:
        colors = {color for row in layout.face_colors(face) for color in row}
        assert colors == {FACE_COLOR[face]}


def test_cells_outside_the_net_are_empty() -> None:
    layout = net_layout(Cube.solved())
    assert layout.cell(0, 0) is None
    assert layout.cell(8, 11) is None
    assert layout.facelet(4, 4) != EMPTY_CELL


def test_face_colors_rejects_unknown_faces() -> None:
    layout = net_layout(Cube.solved())
    with pytest.raises(ValueError, match="'X' is not a valid Face"):
        layout.face_colors("X")


def test_palette_is_the_standard_scheme() -> None:
    assert DEFAULT_PALETTE[Color.WHITE] == (255, 255, 255)
    assert DEFAULT_PALETTE[Color.RED] == (196, 30, 58)
    assert DEFAULT_PALETTE[Color.GREEN] == (0, 158, 96)
    assert DEFAULT_PALETTE[Color.YELLOW] == (255, 213, 0)
    assert DEFAULT_PALETTE[Color.ORANGE] == (255, 88, 0)
    assert DEFAULT_PALETTE[Color.BLUE] == (0, 81, 186)


def test_to_dict_is_json_serializable() -> None:
    payload = net_layout(SCRAMBLED).to_dict()
    round_tripped = json.loads(json.dumps(payload))
    assert round_tripped["faces"]["U"][0][0] == payload["faces"]["U"][0][0]  # type: ignore[index]
    assert set(round_tripped["faces"]) == {face.value for face in FACE_ORDER}
    assert len(round_tripped["net"]) == NET_ROWS


def test_ansi_rendering_uses_truecolor_blocks() -> None:
    text = render_ansi(net_layout(Cube.solved()))
    lines = text.splitlines()
    assert len(lines) == NET_ROWS
    assert "\x1b[48;2;255;255;255m" in text  # white, the U face
    assert "\x1b[48;2;196;30;58m" in text  # red, the R face
    assert text.endswith("\x1b[0m")


def test_ansi_rendering_has_no_letters() -> None:
    text = render_ansi(net_layout(SCRAMBLED))
    stripped = text.replace("\x1b", " ").replace("[", " ").replace("m", " ")
    assert not any(character.isalpha() for character in stripped)


def test_ansi_rendering_accepts_a_custom_palette() -> None:
    palette = dict.fromkeys(Color, (1, 2, 3))
    text = render_ansi(net_layout(Cube.solved()), palette=palette)
    assert "\x1b[48;2;1;2;3m" in text


def test_emoji_rendering_has_54_squares() -> None:
    text = render_emoji(net_layout(Cube.solved()))
    assert len(text.splitlines()) == NET_ROWS
    assert (
        sum(
            1
            for character in text
            if character in "\u2b1c\U0001f7e5\U0001f7e9\U0001f7e8\U0001f7e7\U0001f7e6"
        )
        == 54
    )


def test_letter_rendering_matches_the_state() -> None:
    text = render_letters(net_layout(SCRAMBLED))
    lines = text.splitlines()
    assert lines[0].split() == list(SCRAMBLED.facelets[0:3])
    middle = (
        SCRAMBLED.facelets[36:39]  # L
        + SCRAMBLED.facelets[18:21]  # F
        + SCRAMBLED.facelets[9:12]  # R
        + SCRAMBLED.facelets[45:48]  # B
    )
    assert lines[3].split() == list(middle)
    assert lines[8].split() == list(SCRAMBLED.facelets[33:36])


def test_plain_rendering_lists_the_six_faces() -> None:
    text = render_plain(Cube.solved())
    assert text.splitlines() == [
        "UUUUUUUUU",
        "RRRRRRRRR",
        "FFFFFFFFF",
        "DDDDDDDDD",
        "LLLLLLLLL",
        "BBBBBBBBB",
    ]


def test_rendering_is_deterministic() -> None:
    first = render_ansi(net_layout(SCRAMBLED))
    second = render_ansi(net_layout(Cube.solved().apply_sequence(SCRAMBLE)))
    assert first == second

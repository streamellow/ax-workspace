# tests/test_piece.py — 피스 로직 테스트

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from piece import Piece, PieceBag, PIECE_NAMES, TETROMINOES


class TestPieceCells:
    def test_I_piece_default_cells(self):
        p = Piece("I", col=3, row=0)
        cells = p.cells()
        assert len(cells) == 4
        assert (3, 0) in cells
        assert (6, 0) in cells

    def test_O_piece_all_rotations_same(self):
        p = Piece("O", col=3, row=0)
        base = p.cells()
        for _ in range(3):
            p.rotate(1)
            assert p.cells() == base


class TestRotation:
    def test_rotate_cw_changes_rotation(self):
        p = Piece("T", col=3, row=5)
        p.rotate(1)
        assert p.rotation == 1

    def test_rotate_four_times_returns_to_origin(self):
        p = Piece("T", col=3, row=5)
        original = p.cells()
        for _ in range(4):
            p.rotate(1)
        assert p.cells() == original

    def test_rotated_cells_does_not_mutate(self):
        p = Piece("S", col=3, row=5)
        before = p.rotation
        _ = p.rotated_cells(1)
        assert p.rotation == before


class TestPieceBag:
    def test_bag_returns_valid_piece_names(self):
        bag = PieceBag()
        for _ in range(14):
            p = bag.next()
            assert p.name in PIECE_NAMES

    def test_bag_peek_does_not_consume(self):
        bag = PieceBag()
        names = bag.peek(3)
        for name in names:
            p = bag.next()
            assert p.name == name

    def test_bag_distributes_all_7_in_14_picks(self):
        """7-bag 특성: 14개 중 각 피스가 정확히 2번씩."""
        bag = PieceBag()
        counts = {n: 0 for n in PIECE_NAMES}
        for _ in range(14):
            counts[bag.next().name] += 1
        assert all(v == 2 for v in counts.values())


class TestPieceCopy:
    def test_copy_is_independent(self):
        p = Piece("L", col=3, row=5)
        c = p.copy()
        c.rotate(1)
        assert p.rotation == 0
        assert c.rotation == 1

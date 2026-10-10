"""契約とテストのつながりの検査。

fport には Specification 文書がなく、契約が振る舞いの正本になる。そのため、
契約のすべての条項に少なくとも一つのテストが結びついていることを確かめる。
"""

from __future__ import annotations

import pytest
from shikumi_contrace.reading import untested_clauses

from contract.port_contract import ConnectionContract, PortContract
from contract.tap_contract import TapContract
from tests import test_port_contract, test_tap_contract

CONTRACTS = (PortContract, ConnectionContract, TapContract)
TEST_MODULES = (test_port_contract, test_tap_contract)


@pytest.mark.parametrize("contract", CONTRACTS, ids=lambda c: c.__name__)
def test_every_clause_has_a_test(contract: type) -> None:
    missing = [clause.path for clause in untested_clauses(contract, TEST_MODULES)]
    assert missing == []

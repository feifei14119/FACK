"""Independent ISA/ordering expectations for gfx942 LDS-direct operands."""
import pytest
from isa.gfx942.target import Gfx942Target
from reorder import parser, regions
from reorder.depgraph import DepGraph
from reorder.model import EdgeType, WaitType
from reorder.verifier import Verifier
from reorder.waitcnt import _Scoreboard

DIRECT = [
    'buffer_load_dword v8, s[16:19], 0 offen lds',
    'buffer_load_dword v8, s[16:19], 0 offen offset:256 lds',
    'global_load_lds_dword v[8:9], off offset:128',
]
NORMAL = [
    'buffer_load_dword v8, v10, s[16:19], 0 offen',
    'global_load_dword v8, v[10:11], off',
]


def load(body):
    program = parser.parse('.text\nkernel:\n' + body + '\n')
    return program, Gfx942Target.from_program(program)


def verify(body):
    program, target = load(body)
    return Verifier(target, analysis=regions.analyze(program, target)).verify(program)


@pytest.mark.parametrize('instruction', DIRECT)
def test_lds_direct_has_address_uses_and_no_register_result(instruction):
    program, target = load(instruction)
    line = program.instr_lines()[0]
    defs, uses = target.def_use(line.opcode, line.operands)
    assert not defs
    assert ('v', 8) in uses
    if instruction.startswith('global_'):
        assert ('v', 9) in uses
    else:
        assert {('s', i) for i in range(16, 20)} <= uses
    assert target.wait_type(line.opcode, line.operands) == WaitType.VM
    assert target.is_lds_load(line.opcode, line.operands)
    board = _Scoreboard(target.counter_model().names, cm=target.counter_model())
    board.issue(line, target)
    assert board.issued['vm'] == 1
    assert board.lds_seq == {'vm': [0]}
    assert board.prod.get(('v', 8)) is None


@pytest.mark.parametrize('instruction', DIRECT)
def test_ready_address_may_be_reused_without_fake_result_wait(instruction):
    result = verify('v_mov_b32 v8, 0\nv_mov_b32 v9, 0\n' + instruction +
                    '\nv_add_u32 v8, 16, v8\ns_waitcnt vmcnt(0)\ns_endpgm')
    assert result.ok, result.violations


@pytest.mark.parametrize('instruction', DIRECT)
def test_async_address_requires_real_wait_before_lds_direct(instruction):
    prefix = 'buffer_load_dword v8, v10, s[16:19], 0 offen\n'
    bad = verify(prefix + instruction + '\ns_waitcnt vmcnt(0)\ns_endpgm')
    assert any("use of ('v', 8) not synced" in x for x in bad.violations)
    good = verify(prefix + 's_waitcnt vmcnt(0)\n' + instruction +
                  '\ns_waitcnt vmcnt(0)\ns_endpgm')
    assert good.ok, good.violations


@pytest.mark.parametrize('instruction', NORMAL)
def test_ordinary_load_keeps_true_result_and_wait_requirement(instruction):
    program, target = load(instruction)
    line = program.instr_lines()[0]
    defs, uses = target.def_use(line.opcode, line.operands)
    assert ('v', 8) in defs and ('v', 10) in uses
    bad = verify(instruction + '\nv_add_u32 v9, 1, v8\ns_endpgm')
    assert any("use of ('v', 8) not synced" in x for x in bad.violations)
    good = verify(instruction + '\ns_waitcnt vmcnt(0)\nv_add_u32 v9, 1, v8\ns_endpgm')
    assert good.ok, good.violations


@pytest.mark.parametrize('instruction', DIRECT)
def test_graph_has_address_raw_and_war_instead_of_fake_load_result(instruction):
    program, target = load('v_mov_b32 v8, 0\n' + instruction + '\nv_add_u32 v8, 16, v8')
    lines = list(program.instr_lines())
    edges = set(DepGraph.build(lines, target).edges())
    a, b, c = [line.idx for line in lines]
    assert (a, b, EdgeType.RAW) in edges
    assert (b, c, EdgeType.WAR) in edges
    assert (b, c, EdgeType.RAW) not in edges


@pytest.mark.parametrize('instruction', DIRECT)
def test_m0_and_lds_memory_order_edges_survive(instruction):
    program, target = load('s_mov_b32 m0, 0\n' + instruction +
                           '\ns_mov_b32 m0, 256\nds_read_b32 v12, v20')
    lines = list(program.instr_lines())
    edges = set(DepGraph.build(lines, target).edges())
    a, b, c, d = [line.idx for line in lines]
    assert (a, b, EdgeType.M0) in edges
    assert (b, c, EdgeType.M0) in edges
    assert (b, d, EdgeType.MEM) in edges

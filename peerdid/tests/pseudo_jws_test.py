from ..pseudo_jws import sign, verify

def test_roundtrip():
    fake_jws = 'J1WJV2ehEmI=.Ccp-Tqpuiuk=.oOEtYB4QFU8='
    assert sign('hello, world', 'my key') == fake_jws
    assert verify('hello, world', 'my key', fake_jws)
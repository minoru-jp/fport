import fport.policy
from fport.port import Port
import threading

def test_create_port_is_thread_safe():
    """Concurrent calls to create_port must return distinct and valid Port instances."""

    role = fport.policy._create_session_policy_role()
    core = role.core

    results: list[Port] = []
    errors: list[Exception] = []

    def worker():
        try:
            p = core.create_port()
            results.append(p)
        except Exception as e:
            errors.append(e)

    # Launch multiple threads calling create_port concurrently
    threads = [threading.Thread(target=worker) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # No errors must occur
    assert not errors

    # All results must be Port instances
    assert all(isinstance(p, Port) for p in results)

    # They must all be distinct instances
    assert len(results) == len(set(map(id, results)))


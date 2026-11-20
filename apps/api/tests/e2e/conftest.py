import pytest


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):  # noqa: ARG001
    rep = (yield).get_result()
    if rep.when == "call" and rep.failed:
        item.module.S.failed = True
        pg = item.funcargs.get("page")
        if pg is not None:
            try:
                item.module.SHOTS.mkdir(parents=True, exist_ok=True)
                pg.screenshot(path=str(item.module.SHOTS / f"FAIL_{item.name}.png"))
            except Exception:  # noqa: S110 - best-effort diagnostics
                pass


@pytest.fixture(autouse=True)
def _sequential(request):
    if getattr(request.module, "S", None) and request.module.S.failed:
        pytest.skip("an earlier e2e step failed")

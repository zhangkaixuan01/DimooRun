import json
from pathlib import Path


def test_typescript_sdk_declares_package_version_and_build_contract() -> None:
    package = json.loads(Path("packages/sdk-js/package.json").read_text(encoding="utf-8"))

    assert package["name"] == "@dimoorun/sdk"
    assert package["version"] == "0.1.0"
    assert package["scripts"]["build"] == "tsc -p tsconfig.json"
    assert package["exports"]["."]["import"] == "./dist/index.js"
    assert package["exports"]["."]["types"] == "./dist/index.d.ts"


def test_typescript_sdk_exposes_native_runtime_workflow_methods() -> None:
    client_text = Path("packages/sdk-js/src/client.ts").read_text(encoding="utf-8")
    index_text = Path("packages/sdk-js/src/index.ts").read_text(encoding="utf-8")

    for marker in [
        "class DimooRunClient",
        "validatePackage(",
        "createAgent(",
        "createAgentVersion(",
        "createDeployment(",
        "createRun(",
        "submitDeploymentTask(",
        "getRun(",
        "listRunEvents(",
        "replayRun(",
        "getTask(",
        "class DimooRunAPIError",
    ]:
        assert marker in client_text
    assert 'export { DimooRunAPIError, DimooRunClient }' in index_text

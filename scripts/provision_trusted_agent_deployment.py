"""
TODOBA Trusted Agent Secure Deployment Provisioner

Creates an isolated, agent-specific MQL5 build workspace.

Security rules:

- never modify repository-local credentials
- never copy repository-local credential material
- never copy compiled EX5 artifacts
- never copy local MQL5 logs
- never silently overwrite an existing deployment
- bind every generated workspace to one explicit Agent identity
- bind every generated workspace to one expected MT5 account
- keep authentication, execution signing, and control signing
  secrets isolated per deployment
- mutate only the copied deployment Agent source
"""

from pathlib import Path
import re
import shutil


_CREDENTIAL_RELATIVE_PATH = (
    Path("Include")
    / "TODOBAExecution"
    / "TODOBAAgentCredentials.mqh"
)

_AGENT_RELATIVE_PATH = (
    Path("Experts")
    / "TODOBA_Trusted_Agent.mq5"
)


def _require_value(
    *,
    name: str,
    value: str,
) -> str:
    normalized = str(
        value
    ).strip()

    if not normalized:
        raise ValueError(
            f"{name} is required."
        )

    forbidden = (
        '"',
        "\\",
        "\r",
        "\n",
        "\x00",
    )

    if any(
        token in normalized
        for token in forbidden
    ):
        raise ValueError(
            f"{name} contains unsupported characters."
        )

    return normalized


def _require_deployment_name(
    *,
    name: str,
    value: str,
) -> str:
    normalized = _require_value(
        name=name,
        value=value,
    )

    if (
        normalized in {
            ".",
            "..",
        }
        or "/" in normalized
        or ":" in normalized
        or "\\" in normalized
    ):
        raise ValueError(
            f"{name} must be a single deployment name."
        )

    return normalized


def _ignore_local_build_material(
    directory: str,
    names: list[str],
) -> set[str]:
    ignored: set[str] = set()

    directory_path = Path(
        directory
    )

    for name in names:
        candidate = (
            directory_path
            / name
        )

        if (
            candidate.name
            == "TODOBAAgentCredentials.mqh"
            and candidate.parent.name
            == "TODOBAExecution"
        ):
            ignored.add(
                name
            )

            continue

        if candidate.suffix.lower() in {
            ".ex5",
            ".log",
        }:
            ignored.add(
                name
            )

    return ignored


def _build_credentials_header(
    *,
    agent_id: str,
    account_fingerprint: str,
    agent_secret: str,
    execution_mission_signing_secret: str,
    control_mission_signing_secret: str,
) -> str:
    return (
        "// TODOBA Provisioned Agent Credentials\n"
        "// Generated deployment-local material.\n"
        "// Never commit this file.\n"
        "\n"
        "#ifndef TODOBA_AGENT_CREDENTIALS_MQH\n"
        "#define TODOBA_AGENT_CREDENTIALS_MQH\n"
        "\n"
        f'const string TODOBA_AGENT_ID = "{agent_id}";\n'
        "const string "
        "TODOBA_EXPECTED_ACCOUNT_FINGERPRINT = "
        f'"{account_fingerprint}";\n'
        f'const string TODOBA_AGENT_SECRET = "{agent_secret}";\n'
        "const string TODOBA_MISSION_SIGNING_SECRET = "
        f'"{execution_mission_signing_secret}";\n'
        "const string "
        "TODOBA_CONTROL_MISSION_SIGNING_SECRET = "
        f'"{control_mission_signing_secret}";\n'
        "\n"
        "#endif\n"
    )


def _bind_provisioned_agent_source(
    *,
    agent_path: Path,
) -> None:
    source = agent_path.read_text(
        encoding="utf-8"
    )

    input_pattern = re.compile(
        (
            r"(?m)^input string AgentId\s*=\s*\n"
            r'\s*"[^"]*";\s*\n'
        )
    )

    source, input_count = (
        input_pattern.subn(
            "",
            source,
            count=1,
        )
    )

    if input_count != 1:
        raise RuntimeError(
            "Trusted Agent template AgentId input "
            f"contract mismatch: found {input_count}."
        )

    source, identity_count = re.subn(
        r"\bAgentId\b",
        "TODOBA_AGENT_ID",
        source,
    )

    if identity_count < 1:
        raise RuntimeError(
            "Trusted Agent template does not use AgentId."
        )

    validator_include = (
        "#include "
        "<TODOBAExecution/"
        "ExecutionMissionValidator.mqh>\n"
    )

    account_include = (
        "#include "
        "<TODOBAExecution/"
        "AccountFingerprint.mqh>\n"
    )

    if account_include not in source:
        include_count = source.count(
            validator_include
        )

        if include_count != 1:
            raise RuntimeError(
                "Trusted Agent validator include "
                f"contract mismatch: found {include_count}."
            )

        source = source.replace(
            validator_include,
            (
                validator_include
                + account_include
            ),
            1,
        )

    vps_guard = (
        "   if(\n"
        "      !TerminalInfoInteger(\n"
        "         TERMINAL_VPS\n"
        "      )\n"
        "   )\n"
    )

    vps_guard_count = source.count(
        vps_guard
    )

    if vps_guard_count != 1:
        raise RuntimeError(
            "Trusted Agent VPS startup guard "
            f"contract mismatch: found {vps_guard_count}."
        )

    account_guard = (
        "   if(\n"
        "      StringLen(\n"
        "         TODOBA_EXPECTED_ACCOUNT_FINGERPRINT\n"
        "      ) == 0\n"
        "   )\n"
        "   {\n"
        "      return INIT_PARAMETERS_INCORRECT;\n"
        "   }\n"
        "\n"
        "   string current_account_fingerprint =\n"
        "      TODOBAAccountFingerprint::Build();\n"
        "\n"
        "   if(\n"
        "      StringLen(\n"
        "         current_account_fingerprint\n"
        "      ) == 0\n"
        "   )\n"
        "   {\n"
        "      Print(\n"
        '         "TODOBA Agent account fingerprint "\n'
        '         "is unavailable."\n'
        "      );\n"
        "\n"
        "      return INIT_FAILED;\n"
        "   }\n"
        "\n"
        "   if(\n"
        "      current_account_fingerprint\n"
        "      != TODOBA_EXPECTED_ACCOUNT_FINGERPRINT\n"
        "   )\n"
        "   {\n"
        "      Print(\n"
        '         "TODOBA Agent account binding mismatch. "\n'
        '         "Expected=",\n'
        "         TODOBA_EXPECTED_ACCOUNT_FINGERPRINT,\n"
        '         " Actual=",\n'
        "         current_account_fingerprint\n"
        "      );\n"
        "\n"
        "      return INIT_FAILED;\n"
        "   }\n"
        "\n"
    )

    source = source.replace(
        vps_guard,
        account_guard + vps_guard,
        1,
    )

    if "input string AgentId" in source:
        raise RuntimeError(
            "Mutable AgentId input remains in "
            "provisioned Agent."
        )

    if re.search(
        r"\bAgentId\b",
        source,
    ):
        raise RuntimeError(
            "Mutable AgentId reference remains in "
            "provisioned Agent."
        )

    if (
        "TODOBA_EXPECTED_ACCOUNT_FINGERPRINT"
        not in source
    ):
        raise RuntimeError(
            "Provisioned Agent account binding "
            "was not installed."
        )

    agent_path.write_text(
        source,
        encoding="utf-8",
    )


def provision_trusted_agent_deployment(
    *,
    mql5_source_root: Path,
    output_root: Path,
    agent_id: str,
    account_fingerprint: str,
    agent_secret: str,
    execution_mission_signing_secret: str,
    control_mission_signing_secret: str,
) -> Path:
    source_root = Path(
        mql5_source_root
    ).resolve()

    agent_id = _require_deployment_name(
        name="agent_id",
        value=agent_id,
    )

    output_root = Path(
        output_root
    ).resolve()

    repository_root = (
        source_root.parent
    )

    if (
        output_root == repository_root
        or repository_root
        in output_root.parents
    ):
        raise ValueError(
            "output_root must be outside "
            "the repository."
        )

    deployment_root = (
        output_root
        / agent_id
    )

    account_fingerprint = _require_value(
        name="account_fingerprint",
        value=account_fingerprint,
    )

    agent_secret = _require_value(
        name="agent_secret",
        value=agent_secret,
    )

    execution_mission_signing_secret = (
        _require_value(
            name=(
                "execution_mission_signing_secret"
            ),
            value=(
                execution_mission_signing_secret
            ),
        )
    )

    control_mission_signing_secret = (
        _require_value(
            name=(
                "control_mission_signing_secret"
            ),
            value=(
                control_mission_signing_secret
            ),
        )
    )

    if not source_root.is_dir():
        raise FileNotFoundError(
            "MQL5 source root does not exist."
        )

    if deployment_root.exists():
        raise FileExistsError(
            "Trusted Agent deployment already exists."
        )

    deployment_mql5_root = (
        deployment_root
        / "MQL5"
    )

    try:
        shutil.copytree(
            source_root,
            deployment_mql5_root,
            ignore=_ignore_local_build_material,
        )

        credential_path = (
            deployment_mql5_root
            / _CREDENTIAL_RELATIVE_PATH
        )

        credential_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        credential_path.write_text(
            _build_credentials_header(
                agent_id=agent_id,
                account_fingerprint=(
                    account_fingerprint
                ),
                agent_secret=agent_secret,
                execution_mission_signing_secret=(
                    execution_mission_signing_secret
                ),
                control_mission_signing_secret=(
                    control_mission_signing_secret
                ),
            ),
            encoding="utf-8",
        )

        agent_path = (
            deployment_mql5_root
            / _AGENT_RELATIVE_PATH
        )

        if not agent_path.is_file():
            raise FileNotFoundError(
                "Trusted Agent source was not copied."
            )

        _bind_provisioned_agent_source(
            agent_path=agent_path
        )

    except Exception:
        if deployment_root.exists():
            shutil.rmtree(
                deployment_root
            )

        raise

    return deployment_root

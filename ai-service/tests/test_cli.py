import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "ai-service" / "run.py"


class CliTests(unittest.TestCase):
    def run_cli(self, *args, commands=None):
        completed = subprocess.run(
            [sys.executable, str(RUN), *args],
            input=commands, capture_output=True, text=True, encoding="utf-8",
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            timeout=10, cwd=ROOT.parent,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return completed.stdout

    def test_all_scenarios_recover_and_finish_without_green(self):
        for scenario in (
            "fluxo", "perda-visibilidade", "falha-camera", "falha-sensor",
            "falha-processamento", "luva-oculta", "luva-ausente", "troca-pessoa",
            "quadros-expirados", "falha-sinalizacao",
        ):
            with self.subTest(scenario=scenario):
                rows = [json.loads(line) for line in self.run_cli("--scenario", scenario).splitlines()]
                self.assertTrue(any(row["outputs"]["green"] for row in rows))
                self.assertEqual(rows[-1]["status"]["state"], "AGUARDANDO_TOCHA")
                self.assertFalse(rows[-1]["outputs"]["green"])
                self.assertIsNone(rows[-1]["status"]["session_id"])
                if scenario != "fluxo":
                    failures = [row for row in rows if row["passo"] == scenario]
                    self.assertEqual(len(failures), 10)
                    self.assertTrue(all(not row["outputs"]["green"] for row in failures))
                    last_failure = rows.index(failures[-1])
                    self.assertTrue(any(row["outputs"]["green"] for row in rows[last_failure + 1:]))

    def test_events_are_parseable_and_include_session_closure(self):
        output = self.run_cli("--scenario", "fluxo", "--events")
        events_start = output.index('{\n  "eventos"')
        events = json.loads(output[events_start:])["eventos"]
        self.assertTrue(any(event["kind"] == "SESSAO_ENCERRADA" for event in events))

    def test_interactive_ack_and_exit(self):
        output = self.run_cli(
            "--interactive", "--role", "operador",
            commands="retirar\ncima\ncima\nbaixo\nbaixo\nbaixo\noculto\nreconhecer\nsair\n",
        )
        self.assertIn("Incidente reconhecido", output)
        self.assertIn('"green": true', output)
        self.assertIn('"passo": "encerramento"', output)

    def test_interactive_default_role_cannot_acknowledge(self):
        output = self.run_cli("--interactive", commands="retirar\noculto\nreconhecer\nsair\n")
        self.assertIn("Reconhecimento exige operador autorizado", output)


if __name__ == "__main__":
    unittest.main()

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class Outbox:
    def __init__(self, workdir: Optional[str], state_dir: Optional[str] = None):
        base = Path(
            state_dir
            or os.environ.get("SHIPSMITH_STATE_DIR")
            or (Path.home() / ".local" / "state" / "shipsmith")
        )
        key = hashlib.sha256((workdir or "default").encode("utf-8")).hexdigest()[:16]
        self.root = base / "outbox" / key
        self.root.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.root, 0o700)
        except OSError:
            pass

    def _write(self, path: Path, payload: Dict[str, Any]) -> None:
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)

    def enqueue_result(self, task_id: int, payload: Dict[str, Any]) -> None:
        self._write(
            self.root / f"result-{task_id}.json",
            {"task_id": task_id, "payload": payload, "queued_at": time.time()},
        )

    def remove_result(self, task_id: int) -> None:
        (self.root / f"result-{task_id}.json").unlink(missing_ok=True)

    def enqueue_log(self, task_id: int, seq: int, phase: Optional[str], content: str) -> None:
        self._write(
            self.root / f"log-{task_id}-{seq:08d}.json",
            {
                "task_id": task_id,
                "seq": seq,
                "phase": phase,
                "content": content,
                "queued_at": time.time(),
            },
        )

    def pending_results(self) -> List[Tuple[Path, Dict[str, Any]]]:
        items: List[Tuple[Path, Dict[str, Any]]] = []
        for path in sorted(self.root.glob("result-*.json")):
            try:
                items.append((path, json.loads(path.read_text(encoding="utf-8"))))
            except Exception:
                continue
        return items

    def pending_logs(self) -> List[Tuple[Path, Dict[str, Any]]]:
        items: List[Tuple[Path, Dict[str, Any]]] = []
        for path in sorted(self.root.glob("log-*.json")):
            try:
                items.append((path, json.loads(path.read_text(encoding="utf-8"))))
            except Exception:
                continue
        return items

    def remove(self, path: Path) -> None:
        path.unlink(missing_ok=True)
